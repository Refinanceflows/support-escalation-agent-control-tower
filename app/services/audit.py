from app.core.storage import JsonStateStore
from app.models import AuditEvent


class AuditService:
    def __init__(self, store: JsonStateStore):
        self.store = store

    async def record(self, event: AuditEvent) -> AuditEvent:
        def mutate(state):
            state["audit_events"][event.audit_id] = event.model_dump(mode="json")
            return event

        return await self.store.update(mutate)

    async def list_events(self) -> list[AuditEvent]:
        state = await self.store.load()
        return sorted([AuditEvent(**item) for item in state["audit_events"].values()], key=lambda e: e.timestamp, reverse=True)

