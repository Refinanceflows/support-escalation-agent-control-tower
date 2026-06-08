import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class LLMResult:
    content: dict[str, Any]
    input_tokens: int
    output_tokens: int
    latency_ms: int
    estimated_cost: float
    model: str


class BaseLLMProvider(ABC):
    name: str
    model: str

    @abstractmethod
    async def complete_json(self, task: str, payload: dict[str, Any]) -> LLMResult:
        raise NotImplementedError


class MockLLMProvider(BaseLLMProvider):
    name = "mock"
    model = "deterministic-support-agent-v1"

    async def complete_json(self, task: str, payload: dict[str, Any]) -> LLMResult:
        start = time.perf_counter()
        ticket = payload.get("ticket", {})
        text = f"{ticket.get('subject', '')} {ticket.get('body', '')}".lower()
        result = self._dispatch(task, text, payload)
        input_tokens = max(20, len(str(payload)) // 4)
        output_tokens = max(12, len(str(result)) // 4)
        latency_ms = int((time.perf_counter() - start) * 1000) + 5
        return LLMResult(
            content=result,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            estimated_cost=0.0,
            model=self.model,
        )

    def _dispatch(self, task: str, text: str, payload: dict[str, Any]) -> dict[str, Any]:
        if task == "classify":
            category = "how_to"
            owner = "support"
            urgency = "medium"
            confidence = 0.82
            impact = "single customer productivity impact"
            incident_signals = ["outage", "cannot login", "login loop", "all users", "app is down"]
            bug_signals = ["webhook", "api", "sync", "regression", "bug", "500"]
            if "api key" in text and any(signal in text for signal in ["rotate", "rotation"]):
                category, owner, urgency, confidence = "how_to", "support", "medium", 0.9
                impact = "security maintenance guidance needed"
            elif any(signal in text for signal in incident_signals):
                category, owner, urgency, confidence = "incident", "engineering", "critical", 0.93
                impact = "active production outage for customer users"
            elif any(signal in text for signal in bug_signals):
                category, owner, urgency, confidence = "bug", "engineering", "high", 0.88
                impact = "integration or workflow failure"
            elif any(word in text for word in ["invoice", "billing", "payment"]):
                category, owner, urgency, confidence = "billing", "finance_ops", "medium", 0.8
                impact = "commercial workflow blocked"
            elif "maybe" in text or "unclear" in text:
                confidence = 0.48
                urgency = "low"
            return {
                "category": category,
                "urgency": urgency,
                "customer_impact": impact,
                "likely_owner": owner,
                "confidence": confidence,
            }
        if task == "customer_reply":
            citations = payload.get("citations", [])
            cited_titles = ", ".join(c.get("title", "internal guidance") for c in citations[:2])
            return {
                "subject": f"Re: {payload['ticket']['subject']}",
                "body": (
                    "Thanks for the detail. We reviewed the ticket against our internal guidance"
                    f" ({cited_titles or 'support playbooks'}). We are keeping the case under active"
                    " review and will not take external action until the proposed response is approved."
                ),
                "tone": "calm, accountable, specific",
                "citations": citations,
                "confidence": 0.84 if citations else 0.58,
                "risk_notes": [] if citations else ["No strong KB citation found"],
            }
        if task == "engineering_escalation":
            classification = payload.get("classification", {})
            return {
                "title": f"{classification.get('urgency', 'medium').upper()}: {payload['ticket']['subject']}",
                "severity": "sev1" if classification.get("urgency") == "critical" else "sev2",
                "summary": payload["ticket"]["body"][:500],
                "reproduction_steps": [
                    "Open affected customer workspace",
                    "Run the workflow described in the ticket",
                    "Observe the reported failure and capture request IDs",
                ],
                "suspected_area": classification.get("likely_owner", "engineering"),
                "customer_impact": classification.get("customer_impact", "customer impact under review"),
                "citations": payload.get("citations", []),
            }
        return {"message": "ok"}


class OpenAIProvider(BaseLLMProvider):
    name = "openai"

    def __init__(self, api_key: str | None, model: str):
        self.api_key = api_key
        self.model = model

    async def complete_json(self, task: str, payload: dict[str, Any]) -> LLMResult:
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is required when LLM_PROVIDER=openai")
        raise NotImplementedError("OpenAI adapter is intentionally optional; wire SDK calls here.")


class AzureOpenAIProvider(BaseLLMProvider):
    name = "azure_openai"

    def __init__(self, endpoint: str | None, api_key: str | None, deployment: str | None):
        self.endpoint = endpoint
        self.api_key = api_key
        self.model = deployment or "azure-openai-deployment"

    async def complete_json(self, task: str, payload: dict[str, Any]) -> LLMResult:
        if not (self.endpoint and self.api_key and self.model):
            raise RuntimeError("Azure OpenAI endpoint, key, and deployment are required")
        raise NotImplementedError("Azure OpenAI adapter is optional; wire Azure SDK calls here.")
