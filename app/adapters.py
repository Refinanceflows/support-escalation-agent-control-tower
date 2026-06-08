import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


SAMPLE_DIR = Path(__file__).resolve().parents[1] / "sample_data"


def load_json(name: str) -> Any:
    return json.loads((SAMPLE_DIR / name).read_text(encoding="utf-8"))


class ZendeskAdapter(ABC):
    @abstractmethod
    async def fetch_tickets(self) -> list[dict[str, Any]]:
        raise NotImplementedError


class JiraAdapter(ABC):
    @abstractmethod
    async def create_issue(self, payload: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError


class SlackAdapter(ABC):
    @abstractmethod
    async def post_message(self, channel: str, payload: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError


class KnowledgeBaseAdapter(ABC):
    @abstractmethod
    async def documents(self) -> list[dict[str, Any]]:
        raise NotImplementedError


class FakeZendeskAdapter(ZendeskAdapter):
    async def fetch_tickets(self) -> list[dict[str, Any]]:
        return load_json("tickets.json")


class FakeJiraAdapter(JiraAdapter):
    async def create_issue(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {"external_id": "JIRA-DEMO-101", "status": "created", "payload": payload}


class FakeSlackAdapter(SlackAdapter):
    async def post_message(self, channel: str, payload: dict[str, Any]) -> dict[str, Any]:
        return {"channel": channel, "status": "posted", "payload": payload}


class FakeKnowledgeBaseAdapter(KnowledgeBaseAdapter):
    async def documents(self) -> list[dict[str, Any]]:
        return load_json("kb_articles.json")
