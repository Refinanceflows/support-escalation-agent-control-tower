import json
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.models import AuditEvent
from app.services.audit import AuditService
from app.services.postmortem_rca import PostmortemRcaService


POSTMORTEM_REVIEW_VERIFY_COMMANDS = [
    r".\.venv\Scripts\python.exe -m pytest -q",
    r".\.venv\Scripts\python.exe -m ruff check app tests dashboard scripts",
    r".\.venv\Scripts\python.exe -m app.evals.run_eval",
    r".\.venv\Scripts\python.exe scripts\dashboard_smoke.py",
    r".\.venv\Scripts\python.exe scripts\demo_run.py",
    (
        r'rg "incidents/postmortem-review-board|incidents/postmortem-review-pack|'
        r'Postmortem Review Board|postmortem_review_packs|closure gate" '
        r"app dashboard docs README.md tests scripts"
    ),
]

ROLE_PLAYBOOKS = {
    "Customer Success": {
        "role": "Customer Success",
        "crew": "account_followup_crew",
        "playbook": "Confirm acknowledgement, sentiment, next update cadence, and account-risk note.",
        "approval_boundary": "Cannot send customer-visible RCA language without support lead approval.",
    },
    "Support Ops": {
        "role": "Support Ops",
        "crew": "evidence_quality_crew",
        "playbook": "Verify trace, approval, outbox, audit, and artifact evidence before closure.",
        "approval_boundary": "Cannot close a postmortem while evidence links are missing.",
    },
    "Engineering Manager": {
        "role": "Engineering Manager",
        "crew": "engineering_fix_crew",
        "playbook": "Name mitigation owner, ETA, rollback state, and recurrence guard.",
        "approval_boundary": "Cannot declare engineering mitigation complete without linked trace or ticket evidence.",
    },
    "Incident Commander": {
        "role": "Incident Commander",
        "crew": "incident_process_crew",
        "playbook": "Update the incident runbook and schedule the follow-up review gate.",
        "approval_boundary": "Cannot mark playbook updates complete without reviewer signoff.",
    },
    "Platform Support": {
        "role": "Platform Support",
        "crew": "adapter_reliability_crew",
        "playbook": "Repair adapter health checks, fallback paths, and retry-exhaustion prompts.",
        "approval_boundary": "Cannot re-enable automation after failed tools without a passing local verification run.",
    },
    "Knowledge Owner": {
        "role": "Knowledge Owner",
        "crew": "knowledge_quality_crew",
        "playbook": "Patch missing KB fixtures, citations, and support-facing recovery guidance.",
        "approval_boundary": "Cannot publish customer wording without grounded KB citations.",
    },
    "Privacy Reviewer": {
        "role": "Privacy Reviewer",
        "crew": "privacy_control_crew",
        "playbook": "Review export/deletion language, retention proof, and customer-safe privacy wording.",
        "approval_boundary": "Cannot approve privacy language without human review.",
    },
    "Billing Operations": {
        "role": "Billing Operations",
        "crew": "billing_resolution_crew",
        "playbook": "Assign credit/refund owner, renewal escalation, and finance-impact note.",
        "approval_boundary": "Cannot promise credits or contractual relief without finance approval.",
    },
    "Support Lead": {
        "role": "Support Lead",
        "crew": "human_review_crew",
        "playbook": "Resolve ambiguity, capture human review notes, and approve customer-facing next steps.",
        "approval_boundary": "Owns final approval for customer-visible support actions.",
    },
}


class PostmortemReviewService:
    """Turns RCA corrective actions into owner-ready postmortem closure governance."""

    def __init__(
        self,
        postmortem_rca: PostmortemRcaService,
        audit: AuditService,
        review_dir: Path,
    ):
        self.postmortem_rca = postmortem_rca
        self.audit = audit
        self.review_dir = review_dir

    async def review_board(self, run_id: str | None = None) -> dict[str, Any]:
        summary = await self.postmortem_rca.postmortem_summary(run_id)
        action_board = self._action_board(summary)
        role_signoffs = self._role_signoffs(action_board)
        closure_gates = self._closure_gates(summary, action_board, role_signoffs)
        readiness = self._readiness(action_board, closure_gates)
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "title": "Postmortem Review Board",
            "mode": "local-deterministic-postmortem-review-board",
            "local_mock_only": True,
            "run_id": summary["run_id"],
            "ticket_id": summary["ticket_id"],
            "trace_id": summary["trace_id"],
            "severity": summary["severity"],
            "root_cause_category": summary["root_cause_category"],
            "process_mode": self._process_mode(summary),
            "review_status": readiness["status"],
            "closure_score": readiness["score"],
            "action_board": action_board,
            "role_playbooks": self._role_playbook_rows(action_board),
            "role_signoffs": role_signoffs,
            "closure_gates": closure_gates,
            "artifact_handoffs": self._artifact_handoffs(summary),
            "run_transparency": self._run_transparency(summary),
            "review_cadence": self._review_cadence(summary),
            "repo_radar_patterns": [
                "role crews",
                "task delegation",
                "role playbooks",
                "review gates",
                "artifact handoffs",
                "run transparency",
            ],
            "endpoint_list": [
                "GET /incidents/postmortem-review-board",
                "POST /incidents/postmortem-review-pack",
                "GET /incidents/postmortem-summary",
                "POST /incidents/rca-pack",
                "GET /runs/{run_id}/trace",
            ],
            "local_proof_commands": POSTMORTEM_REVIEW_VERIFY_COMMANDS,
            "limitations": self._limitations(),
        }

    async def export_review_pack(self, run_id: str | None = None) -> dict[str, Any]:
        board = await self.review_board(run_id)
        generated_at = datetime.now(timezone.utc)
        pack_id = f"postmortem_review_pack_{generated_at.strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:6]}"
        json_path = self.review_dir / f"{pack_id}.json"
        markdown_path = self.review_dir / f"{pack_id}.md"
        pack = {
            "pack_id": pack_id,
            "generated_at": generated_at.isoformat(),
            "title": "Postmortem Corrective Action Review Pack",
            "review_board": board,
            "closure_owner_summary": self._closure_owner_summary(board["action_board"]),
            "review_gate_summary": self._review_gate_summary(board["closure_gates"]),
            "artifact_handoff_packet": board["artifact_handoffs"],
            "run_transparency": board["run_transparency"],
            "proof_commands": POSTMORTEM_REVIEW_VERIFY_COMMANDS,
            "artifact_paths": {
                "postmortem_review_markdown": str(markdown_path),
                "postmortem_review_json": str(json_path),
            },
            "limitations": board["limitations"],
        }
        markdown = self._markdown(pack)
        self.review_dir.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(pack, indent=2, default=str), encoding="utf-8")
        markdown_path.write_text(markdown, encoding="utf-8")
        await self.audit.record(
            AuditEvent(
                actor="postmortem-review-board",
                action="incident.postmortem_review_pack_exported",
                resource_type="postmortem_review_pack",
                resource_id=pack_id,
                trace_id=board["trace_id"],
                metadata={"markdown_path": str(markdown_path), "json_path": str(json_path)},
            )
        )
        return {
            "pack_id": pack_id,
            "format": "markdown+json",
            "status": board["review_status"],
            "closure_score": board["closure_score"],
            "json_path": str(json_path),
            "markdown_path": str(markdown_path),
            "pack": pack,
            "markdown": markdown,
        }

    def _action_board(self, summary: dict[str, Any]) -> list[dict[str, Any]]:
        today = datetime.now(timezone.utc).date()
        rows = []
        for action in summary["corrective_actions"]:
            due_at = date.fromisoformat(action["due_at"])
            days_until_due = (due_at - today).days
            rows.append(
                {
                    "action_id": action["action_id"],
                    "owner_role": action["owner"],
                    "delegated_crew": ROLE_PLAYBOOKS.get(action["owner"], ROLE_PLAYBOOKS["Support Ops"])["crew"],
                    "closure_lane": self._closure_lane(action["action_id"], action["owner"]),
                    "status": action["status"],
                    "priority": self._priority(summary, days_until_due, action["status"]),
                    "due_at": action["due_at"],
                    "days_until_due": days_until_due,
                    "evidence": action["evidence"],
                    "review_gate": self._review_gate_for_action(action),
                    "required_artifact": self._required_artifact(action),
                    "delegated_task": self._delegated_task(action),
                }
            )
        return rows

    def _closure_lane(self, action_id: str, owner: str) -> str:
        if "customer" in action_id or owner == "Customer Success":
            return "customer_followup"
        if "trace" in action_id or owner == "Support Ops":
            return "evidence_quality"
        if owner in {"Engineering Manager", "Platform Support", "Knowledge Owner"}:
            return "engineering_prevention"
        if owner in {"Privacy Reviewer", "Billing Operations"}:
            return "specialist_control"
        return "process_review"

    def _priority(self, summary: dict[str, Any], days_until_due: int, status: str) -> str:
        if status == "completed":
            return "closed"
        if summary["recurrence_risk"]["level"] == "high" or days_until_due <= 1:
            return "p0"
        if summary["severity"] in {"sev1", "sev2"} or days_until_due <= 3:
            return "p1"
        return "p2"

    def _review_gate_for_action(self, action: dict[str, Any]) -> dict[str, str]:
        playbook = ROLE_PLAYBOOKS.get(action["owner"], ROLE_PLAYBOOKS["Support Ops"])
        return {
            "gate_id": f"{action['action_id']}_closure_gate",
            "owner_role": action["owner"],
            "status": "pass" if action["status"] == "completed" else "review",
            "requirement": playbook["approval_boundary"],
        }

    def _required_artifact(self, action: dict[str, Any]) -> str:
        if action["owner"] == "Customer Success":
            return "POST /handoff/customer-comms-pack"
        if action["owner"] == "Support Ops":
            return "GET /runs/{run_id}/trace"
        if action["owner"] in {"Engineering Manager", "Incident Commander", "Platform Support"}:
            return "POST /runs/{run_id}/remediation-checklist"
        if action["owner"] == "Knowledge Owner":
            return "POST /knowledge/refresh-plan"
        if action["owner"] == "Privacy Reviewer":
            return "POST /compliance/data-residency-pack"
        if action["owner"] == "Billing Operations":
            return "POST /finance/impact-pack"
        return "POST /incidents/rca-pack"

    def _delegated_task(self, action: dict[str, Any]) -> dict[str, str]:
        playbook = ROLE_PLAYBOOKS.get(action["owner"], ROLE_PLAYBOOKS["Support Ops"])
        return {
            "task_id": f"review_{action['action_id']}",
            "crew": playbook["crew"],
            "objective": action["action"],
            "handoff_contract": "owner action, evidence reference, required artifact, due date, and closure gate",
        }

    def _role_signoffs(self, action_board: list[dict[str, Any]]) -> list[dict[str, Any]]:
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for action in action_board:
            grouped[action["owner_role"]].append(action)
        rows = []
        for owner, actions in sorted(grouped.items()):
            open_actions = [action for action in actions if action["status"] != "completed"]
            highest_priority = self._highest_priority([action["priority"] for action in actions])
            playbook = ROLE_PLAYBOOKS.get(owner, ROLE_PLAYBOOKS["Support Ops"])
            rows.append(
                {
                    "owner_role": owner,
                    "crew": playbook["crew"],
                    "required_signoff": owner in {"Support Ops", "Customer Success"} or bool(open_actions),
                    "status": "signed_off" if not open_actions else "pending",
                    "open_action_count": len(open_actions),
                    "highest_priority": highest_priority,
                    "playbook": playbook["playbook"],
                }
            )
        return rows

    def _closure_gates(
        self,
        summary: dict[str, Any],
        action_board: list[dict[str, Any]],
        role_signoffs: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        return [
            self._gate(
                "owner_assignment_gate",
                "Support Ops",
                all(action["owner_role"] for action in action_board),
                "Every corrective action must have a named owner role.",
            ),
            self._gate(
                "customer_followup_gate",
                "Customer Success",
                summary["customer_follow_up_state"]["customer_update_sent"]
                or summary["customer_follow_up_state"]["status"] == "pending_approval",
                "Customer follow-up must be sent or waiting at an approval gate.",
            ),
            self._gate(
                "evidence_linkage_gate",
                "Support Ops",
                all(action["evidence"] for action in action_board)
                and summary["trace_links"]["event_count"] > 0,
                "Every action needs local evidence plus trace events.",
            ),
            self._gate(
                "role_signoff_gate",
                "Operations Commander",
                all(signoff["status"] == "signed_off" for signoff in role_signoffs),
                "All owner crews must sign off or keep the board in review.",
            ),
            self._gate(
                "recurrence_guard_gate",
                "Incident Commander",
                summary["recurrence_risk"]["level"] != "high",
                "High recurrence risk requires daily review cadence before closure.",
            ),
        ]

    def _gate(self, gate_id: str, owner_role: str, passed: bool, requirement: str) -> dict[str, str]:
        return {
            "gate_id": gate_id,
            "owner_role": owner_role,
            "status": "pass" if passed else "review",
            "requirement": requirement,
        }

    def _readiness(
        self,
        action_board: list[dict[str, Any]],
        closure_gates: list[dict[str, Any]],
    ) -> dict[str, Any]:
        completed = len([action for action in action_board if action["status"] == "completed"])
        passed_gates = len([gate for gate in closure_gates if gate["status"] == "pass"])
        action_score = (completed / max(len(action_board), 1)) * 40
        gate_score = (passed_gates / max(len(closure_gates), 1)) * 50
        evidence_score = 10 if all(action["evidence"] for action in action_board) else 0
        score = round(action_score + gate_score + evidence_score)
        status = "ready_to_close" if score >= 90 else "review" if score >= 55 else "blocked"
        return {"score": score, "status": status}

    def _process_mode(self, summary: dict[str, Any]) -> dict[str, Any]:
        if summary["recurrence_risk"]["level"] == "high":
            mode_id = "incident_review_war_room"
            cadence = "daily"
            max_open_actions = 2
        elif summary["customer_follow_up_state"]["status"] != "customer_update_sent":
            mode_id = "customer_followup_review"
            cadence = "daily_until_customer_update"
            max_open_actions = 3
        else:
            mode_id = "standard_closure"
            cadence = "weekly"
            max_open_actions = 5
        return {
            "mode_id": mode_id,
            "cadence": cadence,
            "max_open_actions_before_escalation": max_open_actions,
            "description": "Deterministic local postmortem closure mode selected from recurrence and follow-up state.",
        }

    def _role_playbook_rows(self, action_board: list[dict[str, Any]]) -> list[dict[str, str]]:
        owners = {action["owner_role"] for action in action_board}
        return [ROLE_PLAYBOOKS.get(owner, ROLE_PLAYBOOKS["Support Ops"]) for owner in sorted(owners)]

    def _artifact_handoffs(self, summary: dict[str, Any]) -> list[dict[str, str]]:
        return [
            {
                "artifact": "postmortem_rca_summary",
                "producer": "GET /incidents/postmortem-summary",
                "owner_role": "Support Ops",
                "evidence": summary["run_id"],
            },
            {
                "artifact": "postmortem_rca_pack",
                "producer": "POST /incidents/rca-pack",
                "owner_role": "Operations Commander",
                "evidence": "data/rca_packs",
            },
            {
                "artifact": "trace_timeline",
                "producer": summary["trace_links"]["trace"],
                "owner_role": "Support Ops",
                "evidence": summary["trace_id"],
            },
            {
                "artifact": "approval_queue",
                "producer": summary["trace_links"]["approval_queue"],
                "owner_role": "Support Lead",
                "evidence": str(summary["approval_comms_status"].get("approval_id") or ""),
            },
            {
                "artifact": "postmortem_review_pack",
                "producer": "POST /incidents/postmortem-review-pack",
                "owner_role": "Operations Commander",
                "evidence": "data/postmortem_review_packs",
            },
        ]

    def _run_transparency(self, summary: dict[str, Any]) -> dict[str, Any]:
        return {
            "run_id": summary["run_id"],
            "trace_id": summary["trace_id"],
            "trace_event_count": summary["trace_links"]["event_count"],
            "trace_event_ids": summary["trace_links"]["trace_event_ids"],
            "approval_status": summary["approval_comms_status"]["approval_status"],
            "pending_approval_count": summary["approval_comms_status"]["pending_approval_count"],
            "customer_comms_status": summary["approval_comms_status"]["customer_comms_status"],
            "engineering_comms_status": summary["approval_comms_status"]["engineering_comms_status"],
            "source": summary["source"],
        }

    def _review_cadence(self, summary: dict[str, Any]) -> dict[str, Any]:
        risk = summary["recurrence_risk"]
        return {
            "recommended_cadence": risk["recommended_review_cadence"],
            "recurrence_level": risk["level"],
            "recurrence_score": risk["score"],
            "next_review_trigger": "after_customer_update_or_action_owner_change",
        }

    def _closure_owner_summary(self, action_board: list[dict[str, Any]]) -> list[dict[str, Any]]:
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for action in action_board:
            grouped[action["owner_role"]].append(action)
        return [
            {
                "owner_role": owner,
                "action_count": len(actions),
                "open_action_count": len([action for action in actions if action["status"] != "completed"]),
                "highest_priority": self._highest_priority([action["priority"] for action in actions]),
                "lanes": sorted({action["closure_lane"] for action in actions}),
            }
            for owner, actions in sorted(grouped.items())
        ]

    def _review_gate_summary(self, gates: list[dict[str, Any]]) -> dict[str, Any]:
        counts = Counter(gate["status"] for gate in gates)
        return {
            "pass_count": counts.get("pass", 0),
            "review_count": counts.get("review", 0),
            "blocked_gates": [gate for gate in gates if gate["status"] != "pass"],
        }

    def _highest_priority(self, priorities: list[str]) -> str:
        order = {"p0": 0, "p1": 1, "p2": 2, "closed": 3}
        return sorted(priorities, key=lambda item: order.get(item, 99))[0] if priorities else "closed"

    def _limitations(self) -> list[str]:
        return [
            "The review board is deterministic and local; it does not sync real Jira, Slack, Zendesk, or calendars.",
            "Owner roles are portfolio-ready assignments derived from RCA actions, not live staffing commitments.",
            "Closure gates are governance checks over local state and artifacts; production closure would need identity-backed approvals.",
            "Generated postmortem review artifacts under data/postmortem_review_packs are ignored local proof files.",
        ]

    def _markdown(self, pack: dict[str, Any]) -> str:
        board = pack["review_board"]
        action_rows = [
            (
                f"| `{action['action_id']}` | {action['owner_role']} | {action['closure_lane']} | "
                f"{action['priority']} | {action['status']} | {action['due_at']} | `{action['required_artifact']}` |"
            )
            for action in board["action_board"]
        ]
        signoff_rows = [
            (
                f"| {item['owner_role']} | `{item['crew']}` | {item['status']} | "
                f"{item['open_action_count']} | {item['highest_priority']} |"
            )
            for item in board["role_signoffs"]
        ]
        gate_rows = [
            f"| `{gate['gate_id']}` | {gate['owner_role']} | {gate['status']} | {gate['requirement']} |"
            for gate in board["closure_gates"]
        ]
        artifact_rows = [
            (
                f"| {item['artifact']} | `{item['producer']}` | {item['owner_role']} | "
                f"`{item['evidence']}` |"
            )
            for item in board["artifact_handoffs"]
        ]
        command_rows = [f"- `{command}`" for command in pack["proof_commands"]]
        limitation_rows = [f"- {item}" for item in pack["limitations"]]
        return "\n".join(
            [
                f"# Postmortem Corrective Action Review Pack: {pack['pack_id']}",
                "",
                "## Review Board",
                f"- Status: **{board['review_status']}**",
                f"- Closure score: {board['closure_score']}",
                f"- Run: `{board['run_id']}`",
                f"- Trace: `{board['trace_id']}`",
                f"- Root cause: `{board['root_cause_category']['category']}`",
                f"- Process mode: `{board['process_mode']['mode_id']}`",
                "",
                "## Corrective Action Board",
                "| Action | Owner | Lane | Priority | Status | Due | Required Artifact |",
                "| --- | --- | --- | --- | --- | --- | --- |",
                *action_rows,
                "",
                "## Role Signoffs",
                "| Owner | Crew | Status | Open Actions | Highest Priority |",
                "| --- | --- | --- | ---: | --- |",
                *signoff_rows,
                "",
                "## Closure Gates",
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
                f"- Trace events: {board['run_transparency']['trace_event_count']}",
                f"- Approval status: {board['run_transparency']['approval_status']}",
                f"- Pending approvals: {board['run_transparency']['pending_approval_count']}",
                f"- Customer comms: {board['run_transparency']['customer_comms_status']}",
                f"- Engineering comms: {board['run_transparency']['engineering_comms_status']}",
                "",
                "## Local Proof Commands",
                *command_rows,
                "",
                "## Limitations",
                *limitation_rows,
                "",
            ]
        )
