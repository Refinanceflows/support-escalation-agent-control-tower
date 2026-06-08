import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.core.config import Settings, get_settings
from app.core.security import require_api_key
from app.models import ApprovalDecision, AuditEvent, TicketCreate
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


@router.get("/metrics/agent-performance", dependencies=[Depends(require_api_key)])
async def metrics(request: Request):
    return await get_container(request).metrics.agent_performance()


@router.get("/audit/events", dependencies=[Depends(require_api_key)])
async def audit_events(request: Request):
    return await get_container(request).audit.list_events()

