from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Literal, TypedDict
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, computed_field


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TicketPriority(StrEnum):
    low = "low"
    normal = "normal"
    high = "high"
    urgent = "urgent"


class TicketStatus(StrEnum):
    open = "open"
    analyzing = "analyzing"
    pending_approval = "pending_approval"
    escalated = "escalated"
    replied = "replied"
    human_review = "human_review"


class RunStatus(StrEnum):
    pending = "pending"
    running = "running"
    pending_approval = "awaiting_approval"
    completed = "completed"
    rejected = "rejected"
    human_review = "human_review"


class ApprovalStatus(StrEnum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class TicketCreate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    subject: str
    body: str
    customer_email: str = "customer@example.com"
    priority: TicketPriority = TicketPriority.normal
    external_id: str | None = None
    customer_tier: Literal["standard", "pro", "enterprise"] = "standard"
    tags: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)


class Ticket(TicketCreate):
    ticket_id: str = Field(default_factory=lambda: f"tkt_{uuid4().hex[:10]}")
    status: TicketStatus = TicketStatus.open

    @computed_field
    @property
    def id(self) -> str:
        return self.ticket_id


class Classification(BaseModel):
    category: str
    priority: TicketPriority
    confidence: float
    sentiment: str
    rationale: str


class SlaRisk(BaseModel):
    score: float
    level: Literal["low", "medium", "high"]
    reasons: list[str] = Field(default_factory=list)
    should_escalate: bool = False


class KnowledgeArticle(BaseModel):
    article_id: str
    title: str
    content: str
    tags: list[str] = Field(default_factory=list)
    score: float = 0.0


class QaResult(BaseModel):
    confidence: float
    risky: bool = False
    requires_human_review: bool = False
    findings: list[str] = Field(default_factory=list)


class TraceEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: f"evt_{uuid4().hex[:12]}")
    run_id: str
    trace_id: str
    ticket_id: str
    timestamp: datetime = Field(default_factory=utc_now)
    event_type: str
    node: str | None = None
    status: str = "ok"
    message: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)
    latency_ms: float = 0.0
    tokens: int = 0
    cost_usd: float = 0.0

    @computed_field
    @property
    def node_name(self) -> str | None:
        return self.node


class Approval(BaseModel):
    approval_id: str = Field(default_factory=lambda: f"apr_{uuid4().hex[:10]}")
    run_id: str
    ticket_id: str
    status: ApprovalStatus = ApprovalStatus.pending
    reason: str
    customer_reply: str = ""
    engineering_escalation: str = ""
    created_at: datetime = Field(default_factory=utc_now)
    decided_at: datetime | None = None
    decided_by: str | None = None
    decision_note: str | None = None


class RunRecord(BaseModel):
    run_id: str = Field(default_factory=lambda: f"run_{uuid4().hex[:10]}")
    ticket_id: str
    trace_id: str = Field(default_factory=lambda: f"trc_{uuid4().hex[:12]}")
    status: RunStatus = RunStatus.pending
    started_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime | None = None
    state: dict[str, Any] = Field(default_factory=dict)
    final_action: str = ""
    failure_state: dict[str, Any] | None = None
    metrics: dict[str, Any] = Field(default_factory=dict)

    @computed_field
    @property
    def id(self) -> str:
        return self.run_id


class AuditEvent(BaseModel):
    audit_id: str = Field(default_factory=lambda: f"aud_{uuid4().hex[:12]}")
    timestamp: datetime = Field(default_factory=utc_now)
    actor: str
    action: str
    resource_type: str
    resource_id: str
    trace_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ApprovalDecision(BaseModel):
    model_config = ConfigDict(extra="ignore")
    decided_by: str = "demo-human"
    note: str | None = None
    reviewer: str | None = None
    reviewer_notes: str | None = None

    def actor(self) -> str:
        return self.reviewer or self.decided_by

    def decision_note(self) -> str | None:
        return self.reviewer_notes or self.note


class AgentWorkflowState(TypedDict, total=False):
    run_id: str
    ticket_id: str
    trace_id: str
    ticket: dict[str, Any]
    classification: dict[str, Any]
    sla_risk: dict[str, Any]
    kb_results: list[dict[str, Any]]
    drafts: dict[str, str]
    qa: dict[str, Any]
    approval_id: str | None
    approval_status: str
    approval_decision: str | None
    final_action: str
    failure_state: dict[str, Any] | None
    node_history: list[str]
    tool_calls: list[dict[str, Any]]
    metrics: dict[str, Any]

