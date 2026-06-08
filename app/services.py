import time
from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import Any

from app.adapters import FakeKnowledgeBaseAdapter
from app.models import (
    ActionType,
    AgentRun,
    AgentTraceEvent,
    ApprovalDecision,
    ApprovalRequest,
    ApprovalStatus,
    AuditEvent,
    CustomerReplyDraft,
    KnowledgeCitation,
    MetricsSummary,
    RunStatus,
    Ticket,
    TicketCreate,
    UsageMetric,
    utc_now,
)
from app.storage import SQLiteStore


class TicketService:
    def __init__(self, store: SQLiteStore):
        self.store = store

    def ingest(self, data: TicketCreate) -> Ticket:
        ticket = Ticket(**data.model_dump())
        self.save(ticket)
        return ticket

    def save(self, ticket: Ticket) -> None:
        self.store.upsert_model("tickets", ticket)

    def get(self, ticket_id: str) -> Ticket:
        ticket = self.store.get_model("tickets", Ticket, ticket_id)
        if not ticket:
            raise KeyError(f"ticket not found: {ticket_id}")
        return ticket

    def list(self) -> list[Ticket]:
        return self.store.list_models("tickets", Ticket, "ORDER BY created_at DESC")

    def seed_if_empty(self, tickets: list[dict[str, Any]]) -> None:
        if self.list():
            return
        for raw in tickets:
            self.ingest(TicketCreate.model_validate(self._normalize_seed_ticket(raw)))

    @staticmethod
    def _normalize_seed_ticket(raw: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(raw)
        normalized.setdefault("customer", normalized.get("customer_email", "Demo Customer"))
        if "sla_due_at" not in normalized:
            hours = 1 if normalized.get("priority") == "urgent" else 8
            normalized["sla_due_at"] = (utc_now() + timedelta(hours=hours)).isoformat()
        metadata = dict(normalized.get("metadata", {}))
        for key in ("customer_email", "customer_tier", "tags", "external_id"):
            if key in normalized:
                metadata[key] = normalized.pop(key)
        normalized["metadata"] = metadata
        return normalized


class TraceService:
    def __init__(self, store: SQLiteStore):
        self.store = store

    def record(
        self,
        run_id: str,
        node_name: str,
        event_type: str,
        payload: dict[str, Any] | None = None,
        latency_ms: int = 0,
        token_usage: dict[str, int] | None = None,
    ) -> AgentTraceEvent:
        event = AgentTraceEvent(
            run_id=run_id,
            node_name=node_name,
            event_type=event_type,
            payload=payload or {},
            latency_ms=latency_ms,
            token_usage=token_usage or {},
        )
        self.store.upsert_model(
            "trace_events",
            event,
            {"run_id": run_id, "node_name": node_name, "event_type": event_type},
        )
        return event

    def list_for_run(self, run_id: str) -> list[AgentTraceEvent]:
        return self.store.list_models(
            "trace_events",
            AgentTraceEvent,
            "WHERE run_id = ? ORDER BY created_at ASC",
            (run_id,),
        )


class MetricsService:
    def __init__(self, store: SQLiteStore):
        self.store = store

    def record_usage(
        self,
        trace_id: str,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        latency_ms: int,
        estimated_cost: float,
    ) -> UsageMetric:
        metric = UsageMetric(
            trace_id=trace_id,
            provider=provider,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            estimated_cost=estimated_cost,
        )
        self.store.upsert_model("usage_metrics", metric, {"trace_id": trace_id, "provider": provider})
        return metric

    def summary(self) -> MetricsSummary:
        runs = self.store.list_models("runs", AgentRun)
        traces = self.store.list_models("trace_events", AgentTraceEvent)
        usage = self.store.list_models("usage_metrics", UsageMetric)
        completed = [run for run in runs if run.status == RunStatus.COMPLETED]
        escalated = [run for run in runs if run.final_action == ActionType.ENGINEERING_ESCALATION]
        failures = Counter(event.node_name for event in traces if event.event_type == "failure")
        sla = Counter()
        for run in runs:
            risk = run.state.get("sla_risk", {}).get("risk_level")
            if risk:
                sla[risk] += 1
        avg_latency = sum(event.latency_ms for event in traces) / len(traces) if traces else 0
        return MetricsSummary(
            run_count=len(runs),
            success_rate=(len(completed) / len(runs)) if runs else 0,
            escalation_rate=(len(escalated) / len(runs)) if runs else 0,
            average_latency_ms=round(avg_latency, 2),
            total_input_tokens=sum(item.input_tokens for item in usage),
            total_output_tokens=sum(item.output_tokens for item in usage),
            estimated_cost=round(sum(item.estimated_cost for item in usage), 6),
            failure_counts=dict(failures),
            sla_risk_distribution=dict(sla),
        )


class AuditService:
    def __init__(self, store: SQLiteStore):
        self.store = store

    def record(
        self,
        actor: str,
        action: str,
        resource_type: str,
        resource_id: str,
        metadata: dict[str, Any] | None = None,
        trace_id: str | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            trace_id=trace_id,
            actor=actor,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            metadata=metadata or {},
        )
        self.store.upsert_model("audit_events", event, {"actor": actor, "action": action})
        return event

    def list(self) -> list[AuditEvent]:
        return self.store.list_models("audit_events", AuditEvent, "ORDER BY created_at DESC LIMIT 100")


class ApprovalService:
    def __init__(self, store: SQLiteStore, audit: AuditService):
        self.store = store
        self.audit = audit

    def create(self, run_id: str, action_type: ActionType, proposed_payload: dict[str, Any]) -> ApprovalRequest:
        existing = [
            item
            for item in self.list()
            if item.run_id == run_id and item.status == ApprovalStatus.PENDING
        ]
        if existing:
            return existing[0]
        approval = ApprovalRequest(
            run_id=run_id,
            action_type=action_type,
            proposed_payload=proposed_payload,
        )
        self.store.upsert_model("approvals", approval, {"run_id": run_id, "status": approval.status})
        self.audit.record("agent", "approval_requested", "run", run_id, {"action_type": action_type})
        return approval

    def list(self) -> list[ApprovalRequest]:
        return self.store.list_models("approvals", ApprovalRequest, "ORDER BY created_at DESC")

    def get_for_run(self, run_id: str) -> ApprovalRequest:
        approvals = self.store.list_models(
            "approvals",
            ApprovalRequest,
            "WHERE run_id = ? ORDER BY created_at DESC",
            (run_id,),
        )
        if not approvals:
            raise KeyError(f"approval not found for run: {run_id}")
        return approvals[0]

    def decide(self, run_id: str, decision: ApprovalDecision, status: ApprovalStatus) -> ApprovalRequest:
        approval = self.get_for_run(run_id)
        approval.status = status
        approval.reviewer = decision.reviewer
        approval.reviewer_notes = decision.reviewer_notes
        approval.decided_at = utc_now()
        self.store.upsert_model("approvals", approval, {"run_id": run_id, "status": approval.status})
        self.audit.record(
            decision.reviewer,
            f"approval_{status.value}",
            "approval",
            approval.id,
            {"run_id": run_id, "notes": decision.reviewer_notes},
        )
        return approval


class KnowledgeRetrievalService:
    def __init__(self, adapter: FakeKnowledgeBaseAdapter | None = None):
        self.adapter = adapter or FakeKnowledgeBaseAdapter()

    async def search(self, query: str, limit: int = 3) -> list[KnowledgeCitation]:
        docs = await self.adapter.documents()
        terms = {term.strip(".,:;!?()[]").lower() for term in query.split() if len(term) > 2}
        scored: list[KnowledgeCitation] = []
        for doc in docs:
            body = doc.get("body") or doc.get("content") or ""
            source_id = doc.get("id") or doc.get("article_id") or doc["title"]
            haystack = f"{doc['title']} {body} {' '.join(doc.get('tags', []))}".lower()
            score = sum(1 for term in terms if term in haystack) / max(len(terms), 1)
            if score > 0:
                scored.append(
                    KnowledgeCitation(
                        source_id=source_id,
                        title=doc["title"],
                        snippet=body[:280],
                        score=round(score, 3),
                    )
                )
        scored.sort(key=lambda item: item.score, reverse=True)
        return scored[:limit]


class RunRepository:
    def __init__(self, store: SQLiteStore):
        self.store = store

    def create(self, ticket_id: str) -> AgentRun:
        run = AgentRun(ticket_id=ticket_id)
        self.save(run)
        return run

    def save(self, run: AgentRun) -> None:
        self.store.upsert_model(
            "runs",
            run,
            {"ticket_id": run.ticket_id, "status": run.status, "current_state": run.current_state},
        )

    def get(self, run_id: str) -> AgentRun:
        run = self.store.get_model("runs", AgentRun, run_id)
        if not run:
            raise KeyError(f"run not found: {run_id}")
        return run

    def list(self) -> list[AgentRun]:
        return self.store.list_models("runs", AgentRun, "ORDER BY created_at DESC")


def minutes_until(value: datetime) -> int:
    target = value if value.tzinfo else value.replace(tzinfo=UTC)
    return int((target - datetime.now(UTC)).total_seconds() // 60)


class NodeTimer:
    def __enter__(self) -> "NodeTimer":
        self.started = time.perf_counter()
        self._latency_ms: int | None = None
        return self

    def __exit__(self, *args: Any) -> None:
        self._latency_ms = int((time.perf_counter() - self.started) * 1000)

    @property
    def latency_ms(self) -> int:
        if self._latency_ms is not None:
            return self._latency_ms
        return int((time.perf_counter() - self.started) * 1000)


def customer_reply_payload(reply: CustomerReplyDraft) -> dict[str, Any]:
    return reply.model_dump(mode="json")
