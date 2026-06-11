import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.core.storage import JsonStateStore
from app.models import AuditEvent, RunRecord, Ticket, TicketCreate
from app.services.audit import AuditService
from app.services.tickets import TicketService
from app.services.workflow import AgentWorkflowService


ESCALATION_QUALITY_VERIFY_COMMANDS = [
    r".\.venv\Scripts\python.exe -m pytest -q",
    r".\.venv\Scripts\python.exe -m ruff check app tests dashboard scripts",
    r".\.venv\Scripts\python.exe -m app.evals.run_eval",
    r".\.venv\Scripts\python.exe scripts\dashboard_smoke.py",
    r".\.venv\Scripts\python.exe scripts\demo_run.py",
    (
        r'rg "escalations/quality-audit|escalations/quality-pack|Escalation Quality|'
        r'escalation_quality_packs|actionability|noise control" '
        r"app dashboard docs README.md tests scripts"
    ),
]


ESCALATION_REVIEW_CREW = [
    {
        "role": "engineering_triage_reviewer",
        "decision_scope": "actionability",
        "playbook": "Confirm the escalation has severity, suspected area, owner path, and next engineering action.",
    },
    {
        "role": "support_evidence_reviewer",
        "decision_scope": "reproduction_evidence",
        "playbook": "Verify reproduction clues, customer symptoms, and KB or trace evidence are attached.",
    },
    {
        "role": "customer_impact_reviewer",
        "decision_scope": "customer_impact",
        "playbook": "Check that business impact, tier, SLA pressure, and customer-visible risk are explicit.",
    },
    {
        "role": "escalation_governance_reviewer",
        "decision_scope": "routing_governance",
        "playbook": "Block Jira or Slack handoff when approval, confidence, or failure controls are not satisfied.",
    },
    {
        "role": "noise_control_reviewer",
        "decision_scope": "noise_control",
        "playbook": "Prevent low-signal or duplicate engineering work by checking escalation necessity and evidence density.",
    },
]


class EscalationQualityService:
    """Evaluates engineering escalation drafts before internal dispatch."""

    def __init__(
        self,
        store: JsonStateStore,
        tickets: TicketService,
        workflow: AgentWorkflowService,
        audit: AuditService,
        scenario_fixture: Path,
        quality_pack_dir: Path,
    ):
        self.store = store
        self.tickets = tickets
        self.workflow = workflow
        self.audit = audit
        self.scenario_fixture = scenario_fixture
        self.quality_pack_dir = quality_pack_dir

    async def quality_audit(self, run_id: str | None = None) -> dict[str, Any]:
        run, ticket, source = await self._resolve_run(run_id)
        escalation_required = self._escalation_required(run)
        dimensions = self._score_dimensions(run, ticket, escalation_required)
        overall = round(sum(item["score"] for item in dimensions.values()) / len(dimensions))
        blockers = self._blockers(dimensions, run, escalation_required)
        status = self._status(overall, blockers, escalation_required, run)
        scenario_coverage = await self._scenario_coverage()
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "title": "Engineering Escalation Quality Audit",
            "mode": "local-deterministic-escalation-quality",
            "local_mock_only": True,
            "source": source,
            "run_id": run.run_id,
            "ticket_id": ticket.ticket_id,
            "trace_id": run.trace_id,
            "subject": ticket.subject,
            "customer": ticket.customer or ticket.account or ticket.customer_email,
            "escalation_required": escalation_required,
            "overall_score": overall,
            "status": status,
            "quality_gate": self._quality_gate(status, overall, blockers, escalation_required),
            "score_dimensions": dimensions,
            "review_crew": ESCALATION_REVIEW_CREW,
            "role_playbook_handoffs": self._role_playbook_handoffs(dimensions),
            "artifact_handoffs": self._artifact_handoffs(run),
            "run_transparency": self._run_transparency(run),
            "escalation_evidence": self._escalation_evidence(run, ticket),
            "required_revisions": self._required_revisions(dimensions, blockers, escalation_required),
            "scenario_coverage": scenario_coverage,
            "local_proof_commands": ESCALATION_QUALITY_VERIFY_COMMANDS,
            "patterns_applied": [
                "human-in-the-loop escalation approval",
                "governance gate before internal dispatch",
                "trace-backed observability for handoff evidence",
            ],
            "limitations": [
                "Scores are deterministic local heuristics for reviewer triage, not production Jira policy.",
                "The service reads stored workflow drafts and never creates Jira issues or Slack alerts.",
                "No Azure, OpenAI, Zendesk, Jira, Slack, GitHub, or external services are called.",
            ],
        }

    async def export_quality_pack(self, run_id: str | None = None) -> dict[str, Any]:
        audit = await self.quality_audit(run_id)
        generated_at = datetime.now(timezone.utc)
        pack_id = f"escalation_quality_pack_{generated_at.strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:6]}"
        json_path = self.quality_pack_dir / f"{pack_id}.json"
        markdown_path = self.quality_pack_dir / f"{pack_id}.md"
        pack = {
            "pack_id": pack_id,
            "generated_at": generated_at.isoformat(),
            "title": "Engineering Escalation Quality Pack",
            "quality_audit": audit,
            "review_gate_summary": audit["quality_gate"],
            "role_crew_review": audit["review_crew"],
            "handoff_packet": {
                "artifact_handoffs": audit["artifact_handoffs"],
                "role_playbook_handoffs": audit["role_playbook_handoffs"],
                "run_transparency": audit["run_transparency"],
                "escalation_evidence": audit["escalation_evidence"],
            },
            "reviewer_actions": audit["required_revisions"],
            "local_proof_commands": ESCALATION_QUALITY_VERIFY_COMMANDS,
            "artifact_paths": {
                "escalation_quality_pack_markdown": str(markdown_path),
                "escalation_quality_pack_json": str(json_path),
            },
            "limitations": audit["limitations"],
        }
        markdown = self._markdown(pack)
        self.quality_pack_dir.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(pack, indent=2, default=str), encoding="utf-8")
        markdown_path.write_text(markdown, encoding="utf-8")
        await self.audit.record(
            AuditEvent(
                actor="escalation-quality",
                action="escalations.quality_pack_exported",
                resource_type="escalation_quality_pack",
                resource_id=pack_id,
                trace_id=audit["trace_id"],
                metadata={"markdown_path": str(markdown_path), "json_path": str(json_path)},
            )
        )
        return {
            "pack_id": pack_id,
            "format": "markdown+json",
            "status": audit["status"],
            "overall_score": audit["overall_score"],
            "json_path": str(json_path),
            "markdown_path": str(markdown_path),
            "pack": pack,
            "markdown": markdown,
        }

    async def _resolve_run(self, run_id: str | None) -> tuple[RunRecord, Ticket, str]:
        if run_id:
            run = await self.workflow.get_run(run_id)
            return run, await self._ticket_for_run(run), "requested_run"
        state = await self.store.load()
        if state["runs"]:
            run = RunRecord(**sorted(state["runs"].values(), key=lambda item: item["started_at"])[-1])
            return run, await self._ticket_for_run(run), "latest_run"
        scenario = self._selected_scenarios()[0]
        ticket = await self._ingest_or_get_scenario_ticket(scenario)
        run = await self.workflow.analyze_ticket(ticket.ticket_id)
        return run, ticket, "scenario_bootstrap"

    async def _ticket_for_run(self, run: RunRecord) -> Ticket:
        ticket = await self.tickets.get(run.ticket_id)
        if ticket is None:
            raise KeyError(run.ticket_id)
        return ticket

    async def _ingest_or_get_scenario_ticket(self, scenario: dict[str, Any]) -> Ticket:
        payload = TicketCreate(**scenario["ticket"])
        if payload.external_id:
            existing = await self.tickets.get_by_external_id(payload.external_id)
            if existing:
                return existing
        return await self.tickets.ingest(payload)

    def _selected_scenarios(self) -> list[dict[str, Any]]:
        scenarios = json.loads(self.scenario_fixture.read_text(encoding="utf-8"))
        preferred = [
            "scn_enterprise_login_outage",
            "scn_webhook_api_regression",
            "scn_billing_duplicate_invoice",
            "scn_privacy_data_export",
            "scn_low_confidence_ambiguity",
        ]
        by_id = {item["scenario_id"]: item for item in scenarios}
        return [by_id[item] for item in preferred if item in by_id]

    async def _scenario_coverage(self) -> dict[str, Any]:
        rows = []
        for scenario in self._selected_scenarios():
            ticket = await self._ingest_or_get_scenario_ticket(scenario)
            run = await self.workflow.analyze_ticket(ticket.ticket_id)
            required = self._escalation_required(run)
            dimensions = self._score_dimensions(run, ticket, required)
            overall = round(sum(item["score"] for item in dimensions.values()) / len(dimensions))
            blockers = self._blockers(dimensions, run, required)
            rows.append(
                {
                    "scenario_id": scenario["scenario_id"],
                    "domain": scenario["domain"],
                    "run_id": run.run_id,
                    "ticket_id": ticket.ticket_id,
                    "escalation_required": required,
                    "overall_score": overall,
                    "gate_status": self._status(overall, blockers, required, run),
                    "lowest_dimension": min(dimensions.items(), key=lambda item: item[1]["score"])[0],
                    "approval_linked": bool(run.state.get("approval_id")),
                    "trace_event_count": len(run.state.get("node_history", [])),
                }
            )
        domains = Counter(row["domain"] for row in rows)
        return {
            "coverage_status": "pass" if len(rows) >= 5 and any(row["escalation_required"] for row in rows) else "gap",
            "scenario_count": len(rows),
            "domains": dict(domains),
            "escalation_required_count": sum(1 for row in rows if row["escalation_required"]),
            "approval_linked_count": sum(1 for row in rows if row["approval_linked"]),
            "scenarios": rows,
        }

    def _score_dimensions(
        self,
        run: RunRecord,
        ticket: Ticket,
        escalation_required: bool,
    ) -> dict[str, Any]:
        draft = run.state.get("drafts", {}).get("engineering_escalation", "")
        if not escalation_required and not draft:
            return {
                name: self._not_required_dimension(name)
                for name in [
                    "actionability",
                    "reproduction_evidence",
                    "customer_impact",
                    "routing_governance",
                    "noise_control",
                ]
            }
        text = draft.lower()
        ticket_text = f"{ticket.subject} {ticket.body}".lower()
        kb_results = run.state.get("kb_results", [])
        qa = run.state.get("qa", {})
        sla = run.state.get("sla_risk", {})
        classification = run.state.get("classification", {})
        owner = str(classification.get("owner") or classification.get("likely_owner") or "").lower()
        ticket_terms = self._important_terms(ticket_text)
        return {
            "actionability": self._dimension(
                "actionability",
                40,
                [
                    (bool(draft), 20, "includes an engineering escalation draft"),
                    (any(term in text for term in ["severity", "critical", "high", "sev"]), 15, "states severity"),
                    (any(term in text for term in ["suspected", "area", "auth", "api", "billing", "integration"]), 10, "names suspected area"),
                    (bool(owner) and owner in text or "engineering" in text, 10, "identifies an owner route"),
                    (len(draft.split()) >= 30, 10, "has enough detail for triage"),
                ],
            ),
            "reproduction_evidence": self._dimension(
                "reproduction_evidence",
                40,
                [
                    (any(term in text for term in ["repro", "steps", "observed", "symptom", "clue"]), 15, "includes reproduction clues"),
                    (bool(kb_results), 15, "attaches retrieved KB evidence"),
                    (any(item.get("article_id", "").lower() in text for item in kb_results), 10, "cites KB article IDs"),
                    (any(term in text for term in ticket_terms), 10, "carries ticket-specific symptoms"),
                    (len(run.state.get("node_history", [])) >= 5, 10, "trace shows full workflow context"),
                ],
            ),
            "customer_impact": self._dimension(
                "customer_impact",
                45,
                [
                    ("impact" in text or "customer" in text, 15, "describes customer impact"),
                    (ticket.customer_tier.lower() in text or "enterprise" in text, 10, "names account tier or enterprise impact"),
                    ("sla" in text or sla.get("level") != "high", 10, "mentions SLA risk when high pressure exists"),
                    (ticket.priority.value.lower() in text or str(ticket.priority).lower() in text, 10, "preserves ticket priority"),
                    (ticket.subject.lower()[:20] in text, 10, "ties escalation to the reported issue"),
                ],
            ),
            "routing_governance": self._dimension(
                "routing_governance",
                45,
                [
                    (bool(run.state.get("approval_id")), 20, "links human approval gate"),
                    ("approval" in text or run.status.value == "awaiting_approval", 10, "keeps internal action review-gated"),
                    (qa.get("confidence", 1.0) >= self.workflow.low_confidence_threshold, 10, "QA confidence clears threshold"),
                    (run.failure_state is None, 10, "no unresolved workflow failure"),
                    (run.final_action in {"engineering_escalation", "customer_reply"} or bool(draft), 5, "final action is explicit"),
                ],
            ),
            "noise_control": self._dimension(
                "noise_control",
                50,
                [
                    (escalation_required, 20, "escalation is justified by SLA, incident, API, auth, privacy, or final action"),
                    (bool(kb_results) and len(draft.split()) >= 30, 10, "handoff is evidence-dense enough to reduce back-and-forth"),
                    (not self._contains_noise_terms(text), 10, "avoids vague low-signal escalation language"),
                    (bool(run.state.get("approval_id")), 10, "human reviewer can suppress noisy internal dispatch"),
                    (len(run.state.get("tool_calls", [])) >= 1, 5, "tool evidence is available for reviewers"),
                ],
            ),
        }

    def _dimension(self, name: str, base: int, checks: list[tuple[bool, int, str]]) -> dict[str, Any]:
        passed = [label for ok, _, label in checks if ok]
        gaps = [label for ok, _, label in checks if not ok]
        score = min(100, base + sum(points for ok, points, _ in checks if ok))
        return {
            "dimension": name,
            "score": score,
            "status": "pass" if score >= 75 else "warn" if score >= 60 else "fail",
            "passed_checks": passed,
            "gaps": gaps,
        }

    def _not_required_dimension(self, name: str) -> dict[str, Any]:
        return {
            "dimension": name,
            "score": 88,
            "status": "pass",
            "passed_checks": ["No engineering escalation is required for this run."],
            "gaps": [],
        }

    def _escalation_required(self, run: RunRecord) -> bool:
        sla = run.state.get("sla_risk", {})
        classification = run.state.get("classification", {})
        category = str(classification.get("category", "")).lower()
        tags = " ".join(run.state.get("ticket", {}).get("tags", [])).lower()
        high_signal = any(
            term in f"{category} {tags}"
            for term in ["incident", "outage", "api", "auth", "security", "privacy", "integration", "webhook"]
        )
        return (
            run.final_action == "engineering_escalation"
            or bool(run.state.get("drafts", {}).get("engineering_escalation"))
            or sla.get("level") == "high"
            or high_signal
        )

    def _important_terms(self, ticket_text: str) -> list[str]:
        candidates = [
            "sso",
            "saml",
            "login",
            "webhook",
            "api",
            "500",
            "billing",
            "invoice",
            "privacy",
            "export",
            "outage",
            "latency",
            "integration",
        ]
        return [term for term in candidates if term in ticket_text]

    def _contains_noise_terms(self, text: str) -> bool:
        vague_terms = ["please investigate", "not sure", "something is wrong", "maybe broken"]
        return any(term in text for term in vague_terms)

    def _blockers(
        self,
        dimensions: dict[str, Any],
        run: RunRecord,
        escalation_required: bool,
    ) -> list[str]:
        if not escalation_required and not run.state.get("drafts", {}).get("engineering_escalation"):
            return []
        blockers = [
            f"{name} score is below engineering review threshold"
            for name, item in dimensions.items()
            if item["status"] == "fail"
        ]
        if escalation_required and not run.state.get("drafts", {}).get("engineering_escalation"):
            blockers.append("Engineering escalation is required but no draft exists.")
        if run.failure_state:
            blockers.append("Unresolved workflow failure requires support engineering review.")
        if run.state.get("qa", {}).get("confidence", 1.0) < self.workflow.low_confidence_threshold:
            blockers.append("Low-confidence QA requires senior reviewer approval before Jira handoff.")
        return list(dict.fromkeys(blockers))

    def _status(
        self,
        overall: int,
        blockers: list[str],
        escalation_required: bool,
        run: RunRecord,
    ) -> str:
        if not escalation_required and not run.state.get("drafts", {}).get("engineering_escalation"):
            return "not_required"
        if blockers:
            return "blocked"
        return "ready_for_engineering_review" if overall >= 75 else "needs_revision"

    def _quality_gate(
        self,
        status: str,
        overall: int,
        blockers: list[str],
        escalation_required: bool,
    ) -> dict[str, Any]:
        return {
            "gate": "engineering_escalation_pre_dispatch_review",
            "status": status,
            "overall_score": overall,
            "escalation_required": escalation_required,
            "approved_for_internal_dispatch": status == "ready_for_engineering_review" and not blockers,
            "blockers": blockers,
            "review_gate_pattern": "human_in_the_loop",
            "governance_pattern": "pre_dispatch_policy_gate",
            "observability_pattern": "trace_backed_handoff",
            "required_approver": "support_engineering_lead",
        }
    def _role_playbook_handoffs(self, dimensions: dict[str, Any]) -> list[dict[str, Any]]:
        rows = []
        for role in ESCALATION_REVIEW_CREW:
            dimension = dimensions[role["decision_scope"]]
            rows.append(
                {
                    **role,
                    "status": dimension["status"],
                    "score": dimension["score"],
                    "handoff": dimension["gaps"] or ["No revision required before support engineering review."],
                }
            )
        return rows

    def _artifact_handoffs(self, run: RunRecord) -> list[dict[str, str]]:
        return [
            {
                "artifact": "run_trace",
                "endpoint": f"GET /runs/{run.run_id}/trace",
                "purpose": "Reviewer can inspect classifier, SLA, KB, drafting, QA, and approval nodes.",
            },
            {
                "artifact": "approval_queue",
                "endpoint": "GET /approvals",
                "purpose": "Support engineering lead sees pending escalation approval before Jira/Slack dispatch.",
            },
            {
                "artifact": "escalation_quality_pack",
                "endpoint": "POST /escalations/quality-pack",
                "purpose": "Markdown and JSON handoff for actionability, evidence, governance, and noise-control review.",
            },
        ]

    def _run_transparency(self, run: RunRecord) -> dict[str, Any]:
        return {
            "node_history": run.state.get("node_history", []),
            "tool_call_count": len(run.state.get("tool_calls", [])),
            "failed_tool_call_count": sum(1 for item in run.state.get("tool_calls", []) if item.get("status") == "error"),
            "approval_id": run.state.get("approval_id"),
            "qa": run.state.get("qa", {}),
            "sla_risk": run.state.get("sla_risk", {}),
            "final_action": run.final_action,
        }

    def _escalation_evidence(self, run: RunRecord, ticket: Ticket) -> dict[str, Any]:
        return {
            "engineering_preview": run.state.get("drafts", {}).get("engineering_escalation", "")[:700],
            "customer_reply_preview": run.state.get("drafts", {}).get("customer_reply", "")[:300],
            "kb_citations": [
                {
                    "article_id": item.get("article_id"),
                    "title": item.get("title"),
                    "score": item.get("score"),
                }
                for item in run.state.get("kb_results", [])
            ],
            "ticket_priority": str(ticket.priority),
            "customer_tier": ticket.customer_tier,
            "classification": run.state.get("classification", {}),
            "sla_risk": run.state.get("sla_risk", {}),
        }

    def _required_revisions(
        self,
        dimensions: dict[str, Any],
        blockers: list[str],
        escalation_required: bool,
    ) -> list[dict[str, str]]:
        revisions = []
        for name, item in dimensions.items():
            for gap in item["gaps"]:
                revisions.append(
                    {
                        "dimension": name,
                        "owner": self._owner_for_dimension(name),
                        "revision": gap,
                    }
                )
        for blocker in blockers:
            revisions.append({"dimension": "quality_gate", "owner": "support_engineering_lead", "revision": blocker})
        if revisions:
            return revisions
        if not escalation_required:
            return [
                {
                    "dimension": "noise_control",
                    "owner": "support_engineering_lead",
                    "revision": "No Jira handoff required; keep customer reply in normal approval flow.",
                }
            ]
        return [
            {
                "dimension": "review_gate",
                "owner": "support_engineering_lead",
                "revision": "Approve, reject, or edit the engineering escalation in the human approval queue.",
            }
        ]

    def _owner_for_dimension(self, dimension: str) -> str:
        return {
            "actionability": "engineering_triage_lead",
            "reproduction_evidence": "support_evidence_owner",
            "customer_impact": "customer_success_owner",
            "routing_governance": "support_engineering_lead",
            "noise_control": "support_operations_owner",
        }.get(dimension, "support_engineering_lead")

    def _markdown(self, pack: dict[str, Any]) -> str:
        audit = pack["quality_audit"]
        dimensions = [
            f"- **{name}**: {item['score']} ({item['status']})"
            for name, item in audit["score_dimensions"].items()
        ]
        crew = [
            f"- **{item['role']}**: {item['score']} ({item['status']}) - {item['playbook']}"
            for item in audit["role_playbook_handoffs"]
        ]
        actions = [
            f"- **{item['dimension']}** ({item['owner']}): {item['revision']}"
            for item in pack["reviewer_actions"]
        ]
        scenarios = [
            (
                f"| {item['scenario_id']} | {item['domain']} | {item['escalation_required']} | "
                f"{item['overall_score']} | {item['gate_status']} |"
            )
            for item in audit["scenario_coverage"]["scenarios"]
        ]
        commands = [f"- `{command}`" for command in pack["local_proof_commands"]]
        limitations = [f"- {item}" for item in pack["limitations"]]
        return "\n".join(
            [
                f"# Engineering Escalation Quality Pack: {pack['pack_id']}",
                "",
                "## Review Gate",
                f"- Status: {audit['status']}",
                f"- Overall score: {audit['overall_score']}",
                f"- Escalation required: {audit['escalation_required']}",
                f"- Run: `{audit['run_id']}`",
                f"- Trace: `{audit['trace_id']}`",
                "",
                "## Score Dimensions",
                *dimensions,
                "",
                "## Role Crew Review",
                *crew,
                "",
                "## Reviewer Actions",
                *actions,
                "",
                "## Scenario Coverage",
                "| Scenario | Domain | Required | Overall Score | Gate Status |",
                "| --- | --- | --- | ---: | --- |",
                *scenarios,
                "",
                "## Local Proof Commands",
                *commands,
                "",
                "## Limitations",
                *limitations,
                "",
            ]
        )
