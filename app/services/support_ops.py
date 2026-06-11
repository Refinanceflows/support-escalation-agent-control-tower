import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.core.storage import JsonStateStore
from app.models import AuditEvent, RunRecord, Ticket, TicketCreate
from app.services.audit import AuditService
from app.services.playbooks import PlaybookService
from app.services.tickets import TicketService
from app.services.workflow import AgentWorkflowService


SUPPORT_OPS_VERIFY_COMMANDS = [
    r".\.venv\Scripts\python.exe -m pytest -q",
    r".\.venv\Scripts\python.exe -m ruff check app tests dashboard scripts",
    r".\.venv\Scripts\python.exe -m app.evals.run_eval",
    r".\.venv\Scripts\python.exe scripts\dashboard_smoke.py",
    r".\.venv\Scripts\python.exe scripts\demo_run.py",
    (
        r'rg "ops/crew-plan|ops/crew-pack|Support Ops Crews|support_ops_packs|'
        r'role crews|task delegation|process modes" app dashboard docs README.md tests scripts'
    ),
]


ROLE_CREWS = [
    {
        "crew_id": "support_lead_crew",
        "role": "Support Lead",
        "mission": "Own ticket triage, customer-safe next action, and SLA-risk prioritization.",
        "delegation_scope": ["intake_review", "sla_decision", "approval_packet"],
        "guardrail": "Cannot send customer-visible updates without approval.",
    },
    {
        "crew_id": "account_team_crew",
        "role": "Account Team",
        "mission": "Translate customer impact into account context and executive-ready updates.",
        "delegation_scope": ["customer_impact", "account_risk", "communication_review"],
        "guardrail": "Cannot promise credits, timelines, or contractual concessions.",
    },
    {
        "crew_id": "engineering_owner_crew",
        "role": "Engineering Escalation Owner",
        "mission": "Turn support evidence into a reproducible engineering handoff.",
        "delegation_scope": ["reproduction_steps", "suspected_area", "severity_review"],
        "guardrail": "Cannot create Jira or page on-call until human approval is present.",
    },
    {
        "crew_id": "operations_commander_crew",
        "role": "Operations Commander",
        "mission": "Coordinate process mode, review gates, run transparency, and artifact handoffs.",
        "delegation_scope": ["process_mode", "review_gates", "artifact_handoff"],
        "guardrail": "Must keep every delegated task linked to a trace, run, or local artifact.",
    },
]


PROCESS_MODES = {
    "standard_triage": {
        "description": "Normal support triage with support lead approval before dispatch.",
        "max_parallel_tasks": 3,
        "requires_engineering_owner": False,
    },
    "sla_war_room": {
        "description": "Time-sensitive SLA risk mode with parallel support, account, and engineering work.",
        "max_parallel_tasks": 6,
        "requires_engineering_owner": True,
    },
    "engineering_escalation": {
        "description": "Engineering-first mode for reproducible defects or service impact.",
        "max_parallel_tasks": 5,
        "requires_engineering_owner": True,
    },
    "customer_comms_review": {
        "description": "Customer-language review mode for sensitive, ambiguous, or low-confidence replies.",
        "max_parallel_tasks": 4,
        "requires_engineering_owner": False,
    },
}


class SupportOperationsService:
    """Builds local role-crew plans for support escalation operations."""

    def __init__(
        self,
        store: JsonStateStore,
        tickets: TicketService,
        workflow: AgentWorkflowService,
        playbooks: PlaybookService,
        audit: AuditService,
        scenario_fixture: Path,
        support_ops_dir: Path,
    ):
        self.store = store
        self.tickets = tickets
        self.workflow = workflow
        self.playbooks = playbooks
        self.audit = audit
        self.scenario_fixture = scenario_fixture
        self.support_ops_dir = support_ops_dir

    async def crew_plan(self, run_id: str | None = None, include_scenario_coverage: bool = True) -> dict[str, Any]:
        run, ticket, source = await self._resolve_run(run_id)
        process_mode = self._select_process_mode(run, ticket)
        delegated_tasks = self._delegated_tasks(run, ticket, process_mode)
        gates = self._review_gates(run, delegated_tasks)
        artifact_handoffs = self._artifact_handoffs(run, ticket)
        readiness = self._readiness(gates, delegated_tasks, process_mode)
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "title": "Autonomous Support Operations Crew Plan",
            "mode": "local-deterministic-support-ops-crews",
            "local_mock_only": True,
            "source": source,
            "run_id": run.run_id,
            "ticket_id": ticket.ticket_id,
            "trace_id": run.trace_id,
            "customer": ticket.customer or ticket.account or ticket.customer_email,
            "subject": ticket.subject,
            "readiness_status": readiness["status"],
            "operations_score": readiness["score"],
            "selected_process_mode": process_mode,
            "role_crews": ROLE_CREWS,
            "delegated_tasks": delegated_tasks,
            "review_gates": gates,
            "artifact_handoffs": artifact_handoffs,
            "run_transparency": self._run_transparency(run),
            "handoff_sequence": self._handoff_sequence(process_mode, delegated_tasks),
            "scenario_coverage": await self._scenario_coverage() if include_scenario_coverage else self._skipped_coverage(),
            "repo_radar_patterns": [
                "role crews",
                "task delegation",
                "process modes",
                "agent roles",
                "artifact handoffs",
                "review gates",
                "run transparency",
            ],
            "endpoint_list": [
                "GET /ops/crew-plan",
                "POST /ops/crew-pack",
                "GET /runs/{run_id}/trace",
                "POST /ops/operator-readiness-pack",
                "POST /handoff/customer-comms-pack",
            ],
            "local_commands": SUPPORT_OPS_VERIFY_COMMANDS,
            "limitations": self._limitations(),
        }

    async def export_crew_pack(self, run_id: str | None = None) -> dict[str, Any]:
        plan = await self.crew_plan(run_id)
        generated_at = datetime.now(timezone.utc)
        pack_id = f"support_ops_pack_{generated_at.strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:6]}"
        json_path = self.support_ops_dir / f"{pack_id}.json"
        markdown_path = self.support_ops_dir / f"{pack_id}.md"
        pack = {
            "pack_id": pack_id,
            "generated_at": generated_at.isoformat(),
            "title": "Autonomous Support Operations Pack",
            "crew_plan": plan,
            "process_mode": plan["selected_process_mode"],
            "delegation_board": self._delegation_board(plan["delegated_tasks"]),
            "review_gate_summary": self._review_gate_summary(plan["review_gates"]),
            "artifact_handoff_packet": plan["artifact_handoffs"],
            "local_proof_commands": SUPPORT_OPS_VERIFY_COMMANDS,
            "artifact_paths": {
                "support_ops_pack_markdown": str(markdown_path),
                "support_ops_pack_json": str(json_path),
            },
            "limitations": plan["limitations"],
        }
        markdown = self._markdown(pack)
        self.support_ops_dir.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(pack, indent=2, default=str), encoding="utf-8")
        markdown_path.write_text(markdown, encoding="utf-8")
        await self.audit.record(
            AuditEvent(
                actor="support-ops-crews",
                action="ops.crew_pack_exported",
                resource_type="support_ops_pack",
                resource_id=pack_id,
                trace_id=plan["trace_id"],
                metadata={"markdown_path": str(markdown_path), "json_path": str(json_path)},
            )
        )
        return {
            "pack_id": pack_id,
            "format": "markdown+json",
            "status": plan["readiness_status"],
            "operations_score": plan["operations_score"],
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
            "scn_low_confidence_ambiguity",
            "scn_billing_duplicate_invoice",
        ]
        by_id = {item["scenario_id"]: item for item in scenarios}
        return [by_id[item] for item in preferred if item in by_id]

    async def _scenario_coverage(self) -> dict[str, Any]:
        rows = []
        for scenario in self._selected_scenarios():
            ticket = await self._ingest_or_get_scenario_ticket(scenario)
            run = await self.workflow.analyze_ticket(ticket.ticket_id)
            process_mode = self._select_process_mode(run, ticket)
            tasks = self._delegated_tasks(run, ticket, process_mode)
            rows.append(
                {
                    "scenario_id": scenario["scenario_id"],
                    "domain": scenario["domain"],
                    "run_id": run.run_id,
                    "process_mode": process_mode["mode_id"],
                    "delegated_task_count": len(tasks),
                    "crew_count": len({task["crew_id"] for task in tasks}),
                    "requires_engineering_owner": process_mode["requires_engineering_owner"],
                }
            )
        modes = Counter(row["process_mode"] for row in rows)
        domains = Counter(row["domain"] for row in rows)
        return {
            "coverage_status": "pass" if len(modes) >= 2 and len(rows) >= 4 else "gap",
            "scenario_count": len(rows),
            "process_modes": dict(modes),
            "domains": dict(domains),
            "scenarios": rows,
        }

    def _skipped_coverage(self) -> dict[str, Any]:
        return {
            "coverage_status": "skipped_for_parent_drill",
            "scenario_count": 0,
            "process_modes": {},
            "domains": {},
            "scenarios": [],
        }

    def _select_process_mode(self, run: RunRecord, ticket: Ticket) -> dict[str, Any]:
        classification = run.state.get("classification", {})
        sla = run.state.get("sla_risk", {})
        qa = run.state.get("qa", {})
        category = str(classification.get("category", "")).lower()
        if sla.get("level") == "high" or ticket.priority in {"urgent", "high"}:
            mode_id = "sla_war_room"
        elif category in {"api_integrations", "authentication", "bug", "api", "webhook", "outage"} or sla.get(
            "should_escalate"
        ):
            mode_id = "engineering_escalation"
        elif qa.get("confidence", 1.0) < 0.65:
            mode_id = "customer_comms_review"
        else:
            mode_id = "standard_triage"
        return {"mode_id": mode_id, **PROCESS_MODES[mode_id]}

    def _delegated_tasks(
        self,
        run: RunRecord,
        ticket: Ticket,
        process_mode: dict[str, Any],
    ) -> list[dict[str, Any]]:
        state = run.state
        playbooks = state.get("playbook_recommendations", [])
        top_playbook = playbooks[0] if playbooks else {}
        tasks = [
            self._task(
                "support_triage_summary",
                "support_lead_crew",
                "Summarize issue category, urgency, owner, and approval requirement.",
                "classification",
                bool(state.get("classification") and state.get("sla_risk")),
                [run.trace_id, ticket.ticket_id],
            ),
            self._task(
                "customer_impact_mapping",
                "account_team_crew",
                "Map customer tier, business impact, communication sensitivity, and next update path.",
                "customer_context",
                bool(ticket.customer_tier and state.get("drafts", {}).get("customer_reply")),
                [ticket.customer_tier, run.run_id],
            ),
            self._task(
                "approval_gate_packet",
                "operations_commander_crew",
                "Prepare approval, guardrail, trace, and outbox state for human review.",
                "review_gate",
                bool(state.get("approval_id")),
                [state.get("approval_id", "missing_approval"), state.get("approval_status", "unknown")],
            ),
            self._task(
                "kb_evidence_packet",
                "support_lead_crew",
                "Attach cited KB snippets and any retrieval gaps to the reviewer packet.",
                "knowledge_retrieval",
                bool(state.get("kb_results")),
                [item.get("article_id", "") for item in state.get("kb_results", [])[:3]],
            ),
        ]
        if process_mode["requires_engineering_owner"] or state.get("drafts", {}).get("engineering_escalation"):
            tasks.append(
                self._task(
                    "engineering_escalation_handoff",
                    "engineering_owner_crew",
                    "Prepare severity, reproduction steps, suspected area, and customer impact.",
                    "engineering_handoff",
                    bool(state.get("drafts", {}).get("engineering_escalation")),
                    [top_playbook.get("id", "no_playbook"), run.trace_id],
                )
            )
        if playbooks:
            tasks.append(
                self._task(
                    "playbook_owner_assignment",
                    "operations_commander_crew",
                    "Delegate selected playbook checklist steps to named operational owner roles.",
                    "playbook_handoff",
                    bool(top_playbook.get("owner_roles")),
                    top_playbook.get("owner_roles", []),
                )
            )
        return tasks[: process_mode["max_parallel_tasks"]]

    def _task(
        self,
        task_id: str,
        crew_id: str,
        objective: str,
        artifact_type: str,
        ready: bool,
        evidence_refs: list[str],
    ) -> dict[str, Any]:
        crew = next(item for item in ROLE_CREWS if item["crew_id"] == crew_id)
        return {
            "task_id": task_id,
            "crew_id": crew_id,
            "owner_role": crew["role"],
            "objective": objective,
            "artifact_type": artifact_type,
            "status": "ready" if ready else "needs_input",
            "evidence_refs": [ref for ref in evidence_refs if ref],
            "handoff_contract": {
                "input": "local workflow state, trace events, ticket fields, and generated drafts",
                "output": f"{artifact_type} reviewer-ready handoff",
                "guardrail": crew["guardrail"],
            },
        }

    def _review_gates(
        self,
        run: RunRecord,
        delegated_tasks: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        state = run.state
        return [
            self._gate(
                "classification_sla_gate",
                "Support Lead",
                bool(state.get("classification") and state.get("sla_risk")),
                "Classification and SLA risk must exist before crew delegation.",
            ),
            self._gate(
                "knowledge_grounding_gate",
                "Support Lead",
                bool(state.get("kb_results")),
                "Customer or engineering drafts need cited local KB evidence.",
            ),
            self._gate(
                "human_approval_gate",
                "Operations Commander",
                bool(state.get("approval_id")),
                "External or engineering-facing actions must pause for human approval.",
            ),
            self._gate(
                "delegation_completeness_gate",
                "Operations Commander",
                all(task["status"] == "ready" for task in delegated_tasks),
                "Every delegated task needs evidence references and a ready handoff.",
            ),
        ]

    def _gate(self, gate_id: str, owner_role: str, passed: bool, requirement: str) -> dict[str, str]:
        return {
            "gate_id": gate_id,
            "owner_role": owner_role,
            "status": "pass" if passed else "review",
            "requirement": requirement,
        }

    def _artifact_handoffs(self, run: RunRecord, ticket: Ticket) -> list[dict[str, str]]:
        playbooks = run.state.get("playbook_recommendations", [])
        selected_playbook = playbooks[0] if playbooks else {}
        return [
            {
                "artifact": "trace_timeline",
                "producer": f"GET /runs/{run.run_id}/trace",
                "owner_role": "Operations Commander",
                "evidence": run.trace_id,
            },
            {
                "artifact": "operator_readiness_pack",
                "producer": "POST /ops/operator-readiness-pack",
                "owner_role": "Support Lead",
                "evidence": run.run_id,
            },
            {
                "artifact": "customer_comms_pack",
                "producer": "POST /handoff/customer-comms-pack",
                "owner_role": "Account Team",
                "evidence": ticket.ticket_id,
            },
            {
                "artifact": "remediation_checklist",
                "producer": f"POST /runs/{run.run_id}/remediation-checklist",
                "owner_role": "Engineering Escalation Owner",
                "evidence": selected_playbook.get("id", "no_playbook"),
            },
        ]

    def _run_transparency(self, run: RunRecord) -> dict[str, Any]:
        state = run.state
        metrics = run.metrics or state.get("metrics", {})
        return {
            "run_id": run.run_id,
            "trace_id": run.trace_id,
            "status": str(run.status),
            "node_history": state.get("node_history", []),
            "tool_call_count": len(state.get("tool_calls", [])),
            "approval_id": state.get("approval_id", ""),
            "approval_status": state.get("approval_status", "unknown"),
            "tokens": int(metrics.get("tokens", 0) or 0),
            "estimated_cost_usd": float(metrics.get("cost_usd", 0.0) or 0.0),
        }

    def _handoff_sequence(
        self,
        process_mode: dict[str, Any],
        delegated_tasks: list[dict[str, Any]],
    ) -> list[dict[str, str]]:
        return [
            {
                "step": str(index),
                "process_mode": process_mode["mode_id"],
                "crew_id": task["crew_id"],
                "task_id": task["task_id"],
                "exit_criterion": "Task status is ready and linked evidence is present.",
            }
            for index, task in enumerate(delegated_tasks, start=1)
        ]

    def _readiness(
        self,
        gates: list[dict[str, str]],
        delegated_tasks: list[dict[str, Any]],
        process_mode: dict[str, Any],
    ) -> dict[str, Any]:
        passed_gates = len([gate for gate in gates if gate["status"] == "pass"])
        ready_tasks = len([task for task in delegated_tasks if task["status"] == "ready"])
        gate_score = (passed_gates / max(len(gates), 1)) * 60
        task_score = (ready_tasks / max(len(delegated_tasks), 1)) * 30
        mode_score = 10 if process_mode["mode_id"] in PROCESS_MODES else 0
        score = round(gate_score + task_score + mode_score)
        status = "ready" if score >= 85 else "review" if score >= 65 else "blocked"
        return {"score": score, "status": status}

    def _delegation_board(self, delegated_tasks: list[dict[str, Any]]) -> list[dict[str, str]]:
        return [
            {
                "task_id": task["task_id"],
                "owner_role": task["owner_role"],
                "status": task["status"],
                "artifact_type": task["artifact_type"],
            }
            for task in delegated_tasks
        ]

    def _review_gate_summary(self, gates: list[dict[str, str]]) -> dict[str, Any]:
        return {
            "pass_count": len([gate for gate in gates if gate["status"] == "pass"]),
            "review_count": len([gate for gate in gates if gate["status"] != "pass"]),
            "blocked_gates": [gate for gate in gates if gate["status"] != "pass"],
        }

    def _limitations(self) -> list[str]:
        return [
            "Crew planning is deterministic local orchestration over saved run state, not live staffing.",
            "No Azure, OpenAI, Zendesk, Jira, Slack, GitHub, or external provider is called.",
            "Delegated tasks prepare reviewer handoffs only; they do not dispatch customer or engineering actions.",
            "Production use would need identity-aware owner assignment, calendars, paging policy, and audit retention.",
        ]

    def _markdown(self, pack: dict[str, Any]) -> str:
        plan = pack["crew_plan"]
        mode = pack["process_mode"]
        crew_rows = [
            f"| {crew['role']} | `{crew['crew_id']}` | {crew['mission']} | {crew['guardrail']} |"
            for crew in plan["role_crews"]
        ]
        task_rows = [
            (
                f"| `{task['task_id']}` | {task['owner_role']} | {task['artifact_type']} | "
                f"{task['status']} | {', '.join(task['evidence_refs']) or 'missing'} |"
            )
            for task in plan["delegated_tasks"]
        ]
        gate_rows = [
            f"| `{gate['gate_id']}` | {gate['owner_role']} | {gate['status']} | {gate['requirement']} |"
            for gate in plan["review_gates"]
        ]
        artifact_rows = [
            (
                f"| {item['artifact']} | `{item['producer']}` | {item['owner_role']} | "
                f"{item['evidence']} |"
            )
            for item in plan["artifact_handoffs"]
        ]
        command_rows = [f"- `{command}`" for command in pack["local_proof_commands"]]
        limitation_rows = [f"- {item}" for item in pack["limitations"]]
        return "\n".join(
            [
                f"# Autonomous Support Operations Pack: {pack['pack_id']}",
                "",
                "## Summary",
                f"- Status: {plan['readiness_status']}",
                f"- Operations score: {plan['operations_score']}",
                f"- Run: `{plan['run_id']}`",
                f"- Trace: `{plan['trace_id']}`",
                f"- Process mode: `{mode['mode_id']}` - {mode['description']}",
                "",
                "## Role Crews",
                "| Role | Crew ID | Mission | Guardrail |",
                "| --- | --- | --- | --- |",
                *crew_rows,
                "",
                "## Delegated Tasks",
                "| Task | Owner | Artifact Type | Status | Evidence |",
                "| --- | --- | --- | --- | --- |",
                *task_rows,
                "",
                "## Review Gates",
                "| Gate | Owner | Status | Requirement |",
                "| --- | --- | --- | --- |",
                *gate_rows,
                "",
                "## Artifact Handoffs",
                "| Artifact | Producer | Owner | Evidence |",
                "| --- | --- | --- | --- |",
                *artifact_rows,
                "",
                "## Run Transparency",
                f"- Nodes: {', '.join(plan['run_transparency']['node_history'])}",
                f"- Tool calls: {plan['run_transparency']['tool_call_count']}",
                f"- Approval: {plan['run_transparency']['approval_status']}",
                f"- Tokens: {plan['run_transparency']['tokens']}",
                f"- Estimated cost: {plan['run_transparency']['estimated_cost_usd']}",
                "",
                "## Local Proof Commands",
                *command_rows,
                "",
                "## Limitations",
                *limitation_rows,
                "",
            ]
        )
