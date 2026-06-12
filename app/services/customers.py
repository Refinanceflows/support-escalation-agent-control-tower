import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.storage import JsonStateStore
from app.models import Approval, OutboxEvent, Ticket, TicketStatus
from app.services.playbooks import PlaybookService
from app.services.tickets import TicketService


ACTIVE_STATUSES = {
    TicketStatus.open,
    TicketStatus.analyzing,
    TicketStatus.pending_approval,
    TicketStatus.escalated,
    TicketStatus.human_review,
}


class CustomerHealthService:
    def __init__(
        self,
        store: JsonStateStore,
        ticket_service: TicketService,
        playbook_service: PlaybookService,
        customers_path: Path,
        renewal_inputs_path: Path,
        account_briefs_dir: Path,
        renewal_reviews_dir: Path,
        renewal_control_dir: Path,
        renewal_handoff_dir: Path,
    ):
        self.store = store
        self.ticket_service = ticket_service
        self.playbook_service = playbook_service
        self.customers_path = customers_path
        self.renewal_inputs_path = renewal_inputs_path
        self.account_briefs_dir = account_briefs_dir
        self.renewal_reviews_dir = renewal_reviews_dir
        self.renewal_control_dir = renewal_control_dir
        self.renewal_handoff_dir = renewal_handoff_dir

    async def health(self) -> dict[str, Any]:
        tickets = await self.ticket_service.list()
        state = await self.store.load()
        summaries = self._health_summaries(tickets, state)
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "customers": summaries,
        }

    async def export_account_brief(self, customer_id_or_name: str) -> dict[str, Any]:
        tickets = await self.ticket_service.list()
        state = await self.store.load()
        summaries = self._health_summaries(tickets, state)
        target = self._find_summary(summaries, customer_id_or_name)
        if target is None:
            raise KeyError(customer_id_or_name)

        account_tickets = [
            ticket
            for ticket in tickets
            if self._account_for_ticket(ticket.model_dump(mode="json"))["customer_id"]
            == target["customer_id"]
        ]
        ticket_ids = {ticket.ticket_id for ticket in account_tickets}
        runs = self._runs_for_tickets(state, ticket_ids)
        approvals = self._approvals_for_tickets(state, ticket_ids)
        outbox = self._outbox_for_tickets(state, ticket_ids)
        active_tickets = [
            self._ticket_row(ticket, self._latest_run_for_ticket(runs, ticket.ticket_id))
            for ticket in account_tickets
            if ticket.status in ACTIVE_STATUSES
        ]
        recent_runs = [self._run_row(run) for run in sorted(runs, key=self._run_time, reverse=True)[:8]]
        pending_approvals = [
            self._approval_row(approval)
            for approval in approvals
            if approval.status == "pending"
        ]
        recommended_playbooks = self._recommended_playbooks(account_tickets, runs)
        outbox_summary = self._outbox_summary(outbox)
        brief = {
            "account_brief_id": f"account_brief_{target['customer_id']}",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "customer_health": target,
            "active_tickets": active_tickets,
            "recent_runs": recent_runs,
            "recommended_playbooks": recommended_playbooks,
            "pending_approvals": pending_approvals,
            "outbox_summary": outbox_summary,
            "next_actions": self._brief_next_actions(
                target,
                active_tickets,
                recent_runs,
                pending_approvals,
                recommended_playbooks,
                outbox_summary,
            ),
        }
        markdown = self._markdown(brief)
        json_path, markdown_path = self._write_files(target["customer_id"], brief, markdown)
        return {
            "customer_id": target["customer_id"],
            "format": "markdown+json",
            "json_path": str(json_path),
            "markdown_path": str(markdown_path),
            "brief": brief,
            "markdown": markdown,
        }

    async def renewal_risk(self) -> dict[str, Any]:
        tickets = await self.ticket_service.list()
        state = await self.store.load()
        health_rows = self._health_summaries(tickets, state)
        rows = self._renewal_rows(health_rows, tickets, state)
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "mode": "local-deterministic-renewal-risk",
            "local_mock_only": True,
            "summary": self._renewal_summary(rows),
            "accounts": rows,
            "limitations": self._renewal_limitations(),
        }

    async def renewal_control_board(self) -> dict[str, Any]:
        renewal = await self.renewal_risk()
        controls = [self._renewal_control_row(row) for row in renewal["accounts"]]
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "title": "Renewal Control Board",
            "mode": "local-deterministic-renewal-governance",
            "local_mock_only": True,
            "implemented_patterns": [
                "human-in-the-loop",
                "governance",
                "durable workflows",
                "shared state",
            ],
            "summary": self._renewal_control_summary(controls),
            "review_policy": self._renewal_review_policy(),
            "control_board": controls,
            "limitations": self._renewal_control_limitations(),
        }

    async def export_renewal_control_pack(self) -> dict[str, Any]:
        board = await self.renewal_control_board()
        generated_at = datetime.now(timezone.utc)
        pack_id = f"renewal_control_{generated_at.strftime('%Y%m%d_%H%M%S')}"
        json_path = self.renewal_control_dir / f"{pack_id}.json"
        markdown_path = self.renewal_control_dir / f"{pack_id}.md"
        pack = {
            "pack_id": pack_id,
            "generated_at": generated_at.isoformat(),
            "title": "Renewal Control Pack",
            "control_board": board,
            "review_queue": [
                row
                for row in board["control_board"]
                if row["review_status"] != "monitor"
            ],
            "operator_acceptance_criteria": self._renewal_control_acceptance_criteria(),
            "local_verification": {
                "endpoints": [
                    "GET /customers/renewal-control-board",
                    "POST /customers/renewal-control-pack",
                    "GET /customers/renewal-risk",
                    "POST /customers/{customer_id_or_name}/renewal-review",
                ],
                "artifact_directory": "data/renewal_control_packs",
                "demo_command": r".\.venv\Scripts\python.exe scripts\demo_run.py",
            },
            "artifact_paths": {
                "renewal_control_markdown": str(markdown_path),
                "renewal_control_json": str(json_path),
            },
        }
        markdown = self._renewal_control_markdown(pack)
        self.renewal_control_dir.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(pack, indent=2, default=str), encoding="utf-8")
        markdown_path.write_text(markdown, encoding="utf-8")
        return {
            "pack_id": pack_id,
            "format": "markdown+json",
            "status": board["summary"]["status"],
            "json_path": str(json_path),
            "markdown_path": str(markdown_path),
            "pack": pack,
            "markdown": markdown,
        }

    async def renewal_handoff_gate(self) -> dict[str, Any]:
        renewal = await self.renewal_risk()
        board = await self.renewal_control_board()
        controls_by_id = {row["customer_id"]: row for row in board["control_board"]}
        accounts = [
            self._renewal_handoff_row(row, controls_by_id[row["customer_id"]])
            for row in renewal["accounts"]
            if row["renewal_risk_level"] in {"critical", "high"}
            or controls_by_id[row["customer_id"]]["review_status"] != "monitor"
        ]
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "title": "Renewal Handoff Readiness Gate",
            "mode": "local-deterministic-renewal-handoff-gate",
            "local_mock_only": True,
            "implemented_patterns": [
                "review gates",
                "artifact handoffs",
                "role playbooks",
                "run transparency",
            ],
            "summary": self._renewal_handoff_summary(accounts),
            "role_playbook": self._renewal_handoff_role_playbook(),
            "accounts": accounts,
            "operator_acceptance_criteria": self._renewal_handoff_acceptance_criteria(),
            "limitations": self._renewal_handoff_limitations(),
        }

    async def export_renewal_handoff_pack(self) -> dict[str, Any]:
        gate = await self.renewal_handoff_gate()
        generated_at = datetime.now(timezone.utc)
        pack_id = f"renewal_handoff_{generated_at.strftime('%Y%m%d_%H%M%S')}"
        json_path = self.renewal_handoff_dir / f"{pack_id}.json"
        markdown_path = self.renewal_handoff_dir / f"{pack_id}.md"
        pack = {
            "pack_id": pack_id,
            "generated_at": generated_at.isoformat(),
            "title": "Renewal Handoff Readiness Pack",
            "gate": gate,
            "handoff_queue": [
                row for row in gate["accounts"] if row["handoff_status"] != "ready"
            ],
            "blocked_handoff_actions": [
                action
                for row in gate["accounts"]
                for action in row["blocked_handoff_actions"]
            ],
            "local_verification": {
                "endpoints": [
                    "GET /customers/renewal-handoff-gate",
                    "POST /customers/renewal-handoff-pack",
                    "GET /customers/renewal-control-board",
                    "POST /customers/{customer_id_or_name}/renewal-review",
                ],
                "artifact_directory": "data/renewal_handoff_packs",
                "demo_command": r".\.venv\Scripts\python.exe scripts\demo_run.py",
            },
            "artifact_paths": {
                "renewal_handoff_markdown": str(markdown_path),
                "renewal_handoff_json": str(json_path),
            },
        }
        markdown = self._renewal_handoff_markdown(pack)
        self.renewal_handoff_dir.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(pack, indent=2, default=str), encoding="utf-8")
        markdown_path.write_text(markdown, encoding="utf-8")
        return {
            "pack_id": pack_id,
            "format": "markdown+json",
            "status": gate["summary"]["status"],
            "json_path": str(json_path),
            "markdown_path": str(markdown_path),
            "pack": pack,
            "markdown": markdown,
        }

    async def export_renewal_review(self, customer_id_or_name: str) -> dict[str, Any]:
        tickets = await self.ticket_service.list()
        state = await self.store.load()
        health_rows = self._health_summaries(tickets, state)
        rows = self._renewal_rows(health_rows, tickets, state)
        target = self._find_summary(rows, customer_id_or_name)
        if target is None:
            raise KeyError(customer_id_or_name)

        account_tickets = [
            ticket
            for ticket in tickets
            if self._account_for_ticket(ticket.model_dump(mode="json"))["customer_id"]
            == target["customer_id"]
        ]
        ticket_ids = {ticket.ticket_id for ticket in account_tickets}
        runs = self._runs_for_tickets(state, ticket_ids)
        approvals = self._approvals_for_tickets(state, ticket_ids)
        outbox = self._outbox_for_tickets(state, ticket_ids)
        generated_at = datetime.now(timezone.utc)
        review_id = f"renewal_review_{target['customer_id']}"
        review = {
            "review_id": review_id,
            "generated_at": generated_at.isoformat(),
            "mode": "local-deterministic-renewal-review",
            "local_mock_only": True,
            "account": target,
            "executive_summary": self._renewal_executive_summary(target),
            "support_evidence": {
                "active_tickets": [
                    self._ticket_row(ticket, self._latest_run_for_ticket(runs, ticket.ticket_id))
                    for ticket in account_tickets
                    if ticket.status in ACTIVE_STATUSES
                ],
                "recent_runs": [
                    self._run_row(run)
                    for run in sorted(runs, key=self._run_time, reverse=True)[:8]
                ],
                "pending_approvals": [
                    self._approval_row(approval)
                    for approval in approvals
                    if approval.status == "pending"
                ],
                "outbox_summary": self._outbox_summary(outbox),
            },
            "blocker_register": target["renewal_blockers"],
            "owner_actions": target["owner_actions"],
            "customer_success_review": self._customer_success_review(target),
            "assumptions": [
                "Renewal inputs are bundled fake enterprise account data for local portfolio review.",
                "Support sentiment is derived from local ticket text and workflow classification sentiment.",
                "SLA drag combines fixture minutes with local high-SLA, approval, escalation, and failure signals.",
                "ARR and contract exposure come from sample_data/customers.json when present.",
            ],
            "limitations": self._renewal_limitations(),
        }
        markdown = self._renewal_markdown(review)
        json_path, markdown_path = self._write_renewal_files(target["customer_id"], review, markdown)
        return {
            "customer_id": target["customer_id"],
            "review_id": review_id,
            "format": "markdown+json",
            "json_path": str(json_path),
            "markdown_path": str(markdown_path),
            "review": review,
            "markdown": markdown,
        }

    def _health_summaries(
        self,
        tickets: list[Ticket],
        state: dict[str, Any],
    ) -> list[dict[str, Any]]:
        tickets_by_account: dict[str, list[Ticket]] = defaultdict(list)
        account_metadata: dict[str, dict[str, str]] = {}
        for ticket in tickets:
            account = self._account_for_ticket(ticket.model_dump(mode="json"))
            tickets_by_account[account["customer_id"]].append(ticket)
            account_metadata[account["customer_id"]] = account

        latest_runs = self._latest_runs_by_ticket(state["runs"].values())
        summaries = []
        for customer_id, account_tickets in tickets_by_account.items():
            metadata = account_metadata[customer_id]
            ticket_ids = {ticket.ticket_id for ticket in account_tickets}
            runs = [run for run in latest_runs.values() if run.get("ticket_id") in ticket_ids]
            approvals = self._approvals_for_tickets(state, ticket_ids)
            counts = Counter(ticket.status for ticket in account_tickets)
            high_sla_risk_count = sum(
                1 for run in runs if run.get("state", {}).get("sla_risk", {}).get("level") == "high"
            )
            recent_failure_count = sum(1 for run in runs if run.get("failure_state"))
            pending_approval_count = sum(1 for item in approvals if item.status == "pending")
            recommended_playbook_count = len(self._recommended_playbook_ids(runs))
            open_count = counts[TicketStatus.open] + counts[TicketStatus.analyzing]
            pending_count = counts[TicketStatus.pending_approval]
            escalated_count = counts[TicketStatus.escalated]
            health_score = self._health_score(
                open_count=open_count,
                pending_count=pending_count,
                escalated_count=escalated_count,
                high_sla_risk_count=high_sla_risk_count,
                recent_failure_count=recent_failure_count,
                pending_approval_count=pending_approval_count,
                recommended_playbook_count=recommended_playbook_count,
                tier=metadata.get("tier", ""),
            )
            summary = {
                "customer_id": customer_id,
                "customer": metadata["customer"],
                "account": metadata["account"],
                "segment": metadata.get("segment", "unknown"),
                "tier": metadata.get("tier", "unknown"),
                "region": metadata.get("region", "unknown"),
                "ticket_count": len(account_tickets),
                "open_count": open_count,
                "pending_count": pending_count,
                "escalated_count": escalated_count,
                "high_sla_risk_count": high_sla_risk_count,
                "recent_failure_count": recent_failure_count,
                "pending_approval_count": pending_approval_count,
                "recommended_playbook_count": recommended_playbook_count,
                "health_score": health_score,
                "risk_level": self._risk_level(
                    health_score,
                    high_sla_risk_count,
                    recent_failure_count,
                ),
            }
            summary["recommended_action"] = self._recommended_action(summary)
            summaries.append(summary)
        return sorted(
            summaries,
            key=lambda item: (item["health_score"], -item["ticket_count"], item["account"]),
        )

    def _health_score(
        self,
        *,
        open_count: int,
        pending_count: int,
        escalated_count: int,
        high_sla_risk_count: int,
        recent_failure_count: int,
        pending_approval_count: int,
        recommended_playbook_count: int,
        tier: str,
    ) -> int:
        risk_points = (
            open_count * 3
            + pending_count * 8
            + escalated_count * 12
            + high_sla_risk_count * 18
            + recent_failure_count * 14
            + pending_approval_count * 10
            + recommended_playbook_count * 2
        )
        if tier == "enterprise" and (high_sla_risk_count or pending_approval_count or escalated_count):
            risk_points += 5
        return max(0, 100 - risk_points)

    def _risk_level(
        self,
        health_score: int,
        high_sla_risk_count: int,
        recent_failure_count: int,
    ) -> str:
        if health_score <= 45 or high_sla_risk_count >= 2 or recent_failure_count >= 2:
            return "critical"
        if health_score <= 70 or high_sla_risk_count or recent_failure_count:
            return "at_risk"
        if health_score <= 85:
            return "watch"
        return "healthy"

    def _recommended_action(self, summary: dict[str, Any]) -> str:
        if summary["risk_level"] == "critical":
            return "Open an account war room, clear approvals, and confirm executive update cadence."
        if summary["pending_approval_count"]:
            return "Clear pending approvals before more customer or engineering handoffs queue up."
        if summary["high_sla_risk_count"] or summary["escalated_count"]:
            return "Confirm owner, mitigation path, and customer update cadence for active escalations."
        if summary["recent_failure_count"]:
            return "Assign human validation for recent workflow failures before sending guidance."
        if summary["open_count"]:
            return "Analyze open tickets and attach recommended playbooks for the account team."
        return "Monitor through standard customer success follow-up."

    def _account_for_ticket(self, ticket: dict[str, Any]) -> dict[str, str]:
        customer = ticket.get("customer") or ticket.get("account")
        if not customer:
            customer = self._customer_from_email(ticket.get("customer_email", "customer@example.com"))
        metadata = self._metadata_by_name().get(self._normalize(customer), {})
        account = metadata.get("customer", customer)
        return {
            "customer_id": self._slug(account),
            "customer": account,
            "account": account,
            "segment": metadata.get("segment", "unknown"),
            "tier": metadata.get("tier", ticket.get("customer_tier", "unknown")),
            "region": metadata.get("region", "unknown"),
        }

    def _customer_from_email(self, email: str) -> str:
        domain = email.split("@")[-1].split(".")[0] if "@" in email else email
        cleaned = re.sub(r"[^a-zA-Z0-9]+", " ", domain).strip()
        return cleaned.title() if cleaned else "Unknown Account"

    def _metadata_by_name(self) -> dict[str, dict[str, Any]]:
        if not self.customers_path.exists():
            return {}
        rows = json.loads(self.customers_path.read_text(encoding="utf-8"))
        return {self._normalize(item["customer"]): item for item in rows}

    def _renewal_rows(
        self,
        health_rows: list[dict[str, Any]],
        tickets: list[Ticket],
        state: dict[str, Any],
    ) -> list[dict[str, Any]]:
        inputs_by_name = self._renewal_inputs_by_name()
        metadata_by_name = self._metadata_by_name()
        latest_runs = self._latest_runs_by_ticket(state["runs"].values())
        rows = []
        for health in health_rows:
            account_key = self._normalize(health["account"])
            renewal_input = inputs_by_name.get(account_key, {})
            metadata = metadata_by_name.get(account_key, {})
            account_tickets = [
                ticket
                for ticket in tickets
                if self._account_for_ticket(ticket.model_dump(mode="json"))["customer_id"]
                == health["customer_id"]
            ]
            runs = [
                run
                for run in latest_runs.values()
                if run.get("ticket_id") in {ticket.ticket_id for ticket in account_tickets}
            ]
            sentiment = self._support_sentiment(account_tickets, runs, renewal_input)
            sla_drag = self._sla_drag_minutes(health, renewal_input)
            blockers = self._renewal_blockers(health, renewal_input, sentiment, sla_drag)
            blocker_points = self._blocker_points(blockers)
            relationship_points = self._relationship_points(renewal_input)
            health_points = max(0, 100 - int(health["health_score"]))
            sentiment_points = sentiment["risk_points"]
            sla_points = min(30, round(sla_drag["total_minutes"] / 12))
            risk_score = min(
                100,
                health_points
                + sentiment_points
                + sla_points
                + blocker_points
                + relationship_points,
            )
            arr_usd = int(metadata.get("arr_usd") or renewal_input.get("arr_usd") or 0)
            row = {
                "customer_id": health["customer_id"],
                "customer": health["customer"],
                "account": health["account"],
                "segment": health["segment"],
                "tier": health["tier"],
                "region": health["region"],
                "arr_usd": arr_usd,
                "renewal_window_days": int(renewal_input.get("renewal_window_days", 180)),
                "executive_sponsor": renewal_input.get("executive_sponsor", "unassigned"),
                "commercial_owner": renewal_input.get("commercial_owner", "customer-success"),
                "success_plan_status": renewal_input.get("success_plan_status", "needs_review"),
                "product_adoption_score": int(renewal_input.get("product_adoption_score", 70)),
                "csm_confidence": int(renewal_input.get("csm_confidence", 70)),
                "support_sentiment": sentiment,
                "sla_drag": sla_drag,
                "health": health,
                "renewal_blockers": blockers,
                "renewal_risk_score": risk_score,
                "renewal_risk_level": self._renewal_risk_level(risk_score),
                "arr_at_risk_usd": self._arr_at_risk(arr_usd, risk_score),
                "owner_actions": self._renewal_owner_actions(
                    health,
                    sentiment,
                    sla_drag,
                    blockers,
                    renewal_input,
                ),
            }
            row["recommended_action"] = self._renewal_recommended_action(row)
            rows.append(row)
        return sorted(
            rows,
            key=lambda item: (
                -item["renewal_risk_score"],
                item["renewal_window_days"],
                item["account"],
            ),
        )

    def _renewal_inputs_by_name(self) -> dict[str, dict[str, Any]]:
        if not self.renewal_inputs_path.exists():
            return {}
        rows = json.loads(self.renewal_inputs_path.read_text(encoding="utf-8"))
        return {self._normalize(item["customer"]): item for item in rows}

    def _support_sentiment(
        self,
        tickets: list[Ticket],
        runs: list[dict[str, Any]],
        renewal_input: dict[str, Any],
    ) -> dict[str, Any]:
        negative_terms = {
            "blocked",
            "outage",
            "breach",
            "angry",
            "churn",
            "renewal",
            "escalate",
            "executive",
            "duplicate",
            "regression",
            "down",
        }
        positive_terms = {"resolved", "thanks", "working", "confirmed", "stable"}
        text = " ".join(f"{ticket.subject} {ticket.body}" for ticket in tickets).lower()
        negative_hits = sorted(term for term in negative_terms if term in text)
        positive_hits = sorted(term for term in positive_terms if term in text)
        workflow_sentiment = Counter(
            run.get("state", {}).get("classification", {}).get("sentiment", "neutral")
            for run in runs
        )
        baseline = renewal_input.get("baseline_support_sentiment", "neutral")
        raw = (
            len(negative_hits) * 8
            + workflow_sentiment.get("negative", 0) * 10
            - len(positive_hits) * 4
        )
        if baseline == "negative":
            raw += 16
        elif baseline == "watch":
            raw += 8
        elif baseline == "positive":
            raw -= 8
        risk_points = max(0, min(30, raw))
        if risk_points >= 22:
            label = "negative"
        elif risk_points >= 10:
            label = "watch"
        elif risk_points <= 2 and positive_hits:
            label = "positive"
        else:
            label = "neutral"
        return {
            "label": label,
            "risk_points": risk_points,
            "negative_signals": negative_hits,
            "positive_signals": positive_hits,
            "workflow_sentiment_counts": dict(sorted(workflow_sentiment.items())),
            "baseline": baseline,
        }

    def _sla_drag_minutes(
        self,
        health: dict[str, Any],
        renewal_input: dict[str, Any],
    ) -> dict[str, Any]:
        components = [
            {
                "source": "fixture_open_sla_drag",
                "minutes": int(renewal_input.get("open_sla_drag_minutes", 0)),
                "reason": "Fake enterprise account input for unresolved SLA drag.",
            },
            {
                "source": "high_sla_risk_runs",
                "minutes": int(health["high_sla_risk_count"]) * 45,
                "reason": "Each high-SLA-risk workflow adds account review drag.",
            },
            {
                "source": "pending_approvals",
                "minutes": int(health["pending_approval_count"]) * 25,
                "reason": "Human approval queues delay customer-visible updates.",
            },
            {
                "source": "escalated_tickets",
                "minutes": int(health["escalated_count"]) * 30,
                "reason": "Escalated tickets imply cross-functional coordination time.",
            },
            {
                "source": "workflow_failures",
                "minutes": int(health["recent_failure_count"]) * 40,
                "reason": "Retry/failure paths require manual validation.",
            },
        ]
        components = [item for item in components if item["minutes"] > 0]
        total = sum(item["minutes"] for item in components)
        if total >= 180:
            level = "severe"
        elif total >= 90:
            level = "high"
        elif total >= 30:
            level = "moderate"
        else:
            level = "low"
        return {
            "total_minutes": total,
            "level": level,
            "components": components,
        }

    def _renewal_blockers(
        self,
        health: dict[str, Any],
        renewal_input: dict[str, Any],
        sentiment: dict[str, Any],
        sla_drag: dict[str, Any],
    ) -> list[dict[str, Any]]:
        blockers = [
            {
                "blocker": item["blocker"],
                "severity": item.get("severity", "medium"),
                "owner": item.get("owner", "customer-success"),
                "source": "sample_data/account_health_inputs.json",
                "recommended_clearance": item.get("recommended_clearance", "Confirm owner and next update."),
            }
            for item in renewal_input.get("renewal_blockers", [])
        ]
        if health["pending_approval_count"]:
            blockers.append(
                {
                    "blocker": "Pending support approval is delaying customer-visible action.",
                    "severity": "high",
                    "owner": "support-lead",
                    "source": "local approvals",
                    "recommended_clearance": "Review and approve or reject the pending run.",
                }
            )
        if health["high_sla_risk_count"]:
            blockers.append(
                {
                    "blocker": "High-SLA-risk support work is active during renewal window.",
                    "severity": "high",
                    "owner": "support-incident-lead",
                    "source": "local workflow SLA scorer",
                    "recommended_clearance": "Confirm mitigation owner, update cadence, and escalation path.",
                }
            )
        if sentiment["label"] == "negative":
            blockers.append(
                {
                    "blocker": "Support sentiment is negative across recent local evidence.",
                    "severity": "medium",
                    "owner": "customer-success",
                    "source": "ticket and workflow sentiment",
                    "recommended_clearance": "Schedule stakeholder recovery call with written next steps.",
                }
            )
        if sla_drag["level"] in {"high", "severe"}:
            blockers.append(
                {
                    "blocker": f"SLA drag is {sla_drag['level']} at {sla_drag['total_minutes']} minutes.",
                    "severity": "high" if sla_drag["level"] == "high" else "critical",
                    "owner": "support-ops",
                    "source": "local SLA drag model",
                    "recommended_clearance": "Reduce pending approvals and publish customer update cadence.",
                }
            )
        return blockers

    def _blocker_points(self, blockers: list[dict[str, Any]]) -> int:
        weights = {"low": 4, "medium": 8, "high": 14, "critical": 22}
        return min(35, sum(weights.get(item.get("severity", "medium"), 8) for item in blockers))

    def _relationship_points(self, renewal_input: dict[str, Any]) -> int:
        adoption = int(renewal_input.get("product_adoption_score", 70))
        confidence = int(renewal_input.get("csm_confidence", 70))
        points = 0
        if adoption < 60:
            points += 10
        elif adoption < 75:
            points += 5
        if confidence < 60:
            points += 10
        elif confidence < 75:
            points += 5
        if renewal_input.get("success_plan_status") in {"blocked", "stalled"}:
            points += 10
        if int(renewal_input.get("renewal_window_days", 180)) <= 60:
            points += 8
        return min(25, points)

    def _renewal_risk_level(self, score: int) -> str:
        if score >= 80:
            return "critical"
        if score >= 60:
            return "high"
        if score >= 35:
            return "watch"
        return "healthy"

    def _arr_at_risk(self, arr_usd: int, risk_score: int) -> int:
        if risk_score >= 80:
            multiplier = 0.75
        elif risk_score >= 60:
            multiplier = 0.5
        elif risk_score >= 35:
            multiplier = 0.25
        else:
            multiplier = 0.08
        return round(arr_usd * multiplier)

    def _renewal_owner_actions(
        self,
        health: dict[str, Any],
        sentiment: dict[str, Any],
        sla_drag: dict[str, Any],
        blockers: list[dict[str, Any]],
        renewal_input: dict[str, Any],
    ) -> list[dict[str, str]]:
        actions = [
            {
                "owner": renewal_input.get("commercial_owner", "customer-success"),
                "action": "Prepare renewal risk review with latest support evidence and ARR exposure.",
                "priority": "high" if blockers else "medium",
            }
        ]
        if health["pending_approval_count"]:
            actions.append(
                {
                    "owner": "support-lead",
                    "action": "Clear pending approvals and document the customer update decision.",
                    "priority": "high",
                }
            )
        if sla_drag["total_minutes"]:
            actions.append(
                {
                    "owner": "support-ops",
                    "action": f"Reduce SLA drag from {sla_drag['total_minutes']} minutes by assigning a named owner.",
                    "priority": "high" if sla_drag["level"] in {"high", "severe"} else "medium",
                }
            )
        if sentiment["label"] in {"negative", "watch"}:
            actions.append(
                {
                    "owner": "customer-success",
                    "action": "Run sentiment recovery follow-up with explicit support commitments.",
                    "priority": "medium",
                }
            )
        for blocker in blockers[:3]:
            actions.append(
                {
                    "owner": blocker["owner"],
                    "action": blocker["recommended_clearance"],
                    "priority": "high" if blocker["severity"] in {"high", "critical"} else "medium",
                }
            )
        unique: dict[tuple[str, str], dict[str, str]] = {}
        for action in actions:
            unique[(action["owner"], action["action"])] = action
        return list(unique.values())

    def _renewal_recommended_action(self, row: dict[str, Any]) -> str:
        if row["renewal_risk_level"] == "critical":
            return "Start executive renewal save plan, clear support blockers, and schedule sponsor update within one business day."
        if row["renewal_risk_level"] == "high":
            return "Open renewal risk review with support, success, and engineering owners this week."
        if row["support_sentiment"]["label"] in {"negative", "watch"}:
            return "Run customer sentiment recovery and confirm the next two support commitments."
        if row["sla_drag"]["total_minutes"]:
            return "Track SLA drag to zero before the next renewal checkpoint."
        return "Keep on standard renewal success plan and monitor support queue."

    def _renewal_summary(self, rows: list[dict[str, Any]]) -> dict[str, Any]:
        if not rows:
            return {
                "account_count": 0,
                "critical_or_high_count": 0,
                "arr_at_risk_usd": 0,
                "top_risk_account": None,
            }
        return {
            "account_count": len(rows),
            "critical_or_high_count": sum(
                1 for row in rows if row["renewal_risk_level"] in {"critical", "high"}
            ),
            "arr_at_risk_usd": sum(row["arr_at_risk_usd"] for row in rows),
            "total_sla_drag_minutes": sum(row["sla_drag"]["total_minutes"] for row in rows),
            "negative_sentiment_count": sum(
                1 for row in rows if row["support_sentiment"]["label"] == "negative"
            ),
            "top_risk_account": rows[0]["account"],
        }

    def _renewal_control_row(self, row: dict[str, Any]) -> dict[str, Any]:
        required_decisions = self._required_human_decisions(row)
        checkpoints = self._renewal_review_checkpoints(row)
        blocked_actions = self._blocked_renewal_actions(row)
        evidence_refs = self._renewal_evidence_refs(row)
        if row["renewal_risk_level"] == "critical":
            review_status = "executive_review_required"
        elif row["renewal_risk_level"] == "high":
            review_status = "cross_functional_review_required"
        elif blocked_actions:
            review_status = "owner_review_required"
        else:
            review_status = "monitor"
        return {
            "customer_id": row["customer_id"],
            "account": row["account"],
            "renewal_risk_level": row["renewal_risk_level"],
            "renewal_risk_score": row["renewal_risk_score"],
            "arr_at_risk_usd": row["arr_at_risk_usd"],
            "renewal_window_days": row["renewal_window_days"],
            "review_status": review_status,
            "required_approval_type": self._required_approval_type(row),
            "required_human_decisions": required_decisions,
            "blocked_automation_actions": blocked_actions,
            "durable_review_checkpoints": checkpoints,
            "resume_token": f"renewal:{row['customer_id']}:{row['renewal_risk_score']}",
            "owner_action_count": len(row["owner_actions"]),
            "primary_owner": self._primary_owner(row),
            "control_signals": {
                "support_sentiment": row["support_sentiment"]["label"],
                "sla_drag_minutes": row["sla_drag"]["total_minutes"],
                "blocker_count": len(row["renewal_blockers"]),
                "pending_approval_count": row["health"]["pending_approval_count"],
                "high_sla_risk_count": row["health"]["high_sla_risk_count"],
            },
            "evidence_refs": evidence_refs,
            "next_operator_action": self._control_next_action(row, review_status),
        }

    def _required_human_decisions(self, row: dict[str, Any]) -> list[dict[str, str]]:
        decisions = []
        if row["renewal_risk_level"] in {"critical", "high"}:
            decisions.append(
                {
                    "decision": "Approve renewal save plan before external executive commitments.",
                    "owner": row["commercial_owner"],
                    "reason": f"{row['renewal_risk_level']} renewal risk with ${row['arr_at_risk_usd']:,.0f} ARR at risk.",
                }
            )
        if row["support_sentiment"]["label"] in {"negative", "watch"}:
            decisions.append(
                {
                    "decision": "Review customer sentiment recovery message before dispatch.",
                    "owner": "customer-success",
                    "reason": f"Support sentiment is {row['support_sentiment']['label']}.",
                }
            )
        if row["sla_drag"]["level"] in {"high", "severe"}:
            decisions.append(
                {
                    "decision": "Confirm SLA drag owner and next-update timer.",
                    "owner": "support-ops",
                    "reason": f"SLA drag is {row['sla_drag']['total_minutes']} minutes.",
                }
            )
        return decisions

    def _blocked_renewal_actions(self, row: dict[str, Any]) -> list[dict[str, str]]:
        blocked = []
        if row["renewal_risk_level"] in {"critical", "high"}:
            blocked.append(
                {
                    "action": "send_external_renewal_commitment",
                    "blocked_until": "human renewal review is approved",
                    "policy": "No external executive promise from deterministic local scoring alone.",
                }
            )
        if row["renewal_blockers"]:
            blocked.append(
                {
                    "action": "mark_renewal_green",
                    "blocked_until": "blocker register has owner clearance",
                    "policy": "Open blockers prevent healthy renewal classification.",
                }
            )
        return blocked

    def _renewal_review_checkpoints(self, row: dict[str, Any]) -> list[dict[str, Any]]:
        stages = [
            ("risk_triage", "complete", "Renewal score, health score, sentiment, and SLA drag are computed."),
            (
                "support_evidence_review",
                "pending" if row["health"]["pending_approval_count"] else "complete",
                "Pending approvals and high-SLA support work are reviewed.",
            ),
            (
                "blocker_owner_assignment",
                "pending" if row["renewal_blockers"] else "complete",
                "Every blocker has an accountable owner and clearance action.",
            ),
            (
                "commercial_approval",
                "pending" if row["renewal_risk_level"] in {"critical", "high"} else "not_required",
                "Commercial owner approves renewal posture and customer commitment.",
            ),
        ]
        return [
            {
                "checkpoint_id": f"{row['customer_id']}:{stage}",
                "stage": stage,
                "status": status,
                "detail": detail,
            }
            for stage, status, detail in stages
        ]

    def _renewal_evidence_refs(self, row: dict[str, Any]) -> list[dict[str, str]]:
        refs = [
            {
                "source": "GET /customers/renewal-risk",
                "evidence": f"{row['renewal_risk_score']} {row['renewal_risk_level']} renewal score",
            },
            {
                "source": "sample_data/account_health_inputs.json",
                "evidence": f"{row['renewal_window_days']} day renewal window and {len(row['renewal_blockers'])} blockers",
            },
            {
                "source": "sample_data/customers.json",
                "evidence": f"${row['arr_usd']:,.0f} ARR metadata",
            },
        ]
        if row["health"]["pending_approval_count"]:
            refs.append(
                {
                    "source": "GET /approvals",
                    "evidence": f"{row['health']['pending_approval_count']} pending approvals",
                }
            )
        return refs

    def _required_approval_type(self, row: dict[str, Any]) -> str:
        if row["renewal_risk_level"] == "critical":
            return "executive_sponsor_and_commercial_owner"
        if row["renewal_risk_level"] == "high":
            return "commercial_owner_and_support_lead"
        if row["renewal_blockers"] or row["support_sentiment"]["label"] in {"negative", "watch"}:
            return "account_owner"
        return "none"

    def _primary_owner(self, row: dict[str, Any]) -> str:
        if row["renewal_risk_level"] == "critical":
            return row["commercial_owner"]
        if row["renewal_blockers"]:
            return row["renewal_blockers"][0]["owner"]
        return row["commercial_owner"]

    def _control_next_action(self, row: dict[str, Any], review_status: str) -> str:
        if review_status == "executive_review_required":
            return "Open executive renewal save review and export the account renewal review artifact."
        if review_status == "cross_functional_review_required":
            return "Schedule support, success, and engineering blocker review this week."
        if review_status == "owner_review_required":
            return "Assign blocker owners and clear pending support evidence gaps."
        return "Monitor through standard customer-success operating rhythm."

    def _renewal_control_summary(self, controls: list[dict[str, Any]]) -> dict[str, Any]:
        review_queue = [row for row in controls if row["review_status"] != "monitor"]
        executive = [
            row for row in controls if row["review_status"] == "executive_review_required"
        ]
        return {
            "status": "needs_review" if review_queue else "monitor",
            "account_count": len(controls),
            "review_required_count": len(review_queue),
            "executive_review_required_count": len(executive),
            "blocked_automation_action_count": sum(
                len(row["blocked_automation_actions"]) for row in controls
            ),
            "arr_at_risk_requiring_review_usd": sum(row["arr_at_risk_usd"] for row in review_queue),
            "pending_checkpoint_count": sum(
                1
                for row in controls
                for checkpoint in row["durable_review_checkpoints"]
                if checkpoint["status"] == "pending"
            ),
        }

    def _renewal_review_policy(self) -> dict[str, Any]:
        return {
            "critical_threshold": 80,
            "high_threshold": 60,
            "external_commitments_require_human_approval": True,
            "blocked_actions": [
                "send_external_renewal_commitment",
                "mark_renewal_green",
            ],
            "checkpoint_policy": "Every high or critical renewal-risk account must pass support evidence, blocker owner, and commercial approval checkpoints.",
            "source_of_truth": "GET /customers/renewal-risk",
        }

    def _renewal_control_acceptance_criteria(self) -> list[dict[str, str]]:
        return [
            {
                "criterion": "High and critical renewal risks are not auto-cleared.",
                "evidence": "control_board[].blocked_automation_actions contains policy gates.",
            },
            {
                "criterion": "Every review item has a human owner and explicit decision.",
                "evidence": "control_board[].required_human_decisions and primary_owner are populated.",
            },
            {
                "criterion": "Review work is resumable without external services.",
                "evidence": "control_board[].resume_token and durable_review_checkpoints are deterministic.",
            },
            {
                "criterion": "Reviewer artifacts are reproducible locally.",
                "evidence": "POST /customers/renewal-control-pack writes Markdown and JSON under data/renewal_control_packs.",
            },
        ]

    def _renewal_control_limitations(self) -> list[str]:
        return [
            "Control rows are deterministic local governance views over the renewal risk model.",
            "Human decisions are represented as review gates; this endpoint does not mutate CRM, billing, Slack, Jira, or Zendesk.",
            "Resume tokens are deterministic local identifiers, not distributed workflow locks.",
            "Generated control packs are ignored local proof artifacts and should be regenerated.",
        ]

    def _renewal_handoff_row(
        self,
        row: dict[str, Any],
        control: dict[str, Any],
    ) -> dict[str, Any]:
        artifacts = self._renewal_required_artifacts(row["customer_id"])
        checks = self._renewal_handoff_checks(row, control, artifacts)
        failed_checks = [check for check in checks if check["status"] == "fail"]
        warning_checks = [check for check in checks if check["status"] == "warn"]
        weighted_risk = sum(check["weight"] for check in failed_checks) + round(
            sum(check["weight"] for check in warning_checks) * 0.5
        )
        readiness_score = max(0, 100 - weighted_risk)
        if any(check["critical"] and check["status"] == "fail" for check in checks):
            status = "blocked"
        elif failed_checks or readiness_score < 82:
            status = "needs_review"
        else:
            status = "ready"
        return {
            "customer_id": row["customer_id"],
            "account": row["account"],
            "renewal_risk_level": row["renewal_risk_level"],
            "renewal_risk_score": row["renewal_risk_score"],
            "arr_at_risk_usd": row["arr_at_risk_usd"],
            "review_status": control["review_status"],
            "handoff_status": status,
            "readiness_score": readiness_score,
            "failed_check_count": len(failed_checks),
            "warning_check_count": len(warning_checks),
            "primary_owner": control["primary_owner"],
            "required_approval_type": control["required_approval_type"],
            "resume_token": control["resume_token"],
            "handoff_checks": checks,
            "required_artifact_handoffs": artifacts,
            "role_assignments": self._renewal_role_assignments(row, control),
            "run_transparency": self._renewal_run_transparency(row, control),
            "blocked_handoff_actions": self._renewal_blocked_handoff_actions(row, status),
            "next_operator_action": self._renewal_handoff_next_action(status, failed_checks, warning_checks),
        }

    def _renewal_required_artifacts(self, customer_id: str) -> list[dict[str, str]]:
        review_md = self.renewal_reviews_dir / f"{customer_id}.md"
        review_json = self.renewal_reviews_dir / f"{customer_id}.json"
        control_files = self._latest_artifact_files(self.renewal_control_dir)
        return [
            {
                "artifact": "account_renewal_review_markdown",
                "status": "generated" if review_md.exists() else "missing",
                "path": str(review_md),
                "producer": "POST /customers/{customer_id_or_name}/renewal-review",
            },
            {
                "artifact": "account_renewal_review_json",
                "status": "generated" if review_json.exists() else "missing",
                "path": str(review_json),
                "producer": "POST /customers/{customer_id_or_name}/renewal-review",
            },
            {
                "artifact": "renewal_control_pack",
                "status": "generated" if control_files else "missing",
                "path": control_files[0] if control_files else str(self.renewal_control_dir),
                "producer": "POST /customers/renewal-control-pack",
            },
        ]

    def _latest_artifact_files(self, directory: Path) -> list[str]:
        if not directory.exists():
            return []
        files = [
            path
            for path in directory.iterdir()
            if path.is_file() and path.suffix.lower() in {".md", ".json"}
        ]
        files.sort(key=lambda path: (path.stat().st_mtime, path.name), reverse=True)
        return [str(path) for path in files]

    def _renewal_handoff_checks(
        self,
        row: dict[str, Any],
        control: dict[str, Any],
        artifacts: list[dict[str, str]],
    ) -> list[dict[str, Any]]:
        artifact_ready = all(item["status"] == "generated" for item in artifacts)
        owner_ready = bool(control["primary_owner"]) and all(
            action.get("owner") and action.get("action") for action in row["owner_actions"]
        )
        blockers_ready = all(
            blocker.get("owner") and blocker.get("recommended_clearance")
            for blocker in row["renewal_blockers"]
        )
        support_ready = (
            row["health"]["pending_approval_count"] == 0
            and row["health"]["high_sla_risk_count"] == 0
            and row["sla_drag"]["level"] not in {"high", "severe"}
        )
        commercial_ready = (
            row["renewal_risk_level"] not in {"critical", "high"}
            or bool(control["required_human_decisions"])
        )
        return [
            self._handoff_check(
                "risk_triage",
                "Renewal risk triage is computed.",
                True,
                8,
                "GET /customers/renewal-risk produced score, level, sentiment, SLA drag, and ARR exposure.",
                "support-ops",
                critical=True,
            ),
            self._handoff_check(
                "artifact_handoff",
                "Required review artifacts are generated.",
                artifact_ready,
                22,
                f"{sum(1 for item in artifacts if item['status'] == 'generated')}/{len(artifacts)} artifacts present.",
                "support-ops",
                critical=True,
            ),
            self._handoff_check(
                "owner_assignment",
                "Every action has an accountable owner.",
                owner_ready,
                16,
                f"{len(row['owner_actions'])} owner actions and primary owner {control['primary_owner']}.",
                control["primary_owner"] or "customer-success",
                critical=True,
            ),
            self._handoff_check(
                "blocker_clearance_plan",
                "Renewal blockers have owner clearance plans.",
                blockers_ready,
                14,
                f"{len(row['renewal_blockers'])} blockers reviewed.",
                control["primary_owner"],
            ),
            self._handoff_check(
                "support_evidence_ready",
                "Support evidence is ready for external renewal review.",
                support_ready,
                24,
                (
                    f"{row['health']['pending_approval_count']} pending approvals, "
                    f"{row['health']['high_sla_risk_count']} high-SLA runs, "
                    f"{row['sla_drag']['total_minutes']} SLA-drag minutes."
                ),
                "support-lead",
                critical=row["renewal_risk_level"] == "critical",
            ),
            self._handoff_check(
                "commercial_review_gate",
                "Commercial review gate is explicit.",
                commercial_ready,
                16,
                (
                    f"{len(control['required_human_decisions'])} human decisions; "
                    f"approval type {control['required_approval_type']}."
                ),
                row["commercial_owner"],
                critical=True,
            ),
        ]

    def _handoff_check(
        self,
        check_id: str,
        label: str,
        passed: bool,
        weight: int,
        evidence: str,
        owner: str,
        *,
        critical: bool = False,
    ) -> dict[str, Any]:
        return {
            "check_id": check_id,
            "label": label,
            "status": "pass" if passed else "fail",
            "weight": weight,
            "critical": critical,
            "owner": owner,
            "evidence": evidence,
        }

    def _renewal_role_assignments(
        self,
        row: dict[str, Any],
        control: dict[str, Any],
    ) -> list[dict[str, str]]:
        assignments = [
            {
                "role": "commercial_owner",
                "owner": row["commercial_owner"],
                "responsibility": "Approve renewal posture and customer-facing commitments.",
            },
            {
                "role": "support_lead",
                "owner": "support-lead",
                "responsibility": "Clear pending approvals and certify support evidence.",
            },
            {
                "role": "customer_success",
                "owner": "customer-success",
                "responsibility": "Own sentiment recovery and executive communication cadence.",
            },
        ]
        if row["renewal_blockers"]:
            assignments.append(
                {
                    "role": "blocker_owner",
                    "owner": row["renewal_blockers"][0]["owner"],
                    "responsibility": "Drive the highest-severity blocker to documented clearance.",
                }
            )
        if control["review_status"] == "executive_review_required":
            assignments.append(
                {
                    "role": "executive_sponsor",
                    "owner": row["executive_sponsor"],
                    "responsibility": "Review risk posture before executive renewal meeting.",
                }
            )
        return assignments

    def _renewal_run_transparency(
        self,
        row: dict[str, Any],
        control: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "resume_token": control["resume_token"],
            "evidence_refs": control["evidence_refs"],
            "control_signals": control["control_signals"],
            "checkpoint_statuses": {
                checkpoint["stage"]: checkpoint["status"]
                for checkpoint in control["durable_review_checkpoints"]
            },
            "local_endpoints": [
                "GET /customers/renewal-risk",
                "GET /customers/renewal-control-board",
                "GET /customers/renewal-handoff-gate",
            ],
        }

    def _renewal_blocked_handoff_actions(
        self,
        row: dict[str, Any],
        status: str,
    ) -> list[dict[str, str]]:
        if status == "ready":
            return []
        return [
            {
                "account": row["account"],
                "action": "send_external_qbr_commitment",
                "blocked_until": "renewal handoff gate is ready",
                "policy": "External commitments require generated evidence, named owners, and review-gate clearance.",
            },
            {
                "account": row["account"],
                "action": "close_renewal_risk",
                "blocked_until": "failed handoff checks are cleared",
                "policy": "High-risk account cannot be marked green from local scoring alone.",
            },
        ]

    def _renewal_handoff_next_action(
        self,
        status: str,
        failed_checks: list[dict[str, Any]],
        warning_checks: list[dict[str, Any]],
    ) -> str:
        if status == "ready":
            return "Proceed to human renewal review with generated artifacts attached."
        checks = failed_checks or warning_checks
        if checks:
            check = sorted(checks, key=lambda item: item["weight"], reverse=True)[0]
            return f"Clear `{check['check_id']}` with {check['owner']} before external renewal commitments."
        return "Review handoff gate before external renewal commitments."

    def _renewal_handoff_summary(self, accounts: list[dict[str, Any]]) -> dict[str, Any]:
        blocked = [row for row in accounts if row["handoff_status"] == "blocked"]
        needs_review = [row for row in accounts if row["handoff_status"] == "needs_review"]
        ready = [row for row in accounts if row["handoff_status"] == "ready"]
        return {
            "status": "blocked" if blocked else "needs_review" if needs_review else "ready",
            "account_count": len(accounts),
            "blocked_count": len(blocked),
            "needs_review_count": len(needs_review),
            "ready_count": len(ready),
            "average_readiness_score": round(
                sum(row["readiness_score"] for row in accounts) / len(accounts), 1
            )
            if accounts
            else 100,
            "blocked_handoff_action_count": sum(
                len(row["blocked_handoff_actions"]) for row in accounts
            ),
            "top_gap": self._renewal_top_handoff_gap(accounts),
        }

    def _renewal_top_handoff_gap(self, accounts: list[dict[str, Any]]) -> str | None:
        gaps = Counter(
            check["check_id"]
            for row in accounts
            for check in row["handoff_checks"]
            if check["status"] == "fail"
        )
        return gaps.most_common(1)[0][0] if gaps else None

    def _renewal_handoff_role_playbook(self) -> list[dict[str, str]]:
        return [
            {
                "role": "support-lead",
                "handoff": "Certify pending approvals, high-SLA risk, and SLA drag are represented in the review artifact.",
            },
            {
                "role": "customer-success",
                "handoff": "Own sentiment recovery, sponsor update cadence, and QBR talking points.",
            },
            {
                "role": "commercial-owner",
                "handoff": "Approve renewal posture before external commitments or green status changes.",
            },
            {
                "role": "blocker-owner",
                "handoff": "Attach clearance evidence for the highest-severity renewal blockers.",
            },
        ]

    def _renewal_handoff_acceptance_criteria(self) -> list[dict[str, str]]:
        return [
            {
                "criterion": "Review artifacts are present before customer-facing renewal commitments.",
                "evidence": "accounts[].required_artifact_handoffs all report generated.",
            },
            {
                "criterion": "Each handoff has a role owner and visible next action.",
                "evidence": "accounts[].role_assignments and next_operator_action are populated.",
            },
            {
                "criterion": "Failed checks block external QBR commitments.",
                "evidence": "accounts[].blocked_handoff_actions lists send_external_qbr_commitment when not ready.",
            },
            {
                "criterion": "Run transparency is local and resumable.",
                "evidence": "accounts[].run_transparency includes resume token, endpoint list, and checkpoint statuses.",
            },
        ]

    def _renewal_handoff_limitations(self) -> list[str]:
        return [
            "Handoff readiness is a deterministic local gate over fake account data and generated local artifacts.",
            "The gate does not approve customer commitments or update CRM, billing, Zendesk, Jira, Slack, Azure, OpenAI, or external services.",
            "Artifact presence is checked on the local filesystem under ignored data directories.",
            "Commercial approvals are modeled as review gates, not legally binding renewal decisions.",
        ]

    def _renewal_executive_summary(self, row: dict[str, Any]) -> str:
        return (
            f"{row['account']} is {row['renewal_risk_level']} renewal risk with score "
            f"{row['renewal_risk_score']}/100, {row['sla_drag']['total_minutes']} minutes "
            f"of SLA drag, support sentiment `{row['support_sentiment']['label']}`, and "
            f"${row['arr_at_risk_usd']:,.0f} ARR at risk."
        )

    def _customer_success_review(self, row: dict[str, Any]) -> dict[str, Any]:
        return {
            "renewal_window_days": row["renewal_window_days"],
            "executive_sponsor": row["executive_sponsor"],
            "commercial_owner": row["commercial_owner"],
            "success_plan_status": row["success_plan_status"],
            "product_adoption_score": row["product_adoption_score"],
            "csm_confidence": row["csm_confidence"],
            "recommended_action": row["recommended_action"],
        }

    def _renewal_limitations(self) -> list[str]:
        return [
            "Uses fake enterprise account inputs and local support state only.",
            "Does not query CRM, billing, contracts, Zendesk, Jira, Slack, Azure, OpenAI, or external services.",
            "SLA drag and ARR-at-risk are deterministic portfolio estimates, not finance-grade forecasts.",
            "Review artifacts under data/renewal_reviews are ignored local proof and should be regenerated.",
        ]

    def _latest_runs_by_ticket(self, runs: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        latest: dict[str, dict[str, Any]] = {}
        for run in sorted(runs, key=self._run_time):
            latest[run["ticket_id"]] = run
        return latest

    def _runs_for_tickets(
        self,
        state: dict[str, Any],
        ticket_ids: set[str],
    ) -> list[dict[str, Any]]:
        return [run for run in state["runs"].values() if run.get("ticket_id") in ticket_ids]

    def _approvals_for_tickets(
        self,
        state: dict[str, Any],
        ticket_ids: set[str],
    ) -> list[Approval]:
        return [
            Approval(**raw)
            for raw in state["approvals"].values()
            if raw.get("ticket_id") in ticket_ids
        ]

    def _outbox_for_tickets(
        self,
        state: dict[str, Any],
        ticket_ids: set[str],
    ) -> list[OutboxEvent]:
        return [
            OutboxEvent(**raw)
            for raw in state["outbox"].values()
            if raw.get("ticket_id") in ticket_ids
        ]

    def _latest_run_for_ticket(
        self,
        runs: list[dict[str, Any]],
        ticket_id: str,
    ) -> dict[str, Any] | None:
        matches = [run for run in runs if run.get("ticket_id") == ticket_id]
        return sorted(matches, key=self._run_time)[-1] if matches else None

    def _ticket_row(self, ticket: Ticket, run: dict[str, Any] | None) -> dict[str, Any]:
        state = run.get("state", {}) if run else {}
        return {
            "ticket_id": ticket.ticket_id,
            "subject": ticket.subject,
            "priority": ticket.priority,
            "status": ticket.status,
            "customer_tier": ticket.customer_tier,
            "tags": ticket.tags,
            "sla_risk_level": state.get("sla_risk", {}).get("level", "unanalyzed"),
            "run_id": run.get("run_id") if run else None,
        }

    def _run_row(self, run: dict[str, Any]) -> dict[str, Any]:
        state = run.get("state", {})
        return {
            "run_id": run["run_id"],
            "ticket_id": run["ticket_id"],
            "status": run.get("status"),
            "started_at": run.get("started_at"),
            "completed_at": run.get("completed_at"),
            "category": state.get("classification", {}).get("category", "unknown"),
            "sla_risk_level": state.get("sla_risk", {}).get("level", "unknown"),
            "final_action": run.get("final_action") or "none",
            "has_failure": bool(run.get("failure_state")),
        }

    def _approval_row(self, approval: Approval) -> dict[str, Any]:
        return {
            "approval_id": approval.approval_id,
            "run_id": approval.run_id,
            "ticket_id": approval.ticket_id,
            "status": approval.status,
            "reason": approval.reason,
            "created_at": approval.created_at.isoformat(),
        }

    def _recommended_playbook_ids(self, runs: list[dict[str, Any]]) -> set[str]:
        return {
            item["id"]
            for run in runs
            for item in run.get("state", {}).get("playbook_recommendations", [])
            if item.get("confidence", 0) >= 0.5
        }

    def _recommended_playbooks(
        self,
        tickets: list[Ticket],
        runs: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        rows: dict[str, dict[str, Any]] = {}
        latest_by_ticket = self._latest_runs_by_ticket(runs)
        for ticket in tickets:
            run = latest_by_ticket.get(ticket.ticket_id)
            recommendations = (
                run.get("state", {}).get("playbook_recommendations", [])
                if run
                else [
                    item.model_dump(mode="json")
                    for item in self.playbook_service.recommend_for_ticket(ticket, {}, top_n=1)
                ]
            )
            for item in recommendations[:3]:
                row = rows.setdefault(
                    item["id"],
                    {
                        "id": item["id"],
                        "title": item["title"],
                        "severity": item["severity"],
                        "confidence": item["confidence"],
                        "affected_ticket_ids": [],
                        "owner_roles": item.get("owner_roles", []),
                    },
                )
                row["confidence"] = max(row["confidence"], item["confidence"])
                row["affected_ticket_ids"].append(ticket.ticket_id)
        return sorted(
            rows.values(),
            key=lambda item: (item["confidence"], item["severity"], item["title"]),
            reverse=True,
        )

    def _outbox_summary(self, outbox: list[OutboxEvent]) -> dict[str, Any]:
        by_status = Counter(event.status for event in outbox)
        by_action = Counter(event.action_type for event in outbox)
        recent_events = sorted(outbox, key=lambda event: event.created_at, reverse=True)[:8]
        return {
            "dispatch_count": len(outbox),
            "by_status": dict(sorted(by_status.items())),
            "by_action": dict(sorted(by_action.items())),
            "recent_events": [
                {
                    "outbox_id": event.outbox_id,
                    "run_id": event.run_id,
                    "ticket_id": event.ticket_id,
                    "action_type": event.action_type,
                    "destination": event.destination,
                    "status": event.status,
                    "created_at": event.created_at.isoformat(),
                }
                for event in recent_events
            ],
        }

    def _brief_next_actions(
        self,
        health: dict[str, Any],
        active_tickets: list[dict[str, Any]],
        recent_runs: list[dict[str, Any]],
        pending_approvals: list[dict[str, Any]],
        recommended_playbooks: list[dict[str, Any]],
        outbox_summary: dict[str, Any],
    ) -> list[str]:
        actions = [health["recommended_action"]]
        if pending_approvals:
            actions.append(f"Review {len(pending_approvals)} pending approvals for this account.")
        if any(ticket["sla_risk_level"] == "high" for ticket in active_tickets):
            actions.append("Keep the high-SLA-risk ticket owner and customer update timer visible.")
        if any(run["has_failure"] for run in recent_runs):
            actions.append("Validate any failure-affected guidance with a human support lead.")
        if recommended_playbooks:
            actions.append(f"Use {recommended_playbooks[0]['title']} as the primary account playbook.")
        if outbox_summary["dispatch_count"]:
            actions.append("Audit recent outbox handoffs for owner acknowledgement.")
        return list(dict.fromkeys(actions))

    def _find_summary(
        self,
        summaries: list[dict[str, Any]],
        customer_id_or_name: str,
    ) -> dict[str, Any] | None:
        target = self._normalize(customer_id_or_name)
        for summary in summaries:
            if target in {
                self._normalize(summary["customer_id"]),
                self._normalize(summary["customer"]),
                self._normalize(summary["account"]),
            }:
                return summary
        return None

    def _write_files(
        self,
        customer_id: str,
        brief: dict[str, Any],
        markdown: str,
    ) -> tuple[Path, Path]:
        self.account_briefs_dir.mkdir(parents=True, exist_ok=True)
        json_path = self.account_briefs_dir / f"{customer_id}.json"
        markdown_path = self.account_briefs_dir / f"{customer_id}.md"
        json_path.write_text(json.dumps(brief, indent=2, default=str), encoding="utf-8")
        markdown_path.write_text(markdown, encoding="utf-8")
        return json_path, markdown_path

    def _write_renewal_files(
        self,
        customer_id: str,
        review: dict[str, Any],
        markdown: str,
    ) -> tuple[Path, Path]:
        self.renewal_reviews_dir.mkdir(parents=True, exist_ok=True)
        json_path = self.renewal_reviews_dir / f"{customer_id}.json"
        markdown_path = self.renewal_reviews_dir / f"{customer_id}.md"
        json_path.write_text(json.dumps(review, indent=2, default=str), encoding="utf-8")
        markdown_path.write_text(markdown, encoding="utf-8")
        return json_path, markdown_path

    def _markdown(self, brief: dict[str, Any]) -> str:
        health = brief["customer_health"]
        active_tickets = [
            (
                f"- {item['ticket_id']}: {item['subject']} "
                f"[{item['status']}, SLA {item['sla_risk_level']}]"
            )
            for item in brief["active_tickets"]
        ] or ["- No active tickets."]
        recent_runs = [
            (
                f"- {item['run_id']} on {item['ticket_id']}: {item['status']}, "
                f"{item['category']}, SLA {item['sla_risk_level']}, action {item['final_action']}"
            )
            for item in brief["recent_runs"]
        ] or ["- No recent runs."]
        playbooks = [
            (
                f"- {item['title']} ({item['id']}), severity {item['severity']}, "
                f"tickets: {', '.join(item['affected_ticket_ids'])}"
            )
            for item in brief["recommended_playbooks"]
        ] or ["- No recommended playbooks yet."]
        approvals = [
            f"- {item['approval_id']} on {item['ticket_id']}: {item['reason']}"
            for item in brief["pending_approvals"]
        ] or ["- No pending approvals."]
        outbox = brief["outbox_summary"]
        outbox_rows = [
            f"- {item['action_type']} -> {item['destination']} [{item['status']}]"
            for item in outbox["recent_events"]
        ] or ["- No outbox dispatches for this account."]
        next_actions = [f"- {item}" for item in brief["next_actions"]]
        return "\n".join(
            [
                f"# Account Brief: {health['account']}",
                "",
                "## Customer Health",
                f"- Health score: {health['health_score']} ({health['risk_level']})",
                f"- Tickets: {health['ticket_count']}",
                f"- Open: {health['open_count']}",
                f"- Pending: {health['pending_count']}",
                f"- Escalated: {health['escalated_count']}",
                f"- High SLA risk: {health['high_sla_risk_count']}",
                f"- Recent failures: {health['recent_failure_count']}",
                f"- Pending approvals: {health['pending_approval_count']}",
                f"- Recommended playbooks: {health['recommended_playbook_count']}",
                f"- Recommended action: {health['recommended_action']}",
                "",
                "## Active Tickets",
                *active_tickets,
                "",
                "## Recent Runs",
                *recent_runs,
                "",
                "## Recommended Playbooks",
                *playbooks,
                "",
                "## Pending Approvals",
                *approvals,
                "",
                "## Outbox Summary",
                f"- Dispatch count: {outbox['dispatch_count']}",
                f"- By action: {json.dumps(outbox['by_action'], sort_keys=True)}",
                *outbox_rows,
                "",
                "## Next Actions",
                *next_actions,
                "",
            ]
        )

    def _renewal_markdown(self, review: dict[str, Any]) -> str:
        account = review["account"]
        sentiment = account["support_sentiment"]
        sla_drag = account["sla_drag"]
        blocker_rows = [
            (
                f"- {item['blocker']} [{item['severity']}] owner={item['owner']}; "
                f"clearance: {item['recommended_clearance']}"
            )
            for item in review["blocker_register"]
        ] or ["- No active renewal blockers detected."]
        action_rows = [
            f"- {item['owner']} ({item['priority']}): {item['action']}"
            for item in review["owner_actions"]
        ]
        drag_rows = [
            f"- {item['source']}: {item['minutes']} minutes - {item['reason']}"
            for item in sla_drag["components"]
        ] or ["- No SLA drag components."]
        ticket_rows = [
            (
                f"- {item['ticket_id']}: {item['subject']} "
                f"[{item['status']}, SLA {item['sla_risk_level']}]"
            )
            for item in review["support_evidence"]["active_tickets"]
        ] or ["- No active tickets."]
        run_rows = [
            (
                f"- {item['run_id']} on {item['ticket_id']}: {item['status']}, "
                f"{item['category']}, SLA {item['sla_risk_level']}, action {item['final_action']}"
            )
            for item in review["support_evidence"]["recent_runs"]
        ] or ["- No recent runs."]
        approval_rows = [
            f"- {item['approval_id']} on {item['ticket_id']}: {item['reason']}"
            for item in review["support_evidence"]["pending_approvals"]
        ] or ["- No pending approvals."]
        limitations = [f"- {item}" for item in review["limitations"]]
        return "\n".join(
            [
                f"# Renewal Risk Review: {account['account']}",
                "",
                "## Executive Summary",
                review["executive_summary"],
                "",
                "## Renewal Risk",
                f"- Risk score: {account['renewal_risk_score']} ({account['renewal_risk_level']})",
                f"- ARR: ${account['arr_usd']:,.0f}",
                f"- ARR at risk: ${account['arr_at_risk_usd']:,.0f}",
                f"- Renewal window: {account['renewal_window_days']} days",
                f"- Executive sponsor: {account['executive_sponsor']}",
                f"- Commercial owner: {account['commercial_owner']}",
                f"- Recommended action: {account['recommended_action']}",
                "",
                "## Support Sentiment",
                f"- Label: {sentiment['label']}",
                f"- Risk points: {sentiment['risk_points']}",
                f"- Baseline: {sentiment['baseline']}",
                f"- Negative signals: {', '.join(sentiment['negative_signals']) or 'none'}",
                "",
                "## SLA Drag",
                f"- Total minutes: {sla_drag['total_minutes']}",
                f"- Level: {sla_drag['level']}",
                *drag_rows,
                "",
                "## Renewal Blockers",
                *blocker_rows,
                "",
                "## Owner Actions",
                *action_rows,
                "",
                "## Active Tickets",
                *ticket_rows,
                "",
                "## Recent Runs",
                *run_rows,
                "",
                "## Pending Approvals",
                *approval_rows,
                "",
                "## Customer Success Review",
                f"- Success plan: {review['customer_success_review']['success_plan_status']}",
                f"- Product adoption score: {review['customer_success_review']['product_adoption_score']}",
                f"- CSM confidence: {review['customer_success_review']['csm_confidence']}",
                "",
                "## Limitations",
                *limitations,
                "",
            ]
        )

    def _renewal_control_markdown(self, pack: dict[str, Any]) -> str:
        board = pack["control_board"]
        summary = board["summary"]
        control_rows = [
            (
                f"| {row['account']} | {row['renewal_risk_level']} | {row['renewal_risk_score']} | "
                f"${row['arr_at_risk_usd']:,.0f} | {row['review_status']} | "
                f"{row['required_approval_type']} | {row['primary_owner']} |"
            )
            for row in board["control_board"]
        ]
        checkpoint_rows = [
            (
                f"| {row['account']} | {checkpoint['stage']} | {checkpoint['status']} | "
                f"{checkpoint['detail']} |"
            )
            for row in board["control_board"]
            for checkpoint in row["durable_review_checkpoints"]
        ]
        decision_rows = [
            f"- **{row['account']}** / {item['owner']}: {item['decision']} Reason: {item['reason']}"
            for row in board["control_board"]
            for item in row["required_human_decisions"]
        ] or ["- No human decisions required."]
        blocked_rows = [
            f"- **{row['account']}**: `{item['action']}` blocked until {item['blocked_until']} ({item['policy']})"
            for row in board["control_board"]
            for item in row["blocked_automation_actions"]
        ] or ["- No blocked automation actions."]
        criteria_rows = [
            f"- [ ] **{item['criterion']}** Evidence: {item['evidence']}"
            for item in pack["operator_acceptance_criteria"]
        ]
        limitation_rows = [f"- {item}" for item in board["limitations"]]
        return "\n".join(
            [
                f"# Renewal Control Pack: {pack['pack_id']}",
                "",
                "## Summary",
                f"- Status: {summary['status']}",
                f"- Accounts: {summary['account_count']}",
                f"- Review required: {summary['review_required_count']}",
                f"- Executive review required: {summary['executive_review_required_count']}",
                f"- Blocked automation actions: {summary['blocked_automation_action_count']}",
                f"- ARR at risk requiring review: ${summary['arr_at_risk_requiring_review_usd']:,.0f}",
                f"- Pending checkpoints: {summary['pending_checkpoint_count']}",
                "",
                "## Review Policy",
                f"- External commitments require human approval: {board['review_policy']['external_commitments_require_human_approval']}",
                f"- Source of truth: `{board['review_policy']['source_of_truth']}`",
                f"- Checkpoint policy: {board['review_policy']['checkpoint_policy']}",
                "",
                "## Control Board",
                "| Account | Risk | Score | ARR At Risk | Review Status | Approval | Owner |",
                "| --- | --- | ---: | ---: | --- | --- | --- |",
                *control_rows,
                "",
                "## Required Human Decisions",
                *decision_rows,
                "",
                "## Blocked Automation Actions",
                *blocked_rows,
                "",
                "## Durable Review Checkpoints",
                "| Account | Stage | Status | Detail |",
                "| --- | --- | --- | --- |",
                *checkpoint_rows,
                "",
                "## Operator Acceptance Criteria",
                *criteria_rows,
                "",
                "## Local Verification",
                f"- Artifact directory: `{pack['local_verification']['artifact_directory']}`",
                f"- Demo command: `{pack['local_verification']['demo_command']}`",
                *[f"- `{endpoint}`" for endpoint in pack["local_verification"]["endpoints"]],
                "",
                "## Limitations",
                *limitation_rows,
                "",
            ]
        )

    def _renewal_handoff_markdown(self, pack: dict[str, Any]) -> str:
        gate = pack["gate"]
        summary = gate["summary"]
        account_rows = [
            (
                f"| {row['account']} | {row['handoff_status']} | {row['readiness_score']} | "
                f"{row['renewal_risk_level']} | ${row['arr_at_risk_usd']:,.0f} | "
                f"{row['failed_check_count']} | {row['primary_owner']} |"
            )
            for row in gate["accounts"]
        ] or ["| None | ready | 100 | healthy | $0 | 0 | support-ops |"]
        check_rows = [
            (
                f"| {row['account']} | {check['check_id']} | {check['status']} | "
                f"{check['owner']} | {check['evidence']} |"
            )
            for row in gate["accounts"]
            for check in row["handoff_checks"]
        ]
        artifact_rows = [
            (
                f"| {row['account']} | {artifact['artifact']} | {artifact['status']} | "
                f"`{artifact['path']}` | `{artifact['producer']}` |"
            )
            for row in gate["accounts"]
            for artifact in row["required_artifact_handoffs"]
        ]
        role_rows = [
            f"- **{item['role']}**: {item['handoff']}"
            for item in gate["role_playbook"]
        ]
        blocked_rows = [
            (
                f"- **{item['account']}**: `{item['action']}` blocked until "
                f"{item['blocked_until']} ({item['policy']})"
            )
            for item in pack["blocked_handoff_actions"]
        ] or ["- No handoff actions are blocked."]
        criteria_rows = [
            f"- [ ] **{item['criterion']}** Evidence: {item['evidence']}"
            for item in gate["operator_acceptance_criteria"]
        ]
        limitations = [f"- {item}" for item in gate["limitations"]]
        return "\n".join(
            [
                f"# Renewal Handoff Readiness Pack: {pack['pack_id']}",
                "",
                "## Summary",
                f"- Status: {summary['status']}",
                f"- Accounts: {summary['account_count']}",
                f"- Blocked: {summary['blocked_count']}",
                f"- Needs review: {summary['needs_review_count']}",
                f"- Ready: {summary['ready_count']}",
                f"- Average readiness score: {summary['average_readiness_score']}",
                f"- Blocked handoff actions: {summary['blocked_handoff_action_count']}",
                f"- Top gap: {summary['top_gap'] or 'none'}",
                "",
                "## Role Playbook",
                *role_rows,
                "",
                "## Account Gate",
                "| Account | Handoff Status | Score | Renewal Risk | ARR At Risk | Failed Checks | Owner |",
                "| --- | --- | ---: | --- | ---: | ---: | --- |",
                *account_rows,
                "",
                "## Review Checks",
                "| Account | Check | Status | Owner | Evidence |",
                "| --- | --- | --- | --- | --- |",
                *check_rows,
                "",
                "## Artifact Handoffs",
                "| Account | Artifact | Status | Path | Producer |",
                "| --- | --- | --- | --- | --- |",
                *artifact_rows,
                "",
                "## Blocked Handoff Actions",
                *blocked_rows,
                "",
                "## Operator Acceptance Criteria",
                *criteria_rows,
                "",
                "## Local Verification",
                f"- Artifact directory: `{pack['local_verification']['artifact_directory']}`",
                f"- Demo command: `{pack['local_verification']['demo_command']}`",
                *[f"- `{endpoint}`" for endpoint in pack["local_verification"]["endpoints"]],
                "",
                "## Limitations",
                *limitations,
                "",
            ]
        )

    def _run_time(self, run: dict[str, Any]) -> str:
        return run.get("started_at") or ""

    def _normalize(self, value: str) -> str:
        return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()

    def _slug(self, value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "unknown-account"
