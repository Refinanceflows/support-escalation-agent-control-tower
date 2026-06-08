from abc import ABC, abstractmethod
from typing import Any

from app.models import KnowledgeArticle, Ticket


class LlmProvider(ABC):
    @abstractmethod
    async def draft_customer_reply(self, ticket: Ticket, context: list[KnowledgeArticle]) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def draft_engineering_escalation(
        self,
        ticket: Ticket,
        classification: dict[str, Any],
        sla_risk: dict[str, Any],
        context: list[KnowledgeArticle],
    ) -> dict[str, Any]:
        raise NotImplementedError


class KnowledgeAdapter(ABC):
    @abstractmethod
    async def search(self, query: str, tags: list[str], limit: int = 3) -> list[KnowledgeArticle]:
        raise NotImplementedError

