import json
import math
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.core.storage import JsonStateStore
from app.models import AuditEvent, Ticket, TicketCreate
from app.services.audit import AuditService
from app.services.tickets import TicketService


CATEGORY_TAGS = {
    "authentication": {"auth", "sso", "login", "oauth", "saml", "mfa", "outage"},
    "billing": {"billing", "invoice", "refund", "finance", "credit", "renewal"},
    "api_integrations": {"api", "webhook", "latency", "5xx", "500", "integration", "retry"},
    "security_privacy": {"privacy", "data", "compliance", "security", "deletion", "export", "breach"},
    "incident": {"incident", "outage", "sla", "production", "blocked", "breach"},
    "how_to": {"how_to", "how-to", "rotation", "question", "setup"},
    "general_support": {"reply", "support", "qa", "customer", "help"},
}

OWNER_BY_CATEGORY = {
    "authentication": "Identity Support Lead",
    "billing": "Billing Operations Lead",
    "api_integrations": "Developer Support Lead",
    "security_privacy": "Security and Compliance Owner",
    "incident": "Incident Commander",
    "how_to": "Support Enablement",
    "general_support": "Support QA Lead",
}

AVAILABLE_FTE_BY_CATEGORY = {
    "authentication": 0.08,
    "billing": 0.08,
    "api_integrations": 0.1,
    "security_privacy": 0.08,
    "incident": 0.08,
    "how_to": 0.06,
    "general_support": 0.06,
}

BASE_MINUTES_BY_CATEGORY = {
    "authentication": 52,
    "billing": 38,
    "api_integrations": 64,
    "security_privacy": 72,
    "incident": 95,
    "how_to": 24,
    "general_support": 30,
}

PRIORITY_MULTIPLIER = {"low": 0.8, "normal": 1.0, "high": 1.35, "urgent": 1.7}
TIER_MULTIPLIER = {"standard": 1.0, "pro": 1.15, "enterprise": 1.35}
PRODUCTIVE_HOURS_PER_FTE = 30.0

CAPACITY_ENDPOINTS = [
    "GET /capacity/forecast",
    "POST /capacity/staffing-plan",
    "GET /tickets",
    "GET /scenarios/catalog",
    "GET /metrics/agent-performance",
    "GET /runbooks/coverage-audit",
]

CAPACITY_COMMANDS = [
    r".\.venv\Scripts\python.exe scripts\capacity_plan.py",
    r".\.venv\Scripts\python.exe -m pytest -q",
    r".\.venv\Scripts\python.exe -m ruff check app tests dashboard scripts",
    r".\.venv\Scripts\python.exe -m app.evals.run_eval",
    r".\.venv\Scripts\python.exe scripts\dashboard_smoke.py",
    r".\.venv\Scripts\python.exe scripts\demo_run.py",
]


class CapacityPlanningService:
    """Forecasts local support load and exports owner-ready staffing plans."""

    def __init__(
        self,
        store: JsonStateStore,
        tickets: TicketService,
        audit: AuditService,
        scenarios_path: Path,
        capacity_plans_dir: Path,
    ):
        self.store = store
        self.tickets = tickets
        self.audit = audit
        self.scenarios_path = scenarios_path
        self.capacity_plans_dir = capacity_plans_dir

    async def forecast(self) -> dict[str, Any]:
        active_tickets = await self.tickets.list()
        scenario_tickets = self._scenario_tickets()
        state = await self.store.load()
        rows = self._queue_rows(active_tickets, scenario_tickets, state)
        summary = self._summary(rows, state)
        gaps = self._capacity_gaps(rows)
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "mode": "local-deterministic-capacity-planner",
            "local_mock_only": True,
            "readiness_status": summary["readiness_status"],
            "capacity_score": summary["capacity_score"],
            "demand_summary": summary,
            "queue_forecast": rows,
            "staffing_gaps": gaps,
            "owner_assignments": self._owner_assignments(rows, gaps),
            "endpoint_list": CAPACITY_ENDPOINTS,
            "evidence_sources": {
                "active_ticket_count": len(active_tickets),
                "scenario_ticket_count": len(scenario_tickets),
                "run_count": len(state.get("runs", {})),
                "scenario_fixture": str(self.scenarios_path),
                "artifact_directory": "data/capacity_plans",
            },
            "local_commands": CAPACITY_COMMANDS,
            "limitations": self._limitations(),
        }

    async def export_staffing_plan(self) -> dict[str, Any]:
        forecast = await self.forecast()
        generated_at = datetime.now(timezone.utc)
        plan_id = f"capacity_plan_{generated_at.strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:6]}"
        json_path = self.capacity_plans_dir / f"{plan_id}.json"
        markdown_path = self.capacity_plans_dir / f"{plan_id}.md"
        plan = {
            "plan_id": plan_id,
            "generated_at": generated_at.isoformat(),
            "title": "Support Capacity Forecast and Staffing Plan",
            "readiness_status": forecast["readiness_status"],
            "capacity_score": forecast["capacity_score"],
            "demand_summary": forecast["demand_summary"],
            "queue_forecast": forecast["queue_forecast"],
            "staffing_gaps": forecast["staffing_gaps"],
            "owner_assignments": forecast["owner_assignments"],
            "staffing_actions": self._staffing_actions(forecast["staffing_gaps"]),
            "acceptance_criteria": self._acceptance_criteria(),
            "endpoint_list": CAPACITY_ENDPOINTS,
            "local_commands": CAPACITY_COMMANDS,
            "jd_skills_demonstrated": self._jd_skills(),
            "interviewer_talking_points": self._talking_points(forecast),
            "limitations": forecast["limitations"],
            "artifact_paths": {
                "capacity_plan_json": str(json_path),
                "capacity_plan_markdown": str(markdown_path),
            },
        }
        markdown = self._markdown(plan)
        self.capacity_plans_dir.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(plan, indent=2, default=str), encoding="utf-8")
        markdown_path.write_text(markdown, encoding="utf-8")
        await self.audit.record(
            AuditEvent(
                actor="capacity-planning",
                action="capacity.staffing_plan_exported",
                resource_type="capacity_plan",
                resource_id=plan_id,
                metadata={"markdown_path": str(markdown_path), "json_path": str(json_path)},
            )
        )
        return {
            "plan_id": plan_id,
            "format": "markdown+json",
            "json_path": str(json_path),
            "markdown_path": str(markdown_path),
            "readiness_status": forecast["readiness_status"],
            "capacity_score": forecast["capacity_score"],
            "plan": plan,
            "markdown": markdown,
        }

    def _scenario_tickets(self) -> list[Ticket]:
        if not self.scenarios_path.exists():
            return []
        scenarios = json.loads(self.scenarios_path.read_text(encoding="utf-8"))
        tickets = []
        for scenario in scenarios:
            ticket = Ticket(
                **TicketCreate(**scenario["ticket"]).model_dump(),
                ticket_id=f"scenario:{scenario['scenario_id']}",
            )
            expected = scenario.get("expected", {})
            ticket.tags = [*ticket.tags, f"expected:{expected.get('classification_category', '')}"]
            tickets.append(ticket)
        return tickets

    def _queue_rows(
        self,
        active_tickets: list[Ticket],
        scenario_tickets: list[Ticket],
        state: dict[str, Any],
    ) -> list[dict[str, Any]]:
        grouped: dict[str, list[tuple[Ticket, str]]] = defaultdict(list)
        for ticket in active_tickets:
            grouped[self._category(ticket)].append((ticket, "ticket_state"))
        for ticket in scenario_tickets:
            grouped[self._category(ticket)].append((ticket, "scenario_fixture"))

        rows = []
        for category in sorted(CATEGORY_TAGS):
            items = grouped.get(category, [])
            effort_minutes = sum(self._effort_minutes(ticket) for ticket, _ in items)
            active_count = len([item for item in items if item[1] == "ticket_state"])
            scenario_count = len(items) - active_count
            recent_runs = self._recent_run_count_for_category(category, state)
            projected_hours = round((effort_minutes / 60.0) + (recent_runs * 0.4), 2)
            available_fte = AVAILABLE_FTE_BY_CATEGORY[category]
            required_fte = round(projected_hours / PRODUCTIVE_HOURS_PER_FTE, 2)
            gap_fte = round(max(required_fte - available_fte, 0), 2)
            rows.append(
                {
                    "queue": category,
                    "owner": OWNER_BY_CATEGORY[category],
                    "ticket_count": len(items),
                    "active_ticket_count": active_count,
                    "scenario_ticket_count": scenario_count,
                    "recent_run_count": recent_runs,
                    "weighted_points": self._weighted_points(items),
                    "projected_effort_hours": projected_hours,
                    "available_fte": available_fte,
                    "required_fte": required_fte,
                    "capacity_gap_fte": gap_fte,
                    "status": self._queue_status(gap_fte, required_fte, available_fte),
                    "risk_drivers": self._risk_drivers(items, recent_runs, gap_fte),
                    "sample_ticket_ids": [ticket.ticket_id for ticket, _ in items[:5]],
                }
            )
        return sorted(rows, key=lambda item: (item["capacity_gap_fte"], item["weighted_points"]), reverse=True)

    def _category(self, ticket: Ticket) -> str:
        expected = next((tag.split(":", 1)[1] for tag in ticket.tags if tag.startswith("expected:")), "")
        if expected:
            return self._map_category(expected)
        text = self._normalized_text(ticket)
        scores = {
            category: sum(1 for tag in tags if tag.replace("_", " ") in text or tag in text)
            for category, tags in CATEGORY_TAGS.items()
        }
        best = max(scores, key=scores.get)
        return best if scores[best] else "general_support"

    def _map_category(self, category: str) -> str:
        return {
            "bug": "api_integrations",
            "authentication": "authentication",
            "billing": "billing",
            "api_integrations": "api_integrations",
            "security_privacy": "security_privacy",
            "incident": "incident",
            "how_to": "how_to",
            "general_support": "general_support",
        }.get(category, "general_support")

    def _normalized_text(self, ticket: Ticket) -> str:
        return re.sub(
            r"[^a-z0-9_ ]+",
            " ",
            f"{ticket.subject} {ticket.body} {' '.join(ticket.tags)}".lower(),
        )

    def _effort_minutes(self, ticket: Ticket) -> float:
        category = self._category(ticket)
        priority = str(ticket.priority)
        base = BASE_MINUTES_BY_CATEGORY[category]
        return base * PRIORITY_MULTIPLIER[priority] * TIER_MULTIPLIER[ticket.customer_tier]

    def _weighted_points(self, items: list[tuple[Ticket, str]]) -> int:
        points = 0
        for ticket, source in items:
            priority = str(ticket.priority)
            points += {"low": 1, "normal": 2, "high": 4, "urgent": 6}[priority]
            points += 2 if ticket.customer_tier == "enterprise" else 0
            points += 1 if source == "scenario_fixture" else 0
        return points

    def _recent_run_count_for_category(self, category: str, state: dict[str, Any]) -> int:
        count = 0
        for raw_run in state.get("runs", {}).values():
            run_category = raw_run.get("state", {}).get("classification", {}).get("category", "")
            if self._map_category(run_category) == category:
                count += 1
        return count

    def _queue_status(self, gap_fte: float, required_fte: float, available_fte: float) -> str:
        if gap_fte >= 0.1:
            return "capacity_gap"
        if required_fte >= available_fte * 0.85:
            return "near_capacity"
        return "covered"

    def _risk_drivers(
        self,
        items: list[tuple[Ticket, str]],
        recent_runs: int,
        gap_fte: float,
    ) -> list[str]:
        drivers = []
        urgent = len([ticket for ticket, _ in items if str(ticket.priority) == "urgent"])
        enterprise = len([ticket for ticket, _ in items if ticket.customer_tier == "enterprise"])
        if urgent:
            drivers.append(f"{urgent} urgent tickets")
        if enterprise:
            drivers.append(f"{enterprise} enterprise-tier tickets")
        if recent_runs:
            drivers.append(f"{recent_runs} recent workflow runs")
        if gap_fte:
            drivers.append(f"{gap_fte} FTE projected gap")
        return drivers or ["Local fixture demand is within available staffing model."]

    def _summary(self, rows: list[dict[str, Any]], state: dict[str, Any]) -> dict[str, Any]:
        total_hours = round(sum(row["projected_effort_hours"] for row in rows), 2)
        available_fte = round(sum(row["available_fte"] for row in rows), 2)
        required_fte = round(total_hours / PRODUCTIVE_HOURS_PER_FTE, 2)
        gap_fte = round(max(required_fte - available_fte, 0), 2)
        gap_queues = [row for row in rows if row["status"] == "capacity_gap"]
        near_capacity = [row for row in rows if row["status"] == "near_capacity"]
        score = self._capacity_score(rows, required_fte, available_fte)
        return {
            "ticket_count": sum(row["ticket_count"] for row in rows),
            "projected_weekly_tickets": sum(row["ticket_count"] for row in rows)
            + math.ceil(len(state.get("runs", {})) * 0.2),
            "projected_effort_hours": total_hours,
            "available_fte": available_fte,
            "required_fte": required_fte,
            "capacity_gap_fte": gap_fte,
            "capacity_gap_queue_count": len(gap_queues),
            "near_capacity_queue_count": len(near_capacity),
            "capacity_score": score,
            "readiness_status": self._readiness_status(score, gap_queues, near_capacity),
        }

    def _capacity_score(
        self,
        rows: list[dict[str, Any]],
        required_fte: float,
        available_fte: float,
    ) -> int:
        if required_fte == 0:
            return 100
        coverage = min(available_fte / required_fte, 1.0) * 80
        queue_health = len([row for row in rows if row["status"] == "covered"]) / max(len(rows), 1) * 20
        return round(coverage + queue_health)

    def _readiness_status(
        self,
        score: int,
        gap_queues: list[dict[str, Any]],
        near_capacity: list[dict[str, Any]],
    ) -> str:
        if gap_queues:
            return "staffing_gaps_require_owner_action"
        if score < 85 or near_capacity:
            return "review_ready_with_capacity_watchlist"
        return "ready_for_current_fixture_load"

    def _capacity_gaps(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        gaps = []
        for row in rows:
            if row["status"] == "covered":
                continue
            gaps.append(
                {
                    "gap_id": f"capacity_gap_{row['queue']}",
                    "queue": row["queue"],
                    "severity": "high" if row["capacity_gap_fte"] >= 0.25 else "medium",
                    "owner": row["owner"],
                    "capacity_gap_fte": row["capacity_gap_fte"],
                    "projected_effort_hours": row["projected_effort_hours"],
                    "risk_drivers": row["risk_drivers"],
                    "recommended_remediation": self._remediation(row),
                }
            )
        return gaps

    def _remediation(self, row: dict[str, Any]) -> list[str]:
        actions = [
            f"Assign {row['owner']} to rebalance queue coverage for `{row['queue']}`.",
            "Review active high-SLA tickets and pending approvals before the next shift handoff.",
        ]
        if row["capacity_gap_fte"]:
            actions.append(f"Add {row['capacity_gap_fte']} temporary FTE or deflect lower-risk tickets.")
        else:
            actions.append("Keep this queue on watch; it is forecast near available staffing capacity.")
        actions.append("Regenerate `POST /capacity/staffing-plan` after queue or scenario changes.")
        return actions

    def _owner_assignments(
        self,
        rows: list[dict[str, Any]],
        gaps: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        gaps_by_owner: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for gap in gaps:
            gaps_by_owner[gap["owner"]].append(gap)
        assignments = []
        for row in rows:
            owner_gaps = gaps_by_owner.get(row["owner"], [])
            assignments.append(
                {
                    "owner": row["owner"],
                    "queue": row["queue"],
                    "status": row["status"],
                    "ticket_count": row["ticket_count"],
                    "capacity_gap_fte": row["capacity_gap_fte"],
                    "next_action": self._owner_next_action(row, owner_gaps),
                }
            )
        return assignments

    def _owner_next_action(self, row: dict[str, Any], gaps: list[dict[str, Any]]) -> str:
        if gaps:
            return f"Close {gaps[0]['gap_id']} by adding coverage or deflecting low-risk work."
        if row["status"] == "near_capacity":
            return "Monitor backlog, approvals, and SLA clocks during the next handoff."
        return "Maintain current staffing coverage and watch for fixture or run volume changes."

    def _staffing_actions(self, gaps: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not gaps:
            return [
                {
                    "task_id": "capacity_task_01",
                    "owner": "Support Operations",
                    "priority": "low",
                    "queue": "all",
                    "actions": ["Keep capacity planning in the demo run and review after fixture changes."],
                }
            ]
        return [
            {
                "task_id": f"capacity_task_{index:02d}",
                "owner": gap["owner"],
                "priority": gap["severity"],
                "queue": gap["queue"],
                "actions": gap["recommended_remediation"],
            }
            for index, gap in enumerate(gaps, start=1)
        ]

    def _acceptance_criteria(self) -> list[str]:
        return [
            "Every queue has an explicit owner, available FTE, required FTE, and capacity status.",
            "High-risk queues have owner actions before increasing automation or support volume.",
            "The staffing plan exports Markdown/JSON under ignored local artifacts.",
            "Dashboard, demo, API, and tests exercise the local deterministic capacity surface.",
        ]

    def _jd_skills(self) -> list[str]:
        return [
            "Production-style operations analytics for AI-assisted support queues.",
            "FastAPI endpoint design with local-only deterministic forecasting and artifacts.",
            "Human operations governance that connects queue load, SLA risk, owners, and approvals.",
            "Portfolio-ready demo output, dashboard wiring, tests, docs, and generated evidence.",
        ]

    def _talking_points(self, forecast: dict[str, Any]) -> list[str]:
        summary = forecast["demand_summary"]
        return [
            (
                f"Capacity score is {summary['capacity_score']} across "
                f"{summary['ticket_count']} active and scenario tickets."
            ),
            "The forecast separates queue demand from available FTE so staffing gaps are explicit.",
            "Owner assignments connect support load to concrete operational follow-up.",
            "The plan is local/mock only and can be regenerated without Zendesk, Jira, Slack, or BI tools.",
            "This hardens the project beyond triage by showing how AI support operations scale safely.",
        ]

    def _limitations(self) -> list[str]:
        return [
            "Capacity estimates are deterministic portfolio assumptions over local fixtures and run state.",
            "Available FTE values are illustrative defaults, not real workforce schedules.",
            "The forecast does not call workforce management, HR, BI, CRM, Zendesk, Jira, Slack, Azure, or OpenAI.",
            "Production use would require calibrated handle-time data, shift schedules, holidays, and arrival rates.",
        ]

    def _markdown(self, plan: dict[str, Any]) -> str:
        summary = plan["demand_summary"]
        queue_rows = [
            (
                f"| {row['queue']} | {row['status']} | {row['ticket_count']} | "
                f"{row['projected_effort_hours']} | {row['available_fte']} | "
                f"{row['required_fte']} | {row['capacity_gap_fte']} | {row['owner']} |"
            )
            for row in plan["queue_forecast"]
        ]
        gap_rows = [
            (
                f"| {gap['gap_id']} | {gap['severity']} | {gap['owner']} | "
                f"{gap['capacity_gap_fte']} | {'; '.join(gap['risk_drivers'])} |"
            )
            for gap in plan["staffing_gaps"]
        ] or ["| None | none | Support Operations | 0 | No open capacity gaps |"]
        action_rows = [
            (
                f"- {task['task_id']} | {task['priority']} | {task['owner']} | "
                f"{task['queue']}: {'; '.join(task['actions'])}"
            )
            for task in plan["staffing_actions"]
        ]
        endpoints = [f"- `{endpoint}`" for endpoint in plan["endpoint_list"]]
        commands = [f"- `{command}`" for command in plan["local_commands"]]
        criteria = [f"- {item}" for item in plan["acceptance_criteria"]]
        skills = [f"- {item}" for item in plan["jd_skills_demonstrated"]]
        talking_points = [f"- {item}" for item in plan["interviewer_talking_points"]]
        limitations = [f"- {item}" for item in plan["limitations"]]
        return "\n".join(
            [
                f"# Support Capacity Forecast and Staffing Plan: {plan['plan_id']}",
                "",
                "## Summary",
                f"- Status: {plan['readiness_status']}",
                f"- Capacity score: {plan['capacity_score']}",
                f"- Projected weekly tickets: {summary['projected_weekly_tickets']}",
                f"- Projected effort hours: {summary['projected_effort_hours']}",
                f"- Required FTE: {summary['required_fte']}",
                f"- Available FTE: {summary['available_fte']}",
                f"- Capacity gap FTE: {summary['capacity_gap_fte']}",
                "",
                "## Queue Forecast",
                "| Queue | Status | Tickets | Hours | Available FTE | Required FTE | Gap FTE | Owner |",
                "| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |",
                *queue_rows,
                "",
                "## Staffing Gaps",
                "| Gap | Severity | Owner | Gap FTE | Risk Drivers |",
                "| --- | --- | --- | ---: | --- |",
                *gap_rows,
                "",
                "## Staffing Actions",
                *action_rows,
                "",
                "## Acceptance Criteria",
                *criteria,
                "",
                "## Endpoints",
                *endpoints,
                "",
                "## Local Commands",
                *commands,
                "",
                "## JD Skills Demonstrated",
                *skills,
                "",
                "## Interviewer Talking Points",
                *talking_points,
                "",
                "## Limitations",
                *limitations,
                "",
            ]
        )
