import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.models import AuditEvent
from app.services.audit import AuditService
from app.services.support_ops import SupportOperationsService


SUPPORT_OPS_SANDBOX_VERIFY_COMMANDS = [
    r".\.venv\Scripts\python.exe -m pytest -q",
    r".\.venv\Scripts\python.exe -m ruff check app tests dashboard scripts",
    r".\.venv\Scripts\python.exe -m app.evals.run_eval",
    r".\.venv\Scripts\python.exe scripts\dashboard_smoke.py",
    r".\.venv\Scripts\python.exe scripts\demo_run.py",
    (
        r'rg "ops/crew-sandbox|ops/crew-sandbox-pack|Support Ops Sandbox|'
        r'support_ops_sandbox|task sandbox|worker scale-out|tool transcripts" '
        r"app dashboard docs README.md tests scripts"
    ),
]

WORKERS = [
    {
        "worker_id": "support_lead_worker",
        "crew_id": "support_lead_crew",
        "role": "Support Lead",
        "local_tools": ["classification_reader", "kb_evidence_reader", "approval_state_reader"],
        "max_active_tasks": 2,
    },
    {
        "worker_id": "account_team_worker",
        "crew_id": "account_team_crew",
        "role": "Account Team",
        "local_tools": ["customer_context_reader", "draft_quality_checker"],
        "max_active_tasks": 2,
    },
    {
        "worker_id": "engineering_owner_worker",
        "crew_id": "engineering_owner_crew",
        "role": "Engineering Escalation Owner",
        "local_tools": ["engineering_draft_reader", "repro_step_checker"],
        "max_active_tasks": 2,
    },
    {
        "worker_id": "operations_commander_worker",
        "crew_id": "operations_commander_crew",
        "role": "Operations Commander",
        "local_tools": ["trace_reader", "review_gate_checker", "artifact_inventory_reader"],
        "max_active_tasks": 3,
    },
]


class SupportOpsSandboxService:
    """Runs deterministic local worker simulations over support-ops delegated tasks."""

    def __init__(
        self,
        support_ops: SupportOperationsService,
        audit: AuditService,
        sandbox_dir: Path,
    ):
        self.support_ops = support_ops
        self.audit = audit
        self.sandbox_dir = sandbox_dir

    async def sandbox_run(self, run_id: str | None = None, include_scenario_coverage: bool = True) -> dict[str, Any]:
        plan = await self.support_ops.crew_plan(run_id, include_scenario_coverage=include_scenario_coverage)
        task_runs = [self._execute_task(plan, task, index) for index, task in enumerate(plan["delegated_tasks"], 1)]
        gates = self._verification_gates(plan, task_runs)
        score = self._score(gates, task_runs)
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "title": "Support Ops Worker Sandbox Run",
            "mode": "local-deterministic-worker-sandbox",
            "local_mock_only": True,
            "source": plan["source"],
            "run_id": plan["run_id"],
            "ticket_id": plan["ticket_id"],
            "trace_id": plan["trace_id"],
            "process_mode": plan["selected_process_mode"],
            "sandbox_policy": self._sandbox_policy(plan),
            "worker_pool": WORKERS,
            "worker_scale_out": self._scale_out(plan, task_runs),
            "task_runs": task_runs,
            "verification_gates": gates,
            "issue_to_handoff_loop": self._issue_loop(plan),
            "benchmark_discipline": self._benchmark(score, task_runs, gates),
            "scenario_coverage": plan["scenario_coverage"],
            "run_transparency": plan["run_transparency"],
            "repo_radar_patterns": [
                "task sandbox",
                "run transparency",
                "task delegation",
                "worker scale-out",
                "review gates",
                "tool transcripts",
            ],
            "endpoint_list": [
                "GET /ops/crew-sandbox",
                "POST /ops/crew-sandbox-pack",
                "GET /ops/crew-plan",
                "GET /runs/{run_id}/trace",
            ],
            "local_commands": SUPPORT_OPS_SANDBOX_VERIFY_COMMANDS,
            "limitations": self._limitations(),
        }

    async def export_sandbox_pack(self, run_id: str | None = None) -> dict[str, Any]:
        sandbox = await self.sandbox_run(run_id)
        generated_at = datetime.now(timezone.utc)
        pack_id = f"support_ops_sandbox_{generated_at.strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:6]}"
        json_path = self.sandbox_dir / f"{pack_id}.json"
        markdown_path = self.sandbox_dir / f"{pack_id}.md"
        pack = {
            "pack_id": pack_id,
            "generated_at": generated_at.isoformat(),
            "title": "Support Ops Worker Sandbox Pack",
            "status": sandbox["benchmark_discipline"]["status"],
            "sandbox_score": sandbox["benchmark_discipline"]["score"],
            "sandbox_run": sandbox,
            "worker_assignment_board": self._worker_assignment_board(sandbox["task_runs"]),
            "tool_transcript_summary": self._tool_transcript_summary(sandbox["task_runs"]),
            "verification_summary": self._verification_summary(sandbox["verification_gates"]),
            "local_proof_commands": SUPPORT_OPS_SANDBOX_VERIFY_COMMANDS,
            "artifact_paths": {
                "support_ops_sandbox_markdown": str(markdown_path),
                "support_ops_sandbox_json": str(json_path),
            },
            "limitations": sandbox["limitations"],
        }
        markdown = self._markdown(pack)
        self.sandbox_dir.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(pack, indent=2, default=str), encoding="utf-8")
        markdown_path.write_text(markdown, encoding="utf-8")
        await self.audit.record(
            AuditEvent(
                actor="support-ops-sandbox",
                action="ops.crew_sandbox_pack_exported",
                resource_type="support_ops_sandbox_pack",
                resource_id=pack_id,
                trace_id=sandbox["trace_id"],
                metadata={"markdown_path": str(markdown_path), "json_path": str(json_path)},
            )
        )
        return {
            "pack_id": pack_id,
            "format": "markdown+json",
            "status": sandbox["benchmark_discipline"]["status"],
            "sandbox_score": sandbox["benchmark_discipline"]["score"],
            "json_path": str(json_path),
            "markdown_path": str(markdown_path),
            "pack": pack,
            "markdown": markdown,
        }

    def _execute_task(self, plan: dict[str, Any], task: dict[str, Any], index: int) -> dict[str, Any]:
        worker = self._worker_for_task(task)
        evidence_count = len(task["evidence_refs"])
        transcript = [
            self._transcript_event(index, "sandbox.start", "Created isolated local task context.", []),
            self._transcript_event(
                index,
                "tool.read_plan",
                "Read delegated task and handoff contract from the local crew plan.",
                ["GET /ops/crew-plan"],
            ),
            self._transcript_event(
                index,
                "tool.verify_evidence",
                "Checked linked local evidence references without dispatching external actions.",
                task["evidence_refs"],
            ),
            self._transcript_event(
                index,
                "review.gate",
                "Evaluated task readiness, approval boundary, and owner role handoff.",
                [plan["trace_id"], task["status"]],
            ),
        ]
        status = "passed" if task["status"] == "ready" and evidence_count else "needs_human_input"
        return {
            "task_run_id": f"sandbox_task_{index:02d}_{task['task_id']}",
            "task_id": task["task_id"],
            "worker_id": worker["worker_id"],
            "crew_id": task["crew_id"],
            "owner_role": task["owner_role"],
            "status": status,
            "sandbox_mode": "dry_run_no_side_effects",
            "allowed_tools": worker["local_tools"],
            "blocked_actions": ["send_customer_reply", "create_jira_issue", "post_slack_alert", "call_external_llm"],
            "budget": {
                "tool_call_budget": 5,
                "tool_calls_used": len(transcript) - 1,
                "token_budget": 800,
                "estimated_tokens_used": 120 + (evidence_count * 35),
            },
            "transcript": transcript,
            "handoff_output": {
                "artifact_type": task["artifact_type"],
                "ready_for_reviewer": status == "passed",
                "handoff_contract": task["handoff_contract"],
                "evidence_refs": task["evidence_refs"],
            },
        }

    def _worker_for_task(self, task: dict[str, Any]) -> dict[str, Any]:
        return next(worker for worker in WORKERS if worker["crew_id"] == task["crew_id"])

    def _transcript_event(
        self,
        index: int,
        event_type: str,
        summary: str,
        evidence_refs: list[str],
    ) -> dict[str, Any]:
        return {
            "step": index,
            "event_type": event_type,
            "summary": summary,
            "evidence_refs": [ref for ref in evidence_refs if ref],
            "external_call": False,
        }

    def _sandbox_policy(self, plan: dict[str, Any]) -> dict[str, Any]:
        mode = plan["selected_process_mode"]
        return {
            "policy_id": "local_support_ops_worker_sandbox",
            "process_mode": mode["mode_id"],
            "max_parallel_tasks": mode["max_parallel_tasks"],
            "max_tool_calls_per_task": 5,
            "max_tokens_per_task": 800,
            "external_network_allowed": False,
            "write_actions_allowed": False,
            "requires_human_approval_for_dispatch": True,
        }

    def _scale_out(self, plan: dict[str, Any], task_runs: list[dict[str, Any]]) -> dict[str, Any]:
        active_workers = sorted({run["worker_id"] for run in task_runs})
        mode = plan["selected_process_mode"]
        queued = max(0, len(task_runs) - mode["max_parallel_tasks"])
        return {
            "assigned_worker_count": len(active_workers),
            "assigned_workers": active_workers,
            "delegated_task_count": len(task_runs),
            "max_parallel_tasks": mode["max_parallel_tasks"],
            "queued_task_count": queued,
            "scale_decision": "within_local_capacity" if queued == 0 else "queue_for_human_prioritization",
        }

    def _verification_gates(
        self,
        plan: dict[str, Any],
        task_runs: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        return [
            self._gate(
                "sandbox_isolation_gate",
                "Operations Commander",
                True,
                "All simulated worker actions run in dry-run mode with external calls disabled.",
            ),
            self._gate(
                "budget_gate",
                "Operations Commander",
                all(
                    run["budget"]["tool_calls_used"] <= run["budget"]["tool_call_budget"]
                    and run["budget"]["estimated_tokens_used"] <= run["budget"]["token_budget"]
                    for run in task_runs
                ),
                "Every worker task must stay inside local tool-call and token budgets.",
            ),
            self._gate(
                "dispatch_boundary_gate",
                "Support Lead",
                plan["run_transparency"]["approval_status"] in {"pending", "approved", "unknown"},
                "Sandbox may prepare handoffs but cannot dispatch customer or engineering actions.",
            ),
            self._gate(
                "task_execution_gate",
                "Operations Commander",
                all(run["status"] == "passed" for run in task_runs),
                "Every delegated task must produce a reviewer-ready handoff output.",
            ),
            self._gate(
                "transcript_gate",
                "Engineering Escalation Owner",
                all(run["transcript"] and not any(item["external_call"] for item in run["transcript"]) for run in task_runs),
                "Every task run must retain a local transcript and prove no external provider call occurred.",
            ),
        ]

    def _gate(self, gate_id: str, owner_role: str, passed: bool, requirement: str) -> dict[str, str]:
        return {
            "gate_id": gate_id,
            "owner_role": owner_role,
            "status": "pass" if passed else "review",
            "requirement": requirement,
        }

    def _score(self, gates: list[dict[str, Any]], task_runs: list[dict[str, Any]]) -> int:
        passed_gates = len([gate for gate in gates if gate["status"] == "pass"])
        passed_tasks = len([run for run in task_runs if run["status"] == "passed"])
        gate_score = (passed_gates / max(len(gates), 1)) * 70
        task_score = (passed_tasks / max(len(task_runs), 1)) * 30
        return round(gate_score + task_score)

    def _issue_loop(self, plan: dict[str, Any]) -> list[dict[str, str]]:
        return [
            {"stage": "issue_intake", "evidence": plan["ticket_id"], "exit_criterion": "Ticket is persisted locally."},
            {"stage": "crew_plan", "evidence": plan["run_id"], "exit_criterion": "Process mode and delegated tasks exist."},
            {"stage": "sandbox_execute", "evidence": plan["trace_id"], "exit_criterion": "Workers produce local handoff outputs."},
            {"stage": "verify", "evidence": "verification_gates", "exit_criterion": "Budget, transcript, and dispatch gates pass."},
            {"stage": "human_review", "evidence": plan["run_transparency"]["approval_id"], "exit_criterion": "Approver reviews before dispatch."},
        ]

    def _benchmark(
        self,
        score: int,
        task_runs: list[dict[str, Any]],
        gates: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return {
            "score": score,
            "status": "pass" if score >= 90 else "review" if score >= 70 else "blocked",
            "task_pass_rate": round(len([run for run in task_runs if run["status"] == "passed"]) / max(len(task_runs), 1), 3),
            "gate_pass_rate": round(len([gate for gate in gates if gate["status"] == "pass"]) / max(len(gates), 1), 3),
            "measures": [
                "worker tasks stay inside deterministic local budgets",
                "tool transcripts prove no external calls",
                "handoff outputs are reviewer-ready before dispatch",
                "human approval remains the boundary for customer or engineering actions",
            ],
        }

    def _worker_assignment_board(self, task_runs: list[dict[str, Any]]) -> list[dict[str, str]]:
        return [
            {
                "task_run_id": run["task_run_id"],
                "task_id": run["task_id"],
                "worker_id": run["worker_id"],
                "owner_role": run["owner_role"],
                "status": run["status"],
            }
            for run in task_runs
        ]

    def _tool_transcript_summary(self, task_runs: list[dict[str, Any]]) -> dict[str, Any]:
        transcript_count = sum(len(run["transcript"]) for run in task_runs)
        return {
            "task_run_count": len(task_runs),
            "transcript_event_count": transcript_count,
            "external_call_count": sum(
                1 for run in task_runs for item in run["transcript"] if item["external_call"]
            ),
            "tools_used": sorted({tool for run in task_runs for tool in run["allowed_tools"]}),
        }

    def _verification_summary(self, gates: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "pass_count": len([gate for gate in gates if gate["status"] == "pass"]),
            "review_count": len([gate for gate in gates if gate["status"] != "pass"]),
            "review_gates": [gate for gate in gates if gate["status"] != "pass"],
        }

    def _limitations(self) -> list[str]:
        return [
            "Worker sandbox runs are deterministic local simulations over saved support workflow state.",
            "No Azure, OpenAI, Zendesk, Jira, Slack, GitHub, browser, shell, or network worker is invoked.",
            "Tool transcripts are synthetic local audit evidence, not a replacement for production worker runtime logs.",
            "Production use would need identity-scoped workers, real queue leases, sandbox isolation, and retention policy.",
        ]

    def _markdown(self, pack: dict[str, Any]) -> str:
        sandbox = pack["sandbox_run"]
        assignment_rows = [
            f"| `{row['task_id']}` | `{row['worker_id']}` | {row['owner_role']} | {row['status']} |"
            for row in pack["worker_assignment_board"]
        ]
        gate_rows = [
            f"| `{gate['gate_id']}` | {gate['owner_role']} | {gate['status']} | {gate['requirement']} |"
            for gate in sandbox["verification_gates"]
        ]
        transcript_rows = [
            (
                f"| `{run['task_id']}` | {len(run['transcript'])} | "
                f"{run['budget']['tool_calls_used']}/{run['budget']['tool_call_budget']} | "
                f"{run['budget']['estimated_tokens_used']}/{run['budget']['token_budget']} |"
            )
            for run in sandbox["task_runs"]
        ]
        command_rows = [f"- `{command}`" for command in pack["local_proof_commands"]]
        limitation_rows = [f"- {item}" for item in pack["limitations"]]
        return "\n".join(
            [
                f"# Support Ops Worker Sandbox Pack: {pack['pack_id']}",
                "",
                "## Summary",
                f"- Status: {pack['status']}",
                f"- Sandbox score: {pack['sandbox_score']}",
                f"- Run: `{sandbox['run_id']}`",
                f"- Trace: `{sandbox['trace_id']}`",
                f"- Process mode: `{sandbox['process_mode']['mode_id']}`",
                f"- Scale decision: `{sandbox['worker_scale_out']['scale_decision']}`",
                "",
                "## Worker Assignment Board",
                "| Task | Worker | Owner Role | Status |",
                "| --- | --- | --- | --- |",
                *assignment_rows,
                "",
                "## Verification Gates",
                "| Gate | Owner | Status | Requirement |",
                "| --- | --- | --- | --- |",
                *gate_rows,
                "",
                "## Tool Transcript Budgets",
                "| Task | Transcript Events | Tool Calls | Tokens |",
                "| --- | --- | --- | --- |",
                *transcript_rows,
                "",
                "## Local Proof Commands",
                *command_rows,
                "",
                "## Limitations",
                *limitation_rows,
                "",
            ]
        )
