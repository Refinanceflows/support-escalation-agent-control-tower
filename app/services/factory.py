from pathlib import Path

from app.adapters.fake import FakeKnowledgeBaseAdapter
from app.core.config import Settings
from app.core.storage import JsonStateStore
from app.services.approvals import ApprovalService
from app.services.audit import AuditService
from app.services.knowledge import KnowledgeRetrievalService
from app.services.metrics import MetricsService
from app.services.tickets import TicketService
from app.services.trace import TraceService
from app.services.workflow import AgentWorkflowService


class ServiceContainer:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.store = JsonStateStore(settings.state_file)
        self.trace = TraceService(self.store)
        self.audit = AuditService(self.store)
        self.metrics = MetricsService(self.store)
        self.tickets = TicketService(self.store)
        self.knowledge = KnowledgeRetrievalService(
            FakeKnowledgeBaseAdapter(Path("sample_data/kb_articles.json")),
            self.trace,
            settings.max_tool_attempts,
        )
        self.approvals = ApprovalService(self.store)
        self.workflow = AgentWorkflowService(
            self.store,
            self.tickets,
            self.knowledge,
            self.approvals,
            self.trace,
            self.metrics,
            self.audit,
            settings.low_confidence_threshold,
            settings.sla_high_risk_threshold,
        )

