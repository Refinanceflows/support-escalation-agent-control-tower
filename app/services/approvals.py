from datetime import datetime, timezone

from app.core.storage import JsonStateStore
from app.models import Approval, ApprovalStatus


class ApprovalService:
    def __init__(self, store: JsonStateStore):
        self.store = store

    async def create_or_get_pending(self, run_id: str, ticket_id: str, reason: str, customer_reply: str, engineering_escalation: str) -> Approval:
        def mutate(state):
            for raw in state["approvals"].values():
                if raw["run_id"] == run_id and raw["status"] == "pending":
                    return Approval(**raw)
            approval = Approval(run_id=run_id, ticket_id=ticket_id, reason=reason, customer_reply=customer_reply, engineering_escalation=engineering_escalation)
            state["approvals"][approval.approval_id] = approval.model_dump(mode="json")
            return approval

        return await self.store.update(mutate)

    async def list_pending(self) -> list[Approval]:
        state = await self.store.load()
        return sorted([Approval(**item) for item in state["approvals"].values() if item["status"] == "pending"], key=lambda a: a.created_at)

    async def decide(self, run_id: str, status: ApprovalStatus, decided_by: str, note: str | None) -> Approval | None:
        now = datetime.now(timezone.utc).isoformat()

        def mutate(state):
            for approval_id, raw in state["approvals"].items():
                if raw["run_id"] == run_id and raw["status"] == "pending":
                    raw.update({"status": status, "decided_by": decided_by, "decision_note": note, "decided_at": now})
                    state["approvals"][approval_id] = raw
                    return Approval(**raw)
            return None

        return await self.store.update(mutate)

