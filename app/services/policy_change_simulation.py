import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.models import PolicyChangeKnobs, PolicyChangeSimulationRequest, TicketCreate
from app.services.tickets import TicketService
from app.services.workflow import AgentWorkflowService


POLICY_CHANGE_VERIFY_COMMANDS = [
    r".\.venv\Scripts\python.exe -m pytest -q",
    r".\.venv\Scripts\python.exe -m ruff check app tests dashboard scripts",
    r".\.venv\Scripts\python.exe -m app.evals.run_eval",
    r".\.venv\Scripts\python.exe scripts\dashboard_smoke.py",
    r".\.venv\Scripts\python.exe scripts\demo_run.py",
    (
        r'rg "policies/change-simulation|policies/change-pack|Policy Change Simulation|'
        r'policy_change_packs|blast radius" app dashboard docs README.md tests scripts'
    ),
]


class PolicyChangeSimulationService:
    """Local policy-workbench for approval, confidence, and SLA threshold changes."""

    def __init__(
        self,
        tickets: TicketService,
        workflow: AgentWorkflowService,
        fixture_path: Path,
        policy_change_packs_dir: Path,
    ):
        self.tickets = tickets
        self.workflow = workflow
        self.fixture_path = fixture_path
        self.policy_change_packs_dir = policy_change_packs_dir

    async def simulate(
        self,
        payload: PolicyChangeSimulationRequest | None = None,
    ) -> dict[str, Any]:
        request = payload or PolicyChangeSimulationRequest()
        scenarios = self._load_scenarios(request.scenario_limit)
        rows = [await self._scenario_row(scenario, request.baseline, request.proposed) for scenario in scenarios]
        baseline_summary = self._policy_summary(rows, "baseline")
        proposed_summary = self._policy_summary(rows, "proposed")
        deltas = self._deltas(baseline_summary, proposed_summary)
        return {
            "simulation_id": f"polchange_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "title": "Policy Change Simulation",
            "mode": "local-deterministic-policy-change-workbench",
            "local_mock_only": True,
            "fixture_path": str(self.fixture_path),
            "scenario_count": len(rows),
            "baseline_policy": request.baseline.model_dump(mode="json"),
            "proposed_policy": request.proposed.model_dump(mode="json"),
            "summary": {
                "baseline": baseline_summary,
                "proposed": proposed_summary,
                "deltas": deltas,
                "recommendation": self._recommendation(proposed_summary, deltas),
            },
            "blast_radius": self._blast_radius(rows, deltas),
            "sla_routing": self._sla_routing(rows),
            "scenario_results": rows,
            "reviewer_notes": self._reviewer_notes(deltas),
            "local_verification_commands": POLICY_CHANGE_VERIFY_COMMANDS,
        }

    async def export_pack(
        self,
        payload: PolicyChangeSimulationRequest | None = None,
    ) -> dict[str, Any]:
        simulation = await self.simulate(payload)
        generated_at = datetime.now(timezone.utc)
        pack_id = f"policy_change_pack_{generated_at.strftime('%Y%m%d_%H%M%S')}"
        json_path = self.policy_change_packs_dir / f"{pack_id}.json"
        markdown_path = self.policy_change_packs_dir / f"{pack_id}.md"
        pack = {
            "pack_id": pack_id,
            "generated_at": generated_at.isoformat(),
            "title": "Agent Policy Simulation Pack",
            "simulation": simulation,
            "approval_thresholds": {
                "baseline": simulation["baseline_policy"]["auto_approval_max_blast_radius"],
                "proposed": simulation["proposed_policy"]["auto_approval_max_blast_radius"],
            },
            "confidence_cutoffs": {
                "baseline": simulation["baseline_policy"]["confidence_cutoff"],
                "proposed": simulation["proposed_policy"]["confidence_cutoff"],
            },
            "sla_thresholds": {
                "baseline": simulation["baseline_policy"]["sla_high_risk_threshold"],
                "proposed": simulation["proposed_policy"]["sla_high_risk_threshold"],
            },
            "local_verification_commands": POLICY_CHANGE_VERIFY_COMMANDS,
            "reviewer_artifacts": {
                "policy_change_pack_markdown": str(markdown_path),
                "policy_change_pack_json": str(json_path),
            },
            "interviewer_talking_points": self._talking_points(simulation),
        }
        markdown = self._markdown(pack)
        self.policy_change_packs_dir.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(pack, indent=2, default=str), encoding="utf-8")
        markdown_path.write_text(markdown, encoding="utf-8")
        return {
            "pack_id": pack_id,
            "format": "markdown+json",
            "json_path": str(json_path),
            "markdown_path": str(markdown_path),
            "summary": simulation["summary"],
            "pack": pack,
            "markdown": markdown,
        }

    def _load_scenarios(self, limit: int | None) -> list[dict[str, Any]]:
        scenarios = json.loads(self.fixture_path.read_text(encoding="utf-8"))
        return scenarios[:limit] if limit else scenarios

    async def _scenario_row(
        self,
        scenario: dict[str, Any],
        baseline: PolicyChangeKnobs,
        proposed: PolicyChangeKnobs,
    ) -> dict[str, Any]:
        ticket = await self.tickets.ingest(TicketCreate(**scenario["ticket"]))
        run = await self.workflow.analyze_ticket(ticket.ticket_id)
        state = run.state
        actual = self._actual_state(scenario, run, state)
        baseline_outcome = self._policy_outcome(actual, baseline)
        proposed_outcome = self._policy_outcome(actual, proposed)
        return {
            "scenario_id": scenario["scenario_id"],
            "title": scenario["title"],
            "domain": scenario["domain"],
            "customer_tier": scenario["ticket"].get("customer_tier", "standard"),
            "priority": scenario["ticket"].get("priority", "normal"),
            "expected_sla_level": scenario["expected"]["sla_level"],
            "expected_escalation": scenario["expected"]["should_escalate"],
            "actual": actual,
            "baseline": baseline_outcome,
            "proposed": proposed_outcome,
            "changed": self._changed_fields(baseline_outcome, proposed_outcome),
        }

    def _actual_state(
        self,
        scenario: dict[str, Any],
        run: Any,
        state: dict[str, Any],
    ) -> dict[str, Any]:
        qa = state.get("qa", {})
        confidence = float(qa.get("confidence", state["classification"]["confidence"]))
        return {
            "run_id": run.run_id,
            "ticket_id": run.ticket_id,
            "final_action": run.final_action,
            "classification_category": state["classification"]["category"],
            "classification_confidence": state["classification"]["confidence"],
            "qa_confidence": round(confidence, 2),
            "sla_score": float(state["sla_risk"]["score"]),
            "workflow_sla_level": state["sla_risk"]["level"],
            "workflow_should_escalate": bool(state["sla_risk"]["should_escalate"]),
            "failure_state": bool(run.failure_state),
            "customer_tier": scenario["ticket"].get("customer_tier", "standard"),
            "tool_error_count": len(
                [call for call in state.get("tool_calls", []) if call.get("status") == "error"]
            ),
            "sensitive_domain": scenario["domain"]
            in {"security", "data_export_privacy", "renewal_risk"},
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
        proposed: dict[str, Any],
    ) -> list[str]:
        return [
            field
            for field in ["decision", "approval_type", "confidence_block", "sla_route", "blast_radius_score"]
            if baseline[field] != proposed[field]
        ]

    def _policy_summary(self, rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
        total = len(rows) or 1
        decisions = [row[key]["decision"] for row in rows]
        sla_correct = sum(1 for row in rows if row[key]["sla_route"] == row["expected_sla_level"])
        high_sla_count = sum(1 for row in rows if row[key]["sla_route"] == "high")
        return {
            "auto_allowed_count": decisions.count("auto_allowed"),
            "requires_approval_count": decisions.count("requires_approval"),
            "blocked_for_review_count": decisions.count("blocked_for_review"),
            "high_sla_route_count": high_sla_count,
            "sla_routing_accuracy_percent": round((sla_correct / total) * 100, 2),
            "average_blast_radius_score": round(
                sum(row[key]["blast_radius_score"] for row in rows) / total,
                2,
            ),
            "max_blast_radius_score": max((row[key]["blast_radius_score"] for row in rows), default=0),
        }

    def _deltas(
        self,
        baseline: dict[str, Any],
        proposed: dict[str, Any],
    ) -> dict[str, Any]:
        fields = [
            "auto_allowed_count",
            "requires_approval_count",
            "blocked_for_review_count",
            "high_sla_route_count",
            "sla_routing_accuracy_percent",
            "average_blast_radius_score",
            "max_blast_radius_score",
        ]
        return {field: round(proposed[field] - baseline[field], 2) for field in fields}

    def _blast_radius(self, rows: list[dict[str, Any]], deltas: dict[str, Any]) -> dict[str, Any]:
        changed = [row for row in rows if row["changed"]]
        escalated_to_auto = [
            row
            for row in changed
            if row["baseline"]["decision"] != "auto_allowed"
            and row["proposed"]["decision"] == "auto_allowed"
        ]
        removed_from_auto = [
            row
            for row in changed
            if row["baseline"]["decision"] == "auto_allowed"
            and row["proposed"]["decision"] != "auto_allowed"
        ]
        risk = min(
            100,
            max(0, len(escalated_to_auto) * 20 - len(removed_from_auto) * 8)
            + max(0, int(deltas["average_blast_radius_score"] * 2)),
        )
        return {
            "overall_change_risk_score": risk,
            "changed_scenario_count": len(changed),
            "newly_auto_allowed_count": len(escalated_to_auto),
            "removed_from_auto_count": len(removed_from_auto),
            "highest_risk_changed_scenarios": [
                {
                    "scenario_id": row["scenario_id"],
                    "title": row["title"],
                    "baseline_decision": row["baseline"]["decision"],
                    "proposed_decision": row["proposed"]["decision"],
                    "proposed_blast_radius_score": row["proposed"]["blast_radius_score"],
                    "changed_fields": row["changed"],
                }
                for row in sorted(
                    changed,
                    key=lambda item: item["proposed"]["blast_radius_score"],
                    reverse=True,
                )[:5]
            ],
        }

    def _sla_routing(self, rows: list[dict[str, Any]]) -> dict[str, Any]:
        changed = [row for row in rows if row["baseline"]["sla_route"] != row["proposed"]["sla_route"]]
        regressions = [
            row
            for row in changed
            if row["baseline"]["sla_route"] == row["expected_sla_level"]
            and row["proposed"]["sla_route"] != row["expected_sla_level"]
        ]
        improvements = [
            row
            for row in changed
            if row["baseline"]["sla_route"] != row["expected_sla_level"]
            and row["proposed"]["sla_route"] == row["expected_sla_level"]
        ]
        return {
            "changed_route_count": len(changed),
            "regression_count": len(regressions),
            "improvement_count": len(improvements),
            "changed_routes": [
                {
                    "scenario_id": row["scenario_id"],
                    "expected": row["expected_sla_level"],
                    "baseline": row["baseline"]["sla_route"],
                    "proposed": row["proposed"]["sla_route"],
                }
                for row in changed
            ],
        }

    def _recommendation(self, proposed: dict[str, Any], deltas: dict[str, Any]) -> str:
        if deltas["auto_allowed_count"] > 0 and proposed["average_blast_radius_score"] > 55:
            return "Do not ship: proposed policy increases auto-approval while average blast radius remains elevated."
        if deltas["blocked_for_review_count"] > 2:
            return "Pilot with support leads: proposed policy materially increases manual review volume."
        if deltas["sla_routing_accuracy_percent"] < 0:
            return "Revise SLA threshold before rollout because routing accuracy regresses."
        return "Safe for local pilot with audit monitoring and reviewer sign-off."

    def _reviewer_notes(self, deltas: dict[str, Any]) -> list[str]:
        return [
            "All calculations are deterministic and local; no external policy engine or LLM call is required.",
            "Approval threshold changes are represented by `auto_approval_max_blast_radius`.",
            "Confidence cutoff changes show expected support-lead review volume before rollout.",
            f"SLA routing accuracy delta is {deltas['sla_routing_accuracy_percent']} percentage points.",
            "Blast-radius scoring is explainable per scenario through weighted factors.",
        ]

    def _talking_points(self, simulation: dict[str, Any]) -> list[str]:
        summary = simulation["summary"]
        return [
            "The pack compares baseline and proposed automation controls against the scenario corpus.",
            (
                "Approval threshold impact is visible through auto-allowed, approval-required, "
                "and blocked-for-review counts."
            ),
            (
                "SLA routing impact is measured separately from policy decisioning so managers can "
                "see operational risk, not only automation volume."
            ),
            (
                "Blast-radius scoring explains why sensitive, enterprise, high-SLA, low-confidence, "
                "or failure scenarios require tighter rollout controls."
            ),
            f"Recommendation: {summary['deltas']} -> {summary['recommendation']}",
        ]

    def _markdown(self, pack: dict[str, Any]) -> str:
        simulation = pack["simulation"]
        summary = simulation["summary"]
        blast = simulation["blast_radius"]
        sla = simulation["sla_routing"]
        commands = [f"- `{command}`" for command in pack["local_verification_commands"]]
        notes = [f"- {note}" for note in simulation["reviewer_notes"]]
        talking_points = [f"- {point}" for point in pack["interviewer_talking_points"]]
        scenario_rows = [
            (
                f"| {row['scenario_id']} | {row['expected_sla_level']} | "
                f"{row['baseline']['decision']} | {row['proposed']['decision']} | "
                f"{row['baseline']['sla_route']} -> {row['proposed']['sla_route']} | "
                f"{row['proposed']['blast_radius_score']} | {', '.join(row['changed']) or 'none'} |"
            )
            for row in simulation["scenario_results"]
        ]
        return "\n".join(
            [
                f"# Agent Policy Simulation Pack: {pack['pack_id']}",
                "",
                "## Summary",
                f"- Recommendation: {summary['recommendation']}",
                f"- Scenario count: {simulation['scenario_count']}",
                f"- Baseline approval threshold: {pack['approval_thresholds']['baseline']}",
                f"- Proposed approval threshold: {pack['approval_thresholds']['proposed']}",
                f"- Baseline confidence cutoff: {pack['confidence_cutoffs']['baseline']}",
                f"- Proposed confidence cutoff: {pack['confidence_cutoffs']['proposed']}",
                f"- Baseline SLA high-risk threshold: {pack['sla_thresholds']['baseline']}",
                f"- Proposed SLA high-risk threshold: {pack['sla_thresholds']['proposed']}",
                "",
                "## Decision Deltas",
                f"- Auto-allowed delta: {summary['deltas']['auto_allowed_count']}",
                f"- Requires-approval delta: {summary['deltas']['requires_approval_count']}",
                f"- Blocked-for-review delta: {summary['deltas']['blocked_for_review_count']}",
                f"- SLA routing accuracy delta: {summary['deltas']['sla_routing_accuracy_percent']}",
                f"- Average blast-radius delta: {summary['deltas']['average_blast_radius_score']}",
                "",
                "## Blast Radius",
                f"- Overall change risk score: {blast['overall_change_risk_score']}",
                f"- Changed scenarios: {blast['changed_scenario_count']}",
                f"- Newly auto-allowed scenarios: {blast['newly_auto_allowed_count']}",
                f"- Removed from auto scenarios: {blast['removed_from_auto_count']}",
                "",
                "## SLA Routing",
                f"- Changed routes: {sla['changed_route_count']}",
                f"- Regressions: {sla['regression_count']}",
                f"- Improvements: {sla['improvement_count']}",
                "",
                "## Scenario Impact",
                "| Scenario | Expected SLA | Baseline Decision | Proposed Decision | SLA Route | Proposed Blast | Changed |",
                "| --- | --- | --- | --- | --- | ---: | --- |",
                *scenario_rows,
                "",
                "## Reviewer Notes",
                *notes,
                "",
                "## Interviewer Talking Points",
                *talking_points,
                "",
                "## Local Verification Commands",
                *commands,
                "",
            ]
        )
