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
    ):
        self.store = store
        self.ticket_service = ticket_service
        self.playbook_service = playbook_service
        self.customers_path = customers_path
        self.renewal_inputs_path = renewal_inputs_path
        self.account_briefs_dir = account_briefs_dir
        self.renewal_reviews_dir = renewal_reviews_dir

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

    def _run_time(self, run: dict[str, Any]) -> str:
        return run.get("started_at") or ""

    def _normalize(self, value: str) -> str:
        return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()

    def _slug(self, value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "unknown-account"
