import time

from app.adapters.fake import AdapterError, FakeKnowledgeBaseAdapter
from app.models import KnowledgeArticle
from app.services.trace import TraceService


class KnowledgeRetrievalService:
    def __init__(self, adapter: FakeKnowledgeBaseAdapter, trace_service: TraceService, max_attempts: int):
        self.adapter = adapter
        self.trace_service = trace_service
        self.max_attempts = max_attempts

    async def search_with_retries(self, run_id: str, trace_id: str, ticket_id: str, query: str, tags: list[str]) -> tuple[list[KnowledgeArticle], list[dict], dict | None]:
        calls = []
        last_error = None
        for attempt in range(1, self.max_attempts + 1):
            start = time.perf_counter()
            try:
                results = await self.adapter.search(query, tags, 3)
                latency = (time.perf_counter() - start) * 1000
                calls.append({"name": "internal_kb.search", "attempt": attempt, "status": "ok", "latency_ms": latency})
                await self.trace_service.tool_call(run_id, trace_id, ticket_id, "knowledge_retriever", "internal_kb.search", attempt, "ok", latency, f"Retrieved {len(results)} KB articles")
                return results, calls, None
            except AdapterError as exc:
                latency = (time.perf_counter() - start) * 1000
                last_error = str(exc)
                calls.append({"name": "internal_kb.search", "attempt": attempt, "status": "error", "latency_ms": latency, "message": last_error})
                await self.trace_service.tool_call(run_id, trace_id, ticket_id, "knowledge_retriever", "internal_kb.search", attempt, "error", latency, last_error)
        return [], calls, {"node": "knowledge_retriever", "error": last_error, "attempts": self.max_attempts}

