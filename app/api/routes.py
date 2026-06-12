import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.core.config import Settings, get_settings
from app.core.security import require_api_key
from app.models import (
    ApprovalDecision,
    AuditEvent,
    FinanceImpactRequest,
    IncidentNarrativeRequest,
    PolicyChangePackRequest,
    PolicyChangeSimulationRequest,
    PolicyExportRequest,
    PolicyRolloutPackRequest,
    PolicyRolloutRequest,
    PolicySimulationRequest,
    PlaybookRecommendRequest,
    RemediationChecklistRequest,
    ReplayLabReportRequest,
    ReplayLabRunRequest,
    ReplayModifiers,
    RunbookQaRequest,
    TicketCreate,
)
from app.services.factory import ServiceContainer

router = APIRouter()


def get_container(request: Request) -> ServiceContainer:
    return request.app.state.container


@router.get("/health")
async def health(request: Request):
    container = get_container(request)
    return {
        "status": "ok",
        "service": "support-escalation-agent-control-tower",
        "langgraph_available": getattr(container.workflow, "graph", None) is not None,
    }


@router.post("/auth/demo-token")
async def demo_token(settings: Settings = Depends(get_settings)):
    return {"token_type": "Bearer", "access_token": settings.demo_api_key, "token": settings.demo_api_key}


@router.post("/tickets/ingest", dependencies=[Depends(require_api_key)])
async def ingest_ticket(payload: TicketCreate, request: Request):
    container = get_container(request)
    ticket = await container.tickets.ingest(payload)
    await container.audit.record(
        AuditEvent(
            actor="api",
            action="ticket.ingested",
            resource_type="ticket",
            resource_id=ticket.ticket_id,
            metadata={"subject": ticket.subject},
        )
    )
    return ticket


@router.post("/tickets/ingest-samples", dependencies=[Depends(require_api_key)])
async def ingest_samples(request: Request):
    rows = json.loads(Path("sample_data/tickets.json").read_text(encoding="utf-8"))
    tickets = [await get_container(request).tickets.ingest(TicketCreate(**row)) for row in rows]
    return {"ingested": len(tickets), "tickets": tickets}


@router.get("/tickets", dependencies=[Depends(require_api_key)])
async def list_tickets(request: Request):
    return await get_container(request).tickets.list()


@router.post("/playbooks/recommend", dependencies=[Depends(require_api_key)])
async def recommend_playbooks(payload: PlaybookRecommendRequest, request: Request):
    try:
        return await get_container(request).playbooks.recommend(
            ticket_id=payload.ticket_id,
            ticket_payload=payload.ticket,
            top_n=payload.top_n,
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="ticket_id or ticket payload is required",
        ) from None
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found") from None


@router.post("/tickets/{ticket_id}/analyze", dependencies=[Depends(require_api_key)])
async def analyze_ticket(ticket_id: str, request: Request):
    try:
        return await get_container(request).workflow.analyze_ticket(ticket_id)
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found") from None


@router.get("/runs/{run_id}", dependencies=[Depends(require_api_key)])
async def get_run(run_id: str, request: Request):
    try:
        return await get_container(request).workflow.get_run(run_id)
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found") from None


@router.get("/runs/{run_id}/trace", dependencies=[Depends(require_api_key)])
async def trace(run_id: str, request: Request):
    return await get_container(request).trace.list_events(run_id)


@router.post("/runs/{run_id}/replay-lab", dependencies=[Depends(require_api_key)])
async def replay_run(run_id: str, request: Request, payload: ReplayLabRunRequest | None = None):
    try:
        modifiers = payload.modifiers if payload else ReplayModifiers()
        return await get_container(request).replay_lab.replay(run_id, modifiers)
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found") from None


@router.post("/replay-lab/run", dependencies=[Depends(require_api_key)])
async def replay_lab_run(request: Request, payload: ReplayLabRunRequest | None = None):
    try:
        return await get_container(request).replay_lab.replay(
            payload.run_id if payload else None,
            payload.modifiers if payload else ReplayModifiers(),
        )
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found") from None


@router.post("/replay-lab/report", dependencies=[Depends(require_api_key)])
async def replay_lab_report(request: Request, payload: ReplayLabReportRequest | None = None):
    try:
        return await get_container(request).replay_lab.export_report(
            payload.run_id if payload else None,
            payload.modifiers if payload else ReplayModifiers(),
        )
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found") from None


@router.post("/policies/simulate", dependencies=[Depends(require_api_key)])
async def policy_simulate(request: Request, payload: PolicySimulationRequest | None = None):
    try:
        return await get_container(request).policy_guardrails.simulate(payload)
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found") from None


@router.post("/policies/export", dependencies=[Depends(require_api_key)])
async def policy_export(request: Request, payload: PolicyExportRequest | None = None):
    try:
        return await get_container(request).policy_guardrails.export_pack(payload)
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found") from None


@router.post("/policies/change-simulation", dependencies=[Depends(require_api_key)])
async def policy_change_simulation(
    request: Request,
    payload: PolicyChangeSimulationRequest | None = None,
):
    return await get_container(request).policy_change_simulation.simulate(payload)


@router.post("/policies/change-pack", dependencies=[Depends(require_api_key)])
async def policy_change_pack(
    request: Request,
    payload: PolicyChangePackRequest | None = None,
):
    return await get_container(request).policy_change_simulation.export_pack(payload)


@router.post("/policies/rollout-plan", dependencies=[Depends(require_api_key)])
async def policy_rollout_plan(
    request: Request,
    payload: PolicyRolloutRequest | None = None,
):
    return await get_container(request).policy_rollout.rollout_plan(payload)


@router.post("/policies/rollout-pack", dependencies=[Depends(require_api_key)])
async def policy_rollout_pack(
    request: Request,
    payload: PolicyRolloutPackRequest | None = None,
):
    return await get_container(request).policy_rollout.export_pack(payload)


@router.post("/incidents/timeline", dependencies=[Depends(require_api_key)])
async def incident_timeline(request: Request, payload: IncidentNarrativeRequest | None = None):
    try:
        return await get_container(request).incident_narratives.timeline(payload.run_id if payload else None)
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found") from None


@router.post("/incidents/executive-narrative", dependencies=[Depends(require_api_key)])
async def executive_incident_narrative(
    request: Request,
    payload: IncidentNarrativeRequest | None = None,
):
    try:
        return await get_container(request).incident_narratives.export_executive_narrative(
            payload.run_id if payload else None
        )
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found") from None


@router.get("/incidents/postmortem-summary", dependencies=[Depends(require_api_key)])
async def postmortem_summary(request: Request):
    return await get_container(request).postmortem_rca.postmortem_summary()


@router.post("/incidents/rca-pack", dependencies=[Depends(require_api_key)])
async def rca_pack(request: Request, payload: IncidentNarrativeRequest | None = None):
    try:
        return await get_container(request).postmortem_rca.export_rca_pack(payload.run_id if payload else None)
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found") from None


@router.get("/incidents/postmortem-review-board", dependencies=[Depends(require_api_key)])
async def postmortem_review_board(request: Request, run_id: str | None = None):
    try:
        return await get_container(request).postmortem_review.review_board(run_id)
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found") from None


@router.post("/incidents/postmortem-review-pack", dependencies=[Depends(require_api_key)])
async def postmortem_review_pack(request: Request, payload: IncidentNarrativeRequest | None = None):
    try:
        return await get_container(request).postmortem_review.export_review_pack(payload.run_id if payload else None)
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found") from None


@router.post("/finance/impact-summary", dependencies=[Depends(require_api_key)])
async def finance_impact_summary(request: Request, payload: FinanceImpactRequest | None = None):
    try:
        return await get_container(request).finance_impact.impact_summary(payload.run_id if payload else None)
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found") from None


@router.post("/finance/impact-pack", dependencies=[Depends(require_api_key)])
async def finance_impact_pack(request: Request, payload: FinanceImpactRequest | None = None):
    try:
        return await get_container(request).finance_impact.export_impact_pack(payload.run_id if payload else None)
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found") from None


@router.post("/runs/{run_id}/incident-brief", dependencies=[Depends(require_api_key)])
async def incident_brief(run_id: str, request: Request):
    try:
        return await get_container(request).briefs.export(run_id)
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found") from None


@router.post("/runs/{run_id}/remediation-checklist", dependencies=[Depends(require_api_key)])
async def remediation_checklist(
    run_id: str,
    request: Request,
    payload: RemediationChecklistRequest | None = None,
):
    try:
        playbook_id = payload.playbook_id if payload else None
        return await get_container(request).playbooks.export_remediation_checklist(run_id, playbook_id)
    except KeyError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Run or playbook not found",
        ) from None


@router.post("/runs/{run_id}/approve", dependencies=[Depends(require_api_key)])
async def approve(run_id: str, payload: ApprovalDecision, request: Request):
    try:
        return await get_container(request).workflow.approve(run_id, payload.actor(), payload.decision_note())
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pending approval not found") from None


@router.post("/runs/{run_id}/reject", dependencies=[Depends(require_api_key)])
async def reject(run_id: str, payload: ApprovalDecision, request: Request):
    try:
        return await get_container(request).workflow.reject(run_id, payload.actor(), payload.decision_note())
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pending approval not found") from None


@router.get("/approvals", dependencies=[Depends(require_api_key)])
async def approvals(request: Request):
    return await get_container(request).approvals.list_pending()


@router.get("/integrations/outbox", dependencies=[Depends(require_api_key)])
async def outbox(request: Request):
    return await get_container(request).outbox.list_events()


@router.get("/integrations/outbox/{outbox_id}", dependencies=[Depends(require_api_key)])
async def outbox_event(outbox_id: str, request: Request):
    event = await get_container(request).outbox.get_event(outbox_id)
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Outbox event not found")
    return event


@router.post("/drills/tool-failure", dependencies=[Depends(require_api_key)])
async def tool_failure_drill(request: Request):
    return await get_container(request).drills.tool_failure()


@router.post("/drills/sla-breach-simulation", dependencies=[Depends(require_api_key)])
async def sla_breach_simulation(request: Request):
    return await get_container(request).drills.sla_breach_simulation()


@router.get("/metrics/agent-performance", dependencies=[Depends(require_api_key)])
async def metrics(request: Request):
    return await get_container(request).metrics.agent_performance()


@router.get("/analytics/ops-snapshot", dependencies=[Depends(require_api_key)])
async def ops_snapshot(request: Request):
    return await get_container(request).analytics.ops_snapshot()


@router.post("/analytics/weekly-review", dependencies=[Depends(require_api_key)])
async def weekly_review(request: Request):
    return await get_container(request).analytics.export_weekly_review()


@router.get("/ops/slo-budget", dependencies=[Depends(require_api_key)])
async def slo_budget(request: Request):
    return await get_container(request).ops.slo_budget()


@router.post("/ops/optimization-report", dependencies=[Depends(require_api_key)])
async def optimization_report(request: Request):
    return await get_container(request).ops.export_optimization_report()


@router.get("/ops/ci-doctor", dependencies=[Depends(require_api_key)])
async def ci_doctor(request: Request):
    return await get_container(request).ops.ci_doctor()


@router.post("/ops/audit-pack", dependencies=[Depends(require_api_key)])
async def audit_pack(request: Request):
    return await get_container(request).ops.export_audit_pack()


@router.get("/ops/daily-brief", dependencies=[Depends(require_api_key)])
async def daily_ops_brief(request: Request):
    return await get_container(request).daily_ops_brief.brief(request.app)


@router.post("/ops/daily-brief-pack", dependencies=[Depends(require_api_key)])
async def daily_ops_brief_pack(request: Request):
    return await get_container(request).daily_ops_brief.export_pack(request.app)


@router.get("/ops/smoke-matrix", dependencies=[Depends(require_api_key)])
async def smoke_matrix(request: Request):
    return await get_container(request).launch_checklist.smoke_matrix()


@router.post("/ops/launch-checklist", dependencies=[Depends(require_api_key)])
async def launch_checklist(request: Request):
    return await get_container(request).launch_checklist.export_checklist()


@router.get("/portfolio/evidence-index", dependencies=[Depends(require_api_key)])
async def portfolio_evidence_index(request: Request):
    return await get_container(request).portfolio.evidence_index()


@router.post("/portfolio/interview-pack", dependencies=[Depends(require_api_key)])
async def portfolio_interview_pack(request: Request):
    return await get_container(request).portfolio.export_interview_pack()


@router.get("/release/quality-gate", dependencies=[Depends(require_api_key)])
async def release_quality_gate(request: Request):
    return await get_container(request).release.quality_gate()


@router.post("/release/publish-pack", dependencies=[Depends(require_api_key)])
async def release_publish_pack(request: Request):
    return await get_container(request).release.export_publish_pack()


@router.get("/reviewer/quickstart", dependencies=[Depends(require_api_key)])
async def reviewer_quickstart(request: Request):
    return await get_container(request).reviewer.quickstart()


@router.post("/reviewer/walkthrough-pack", dependencies=[Depends(require_api_key)])
async def reviewer_walkthrough_pack(request: Request):
    return await get_container(request).reviewer.export_walkthrough_pack()


@router.get("/artifacts/inventory", dependencies=[Depends(require_api_key)])
async def artifact_inventory(request: Request):
    return await get_container(request).artifacts.inventory()


@router.post("/artifacts/readme-checklist", dependencies=[Depends(require_api_key)])
async def artifact_readme_checklist(request: Request):
    return await get_container(request).artifacts.export_readme_checklist()


@router.get("/evidence/retention-audit", dependencies=[Depends(require_api_key)])
async def evidence_retention_audit(request: Request):
    return await get_container(request).evidence_retention.retention_audit()


@router.post("/evidence/retention-pack", dependencies=[Depends(require_api_key)])
async def evidence_retention_pack(request: Request):
    return await get_container(request).evidence_retention.export_retention_pack()


@router.get("/capacity/forecast", dependencies=[Depends(require_api_key)])
async def capacity_forecast(request: Request):
    return await get_container(request).capacity_planning.forecast()


@router.post("/capacity/staffing-plan", dependencies=[Depends(require_api_key)])
async def capacity_staffing_plan(request: Request):
    return await get_container(request).capacity_planning.export_staffing_plan()


@router.get("/compliance/data-residency-audit", dependencies=[Depends(require_api_key)])
async def data_residency_audit(request: Request):
    return await get_container(request).data_residency.audit_residency()


@router.post("/compliance/data-residency-pack", dependencies=[Depends(require_api_key)])
async def data_residency_pack(request: Request):
    return await get_container(request).data_residency.export_pack()


@router.get("/ui/dashboard-smoke", dependencies=[Depends(require_api_key)])
async def ui_dashboard_smoke(request: Request):
    return await get_container(request).ui_verification.dashboard_smoke()


@router.post("/ui/verification-pack", dependencies=[Depends(require_api_key)])
async def ui_verification_pack(request: Request):
    return await get_container(request).ui_verification.export_verification_pack()


@router.get("/handoff/final-audit", dependencies=[Depends(require_api_key)])
async def final_handoff_audit(request: Request):
    return await get_container(request).final_handoff.final_audit()


@router.post("/handoff/final-pack", dependencies=[Depends(require_api_key)])
async def final_handoff_pack(request: Request):
    return await get_container(request).final_handoff.export_final_pack()


@router.get("/handoff/on-call-summary", dependencies=[Depends(require_api_key)])
async def on_call_handoff_summary(request: Request):
    return await get_container(request).oncall_handoff.on_call_summary()


@router.post("/handoff/customer-comms-pack", dependencies=[Depends(require_api_key)])
async def customer_comms_pack(request: Request):
    return await get_container(request).oncall_handoff.export_customer_comms_pack()


@router.get("/communications/quality-audit", dependencies=[Depends(require_api_key)])
async def communication_quality_audit(request: Request, run_id: str | None = None):
    try:
        return await get_container(request).communication_quality.quality_audit(run_id)
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found") from None


@router.post("/communications/quality-pack", dependencies=[Depends(require_api_key)])
async def communication_quality_pack(request: Request, run_id: str | None = None):
    try:
        return await get_container(request).communication_quality.export_quality_pack(run_id)
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found") from None


@router.get("/escalations/quality-audit", dependencies=[Depends(require_api_key)])
async def escalation_quality_audit(request: Request, run_id: str | None = None):
    try:
        return await get_container(request).escalation_quality.quality_audit(run_id)
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found") from None


@router.post("/escalations/quality-pack", dependencies=[Depends(require_api_key)])
async def escalation_quality_pack(request: Request, run_id: str | None = None):
    try:
        return await get_container(request).escalation_quality.export_quality_pack(run_id)
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found") from None


@router.get("/git/readiness", dependencies=[Depends(require_api_key)])
async def git_readiness(request: Request):
    return await get_container(request).git_readiness.readiness()


@router.post("/git/push-plan", dependencies=[Depends(require_api_key)])
async def git_push_plan(request: Request):
    return await get_container(request).git_readiness.export_push_plan()


@router.get("/api/contract-audit", dependencies=[Depends(require_api_key)])
async def api_contract_audit(request: Request):
    return await get_container(request).api_contract.audit(request.app)


@router.post("/api/reviewer-collection", dependencies=[Depends(require_api_key)])
async def api_reviewer_collection(request: Request):
    return await get_container(request).api_contract.export_reviewer_collection(request.app)


@router.get("/security/access-matrix", dependencies=[Depends(require_api_key)])
async def security_access_matrix(request: Request):
    return await get_container(request).access_control.matrix(request.app)


@router.post("/security/access-review-pack", dependencies=[Depends(require_api_key)])
async def security_access_review_pack(request: Request):
    return await get_container(request).access_control.export_review_pack(request.app)


@router.get("/risk/register", dependencies=[Depends(require_api_key)])
async def enterprise_risk_register(request: Request):
    return await get_container(request).risk_register.register(request.app)


@router.post("/risk/register-pack", dependencies=[Depends(require_api_key)])
async def enterprise_risk_register_pack(request: Request):
    return await get_container(request).risk_register.export_pack(request.app)


@router.get("/providers/readiness", dependencies=[Depends(require_api_key)])
async def provider_readiness(request: Request):
    return await get_container(request).provider_readiness.readiness()


@router.post("/providers/readiness-pack", dependencies=[Depends(require_api_key)])
async def provider_readiness_pack(request: Request):
    return await get_container(request).provider_readiness.export_pack()


@router.get("/providers/failover-drill", dependencies=[Depends(require_api_key)])
async def provider_failover_drill(request: Request):
    return await get_container(request).provider_failover.failover_drill()


@router.post("/providers/failover-pack", dependencies=[Depends(require_api_key)])
async def provider_failover_pack(request: Request):
    return await get_container(request).provider_failover.export_pack()


@router.get("/governance/autonomy-audit", dependencies=[Depends(require_api_key)])
async def autonomy_governance_audit(request: Request):
    return await get_container(request).autonomy_governance.autonomy_audit()


@router.post("/governance/autonomy-pack", dependencies=[Depends(require_api_key)])
async def autonomy_governance_pack(request: Request):
    return await get_container(request).autonomy_governance.export_pack()


@router.get("/workflows/durability-audit", dependencies=[Depends(require_api_key)])
async def workflow_durability_audit(request: Request):
    return await get_container(request).workflow_recovery.durability_audit()


@router.post("/workflows/durability-pack", dependencies=[Depends(require_api_key)])
async def workflow_durability_pack(request: Request):
    return await get_container(request).workflow_recovery.export_pack()


@router.get("/runtime/demo-readiness")
async def runtime_demo_readiness(request: Request):
    return await get_container(request).runtime_demo.readiness()


@router.post("/runtime/demo-pack", dependencies=[Depends(require_api_key)])
async def runtime_demo_pack(request: Request):
    return await get_container(request).runtime_demo.export_pack()


@router.post("/ops/runbook-qa", dependencies=[Depends(require_api_key)])
async def runbook_qa(request: Request, payload: RunbookQaRequest | None = None):
    try:
        return await get_container(request).runbook_qa.evaluate(payload.run_id if payload else None)
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found") from None


@router.post("/ops/operator-readiness-pack", dependencies=[Depends(require_api_key)])
async def operator_readiness_pack(request: Request, payload: RunbookQaRequest | None = None):
    try:
        return await get_container(request).runbook_qa.export_operator_readiness_pack(
            payload.run_id if payload else None
        )
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found") from None


@router.get("/ops/crew-plan", dependencies=[Depends(require_api_key)])
async def support_ops_crew_plan(request: Request, run_id: str | None = None):
    try:
        return await get_container(request).support_ops.crew_plan(run_id)
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found") from None


@router.post("/ops/crew-pack", dependencies=[Depends(require_api_key)])
async def support_ops_crew_pack(request: Request, run_id: str | None = None):
    try:
        return await get_container(request).support_ops.export_crew_pack(run_id)
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found") from None


@router.get("/ops/crew-sandbox", dependencies=[Depends(require_api_key)])
async def support_ops_crew_sandbox(request: Request, run_id: str | None = None):
    try:
        return await get_container(request).support_ops_sandbox.sandbox_run(run_id)
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found") from None


@router.post("/ops/crew-sandbox-pack", dependencies=[Depends(require_api_key)])
async def support_ops_crew_sandbox_pack(request: Request, run_id: str | None = None):
    try:
        return await get_container(request).support_ops_sandbox.export_sandbox_pack(run_id)
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found") from None


@router.get("/ops/crew-readiness-drill", dependencies=[Depends(require_api_key)])
async def support_ops_crew_readiness_drill(request: Request):
    return await get_container(request).support_ops_readiness.readiness_drill()


@router.post("/ops/crew-readiness-pack", dependencies=[Depends(require_api_key)])
async def support_ops_crew_readiness_pack(request: Request):
    return await get_container(request).support_ops_readiness.export_readiness_pack()


@router.get("/tools/registry", dependencies=[Depends(require_api_key)])
async def tool_registry(request: Request):
    return await get_container(request).tool_governance.registry()


@router.post("/tools/governance-pack", dependencies=[Depends(require_api_key)])
async def tool_governance_pack(request: Request):
    return await get_container(request).tool_governance.export_pack()


@router.get("/ops/agent-bus-audit", dependencies=[Depends(require_api_key)])
async def agent_bus_audit(request: Request):
    return await get_container(request).agent_bus.audit_bus()


@router.post("/ops/agent-bus-pack", dependencies=[Depends(require_api_key)])
async def agent_bus_pack(request: Request):
    return await get_container(request).agent_bus.export_pack()


@router.get("/observability/trace-eval-lab", dependencies=[Depends(require_api_key)])
async def observability_trace_eval_lab(request: Request):
    return await get_container(request).observability_eval.trace_eval_lab()


@router.post("/observability/eval-pack", dependencies=[Depends(require_api_key)])
async def observability_eval_pack(request: Request):
    return await get_container(request).observability_eval.export_eval_pack()


@router.get("/runbooks/coverage-audit", dependencies=[Depends(require_api_key)])
async def runbook_coverage_audit(request: Request):
    return await get_container(request).runbook_coverage.coverage_audit()


@router.post("/runbooks/gap-pack", dependencies=[Depends(require_api_key)])
async def runbook_gap_pack(request: Request):
    return await get_container(request).runbook_coverage.export_gap_pack()


@router.get("/leadership/scorecard", dependencies=[Depends(require_api_key)])
async def leadership_scorecard(request: Request):
    return await get_container(request).leadership.scorecard()


@router.post("/leadership/review-pack", dependencies=[Depends(require_api_key)])
async def leadership_review_pack(request: Request):
    return await get_container(request).leadership.export_review_pack()


@router.get("/knowledge/quality-audit", dependencies=[Depends(require_api_key)])
async def knowledge_quality_audit(request: Request):
    return await get_container(request).knowledge_quality.audit_quality()


@router.post("/knowledge/refresh-plan", dependencies=[Depends(require_api_key)])
async def knowledge_refresh_plan(request: Request):
    return await get_container(request).knowledge_quality.export_refresh_plan()


@router.post("/demo/scenario-run", dependencies=[Depends(require_api_key)])
async def demo_scenario_run(request: Request):
    return await get_container(request).demo.run_scenario()


@router.post("/demo/evidence-pack", dependencies=[Depends(require_api_key)])
async def demo_evidence_pack(request: Request):
    return await get_container(request).demo.export_evidence_pack()


@router.get("/scenarios/catalog", dependencies=[Depends(require_api_key)])
async def scenarios_catalog(request: Request):
    return await get_container(request).scenarios.catalog()


@router.post("/scenarios/eval-pack", dependencies=[Depends(require_api_key)])
async def scenarios_eval_pack(request: Request):
    return await get_container(request).scenarios.export_eval_pack()


@router.get("/customers/health", dependencies=[Depends(require_api_key)])
async def customer_health(request: Request):
    return await get_container(request).customers.health()


@router.post("/customers/{customer_id_or_name}/account-brief", dependencies=[Depends(require_api_key)])
async def account_brief(customer_id_or_name: str, request: Request):
    try:
        return await get_container(request).customers.export_account_brief(customer_id_or_name)
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found") from None


@router.get("/customers/renewal-risk", dependencies=[Depends(require_api_key)])
async def customer_renewal_risk(request: Request):
    return await get_container(request).customers.renewal_risk()


@router.get("/customers/renewal-control-board", dependencies=[Depends(require_api_key)])
async def customer_renewal_control_board(request: Request):
    return await get_container(request).customers.renewal_control_board()


@router.post("/customers/renewal-control-pack", dependencies=[Depends(require_api_key)])
async def customer_renewal_control_pack(request: Request):
    return await get_container(request).customers.export_renewal_control_pack()


@router.get("/customers/renewal-handoff-gate", dependencies=[Depends(require_api_key)])
async def customer_renewal_handoff_gate(request: Request):
    return await get_container(request).customers.renewal_handoff_gate()


@router.post("/customers/renewal-handoff-pack", dependencies=[Depends(require_api_key)])
async def customer_renewal_handoff_pack(request: Request):
    return await get_container(request).customers.export_renewal_handoff_pack()


@router.post("/customers/{customer_id_or_name}/renewal-review", dependencies=[Depends(require_api_key)])
async def customer_renewal_review(customer_id_or_name: str, request: Request):
    try:
        return await get_container(request).customers.export_renewal_review(customer_id_or_name)
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found") from None


@router.get("/audit/events", dependencies=[Depends(require_api_key)])
async def audit_events(request: Request):
    return await get_container(request).audit.list_events()
