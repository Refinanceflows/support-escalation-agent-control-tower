import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.models import AuditEvent, Ticket, TicketCreate
from app.services.audit import AuditService
from app.services.support_ops import ROLE_CREWS, SupportOperationsService
from app.services.support_ops_sandbox import SupportOpsSandboxService
from app.services.tickets import TicketService
from app.services.workflow import AgentWorkflowService


SUPPORT_OPS_READINESS_COMMANDS = [
    r".\.venv\Scripts\python.exe -m pytest -q",
    r".\.venv\Scripts\python.exe -m ruff check app tests dashboard scripts",
    r".\.venv\Scripts\python.exe -m app.evals.run_eval",
    r".\.venv\Scripts\python.exe scripts\dashboard_smoke.py",
    r".\.venv\Scripts\python.exe scripts\demo_run.py",
    (
        r'rg "ops/crew-readiness-drill|ops/crew-readiness-pack|Support Ops Readiness|'
        r'support_ops_readiness|process-mode coverage|crew readiness" '
        r"app dashboard docs README.md tests scripts"
    ),
]

READINESS_SCENARIOS = [
    "scn_enterprise_login_outage",
    "scn_webhook_api_regression",
    "scn_billing_duplicate_invoice",
    "scn_enterprise_onboarding_sso",
    "scn_low_confidence_ambiguity",
]


class SupportOpsReadinessService:
    """Evaluates support-ops crews across deterministic local scenarios."""

    def __init__(
        self,
        tickets: TicketService,
        workflow: AgentWorkflowService,
        support_ops: SupportOperationsService,
        sandbox: SupportOpsSandboxService,
        audit: AuditService,
        scenario_fixture: Path,
        readiness_dir: Path,
    ):
        self.tickets = tickets
        self.workflow = workflow
        self.support_ops = support_ops
        self.sandbox = sandbox
        self.audit = audit
        self.scenario_fixture = scenario_fixture
        self.readiness_dir = readiness_dir

    async def readiness_drill(self) -> dict[str, Any]:
        rows = []
        for scenario in self._selected_scenarios():
            ticket = await self._ingest_or_get_scenario_ticket(scenario)
            run = await self.workflow.analyze_ticket(ticket.ticket_id)
            plan = await self.support_ops.crew_plan(run.run_id, include_scenario_coverage=False)
            sandbox = await self.sandbox.sandbox_run(run.run_id, include_scenario_coverage=False)
            rows.append(self._scenario_row(scenario, ticket, run, plan, sandbox))

        gates = self._readiness_gates(rows)
        score = self._readiness_score(rows, gates)
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "title": "Support Ops Crew Readiness Drill",
            "mode": "local-deterministic-crew-readiness-drill",
            "local_mock_only": True,
            "readiness_status": self._status(score, gates),
            "readiness_score": score,
            "summary": self._summary(rows),
            "scenario_results": rows,
            "readiness_gates": gates,
            "role_coverage_matrix": self._role_coverage_matrix(rows),
            "process_mode_coverage": self._process_mode_coverage(rows),
            "sandbox_transcript_audit": self._sandbox_transcript_audit(rows),
            "repo_radar_patterns": [
                "role crews",
                "task delegation",
                "process modes",
                "review gates",
                "task sandbox",
                "run transparency",
            ],
            "endpoint_list": [
                "GET /ops/crew-readiness-drill",
                "POST /ops/crew-readiness-pack",
                "GET /ops/crew-plan",
                "GET /ops/crew-sandbox",
            ],
            "local_commands": SUPPORT_OPS_READINESS_COMMANDS,
            "limitations": self._limitations(),
        }

    async def export_readiness_pack(self) -> dict[str, Any]:
        drill = await self.readiness_drill()
        generated_at = datetime.now(timezone.utc)
        pack_id = f"support_ops_readiness_{generated_at.strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:6]}"
        json_path = self.readiness_dir / f"{pack_id}.json"
        markdown_path = self.readiness_dir / f"{pack_id}.md"
        pack = {
            "pack_id": pack_id,
            "generated_at": generated_at.isoformat(),
            "title": "Support Ops Crew Readiness Pack",
            "status": drill["readiness_status"],
            "readiness_score": drill["readiness_score"],
            "readiness_drill": drill,
            "process_mode_coverage": drill["process_mode_coverage"],
            "role_coverage_matrix": drill["role_coverage_matrix"],
            "readiness_gate_summary": self._gate_summary(drill["readiness_gates"]),
            "local_proof_commands": SUPPORT_OPS_READINESS_COMMANDS,
            "artifact_paths": {
                "support_ops_readiness_markdown": str(markdown_path),
                "support_ops_readiness_json": str(json_path),
            },
            "limitations": drill["limitations"],
        }
        markdown = self._markdown(pack)
        self.readiness_dir.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(pack, indent=2, default=str), encoding="utf-8")
        markdown_path.write_text(markdown, encoding="utf-8")
        await self.audit.record(
            AuditEvent(
                actor="support-ops-readiness",
                action="ops.crew_readiness_pack_exported",
                resource_type="support_ops_readiness_pack",
                resource_id=pack_id,
                metadata={
                    "status": drill["readiness_status"],
                    "markdown_path": str(markdown_path),
                    "json_path": str(json_path),
                },
            )
        )
        return {
            "pack_id": pack_id,
            "format": "markdown+json",
            "status": drill["readiness_status"],
            "readiness_score": drill["readiness_score"],
            "json_path": str(json_path),
            "markdown_path": str(markdown_path),
            "pack": pack,
            "markdown": markdown,
        }

    def _scenario_row(
        self,
        scenario: dict[str, Any],
        ticket: Ticket,
        run: Any,
        plan: dict[str, Any],
        sandbox: dict[str, Any],
    ) -> dict[str, Any]:
        expected_mode = self._expected_process_mode(scenario, run)
        actual_mode = plan["selected_process_mode"]["mode_id"]
        delegated_roles = sorted({task["owner_role"] for task in plan["delegated_tasks"]})
        required_roles = self._required_roles(plan)
        missing_roles = [role for role in required_roles if role not in delegated_roles]
        failed_gates = [gate for gate in plan["review_gates"] if gate["status"] != "pass"]
        external_call_count = sum(
            1
            for task_run in sandbox["task_runs"]
            for event in task_run["transcript"]
            if event["external_call"]
        )
        return {
            "scenario_id": scenario["scenario_id"],
            "domain": scenario["domain"],
            "ticket_id": ticket.ticket_id,
            "run_id": run.run_id,
            "trace_id": run.trace_id,
            "expected_process_mode": expected_mode,
            "actual_process_mode": actual_mode,
            "process_mode_match": expected_mode == actual_mode,
            "operations_score": plan["operations_score"],
            "sandbox_score": sandbox["benchmark_discipline"]["score"],
            "sandbox_status": sandbox["benchmark_discipline"]["status"],
            "delegated_task_count": len(plan["delegated_tasks"]),
            "delegated_roles": delegated_roles,
            "required_roles": required_roles,
            "missing_roles": missing_roles,
            "review_gate_pass_count": len(plan["review_gates"]) - len(failed_gates),
            "review_gate_count": len(plan["review_gates"]),
            "failed_review_gates": [gate["gate_id"] for gate in failed_gates],
            "external_call_count": external_call_count,
            "transcript_event_count": sum(len(task_run["transcript"]) for task_run in sandbox["task_runs"]),
            "ready_for_autonomous_dry_run": (
                expected_mode == actual_mode
                and not missing_roles
                and sandbox["benchmark_discipline"]["status"] == "pass"
                and external_call_count == 0
            ),
        }

    def _selected_scenarios(self) -> list[dict[str, Any]]:
        scenarios = json.loads(self.scenario_fixture.read_text(encoding="utf-8"))
        by_id = {item["scenario_id"]: item for item in scenarios}
        return [by_id[item] for item in READINESS_SCENARIOS if item in by_id]

    async def _ingest_or_get_scenario_ticket(self, scenario: dict[str, Any]) -> Ticket:
        payload = TicketCreate(**scenario["ticket"])
        if payload.external_id:
            existing = await self.tickets.get_by_external_id(payload.external_id)
            if existing:
                return existing
        return await self.tickets.ingest(payload)

    def _expected_process_mode(self, scenario: dict[str, Any], run: Any) -> str:
        expected = scenario.get("expected", {})
        ticket = scenario.get("ticket", {})
        category = str(run.state.get("classification", {}).get("category", "")).lower()
        if expected.get("sla_level") == "high" or ticket.get("priority") in {"urgent", "high"}:
            return "sla_war_room"
        if category in {"bug", "api", "webhook", "outage"} or expected.get("should_escalate"):
            return "engineering_escalation"
        if expected.get("low_confidence_review"):
            return "customer_comms_review"
        return "standard_triage"

    def _required_roles(self, plan: dict[str, Any]) -> list[str]:
        roles = ["Support Lead", "Account Team", "Operations Commander"]
        if plan["selected_process_mode"]["requires_engineering_owner"]:
            roles.append("Engineering Escalation Owner")
        return roles

    def _readiness_gates(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            self._gate(
                "scenario_coverage_gate",
                len(rows) >= 5,
                f"{len(rows)} scenario(s) exercised across support operations crews.",
            ),
            self._gate(
                "process_mode_coverage_gate",
                len({row["actual_process_mode"] for row in rows}) >= 3,
                "At least three process modes should be covered by the readiness drill.",
            ),
            self._gate(
                "process_mode_alignment_gate",
                all(row["process_mode_match"] for row in rows),
                "Expected and actual process-mode routing must match deterministic scenario intent.",
            ),
            self._gate(
                "role_coverage_gate",
                all(not row["missing_roles"] for row in rows),
                "Every scenario must delegate required support, account, operations, and engineering roles.",
            ),
            self._gate(
                "sandbox_guardrail_gate",
                all(row["sandbox_status"] == "pass" and row["external_call_count"] == 0 for row in rows),
                "Every sandbox dry run must pass with zero external calls.",
            ),
            self._gate(
                "review_gate_health_gate",
                all(row["review_gate_pass_count"] >= 3 for row in rows),
                "Each crew plan should pass core classification, grounding, and approval gates.",
            ),
        ]

    def _gate(self, gate_id: str, passed: bool, detail: str) -> dict[str, str]:
        return {
            "gate_id": gate_id,
            "status": "pass" if passed else "review",
            "detail": detail,
        }

    def _readiness_score(self, rows: list[dict[str, Any]], gates: list[dict[str, Any]]) -> int:
        if not rows:
            return 0
        gate_score = (len([gate for gate in gates if gate["status"] == "pass"]) / len(gates)) * 45
        mode_score = (
            len([row for row in rows if row["process_mode_match"]]) / len(rows)
        ) * 20
        role_score = (len([row for row in rows if not row["missing_roles"]]) / len(rows)) * 20
        sandbox_score = (
            len(
                [
                    row
                    for row in rows
                    if row["sandbox_status"] == "pass" and row["external_call_count"] == 0
                ]
            )
            / len(rows)
        ) * 15
        return round(gate_score + mode_score + role_score + sandbox_score)

    def _status(self, score: int, gates: list[dict[str, Any]]) -> str:
        failed = [gate for gate in gates if gate["status"] != "pass"]
        if score >= 90 and not failed:
            return "ready"
        if score >= 75:
            return "ready_with_review_items"
        return "needs_remediation"

    def _summary(self, rows: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "scenario_count": len(rows),
            "ready_scenario_count": len([row for row in rows if row["ready_for_autonomous_dry_run"]]),
            "process_mode_count": len({row["actual_process_mode"] for row in rows}),
            "delegated_task_count": sum(row["delegated_task_count"] for row in rows),
            "external_call_count": sum(row["external_call_count"] for row in rows),
            "average_operations_score": round(
                sum(row["operations_score"] for row in rows) / max(len(rows), 1),
                2,
            ),
            "average_sandbox_score": round(
                sum(row["sandbox_score"] for row in rows) / max(len(rows), 1),
                2,
            ),
        }

    def _role_coverage_matrix(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        all_roles = [crew["role"] for crew in ROLE_CREWS]
        return [
            {
                "scenario_id": row["scenario_id"],
                **{role: role in row["delegated_roles"] for role in all_roles},
                "missing_roles": ", ".join(row["missing_roles"]),
            }
            for row in rows
        ]

    def _process_mode_coverage(self, rows: list[dict[str, Any]]) -> dict[str, Any]:
        actual = Counter(row["actual_process_mode"] for row in rows)
        expected = Counter(row["expected_process_mode"] for row in rows)
        return {
            "coverage_status": "pass" if len(actual) >= 3 else "review",
            "actual_modes": dict(actual),
            "expected_modes": dict(expected),
            "mismatches": [
                row
                for row in rows
                if row["expected_process_mode"] != row["actual_process_mode"]
            ],
        }

    def _sandbox_transcript_audit(self, rows: list[dict[str, Any]]) -> dict[str, Any]:
        transcript_events = sum(row["transcript_event_count"] for row in rows)
        external_calls = sum(row["external_call_count"] for row in rows)
        return {
            "status": "pass" if external_calls == 0 and transcript_events >= len(rows) * 12 else "review",
            "transcript_event_count": transcript_events,
            "external_call_count": external_calls,
            "average_transcript_events_per_scenario": round(transcript_events / max(len(rows), 1), 2),
        }

    def _gate_summary(self, gates: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "pass_count": len([gate for gate in gates if gate["status"] == "pass"]),
            "review_count": len([gate for gate in gates if gate["status"] != "pass"]),
            "review_gates": [gate for gate in gates if gate["status"] != "pass"],
        }

    def _limitations(self) -> list[str]:
        return [
            "The readiness drill is deterministic over local scenario fixtures and saved run state.",
            "The drill reuses local mock workflow, crew planning, and worker sandbox services only.",
            "No Azure, OpenAI, Zendesk, Jira, Slack, GitHub, shell worker, browser, or network provider is invoked.",
            "Production readiness would need live roster integration, incident calendars, paging policy, and real audit retention.",
        ]

    def _markdown(self, pack: dict[str, Any]) -> str:
        drill = pack["readiness_drill"]
        scenario_rows = [
            (
                f"| `{row['scenario_id']}` | {row['domain']} | `{row['actual_process_mode']}` | "
                f"{row['process_mode_match']} | {row['sandbox_status']} | {row['external_call_count']} |"
            )
            for row in drill["scenario_results"]
        ]
        gate_rows = [
            f"| `{gate['gate_id']}` | {gate['status']} | {gate['detail']} |"
            for gate in drill["readiness_gates"]
        ]
        role_rows = [
            (
                f"| `{row['scenario_id']}` | {row['Support Lead']} | {row['Account Team']} | "
                f"{row['Engineering Escalation Owner']} | {row['Operations Commander']} | "
                f"{row['missing_roles'] or 'none'} |"
            )
            for row in drill["role_coverage_matrix"]
        ]
        command_rows = [f"- `{command}`" for command in pack["local_proof_commands"]]
        limitation_rows = [f"- {item}" for item in pack["limitations"]]
        return "\n".join(
            [
                f"# Support Ops Crew Readiness Pack: {pack['pack_id']}",
                "",
                "## Summary",
                f"- Status: {pack['status']}",
                f"- Readiness score: {pack['readiness_score']}",
                f"- Scenarios: {drill['summary']['scenario_count']}",
                f"- Process modes: {drill['summary']['process_mode_count']}",
                f"- External calls: {drill['summary']['external_call_count']}",
                "",
                "## Scenario Results",
                "| Scenario | Domain | Process Mode | Mode Match | Sandbox | External Calls |",
                "| --- | --- | --- | --- | --- | --- |",
                *scenario_rows,
                "",
                "## Readiness Gates",
                "| Gate | Status | Detail |",
                "| --- | --- | --- |",
                *gate_rows,
                "",
                "## Role Coverage Matrix",
                "| Scenario | Support Lead | Account Team | Engineering Owner | Operations Commander | Missing Roles |",
                "| --- | --- | --- | --- | --- | --- |",
                *role_rows,
                "",
                "## Process-Mode Coverage",
                f"- Status: {drill['process_mode_coverage']['coverage_status']}",
                f"- Actual modes: {drill['process_mode_coverage']['actual_modes']}",
                f"- Expected modes: {drill['process_mode_coverage']['expected_modes']}",
                "",
                "## Sandbox Transcript Audit",
                f"- Status: {drill['sandbox_transcript_audit']['status']}",
                f"- Transcript events: {drill['sandbox_transcript_audit']['transcript_event_count']}",
                f"- External calls: {drill['sandbox_transcript_audit']['external_call_count']}",
                "",
                "## Local Proof Commands",
                *command_rows,
                "",
                "## Limitations",
                *limitation_rows,
                "",
            ]
        )
