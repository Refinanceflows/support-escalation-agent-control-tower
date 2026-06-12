import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.core.storage import JsonStateStore
from app.models import AuditEvent, PolicyChangeKnobs, PolicyDriftRequest, RunRecord
from app.services.audit import AuditService
from app.services.policy_change_simulation import POLICY_CHANGE_VERIFY_COMMANDS


POLICY_DRIFT_VERIFY_COMMANDS = [
    *POLICY_CHANGE_VERIFY_COMMANDS,
    (
        r'rg "policies/drift-audit|policies/drift-pack|Policy Drift|'
        r'policy_drift_packs|decision drift" app dashboard docs README.md tests scripts'
    ),
]


class PolicyDriftService:
    """Detects policy decision drift over persisted local workflow runs."""

    def __init__(
        self,
        store: JsonStateStore,
        audit: AuditService,
        drift_dir: Path,
    ):
        self.store = store
        self.audit = audit
        self.drift_dir = drift_dir

    async def drift_audit(self, payload: PolicyDriftRequest | None = None) -> dict[str, Any]:
        request = payload or PolicyDriftRequest()
        runs = self._select_runs(await self.store.load(), request)
        rows = [self._drift_row(run, request.baseline, request.current) for run in runs]
        summary = self._summary(rows)
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "title": "Policy Decision Drift Audit",
            "mode": "local-deterministic-policy-drift-monitor",
            "local_mock_only": True,
            "status": self._status(summary),
            "summary": summary,
            "baseline_policy": request.baseline.model_dump(mode="json"),
            "current_policy": request.current.model_dump(mode="json"),
            "run_count": len(rows),
            "drift_rows": rows,
            "review_gates": self._review_gates(summary),
            "owner_actions": self._owner_actions(summary),
            "run_transparency": self._run_transparency(rows, request),
            "repo_radar_patterns": [
                "governance",
                "shared state",
                "human-in-the-loop",
                "trace analysis",
            ],
            "local_commands": POLICY_DRIFT_VERIFY_COMMANDS,
            "limitations": self._limitations(),
        }

    async def export_pack(self, payload: PolicyDriftRequest | None = None) -> dict[str, Any]:
        drift = await self.drift_audit(payload)
        generated_at = datetime.now(timezone.utc)
        pack_id = f"policy_drift_pack_{generated_at.strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:6]}"
        json_path = self.drift_dir / f"{pack_id}.json"
        markdown_path = self.drift_dir / f"{pack_id}.md"
        pack = {
            "pack_id": pack_id,
            "generated_at": generated_at.isoformat(),
            "title": "Policy Drift Reviewer Pack",
            "drift_audit": drift,
            "reviewer_artifacts": {
                "policy_drift_markdown": str(markdown_path),
                "policy_drift_json": str(json_path),
                "audit_endpoint": "POST /policies/drift-audit",
                "export_endpoint": "POST /policies/drift-pack",
            },
            "acceptance_criteria": self._acceptance_criteria(),
            "local_commands": POLICY_DRIFT_VERIFY_COMMANDS,
            "limitations": drift["limitations"],
        }
        markdown = self._markdown(pack)
        self.drift_dir.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(pack, indent=2, default=str), encoding="utf-8")
        markdown_path.write_text(markdown, encoding="utf-8")
        await self.audit.record(
            AuditEvent(
                actor="policy-drift",
                action="policy.drift_pack_exported",
                resource_type="policy_drift_pack",
                resource_id=pack_id,
                metadata={
                    "status": drift["status"],
                    "drifted_run_count": drift["summary"]["drifted_run_count"],
                    "markdown_path": str(markdown_path),
                    "json_path": str(json_path),
                },
            )
        )
        return {
            "pack_id": pack_id,
            "format": "markdown+json",
            "status": drift["status"],
            "json_path": str(json_path),
            "markdown_path": str(markdown_path),
            "pack": pack,
            "markdown": markdown,
        }

    def _select_runs(
        self,
        state: dict[str, Any],
        request: PolicyDriftRequest,
    ) -> list[RunRecord]:
        runs = []
        for raw in state["runs"].values():
            run = RunRecord(**raw)
            if not self._has_policy_state(run):
                continue
            if not request.include_pending and run.status == "awaiting_approval":
                continue
            runs.append(run)
        runs.sort(key=lambda item: str(item.started_at), reverse=True)
        return runs[: request.max_runs]

    def _has_policy_state(self, run: RunRecord) -> bool:
        state = run.state
        return bool(state.get("classification") and state.get("sla_risk") and state.get("qa"))

    def _drift_row(
        self,
        run: RunRecord,
        baseline: PolicyChangeKnobs,
        current: PolicyChangeKnobs,
    ) -> dict[str, Any]:
        actual = self._actual_state(run)
        baseline_outcome = self._policy_outcome(actual, baseline)
        current_outcome = self._policy_outcome(actual, current)
        changed = self._changed_fields(baseline_outcome, current_outcome)
        severity = self._severity(baseline_outcome, current_outcome, changed)
        return {
            "run_id": run.run_id,
            "ticket_id": run.ticket_id,
            "trace_id": run.trace_id,
            "run_status": run.status,
            "final_action": run.final_action,
            "actual": actual,
            "baseline": baseline_outcome,
            "current": current_outcome,
            "changed_fields": changed,
            "drifted": bool(changed),
            "severity": severity,
            "recommended_action": self._recommended_action(severity, current_outcome),
        }

    def _actual_state(self, run: RunRecord) -> dict[str, Any]:
        state = run.state
        ticket = state.get("ticket", {})
        qa = state.get("qa", {})
        classification = state.get("classification", {})
        sla = state.get("sla_risk", {})
        confidence = float(qa.get("confidence", classification.get("confidence", 0.0)))
        return {
            "run_id": run.run_id,
            "ticket_id": run.ticket_id,
            "final_action": run.final_action,
            "classification_category": classification.get("category", "unknown"),
            "classification_confidence": float(classification.get("confidence", 0.0)),
            "qa_confidence": round(confidence, 2),
            "sla_score": float(sla.get("score", 0.0)),
            "workflow_sla_level": sla.get("level", "unknown"),
            "workflow_should_escalate": bool(sla.get("should_escalate", False)),
            "failure_state": bool(run.failure_state or state.get("failure_state")),
            "customer_tier": ticket.get("customer_tier", "standard"),
            "tool_error_count": len(
                [call for call in state.get("tool_calls", []) if call.get("status") == "error"]
            ),
            "sensitive_domain": classification.get("category") in {"security_privacy", "incident"},
        }

    def _policy_outcome(self, actual: dict[str, Any], knobs: PolicyChangeKnobs) -> dict[str, Any]:
        sla_level = self._routed_sla_level(actual["sla_score"], knobs.sla_high_risk_threshold)
        blast_score, factors = self._blast_radius_score(actual, sla_level, knobs)
        confidence_block = actual["qa_confidence"] < knobs.confidence_cutoff
        if confidence_block:
            decision = "blocked_for_review"
            approval_type = "support_lead"
        elif blast_score > knobs.auto_approval_max_blast_radius:
            decision = "requires_approval"
            approval_type = self._approval_type(actual, sla_level, blast_score)
        else:
            decision = "auto_allowed"
            approval_type = "none"
        return {
            "decision": decision,
            "approval_type": approval_type,
            "confidence_block": confidence_block,
            "sla_route": sla_level,
            "blast_radius_score": blast_score,
            "blast_radius_factors": factors,
            "auto_approval_max_blast_radius": knobs.auto_approval_max_blast_radius,
            "confidence_cutoff": knobs.confidence_cutoff,
            "sla_high_risk_threshold": knobs.sla_high_risk_threshold,
        }

    def _routed_sla_level(self, score: float, high_threshold: float) -> str:
        if score >= high_threshold:
            return "high"
        if score >= min(0.45, high_threshold * 0.7):
            return "medium"
        return "low"

    def _blast_radius_score(
        self,
        actual: dict[str, Any],
        sla_level: str,
        knobs: PolicyChangeKnobs,
    ) -> tuple[int, list[str]]:
        score = 10
        factors = ["base_support_action=10"]
        if "engineering" in actual["final_action"]:
            score += 18
            factors.append("engineering_dispatch=18")
        if sla_level == "high":
            score += 22
            factors.append("high_sla_route=22")
        elif sla_level == "medium":
            score += 10
            factors.append("medium_sla_route=10")
        if actual["qa_confidence"] < knobs.confidence_cutoff:
            score += 18
            factors.append("below_confidence_cutoff=18")
        if actual["failure_state"] or actual["tool_error_count"] > 0:
            score += 12
            factors.append("tool_or_adapter_failure=12")
        if actual["sensitive_domain"]:
            score += 14
            factors.append("sensitive_domain=14")
        tier = actual.get("customer_tier", "standard")
        if tier == "enterprise":
            score += 16
            factors.append("enterprise_customer=16")
        elif tier == "pro":
            score += 8
            factors.append("pro_customer=8")
        return min(score, 100), factors

    def _approval_type(self, actual: dict[str, Any], sla_level: str, blast_score: int) -> str:
        if blast_score >= 80:
            return "policy_admin"
        if sla_level == "high" or "engineering" in actual["final_action"]:
            return "incident_commander"
        if actual.get("customer_tier") == "enterprise":
            return "support_manager"
        return "support_lead"

    def _changed_fields(
        self,
        baseline: dict[str, Any],
        current: dict[str, Any],
    ) -> list[str]:
        return [
            field
            for field in ["decision", "approval_type", "confidence_block", "sla_route", "blast_radius_score"]
            if baseline[field] != current[field]
        ]

    def _severity(
        self,
        baseline: dict[str, Any],
        current: dict[str, Any],
        changed: list[str],
    ) -> str:
        if not changed:
            return "none"
        if baseline["decision"] != "auto_allowed" and current["decision"] == "auto_allowed":
            return "critical"
        if baseline["sla_route"] == "high" and current["sla_route"] != "high":
            return "high"
        if current["decision"] in {"requires_approval", "blocked_for_review"}:
            return "medium"
        return "low"

    def _recommended_action(self, severity: str, current: dict[str, Any]) -> str:
        if severity == "critical":
            return "Freeze rollout and require Policy Admin review before auto-allowing this class of run."
        if severity == "high":
            return "Review SLA threshold change with Incident Commander before promotion."
        if severity == "medium":
            return f"Route to {current['approval_type']} and measure reviewer queue impact."
        if severity == "low":
            return "Track as informational drift during shadow comparison."
        return "No drift action required."

    def _summary(self, rows: list[dict[str, Any]]) -> dict[str, Any]:
        severity_counts = {
            severity: len([row for row in rows if row["severity"] == severity])
            for severity in ["critical", "high", "medium", "low", "none"]
        }
        return {
            "evaluated_run_count": len(rows),
            "drifted_run_count": len([row for row in rows if row["drifted"]]),
            "critical_drift_count": severity_counts["critical"],
            "high_drift_count": severity_counts["high"],
            "medium_drift_count": severity_counts["medium"],
            "new_auto_allowed_count": len(
                [
                    row
                    for row in rows
                    if row["baseline"]["decision"] != "auto_allowed"
                    and row["current"]["decision"] == "auto_allowed"
                ]
            ),
            "approval_queue_increase_count": len(
                [
                    row
                    for row in rows
                    if row["baseline"]["decision"] == "auto_allowed"
                    and row["current"]["decision"] != "auto_allowed"
                ]
            ),
            "sla_route_change_count": len(
                [row for row in rows if row["baseline"]["sla_route"] != row["current"]["sla_route"]]
            ),
            "severity_counts": severity_counts,
        }

    def _status(self, summary: dict[str, Any]) -> str:
        if summary["evaluated_run_count"] == 0:
            return "needs_runs"
        if summary["critical_drift_count"] or summary["high_drift_count"]:
            return "review_required"
        if summary["drifted_run_count"]:
            return "watch"
        return "stable"

    def _review_gates(self, summary: dict[str, Any]) -> list[dict[str, Any]]:
        return [
            {
                "gate_id": "no_new_auto_allow_without_review",
                "status": "pass" if summary["new_auto_allowed_count"] == 0 else "fail",
                "owner": "Policy Admin",
                "observed": summary["new_auto_allowed_count"],
                "threshold": 0,
            },
            {
                "gate_id": "no_high_sla_downgrade",
                "status": "pass" if summary["high_drift_count"] == 0 else "fail",
                "owner": "Incident Commander",
                "observed": summary["high_drift_count"],
                "threshold": 0,
            },
            {
                "gate_id": "reviewer_capacity_visible",
                "status": "pass" if summary["approval_queue_increase_count"] <= 3 else "fail",
                "owner": "Support Operations",
                "observed": summary["approval_queue_increase_count"],
                "threshold": 3,
            },
        ]

    def _owner_actions(self, summary: dict[str, Any]) -> list[dict[str, str]]:
        actions = [
            {
                "owner": "Support Lead",
                "action": "Review drifted runs before changing customer-visible automation behavior.",
                "priority": "medium" if summary["drifted_run_count"] else "low",
            }
        ]
        if summary["new_auto_allowed_count"]:
            actions.append(
                {
                    "owner": "Policy Admin",
                    "action": "Block policy promotion until new auto-allowed runs are explicitly signed off.",
                    "priority": "critical",
                }
            )
        if summary["sla_route_change_count"]:
            actions.append(
                {
                    "owner": "Incident Commander",
                    "action": "Validate SLA route changes against incident response expectations.",
                    "priority": "high",
                }
            )
        return actions

    def _run_transparency(
        self,
        rows: list[dict[str, Any]],
        request: PolicyDriftRequest,
    ) -> dict[str, Any]:
        return {
            "source": "persisted_run_state",
            "max_runs": request.max_runs,
            "include_pending": request.include_pending,
            "run_ids": [row["run_id"] for row in rows],
            "trace_ids": [row["trace_id"] for row in rows],
            "drifted_run_ids": [row["run_id"] for row in rows if row["drifted"]],
        }

    def _acceptance_criteria(self) -> list[str]:
        return [
            "Critical drift fails closed when a policy change would newly auto-allow a previously gated run.",
            "SLA route downgrades name an Incident Commander owner before rollout.",
            "The pack links every drift row to run_id and trace_id for local review.",
            "No external provider, ticketing, Slack, Jira, GitHub, or policy engine call is made.",
        ]

    def _limitations(self) -> list[str]:
        return [
            "Drift is computed from persisted local run state, not live production traffic.",
            "The service compares supplied policy knobs and does not mutate runtime configuration.",
            "Historical baseline policy is supplied by the reviewer because this repo does not yet version policy configs.",
            "Production use would need tenant-scoped policy versions, reviewer identity, and continuous monitoring.",
        ]

    def _markdown(self, pack: dict[str, Any]) -> str:
        drift = pack["drift_audit"]
        summary = drift["summary"]
        gates = [
            (
                f"| {gate['gate_id']} | {gate['status']} | {gate['owner']} | "
                f"{gate['observed']} / {gate['threshold']} |"
            )
            for gate in drift["review_gates"]
        ]
        rows = [
            (
                f"| {row['run_id']} | {row['ticket_id']} | {row['severity']} | "
                f"{row['baseline']['decision']} -> {row['current']['decision']} | "
                f"{row['baseline']['sla_route']} -> {row['current']['sla_route']} | "
                f"{', '.join(row['changed_fields']) or 'none'} |"
            )
            for row in drift["drift_rows"]
        ]
        actions = [
            f"| {item['owner']} | {item['priority']} | {item['action']} |"
            for item in drift["owner_actions"]
        ]
        criteria = [f"- {item}" for item in pack["acceptance_criteria"]]
        commands = [f"- `{command}`" for command in pack["local_commands"]]
        limitations = [f"- {item}" for item in pack["limitations"]]
        return "\n".join(
            [
                f"# Policy Drift Reviewer Pack: {pack['pack_id']}",
                "",
                "## Summary",
                f"- Status: {drift['status']}",
                f"- Evaluated runs: {summary['evaluated_run_count']}",
                f"- Drifted runs: {summary['drifted_run_count']}",
                f"- Critical drift: {summary['critical_drift_count']}",
                f"- High drift: {summary['high_drift_count']}",
                f"- New auto-allowed runs: {summary['new_auto_allowed_count']}",
                f"- SLA route changes: {summary['sla_route_change_count']}",
                "",
                "## Review Gates",
                "| Gate | Status | Owner | Observed / Threshold |",
                "| --- | --- | --- | --- |",
                *gates,
                "",
                "## Drift Rows",
                "| Run | Ticket | Severity | Decision Drift | SLA Drift | Changed Fields |",
                "| --- | --- | --- | --- | --- | --- |",
                *rows,
                "",
                "## Owner Actions",
                "| Owner | Priority | Action |",
                "| --- | --- | --- |",
                *actions,
                "",
                "## Acceptance Criteria",
                *criteria,
                "",
                "## Local Commands",
                *commands,
                "",
                "## Limitations",
                *limitations,
                "",
            ]
        )
