import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.core.storage import JsonStateStore
from app.models import AuditEvent, RunRecord, Ticket
from app.services.audit import AuditService
from app.services.communication_quality import CustomerCommunicationQualityService
from app.services.escalation_quality import EscalationQualityService
from app.services.finance_impact import FinanceImpactService
from app.services.support_ops import SupportOperationsService
from app.services.tickets import TicketService
from app.services.workflow import AgentWorkflowService


ESCALATION_DECISION_COMMANDS = [
    r".\.venv\Scripts\python.exe -m pytest -q",
    r".\.venv\Scripts\python.exe -m ruff check app tests dashboard scripts",
    r".\.venv\Scripts\python.exe -m app.evals.run_eval",
    r".\.venv\Scripts\python.exe scripts\dashboard_smoke.py",
    r".\.venv\Scripts\python.exe scripts\demo_run.py",
    (
        r'rg "escalations/decision-board|escalations/decision-pack|Escalation Decision Board|'
        r'escalation_decision_packs|decision gate" app dashboard docs README.md tests scripts'
    ),
]


DECISION_CREWS = [
    {
        "role": "Incident Commander",
        "decision_scope": "go_no_go",
        "playbook": "Own the final escalation posture, review gate failures, and approval boundary.",
    },
    {
        "role": "Support Lead",
        "decision_scope": "customer_safe_next_action",
        "playbook": "Confirm the customer reply is grounded, empathetic, and still paused for approval.",
    },
    {
        "role": "Engineering Owner",
        "decision_scope": "internal_dispatch_quality",
        "playbook": "Validate severity, reproduction evidence, suspected area, and engineering actionability.",
    },
    {
        "role": "Finance Partner",
        "decision_scope": "financial_exposure",
        "playbook": "Review support cost, SLA penalty exposure, engineering effort, and ARR at risk.",
    },
    {
        "role": "Account Owner",
        "decision_scope": "customer_commitment_risk",
        "playbook": "Block credits, timelines, and renewal commitments unless an accountable human approves them.",
    },
]


class EscalationDecisionService:
    """Builds an approval-ready escalation decision board from local evidence."""

    def __init__(
        self,
        store: JsonStateStore,
        tickets: TicketService,
        workflow: AgentWorkflowService,
        finance_impact: FinanceImpactService,
        escalation_quality: EscalationQualityService,
        communication_quality: CustomerCommunicationQualityService,
        support_ops: SupportOperationsService,
        audit: AuditService,
        decision_pack_dir: Path,
    ):
        self.store = store
        self.tickets = tickets
        self.workflow = workflow
        self.finance_impact = finance_impact
        self.escalation_quality = escalation_quality
        self.communication_quality = communication_quality
        self.support_ops = support_ops
        self.audit = audit
        self.decision_pack_dir = decision_pack_dir

    async def decision_board(self, run_id: str | None = None) -> dict[str, Any]:
        impact = await self.finance_impact.impact_summary(run_id)
        resolved_run_id = impact["run_id"]
        run = await self.workflow.get_run(resolved_run_id)
        ticket = await self._ticket_for_run(run)
        escalation_quality = await self.escalation_quality.quality_audit(resolved_run_id)
        communication_quality = await self.communication_quality.quality_audit(resolved_run_id)
        ops_plan = await self.support_ops.crew_plan(resolved_run_id, include_scenario_coverage=False)
        signal_rollup = self._signal_rollup(impact, escalation_quality, communication_quality, ops_plan, run)
        review_gates = self._review_gates(signal_rollup, run)
        role_signoffs = self._role_signoffs(signal_rollup, review_gates)
        decision = self._decision_summary(signal_rollup, review_gates, role_signoffs)
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "title": "Escalation Decision Board",
            "mode": "local-deterministic-escalation-decision-board",
            "local_mock_only": True,
            "run_id": run.run_id,
            "ticket_id": ticket.ticket_id,
            "trace_id": run.trace_id,
            "customer": ticket.customer or ticket.account or ticket.customer_email,
            "subject": ticket.subject,
            "decision_status": decision["status"],
            "decision_score": decision["score"],
            "decision_summary": decision,
            "signal_rollup": signal_rollup,
            "role_crews": DECISION_CREWS,
            "role_signoffs": role_signoffs,
            "review_gates": review_gates,
            "owner_action_plan": self._owner_action_plan(review_gates, signal_rollup),
            "artifact_handoffs": self._artifact_handoffs(run, impact),
            "run_transparency": self._run_transparency(run, ops_plan),
            "repo_radar_patterns": [
                "role crews",
                "task delegation",
                "process modes",
                "agent roles",
                "artifact handoffs",
                "review gates",
                "run transparency",
                "requirements to implementation",
            ],
            "endpoint_list": [
                "GET /escalations/decision-board",
                "POST /escalations/decision-pack",
                "POST /finance/impact-summary",
                "GET /escalations/quality-audit",
                "GET /communications/quality-audit",
                "GET /ops/crew-plan",
            ],
            "local_commands": ESCALATION_DECISION_COMMANDS,
            "limitations": self._limitations(),
        }

    async def export_decision_pack(self, run_id: str | None = None) -> dict[str, Any]:
        board = await self.decision_board(run_id)
        generated_at = datetime.now(timezone.utc)
        pack_id = f"escalation_decision_pack_{generated_at.strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:6]}"
        json_path = self.decision_pack_dir / f"{pack_id}.json"
        markdown_path = self.decision_pack_dir / f"{pack_id}.md"
        pack = {
            "pack_id": pack_id,
            "generated_at": generated_at.isoformat(),
            "title": "Escalation Decision Pack",
            "decision_board": board,
            "executive_decision_table": self._executive_decision_table(board),
            "handoff_acceptance_criteria": self._acceptance_criteria(),
            "artifact_paths": {
                "escalation_decision_markdown": str(markdown_path),
                "escalation_decision_json": str(json_path),
            },
            "local_proof_commands": ESCALATION_DECISION_COMMANDS,
            "limitations": board["limitations"],
        }
        markdown = self._markdown(pack)
        self.decision_pack_dir.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(pack, indent=2, default=str), encoding="utf-8")
        markdown_path.write_text(markdown, encoding="utf-8")
        await self.audit.record(
            AuditEvent(
                actor="escalation-decision-board",
                action="escalations.decision_pack_exported",
                resource_type="escalation_decision_pack",
                resource_id=pack_id,
                trace_id=board["trace_id"],
                metadata={"markdown_path": str(markdown_path), "json_path": str(json_path)},
            )
        )
        return {
            "pack_id": pack_id,
            "format": "markdown+json",
            "status": board["decision_status"],
            "decision_score": board["decision_score"],
            "json_path": str(json_path),
            "markdown_path": str(markdown_path),
            "pack": pack,
            "markdown": markdown,
        }

    async def _ticket_for_run(self, run: RunRecord) -> Ticket:
        ticket = await self.tickets.get(run.ticket_id)
        if ticket is None:
            raise KeyError(run.ticket_id)
        return ticket

    def _signal_rollup(
        self,
        impact: dict[str, Any],
        escalation_quality: dict[str, Any],
        communication_quality: dict[str, Any],
        ops_plan: dict[str, Any],
        run: RunRecord,
    ) -> dict[str, Any]:
        finance = impact["finance_rollup"]
        escalation_gate = escalation_quality["quality_gate"]
        communication_gate = communication_quality["quality_gate"]
        return {
            "finance_exposure_usd": finance["estimated_financial_exposure_usd"],
            "arr_at_risk_usd": finance["arr_at_risk_usd"],
            "finance_status": finance["readiness_status"],
            "sla_risk": run.state.get("sla_risk", {}).get("level", "unknown"),
            "approval_status": run.state.get("approval_status", "unknown"),
            "final_action": run.final_action,
            "escalation_quality_score": escalation_quality["overall_score"],
            "escalation_dispatch_ready": escalation_gate.get("approved_for_internal_dispatch", False),
            "communication_quality_score": communication_quality["overall_score"],
            "customer_dispatch_ready": communication_gate.get("approved_for_dispatch", False),
            "ops_status": ops_plan["readiness_status"],
            "ops_score": ops_plan["operations_score"],
            "process_mode": ops_plan["selected_process_mode"]["mode_id"],
            "delegated_task_count": len(ops_plan["delegated_tasks"]),
            "failed_ops_gate_count": len([item for item in ops_plan["review_gates"] if item["status"] == "fail"]),
        }

    def _review_gates(self, signals: dict[str, Any], run: RunRecord) -> list[dict[str, Any]]:
        return [
            {
                "gate_id": "human_approval_boundary",
                "owner": "Incident Commander",
                "status": "pass" if signals["approval_status"] in {"pending", "approved"} else "fail",
                "evidence": f"approval_status={signals['approval_status']}",
                "required_action": "Keep customer and engineering dispatch paused until an accountable reviewer decides.",
            },
            {
                "gate_id": "finance_exposure_review",
                "owner": "Finance Partner",
                "status": "pass" if signals["finance_exposure_usd"] < 500000 else "review",
                "evidence": f"exposure=${signals['finance_exposure_usd']:,.2f}; arr=${signals['arr_at_risk_usd']:,.2f}",
                "required_action": "Attach Finance Impact Pack and confirm credits or concessions stay out of AI drafts.",
            },
            {
                "gate_id": "engineering_escalation_quality",
                "owner": "Engineering Owner",
                "status": "pass" if signals["escalation_dispatch_ready"] or run.final_action != "engineering_escalation" else "review",
                "evidence": f"score={signals['escalation_quality_score']}; final_action={run.final_action}",
                "required_action": "Resolve actionability or reproduction gaps before creating internal engineering work.",
            },
            {
                "gate_id": "customer_communication_quality",
                "owner": "Support Lead",
                "status": "pass" if signals["customer_dispatch_ready"] else "review",
                "evidence": f"score={signals['communication_quality_score']}",
                "required_action": "Ensure customer-facing language is grounded, specific, and approved.",
            },
            {
                "gate_id": "ops_delegation_readiness",
                "owner": "Incident Commander",
                "status": "pass" if signals["failed_ops_gate_count"] == 0 else "review",
                "evidence": f"mode={signals['process_mode']}; tasks={signals['delegated_task_count']}",
                "required_action": "Assign any failed support-ops gate to a named role before escalation execution.",
            },
        ]

    def _role_signoffs(
        self,
        signals: dict[str, Any],
        gates: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        gates_by_owner: dict[str, list[dict[str, Any]]] = {}
        for gate in gates:
            gates_by_owner.setdefault(gate["owner"], []).append(gate)
        rows = []
        for crew in DECISION_CREWS:
            owner_gates = gates_by_owner.get(crew["role"], [])
            blocked = [gate for gate in owner_gates if gate["status"] == "fail"]
            review = [gate for gate in owner_gates if gate["status"] == "review"]
            status = "blocked" if blocked else "needs_review" if review else "ready"
            rows.append(
                {
                    "role": crew["role"],
                    "decision_scope": crew["decision_scope"],
                    "status": status,
                    "assigned_gate_count": len(owner_gates),
                    "next_action": self._signoff_next_action(status, crew["role"], signals),
                }
            )
        return rows

    def _decision_summary(
        self,
        signals: dict[str, Any],
        gates: list[dict[str, Any]],
        signoffs: list[dict[str, Any]],
    ) -> dict[str, Any]:
        failed = len([gate for gate in gates if gate["status"] == "fail"])
        review = len([gate for gate in gates if gate["status"] == "review"])
        score = max(0, 100 - failed * 25 - review * 8)
        if failed:
            status = "blocked"
            recommendation = "Do not dispatch. Resolve failed decision gates first."
        elif review or signals["finance_status"] == "finance_review_required":
            status = "executive_review_required"
            recommendation = "Route to executive and incident-owner review with finance and quality evidence attached."
        else:
            status = "ready_for_human_approval"
            recommendation = "Ready for accountable human approval; keep external actions paused until approved."
        return {
            "status": status,
            "score": score,
            "recommendation": recommendation,
            "failed_gate_count": failed,
            "review_gate_count": review,
            "ready_signoff_count": len([item for item in signoffs if item["status"] == "ready"]),
            "risk_statement": (
                f"{signals['process_mode']} run with SLA={signals['sla_risk']}, "
                f"exposure=${signals['finance_exposure_usd']:,.2f}, "
                f"approval={signals['approval_status']}."
            ),
        }

    def _owner_action_plan(self, gates: list[dict[str, Any]], signals: dict[str, Any]) -> list[dict[str, str]]:
        actions = [
            {
                "owner": gate["owner"],
                "priority": "high" if gate["status"] == "fail" else "medium",
                "action": gate["required_action"],
                "evidence": gate["evidence"],
            }
            for gate in gates
            if gate["status"] != "pass"
        ]
        if not actions:
            actions.append(
                {
                    "owner": "Incident Commander",
                    "priority": "low",
                    "action": "Present the decision pack for final human approval before any external or Jira-facing dispatch.",
                    "evidence": f"decision_mode={signals['process_mode']}",
                }
            )
        return actions

    def _artifact_handoffs(self, run: RunRecord, impact: dict[str, Any]) -> list[dict[str, str]]:
        return [
            {
                "artifact": "finance_impact_summary",
                "producer": "POST /finance/impact-summary",
                "consumer": "Finance Partner",
                "evidence": impact["finance_rollup"]["readiness_status"],
            },
            {
                "artifact": "engineering_escalation_quality",
                "producer": "GET /escalations/quality-audit",
                "consumer": "Engineering Owner",
                "evidence": run.final_action or "pending",
            },
            {
                "artifact": "customer_communication_quality",
                "producer": "GET /communications/quality-audit",
                "consumer": "Support Lead",
                "evidence": run.state.get("approval_status", "unknown"),
            },
            {
                "artifact": "support_ops_crew_plan",
                "producer": "GET /ops/crew-plan",
                "consumer": "Incident Commander",
                "evidence": run.trace_id,
            },
            {
                "artifact": "decision_pack",
                "producer": "POST /escalations/decision-pack",
                "consumer": "Executive reviewer",
                "evidence": "Markdown and JSON local artifact",
            },
        ]

    def _run_transparency(self, run: RunRecord, ops_plan: dict[str, Any]) -> dict[str, Any]:
        return {
            "run_id": run.run_id,
            "trace_id": run.trace_id,
            "status": str(run.status),
            "final_action": run.final_action,
            "node_history": run.state.get("node_history", []),
            "tool_call_count": len(run.state.get("tool_calls", [])),
            "checkpoint_count": len(run.state.get("checkpoints", [])),
            "delegated_tasks": len(ops_plan["delegated_tasks"]),
            "selected_process_mode": ops_plan["selected_process_mode"]["mode_id"],
        }

    def _executive_decision_table(self, board: dict[str, Any]) -> list[dict[str, Any]]:
        signals = board["signal_rollup"]
        return [
            {
                "decision": "Approve escalation execution",
                "current_status": board["decision_status"],
                "evidence": board["decision_summary"]["risk_statement"],
                "human_owner": "Incident Commander",
            },
            {
                "decision": "Review financial exposure",
                "current_status": signals["finance_status"],
                "evidence": f"${signals['finance_exposure_usd']:,.2f} exposure; ${signals['arr_at_risk_usd']:,.2f} ARR at risk",
                "human_owner": "Finance Partner",
            },
            {
                "decision": "Dispatch engineering handoff",
                "current_status": "ready" if signals["escalation_dispatch_ready"] else "needs_review",
                "evidence": f"quality score={signals['escalation_quality_score']}",
                "human_owner": "Engineering Owner",
            },
            {
                "decision": "Send customer update",
                "current_status": "ready" if signals["customer_dispatch_ready"] else "needs_review",
                "evidence": f"quality score={signals['communication_quality_score']}",
                "human_owner": "Support Lead",
            },
        ]

    def _acceptance_criteria(self) -> list[str]:
        return [
            "Every non-pass review gate has a named human owner and next action.",
            "Finance, engineering, support, and account signoffs are visible before dispatch.",
            "Customer-facing and engineering-facing actions remain paused until human approval.",
            "The pack links run ID, trace ID, endpoint evidence, and local proof commands.",
        ]

    def _signoff_next_action(self, status: str, role: str, signals: dict[str, Any]) -> str:
        if status == "ready":
            return "Confirm approval posture in the decision pack."
        if role == "Finance Partner":
            return f"Validate exposure assumptions for ${signals['finance_exposure_usd']:,.2f} estimated impact."
        if role == "Engineering Owner":
            return "Close escalation quality gaps before Jira or on-call handoff."
        if role == "Support Lead":
            return "Close customer communication quality gaps before external update."
        return "Resolve assigned review gates and record the accountable approver."

    def _limitations(self) -> list[str]:
        return [
            "Uses deterministic local heuristics and sample customer metadata, not contract, billing, CRM, or BI systems.",
            "Exports local Markdown/JSON only; it does not send customer updates, create Jira issues, or page on-call.",
            "No Azure, OpenAI, Zendesk, Jira, Slack, GitHub, finance, CRM, or external services are called.",
        ]

    def _markdown(self, pack: dict[str, Any]) -> str:
        board = pack["decision_board"]
        gates = [
            f"| {item['gate_id']} | {item['owner']} | {item['status']} | {item['evidence']} |"
            for item in board["review_gates"]
        ]
        signoffs = [
            f"| {item['role']} | {item['decision_scope']} | {item['status']} | {item['next_action']} |"
            for item in board["role_signoffs"]
        ]
        decisions = [
            f"| {item['decision']} | {item['current_status']} | {item['human_owner']} | {item['evidence']} |"
            for item in pack["executive_decision_table"]
        ]
        actions = [
            f"| {item['owner']} | {item['priority']} | {item['action']} | {item['evidence']} |"
            for item in board["owner_action_plan"]
        ]
        return "\n".join(
            [
                "# Escalation Decision Pack",
                "",
                f"- Pack ID: `{pack['pack_id']}`",
                f"- Generated at: `{pack['generated_at']}`",
                f"- Run ID: `{board['run_id']}`",
                f"- Trace ID: `{board['trace_id']}`",
                f"- Decision status: **{board['decision_status']}**",
                f"- Decision score: **{board['decision_score']}**",
                f"- Recommendation: {board['decision_summary']['recommendation']}",
                "",
                "## Executive Decision Table",
                "| Decision | Status | Owner | Evidence |",
                "| --- | --- | --- | --- |",
                *decisions,
                "",
                "## Review Gates",
                "| Gate | Owner | Status | Evidence |",
                "| --- | --- | --- | --- |",
                *gates,
                "",
                "## Role Signoffs",
                "| Role | Scope | Status | Next action |",
                "| --- | --- | --- | --- |",
                *signoffs,
                "",
                "## Owner Action Plan",
                "| Owner | Priority | Action | Evidence |",
                "| --- | --- | --- | --- |",
                *actions,
                "",
                "## Artifact Handoffs",
                *[
                    f"- **{item['artifact']}** from `{item['producer']}` to {item['consumer']}: {item['evidence']}"
                    for item in board["artifact_handoffs"]
                ],
                "",
                "## Local Proof Commands",
                *[f"- `{command}`" for command in pack["local_proof_commands"]],
                "",
                "## Limitations",
                *[f"- {item}" for item in pack["limitations"]],
                "",
            ]
        )
