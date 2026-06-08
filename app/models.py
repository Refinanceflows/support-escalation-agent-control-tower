from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


def utc_now() -> datetime:
    return datetime.now(UTC)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


class TicketStatus(StrEnum):
    NEW = "new"
    ANALYZING = "analyzing"
    AWAITING_APPROVAL = "awaiting_approval"
    RESOLVED = "resolved"
    ESCALATED = "escalated"
    REJECTED = "rejected"


class RunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    AWAITING_APPROVAL = "awaiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class ActionType(StrEnum):
    CUSTOMER_REPLY = "customer_reply"
    ENGINEERING_ESCALATION = "engineering_escalation"
    HUMAN_REVIEW = "human_review"


class Ticket(BaseModel):
    id: str = Field(default_factory=lambda: new_id("tkt"))
    customer: str
    subject: str
    body: str
    priority: str = "normal"
    sla_due_at: datetime
    status: TicketStatus = TicketStatus.NEW
    created_at: datetime = Field(default_factory=utc_now)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TicketCreate(BaseModel):
    customer: str
    subject: str
    body: str
    priority: str = "normal"
    sla_due_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)


class TicketClassification(BaseModel):
    category: str
    urgency: str
    customer_impact: str
    likely_owner: str
    confidence: float


class SlaRisk(BaseModel):
    risk_level: str
    minutes_remaining: int
    reason: str
    recommended_action: str


class KnowledgeCitation(BaseModel):
    source_id: str
    title: str
    snippet: str
    score: float


class CustomerReplyDraft(BaseModel):
    subject: str
    body: str
    tone: str
    citations: list[KnowledgeCitation]
    confidence: float
    risk_notes: list[str] = Field(default_factory=list)


class EscalationDraft(BaseModel):
    title: str
    severity: str
    summary: str
    reproduction_steps: list[str]
    suspected_area: str
    customer_impact: str
    citations: list[KnowledgeCitation]


class QAEvaluation(BaseModel):
    confidence: float
    grounded: bool
    tone: str
    risk_flags: list[str] = Field(default_factory=list)
    requires_human_approval: bool
    action_type: ActionType
    reason: str


class AgentRun(BaseModel):
    id: str = Field(default_factory=lambda: new_id("run"))
    ticket_id: str
    current_state: str = "queued"
    status: RunStatus = RunStatus.QUEUED
    created_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime | None = None
    final_action: str | None = None
    state: dict[str, Any] = Field(default_factory=dict)


class AgentTraceEvent(BaseModel):
    id: str = Field(default_factory=lambda: new_id("trace"))
    run_id: str
    node_name: str
    event_type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    latency_ms: int = 0
    token_usage: dict[str, int] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)


class ApprovalRequest(BaseModel):
    id: str = Field(default_factory=lambda: new_id("apr"))
    run_id: str
    action_type: ActionType
    proposed_payload: dict[str, Any]
    status: ApprovalStatus = ApprovalStatus.PENDING
    reviewer: str | None = None
    reviewer_notes: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    decided_at: datetime | None = None


class ApprovalDecision(BaseModel):
    reviewer: str = "demo-reviewer"
    reviewer_notes: str = ""


class UsageMetric(BaseModel):
    id: str = Field(default_factory=lambda: new_id("usage"))
    trace_id: str
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: int
    estimated_cost: float
    created_at: datetime = Field(default_factory=utc_now)


class AuditEvent(BaseModel):
    id: str = Field(default_factory=lambda: new_id("audit"))
    trace_id: str | None = None
    actor: str
    action: str
    resource_type: str
    resource_id: str
    created_at: datetime = Field(default_factory=utc_now)
    metadata: dict[str, Any] = Field(default_factory=dict)


class MetricsSummary(BaseModel):
    run_count: int
    success_rate: float
    escalation_rate: float
    average_latency_ms: float
    total_input_tokens: int
    total_output_tokens: int
    estimated_cost: float
    failure_counts: dict[str, int]
    sla_risk_distribution: dict[str, int]
