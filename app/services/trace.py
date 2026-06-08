import time
from contextlib import asynccontextmanager

from app.core.storage import JsonStateStore
from app.models import TraceEvent


class TraceService:
    def __init__(self, store: JsonStateStore):
        self.store = store

    async def add_event(self, event: TraceEvent) -> TraceEvent:
        def mutate(state):
            state["traces"].setdefault(event.run_id, []).append(event.model_dump(mode="json"))
            return event

        return await self.store.update(mutate)

    async def list_events(self, run_id: str) -> list[TraceEvent]:
        state = await self.store.load()
        return [TraceEvent(**item) for item in state["traces"].get(run_id, [])]

    @asynccontextmanager
    async def node_span(self, run_id: str, trace_id: str, ticket_id: str, node: str):
        start = time.perf_counter()
        await self.add_event(TraceEvent(run_id=run_id, trace_id=trace_id, ticket_id=ticket_id, event_type="node_start", node=node, message=f"{node} started"))
        try:
            yield
        except Exception as exc:
            await self.add_event(TraceEvent(run_id=run_id, trace_id=trace_id, ticket_id=ticket_id, event_type="node_error", node=node, status="error", message=str(exc), latency_ms=(time.perf_counter() - start) * 1000))
            raise
        await self.add_event(TraceEvent(run_id=run_id, trace_id=trace_id, ticket_id=ticket_id, event_type="node_end", node=node, message=f"{node} completed", latency_ms=(time.perf_counter() - start) * 1000))

    async def tool_call(self, run_id: str, trace_id: str, ticket_id: str, node: str, name: str, attempt: int, status: str, latency_ms: float, message: str):
        return await self.add_event(TraceEvent(run_id=run_id, trace_id=trace_id, ticket_id=ticket_id, event_type="tool_call", node=node, status=status, message=message, metadata={"tool": name, "attempt": attempt}, latency_ms=latency_ms))

