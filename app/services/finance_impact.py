import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.storage import JsonStateStore
from app.models import AuditEvent, RunRecord, Ticket, TicketCreate, TicketPriority
from app.services.approvals import ApprovalService
from app.services.audit import AuditService
from app.services.customers import CustomerHealthService
from app.services.tickets import TicketService
from app.services.trace import TraceService
from app.services.workflow import AgentWorkflowService


SAMPLE_FINANCE_TICKET = TicketCreate(
    external_id="finance-impact-sample-enterprise-sso-outage",
    subject="Finance Impact sample: enterprise SSO outage with renewal risk",
    body=(
        "Northstar Health production SAML SSO is unavailable for all support agents. "
        "The customer reports active revenue-impacting work is blocked, SLA breach risk is high, "
        "and their renewal sponsor asked for executive visibility."
    ),
    customer="Northstar Health",
    customer_email="ops@northstar.example",
    priority=TicketPriority.urgent,
    customer_tier="enterprise",
    tags=["finance-impact", "auth", "sso", "outage", "sla", "renewal"],
)


FINANCE_COMMANDS = [
    r".\.venv\Scripts\python.exe -m pytest -q",
    r".\.venv\Scripts\python.exe -m ruff check app tests dashboard scripts",
    r".\.venv\Scripts\python.exe -m app.evals.run_eval",
    r".\.venv\Scripts\python.exe scripts\dashboard_smoke.py",
    r".\.venv\Scripts\python.exe scripts\demo_run.py",
    (
        r'rg "finance/impact-summary|finance/impact-pack|Finance Impact|'
        r'finance_impact_packs|ARR at risk" app dashboard docs README.md tests scripts'
    ),
]


class FinanceImpactService:
    def __init__(
        self,
        store: JsonStateStore,
        tickets: TicketService,
        workflow: AgentWorkflowService,
        trace: TraceService,
        approvals: ApprovalService,
        customers: CustomerHealthService,
        audit: AuditService,
        customers_path: Path,
        finance_impact_dir: Path,
    ):
        self.store = store
        self.tickets = tickets
        self.workflow = workflow
        self.trace = trace
        self.approvals = approvals
        self.customers = customers
        self.audit = audit
        self.customers_path = customers_path
        self.finance_impact_dir = finance_impact_dir

    async def impact_summary(self, run_id: str | None = None) -> dict[str, Any]:
        run, fallback_used = await self._resolve_run(run_id)
        ticket = await self._ticket_for_run(run)
        state = await self.store.load()
        trace = await self.trace.list_events(run.run_id)
        approvals = [
            item
            for item in state["approvals"].values()
            if item.get("run_id") == run.run_id
        ]
        outbox = [
            item
            for item in state["outbox"].values()
            if item.get("run_id") == run.run_id
        ]
        customer_health = await self.customers.health()
        account = self._account_context(ticket, customer_health["customers"])
        assumptions = self._assumptions(ticket, account)
        support_cost = self._support_cost(ticket, run, trace, approvals, assumptions)
        sla_penalty = self._sla_penalty(ticket, run, assumptions)
        engineering_effort = self._engineering_effort(ticket, run, trace, outbox, assumptions)
        arr_at_risk = self._arr_at_risk(ticket, run, account, assumptions)
        totals = self._totals(support_cost, sla_penalty, engineering_effort, arr_at_risk)
        risk_flags = self._risk_flags(ticket, run, account, totals)
        summary = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "mode": "local-deterministic-finance-impact",
            "local_mock_only": True,
            "run_id": run.run_id,
            "ticket_id": ticket.ticket_id,
            "trace_id": run.trace_id,
            "fallback_used": fallback_used,
            "customer": account["account"],
            "ticket_context": self._ticket_context(ticket, run, trace, approvals, outbox),
            "customer_context": account,
            "assumptions": assumptions,
            "support_cost": support_cost,
            "sla_penalty_exposure": sla_penalty,
            "engineering_effort": engineering_effort,
            "customer_arr_at_risk": arr_at_risk,
            "finance_rollup": totals,
            "risk_flags": risk_flags,
            "recommended_actions": self._recommended_actions(risk_flags, totals, run),
            "dashboard_metrics": self._dashboard_metrics(totals, support_cost, engineering_effort, arr_at_risk),
            "local_commands": FINANCE_COMMANDS,
            "limitations": self._limitations(),
        }
        summary["executive_summary"] = self._executive_summary(summary)
        return summary

    async def export_impact_pack(self, run_id: str | None = None) -> dict[str, Any]:
        summary = await self.impact_summary(run_id)
        generated_at = datetime.now(timezone.utc)
        pack_id = f"finance_impact_{generated_at.strftime('%Y%m%d_%H%M%S')}_{summary['run_id']}"
        json_path = self.finance_impact_dir / f"{pack_id}.json"
        markdown_path = self.finance_impact_dir / f"{pack_id}.md"
        pack = {
            "pack_id": pack_id,
            "generated_at": generated_at.isoformat(),
            "title": "Escalation Finance Impact Pack",
            "impact_summary": summary,
            "executive_decision_table": self._decision_table(summary),
            "finance_controls": self._finance_controls(summary),
            "artifact_paths": {
                "finance_impact_markdown": str(markdown_path),
                "finance_impact_json": str(json_path),
            },
        }
        markdown = self._markdown(pack)
        self.finance_impact_dir.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(pack, indent=2, default=str), encoding="utf-8")
        markdown_path.write_text(markdown, encoding="utf-8")
        await self.audit.record(
            AuditEvent(
                actor="finance-impact",
                action="finance.impact_pack_exported",
                resource_type="run",
                resource_id=summary["run_id"],
                trace_id=summary["trace_id"],
                metadata={"markdown_path": str(markdown_path), "json_path": str(json_path)},
            )
        )
        return {
            "pack_id": pack_id,
            "format": "markdown+json",
            "run_id": summary["run_id"],
            "ticket_id": summary["ticket_id"],
            "readiness_status": summary["finance_rollup"]["readiness_status"],
            "estimated_financial_exposure_usd": summary["finance_rollup"]["estimated_financial_exposure_usd"],
            "json_path": str(json_path),
            "markdown_path": str(markdown_path),
            "pack": pack,
            "markdown": markdown,
        }

    async def _resolve_run(self, run_id: str | None) -> tuple[RunRecord, str]:
        if run_id:
            return await self.workflow.get_run(run_id), "supplied_run"
        state = await self.store.load()
        runs = list(state["runs"].values())
        if runs:
            return RunRecord(**sorted(runs, key=lambda item: item.get("started_at", ""))[-1]), "latest_run"

        ticket = await self.tickets.get_by_external_id(SAMPLE_FINANCE_TICKET.external_id or "")
        if ticket is None:
            ticket = await self.tickets.ingest(SAMPLE_FINANCE_TICKET)
        run = await self.workflow.analyze_ticket(ticket.ticket_id)
        run = await self.workflow.approve(
            run.run_id,
            "finance-impact-sample",
            "Approved sample incident so finance impact includes dispatched local handoffs.",
        )
        return run, "sample_bootstrap"

    async def _ticket_for_run(self, run: RunRecord) -> Ticket:
        ticket = await self.tickets.get(run.ticket_id)
        if ticket is None:
            raise KeyError(run.ticket_id)
        return ticket

    def _account_context(self, ticket: Ticket, customers: list[dict[str, Any]]) -> dict[str, Any]:
        account_name = ticket.customer or ticket.account or self._customer_from_email(ticket.customer_email)
        account_slug = self._slug(account_name)
        health = next(
            (
                item
                for item in customers
                if self._slug(item["account"]) == account_slug or self._slug(item["customer"]) == account_slug
            ),
            None,
        )
        metadata = self._customer_metadata().get(self._slug(account_name), {})
        tier = metadata.get("tier") or ticket.customer_tier
        arr_usd = int(metadata.get("arr_usd") or self._default_arr(ticket.customer_tier, tier))
        return {
            "customer_id": account_slug,
            "account": metadata.get("customer", account_name),
            "segment": metadata.get("segment", "unknown"),
            "tier": tier,
            "region": metadata.get("region", "unknown"),
            "arr_usd": arr_usd,
            "monthly_arr_usd": round(arr_usd / 12, 2),
            "health_score": health.get("health_score", 78) if health else 78,
            "risk_level": health.get("risk_level", "watch") if health else "watch",
            "recommended_action": health.get("recommended_action", "Review with customer success.") if health else "Review with customer success.",
        }

    def _assumptions(self, ticket: Ticket, account: dict[str, Any]) -> dict[str, Any]:
        return {
            "source": "local deterministic assumptions; not pulled from CRM, billing, contracts, or finance systems",
            "support_blended_hourly_rate_usd": 85,
            "engineering_blended_hourly_rate_usd": 140,
            "sla_credit_percent_by_risk": {"low": 0.005, "medium": 0.02, "high": 0.08},
            "arr_risk_percent_by_sla": {"low": 0.05, "medium": 0.15, "high": 0.35},
            "tier_arr_fallbacks_usd": {"standard": 18000, "pro": 72000, "enterprise": 240000},
            "metadata_arr_used": account["arr_usd"],
            "ticket_priority": str(ticket.priority),
            "customer_tier": ticket.customer_tier,
        }

    def _support_cost(
        self,
        ticket: Ticket,
        run: RunRecord,
        trace: list[Any],
        approvals: list[dict[str, Any]],
        assumptions: dict[str, Any],
    ) -> dict[str, Any]:
        sla = run.state.get("sla_risk", {})
        priority_minutes = {"low": 25, "normal": 45, "high": 75, "urgent": 120}.get(str(ticket.priority), 45)
        sla_minutes = {"low": 15, "medium": 45, "high": 90}.get(sla.get("level", "low"), 15)
        approval_minutes = 30 if any(item.get("status") == "pending" for item in approvals) else 15
        failure_minutes = 45 if run.failure_state else 0
        trace_minutes = min(90, len(trace) * 3)
        total_minutes = priority_minutes + sla_minutes + approval_minutes + failure_minutes + trace_minutes
        hourly = assumptions["support_blended_hourly_rate_usd"]
        return {
            "estimated_minutes": total_minutes,
            "blended_hourly_rate_usd": hourly,
            "estimated_cost_usd": round((total_minutes / 60) * hourly, 2),
            "components": [
                {"name": "priority_handling", "minutes": priority_minutes},
                {"name": "sla_coordination", "minutes": sla_minutes},
                {"name": "approval_or_dispatch_review", "minutes": approval_minutes},
                {"name": "failure_validation", "minutes": failure_minutes},
                {"name": "trace_and_handoff_review", "minutes": trace_minutes},
            ],
        }

    def _sla_penalty(
        self,
        ticket: Ticket,
        run: RunRecord,
        assumptions: dict[str, Any],
    ) -> dict[str, Any]:
        sla = run.state.get("sla_risk", {})
        level = sla.get("level", "low")
        monthly_arr = assumptions["metadata_arr_used"] / 12
        pct = assumptions["sla_credit_percent_by_risk"].get(level, 0.005)
        priority_multiplier = 1.25 if ticket.priority == TicketPriority.urgent else 1.0
        exposure = monthly_arr * pct * priority_multiplier
        cap = min(monthly_arr * 0.12, 50000)
        return {
            "risk_level": level,
            "sla_score": sla.get("score", 0),
            "credit_percent": pct,
            "priority_multiplier": priority_multiplier,
            "estimated_penalty_exposure_usd": round(min(exposure, cap), 2),
            "contractual_cap_usd": round(cap, 2),
            "reasons": sla.get("reasons", []),
        }

    def _engineering_effort(
        self,
        ticket: Ticket,
        run: RunRecord,
        trace: list[Any],
        outbox: list[dict[str, Any]],
        assumptions: dict[str, Any],
    ) -> dict[str, Any]:
        state = run.state
        category = state.get("classification", {}).get("category", "unknown")
        sla_level = state.get("sla_risk", {}).get("level", "low")
        base_hours = {
            "authentication": 10,
            "bug": 12,
            "incident": 14,
            "billing": 3,
            "privacy": 8,
            "how_to": 2,
        }.get(category, 6)
        severity_hours = {"low": 1, "medium": 4, "high": 10}.get(sla_level, 1)
        dispatch_hours = 3 if any(item.get("action_type") in {"jira_issue", "engineering_escalation"} for item in outbox) else 1
        failure_hours = 4 if run.failure_state else 0
        trace_review_hours = min(4, round(len(trace) / 12, 1))
        total_hours = round(base_hours + severity_hours + dispatch_hours + failure_hours + trace_review_hours, 1)
        hourly = assumptions["engineering_blended_hourly_rate_usd"]
        roles = self._engineering_roles(category, sla_level)
        return {
            "category": category,
            "estimated_hours": total_hours,
            "blended_hourly_rate_usd": hourly,
            "estimated_cost_usd": round(total_hours * hourly, 2),
            "roles": roles,
            "components": [
                {"name": "category_baseline", "hours": base_hours},
                {"name": "sla_severity", "hours": severity_hours},
                {"name": "handoff_and_acknowledgement", "hours": dispatch_hours},
                {"name": "failure_validation", "hours": failure_hours},
                {"name": "trace_review", "hours": trace_review_hours},
            ],
        }

    def _arr_at_risk(
        self,
        ticket: Ticket,
        run: RunRecord,
        account: dict[str, Any],
        assumptions: dict[str, Any],
    ) -> dict[str, Any]:
        sla_level = run.state.get("sla_risk", {}).get("level", "low")
        base_pct = assumptions["arr_risk_percent_by_sla"].get(sla_level, 0.05)
        health_lift = {"critical": 0.25, "at_risk": 0.15, "watch": 0.05, "healthy": 0.0}.get(
            account["risk_level"],
            0.05,
        )
        tier_lift = 0.1 if ticket.customer_tier == "enterprise" else 0.03 if ticket.customer_tier == "pro" else 0
        renewal_lift = 0.1 if self._contains_any(ticket.body, {"renewal", "executive", "sponsor", "churn"}) else 0
        risk_pct = min(0.8, base_pct + health_lift + tier_lift + renewal_lift)
        return {
            "arr_usd": account["arr_usd"],
            "risk_percent": round(risk_pct, 3),
            "arr_at_risk_usd": round(account["arr_usd"] * risk_pct, 2),
            "drivers": [
                {"name": "sla_risk", "value": sla_level, "risk_lift": base_pct},
                {"name": "account_health", "value": account["risk_level"], "risk_lift": health_lift},
                {"name": "customer_tier", "value": ticket.customer_tier, "risk_lift": tier_lift},
                {"name": "renewal_or_executive_language", "value": bool(renewal_lift), "risk_lift": renewal_lift},
            ],
        }

    def _totals(
        self,
        support_cost: dict[str, Any],
        sla_penalty: dict[str, Any],
        engineering_effort: dict[str, Any],
        arr_at_risk: dict[str, Any],
    ) -> dict[str, Any]:
        direct_cost = (
            support_cost["estimated_cost_usd"]
            + sla_penalty["estimated_penalty_exposure_usd"]
            + engineering_effort["estimated_cost_usd"]
        )
        exposure = direct_cost + arr_at_risk["arr_at_risk_usd"]
        status = "finance_review_required" if exposure >= 100000 else "manager_review" if exposure >= 25000 else "standard_followup"
        return {
            "estimated_direct_cost_usd": round(direct_cost, 2),
            "estimated_financial_exposure_usd": round(exposure, 2),
            "arr_at_risk_usd": arr_at_risk["arr_at_risk_usd"],
            "direct_cost_excludes_arr_risk": True,
            "readiness_status": status,
        }

    def _risk_flags(
        self,
        ticket: Ticket,
        run: RunRecord,
        account: dict[str, Any],
        totals: dict[str, Any],
    ) -> list[str]:
        flags = []
        if ticket.customer_tier == "enterprise":
            flags.append("enterprise_account")
        if run.state.get("sla_risk", {}).get("level") == "high":
            flags.append("high_sla_penalty_exposure")
        if account["risk_level"] in {"critical", "at_risk"}:
            flags.append("customer_health_at_risk")
        if totals["arr_at_risk_usd"] >= 75000:
            flags.append("material_arr_at_risk")
        if run.failure_state:
            flags.append("workflow_failure_increases_human_cost")
        if run.status == "awaiting_approval":
            flags.append("pending_approval_extends_exposure")
        return flags or ["standard_finance_monitoring"]

    def _recommended_actions(
        self,
        flags: list[str],
        totals: dict[str, Any],
        run: RunRecord,
    ) -> list[dict[str, str]]:
        actions = []
        if "material_arr_at_risk" in flags or totals["readiness_status"] == "finance_review_required":
            actions.append(
                {
                    "owner": "Customer Success Director",
                    "action": "Add ARR exposure and customer sponsor status to the executive incident update.",
                }
            )
        if "high_sla_penalty_exposure" in flags:
            actions.append(
                {
                    "owner": "Support Lead",
                    "action": "Confirm SLA clock, mitigation ETA, and whether contract credit language is allowed.",
                }
            )
        if run.status == "awaiting_approval":
            actions.append(
                {
                    "owner": "Approver",
                    "action": "Clear or reject the pending approval before the next customer update timer.",
                }
            )
        actions.append(
            {
                "owner": "Engineering Manager",
                "action": "Validate estimated engineering hours and assign a named mitigation owner.",
            }
        )
        actions.append(
            {
                "owner": "Finance Partner",
                "action": "Treat these numbers as local estimates until contract and CRM data are verified.",
            }
        )
        return actions

    def _dashboard_metrics(
        self,
        totals: dict[str, Any],
        support_cost: dict[str, Any],
        engineering_effort: dict[str, Any],
        arr_at_risk: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "estimated_financial_exposure_usd": totals["estimated_financial_exposure_usd"],
            "direct_cost_usd": totals["estimated_direct_cost_usd"],
            "arr_at_risk_usd": arr_at_risk["arr_at_risk_usd"],
            "support_minutes": support_cost["estimated_minutes"],
            "engineering_hours": engineering_effort["estimated_hours"],
            "readiness_status": totals["readiness_status"],
        }

    def _ticket_context(
        self,
        ticket: Ticket,
        run: RunRecord,
        trace: list[Any],
        approvals: list[dict[str, Any]],
        outbox: list[dict[str, Any]],
    ) -> dict[str, Any]:
        state = run.state
        return {
            "subject": ticket.subject,
            "priority": ticket.priority,
            "status": ticket.status,
            "customer_tier": ticket.customer_tier,
            "classification": state.get("classification", {}),
            "sla_risk": state.get("sla_risk", {}),
            "run_status": run.status,
            "final_action": run.final_action,
            "trace_event_count": len(trace),
            "approval_count": len(approvals),
            "pending_approval_count": len([item for item in approvals if item.get("status") == "pending"]),
            "outbox_dispatch_count": len(outbox),
            "failure_state": run.failure_state,
        }

    def _decision_table(self, summary: dict[str, Any]) -> list[dict[str, Any]]:
        return [
            {
                "decision": "Customer update cadence",
                "finance_signal": summary["sla_penalty_exposure"]["estimated_penalty_exposure_usd"],
                "recommendation": "Increase cadence if SLA exposure is high or approval remains pending.",
            },
            {
                "decision": "Engineering resource allocation",
                "finance_signal": summary["engineering_effort"]["estimated_hours"],
                "recommendation": "Assign named engineering owner when estimated effort exceeds one work day.",
            },
            {
                "decision": "Executive escalation",
                "finance_signal": summary["customer_arr_at_risk"]["arr_at_risk_usd"],
                "recommendation": "Escalate to account leadership when material ARR is at risk.",
            },
        ]

    def _finance_controls(self, summary: dict[str, Any]) -> list[dict[str, str]]:
        return [
            {
                "control": "Local-only estimate",
                "evidence": summary["assumptions"]["source"],
            },
            {
                "control": "Direct cost separated from ARR risk",
                "evidence": str(summary["finance_rollup"]["direct_cost_excludes_arr_risk"]),
            },
            {
                "control": "Human approval remains authoritative",
                "evidence": summary["ticket_context"]["run_status"],
            },
        ]

    def _executive_summary(self, summary: dict[str, Any]) -> str:
        rollup = summary["finance_rollup"]
        return (
            f"{summary['customer']} has estimated direct escalation cost of "
            f"${rollup['estimated_direct_cost_usd']:,.2f} and estimated financial exposure of "
            f"${rollup['estimated_financial_exposure_usd']:,.2f}, including "
            f"${rollup['arr_at_risk_usd']:,.2f} ARR at risk. Finance status is "
            f"`{rollup['readiness_status']}`."
        )

    def _markdown(self, pack: dict[str, Any]) -> str:
        summary = pack["impact_summary"]
        rollup = summary["finance_rollup"]
        support_components = [
            f"- {item['name']}: {item['minutes']} minutes"
            for item in summary["support_cost"]["components"]
        ]
        engineering_components = [
            f"- {item['name']}: {item['hours']} hours"
            for item in summary["engineering_effort"]["components"]
        ]
        arr_drivers = [
            f"- {item['name']}: {item['value']} (lift {item['risk_lift']})"
            for item in summary["customer_arr_at_risk"]["drivers"]
        ]
        decisions = [
            f"- {item['decision']}: {item['recommendation']} (signal: {item['finance_signal']})"
            for item in pack["executive_decision_table"]
        ]
        actions = [
            f"- {item['owner']}: {item['action']}"
            for item in summary["recommended_actions"]
        ]
        controls = [
            f"- {item['control']}: {item['evidence']}"
            for item in pack["finance_controls"]
        ]
        commands = [f"- `{command}`" for command in summary["local_commands"]]
        limitations = [f"- {item}" for item in summary["limitations"]]
        return "\n".join(
            [
                f"# Escalation Finance Impact Pack: {pack['pack_id']}",
                "",
                "## Executive Summary",
                summary["executive_summary"],
                "",
                "## Finance Rollup",
                f"- Direct cost: ${rollup['estimated_direct_cost_usd']:,.2f}",
                f"- Financial exposure: ${rollup['estimated_financial_exposure_usd']:,.2f}",
                f"- ARR at risk: ${rollup['arr_at_risk_usd']:,.2f}",
                f"- Status: {rollup['readiness_status']}",
                "",
                "## Support Cost",
                f"- Estimated cost: ${summary['support_cost']['estimated_cost_usd']:,.2f}",
                f"- Estimated minutes: {summary['support_cost']['estimated_minutes']}",
                *support_components,
                "",
                "## SLA Penalty Exposure",
                f"- Estimated exposure: ${summary['sla_penalty_exposure']['estimated_penalty_exposure_usd']:,.2f}",
                f"- Contractual cap: ${summary['sla_penalty_exposure']['contractual_cap_usd']:,.2f}",
                f"- Risk level: {summary['sla_penalty_exposure']['risk_level']}",
                "",
                "## Engineering Effort",
                f"- Estimated cost: ${summary['engineering_effort']['estimated_cost_usd']:,.2f}",
                f"- Estimated hours: {summary['engineering_effort']['estimated_hours']}",
                f"- Roles: {', '.join(summary['engineering_effort']['roles'])}",
                *engineering_components,
                "",
                "## Customer ARR At Risk",
                f"- ARR: ${summary['customer_arr_at_risk']['arr_usd']:,.2f}",
                f"- Risk percent: {summary['customer_arr_at_risk']['risk_percent']}",
                f"- ARR at risk: ${summary['customer_arr_at_risk']['arr_at_risk_usd']:,.2f}",
                *arr_drivers,
                "",
                "## Executive Decision Table",
                *decisions,
                "",
                "## Recommended Actions",
                *actions,
                "",
                "## Finance Controls",
                *controls,
                "",
                "## Risk Flags",
                *[f"- {flag}" for flag in summary["risk_flags"]],
                "",
                "## Local Verification Commands",
                *commands,
                "",
                "## Limitations",
                *limitations,
                "",
            ]
        )

    def _engineering_roles(self, category: str, sla_level: str) -> list[str]:
        roles = ["Engineering Manager"]
        if category in {"authentication", "incident"}:
            roles.extend(["Backend Engineer", "SRE"])
        elif category == "bug":
            roles.extend(["Backend Engineer", "QA Engineer"])
        elif category == "privacy":
            roles.extend(["Security Engineer", "Support Engineer"])
        else:
            roles.append("Support Engineer")
        if sla_level == "high":
            roles.append("Incident Commander")
        return list(dict.fromkeys(roles))

    def _customer_metadata(self) -> dict[str, dict[str, Any]]:
        if not self.customers_path.exists():
            return {}
        rows = json.loads(self.customers_path.read_text(encoding="utf-8"))
        return {self._slug(item["customer"]): item for item in rows}

    def _default_arr(self, customer_tier: str, metadata_tier: str) -> int:
        if metadata_tier == "growth":
            return 48000
        return {"standard": 18000, "pro": 72000, "enterprise": 240000}.get(customer_tier, 18000)

    def _limitations(self) -> list[str]:
        return [
            "Finance values are local deterministic estimates for portfolio review, not contract or billing records.",
            "ARR uses sample customer metadata or tier fallbacks when no CRM data exists.",
            "SLA penalty exposure is a modeled credit estimate and must be validated against customer contracts.",
            "Engineering effort is blended-role planning input; it is not a staffing commitment.",
            "The pack does not call Azure, OpenAI, Zendesk, Jira, Slack, CRM, billing, finance, or external services.",
        ]

    def _customer_from_email(self, email: str) -> str:
        domain = email.split("@")[-1].split(".")[0] if "@" in email else email
        return domain.replace("-", " ").replace("_", " ").title() or "Unknown Account"

    def _slug(self, value: str) -> str:
        return "".join(char if char.isalnum() else "-" for char in value.lower()).strip("-")

    def _contains_any(self, value: str, terms: set[str]) -> bool:
        lowered = value.lower()
        return any(term in lowered for term in terms)
