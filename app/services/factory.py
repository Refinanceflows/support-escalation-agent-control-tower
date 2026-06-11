from pathlib import Path

from app.adapters.fake import FakeKnowledgeBaseAdapter
from app.adapters.llm import build_llm_provider
from app.core.config import Settings
from app.core.storage import JsonStateStore
from app.services.analytics import AnalyticsService
from app.services.approvals import ApprovalService
from app.services.api_contract import ApiContractService
from app.services.artifacts import ArtifactInventoryService
from app.services.access_control import AccessControlService
from app.services.audit import AuditService
from app.services.autonomy_governance import AutonomyGovernanceService
from app.services.briefs import IncidentBriefService
from app.services.capacity_planning import CapacityPlanningService
from app.services.communication_quality import CustomerCommunicationQualityService
from app.services.customers import CustomerHealthService
from app.services.data_residency import DataResidencyService
from app.services.daily_ops_brief import ExecutiveDailyOpsBriefService
from app.services.demo import DemoService
from app.services.drills import DrillService
from app.services.evidence_retention import EvidenceRetentionService
from app.services.escalation_quality import EscalationQualityService
from app.services.final_handoff import FinalHandoffService
from app.services.finance_impact import FinanceImpactService
from app.services.git_readiness import GitReadinessService
from app.services.incident_narrative import IncidentNarrativeService
from app.services.knowledge import KnowledgeQualityService, KnowledgeRetrievalService
from app.services.launch_checklist import LaunchChecklistService
from app.services.leadership import LeadershipScorecardService
from app.services.metrics import MetricsService
from app.services.oncall_handoff import OnCallHandoffService
from app.services.ops import OpsService
from app.services.outbox import OutboxService
from app.services.playbooks import PlaybookService
from app.services.policy_change_simulation import PolicyChangeSimulationService
from app.services.policy_guardrails import PolicyGuardrailService
from app.services.policy_rollout import PolicyRolloutService
from app.services.postmortem_rca import PostmortemRcaService
from app.services.postmortem_review import PostmortemReviewService
from app.services.portfolio import PortfolioService
from app.services.provider_readiness import ProviderReadinessService
from app.services.replay_lab import ReplayLabService
from app.services.release import ReleaseService
from app.services.reviewer import ReviewerService
from app.services.risk_register import EnterpriseRiskRegisterService
from app.services.runbook_coverage import RunbookCoverageService
from app.services.runbook_qa import RunbookQaService
from app.services.runtime_demo import RuntimeDemoService
from app.services.scenarios import ScenarioCatalogService
from app.services.support_ops import SupportOperationsService
from app.services.support_ops_sandbox import SupportOpsSandboxService
from app.services.tickets import TicketService
from app.services.tool_governance import ToolGovernanceService
from app.services.trace import TraceService
from app.services.ui_verification import UIVerificationService
from app.services.workflow import AgentWorkflowService
from app.services.workflow_recovery import WorkflowRecoveryService


class ServiceContainer:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.store = JsonStateStore(settings.state_file)
        self.trace = TraceService(self.store)
        self.audit = AuditService(self.store)
        self.metrics = MetricsService(self.store)
        self.outbox = OutboxService(self.store)
        self.tickets = TicketService(self.store)
        self.knowledge = KnowledgeRetrievalService(
            FakeKnowledgeBaseAdapter(Path("sample_data/kb_articles.json")),
            self.trace,
            settings.max_tool_attempts,
        )
        self.approvals = ApprovalService(self.store)
        self.playbooks = PlaybookService(
            self.store,
            self.tickets,
            Path("sample_data/playbooks.json"),
            settings.state_file.parent / "checklists",
        )
        self.workflow = AgentWorkflowService(
            self.store,
            self.tickets,
            self.knowledge,
            self.approvals,
            self.trace,
            self.metrics,
            self.audit,
            self.outbox,
            self.playbooks,
            settings.low_confidence_threshold,
            settings.sla_high_risk_threshold,
            build_llm_provider(settings),
        )
        self.drills = DrillService(
            self.store,
            self.tickets,
            self.workflow,
            self.trace,
            self.approvals,
        )
        self.briefs = IncidentBriefService(
            self.store,
            self.tickets,
            self.workflow,
            self.trace,
            settings.state_file.parent / "briefs",
        )
        self.analytics = AnalyticsService(
            self.store,
            settings.state_file.parent / "reports",
            settings.state_file.parent / "briefs",
        )
        self.ops = OpsService(
            self.store,
            settings.state_file.parent / "optimization_reports",
        )
        self.launch_checklist = LaunchChecklistService(
            settings.state_file.parent / "launch_checklists",
        )
        self.customers = CustomerHealthService(
            self.store,
            self.tickets,
            self.playbooks,
            Path("sample_data/customers.json"),
            Path("sample_data/account_health_inputs.json"),
            settings.state_file.parent / "account_briefs",
            settings.state_file.parent / "renewal_reviews",
            settings.state_file.parent / "renewal_control_packs",
        )
        self.replay_lab = ReplayLabService(
            self.store,
            self.tickets,
            self.workflow,
            self.trace,
            settings.state_file.parent / "replay_reports",
            settings.low_confidence_threshold,
        )
        self.policy_guardrails = PolicyGuardrailService(
            self.store,
            self.tickets,
            self.workflow,
            self.replay_lab,
            settings.state_file.parent / "policy_packs",
            settings.low_confidence_threshold,
        )
        self.policy_change_simulation = PolicyChangeSimulationService(
            self.tickets,
            self.workflow,
            Path("sample_data/scenarios.json"),
            settings.state_file.parent / "policy_change_packs",
        )
        self.policy_rollout = PolicyRolloutService(
            self.policy_change_simulation,
            self.audit,
            settings.state_file.parent / "policy_rollout_packs",
        )
        self.incident_narratives = IncidentNarrativeService(
            self.store,
            self.tickets,
            self.workflow,
            self.trace,
            self.approvals,
            self.briefs,
            self.playbooks,
            self.analytics,
            self.customers,
            self.ops,
            self.replay_lab,
            self.policy_guardrails,
            self.audit,
            settings.state_file.parent / "incident_narratives",
        )
        self.finance_impact = FinanceImpactService(
            self.store,
            self.tickets,
            self.workflow,
            self.trace,
            self.approvals,
            self.customers,
            self.audit,
            Path("sample_data/customers.json"),
            settings.state_file.parent / "finance_impact_packs",
        )
        self.demo = DemoService(
            self.tickets,
            self.workflow,
            self.trace,
            self.approvals,
            self.outbox,
            self.playbooks,
            self.drills,
            self.briefs,
            self.analytics,
            self.customers,
            self.ops,
            self.replay_lab,
            self.incident_narratives,
            self.finance_impact,
            self.audit,
            settings.state_file.parent / "demo_packs",
        )
        self.runbook_qa = RunbookQaService(
            self.store,
            self.tickets,
            self.workflow,
            self.trace,
            self.approvals,
            self.outbox,
            self.playbooks,
            self.drills,
            self.briefs,
            self.analytics,
            self.customers,
            self.ops,
            settings.state_file.parent / "operator_packs",
        )
        self.runbook_coverage = RunbookCoverageService(
            self.tickets,
            self.playbooks,
            self.audit,
            Path("sample_data/kb_articles.json"),
            Path("sample_data/scenarios.json"),
            settings.state_file.parent / "runbook_gap_packs",
        )
        self.leadership = LeadershipScorecardService(
            self.store,
            self.tickets,
            self.workflow,
            self.metrics,
            self.analytics,
            self.customers,
            self.ops,
            self.replay_lab,
            self.policy_guardrails,
            self.runbook_qa,
            settings.state_file.parent / "leadership_reviews",
        )
        self.knowledge_quality = KnowledgeQualityService(
            self.store,
            self.tickets,
            self.audit,
            self.leadership,
            Path("sample_data/kb_articles.json"),
            settings.state_file.parent / "kb_refresh_plans",
            settings.state_file.parent / "incident_narratives",
        )
        self.portfolio = PortfolioService(
            self.store,
            settings.state_file.parent / "portfolio_packs",
        )
        self.release = ReleaseService(
            self.store,
            settings.state_file.parent / "release_packs",
        )
        self.reviewer = ReviewerService(
            self.store,
            settings.state_file.parent / "reviewer_packs",
        )
        self.artifacts = ArtifactInventoryService(settings.state_file.parent)
        self.ui_verification = UIVerificationService(
            settings.state_file.parent / "ui_verification",
        )
        self.final_handoff = FinalHandoffService(
            self.store,
            settings.state_file.parent,
        )
        self.oncall_handoff = OnCallHandoffService(
            self.store,
            self.tickets,
            self.workflow,
            self.trace,
            self.approvals,
            self.policy_guardrails,
            self.audit,
            Path("sample_data/scenarios.json"),
            settings.state_file.parent / "customer_comms_packs",
        )
        self.communication_quality = CustomerCommunicationQualityService(
            self.store,
            self.tickets,
            self.workflow,
            self.audit,
            Path("sample_data/scenarios.json"),
            settings.state_file.parent / "communication_quality_packs",
        )
        self.escalation_quality = EscalationQualityService(
            self.store,
            self.tickets,
            self.workflow,
            self.audit,
            Path("sample_data/scenarios.json"),
            settings.state_file.parent / "escalation_quality_packs",
        )
        self.postmortem_rca = PostmortemRcaService(
            self.store,
            self.tickets,
            self.workflow,
            self.trace,
            self.approvals,
            self.audit,
            self.oncall_handoff,
            Path("sample_data/scenarios.json"),
            settings.state_file.parent / "rca_packs",
        )
        self.postmortem_review = PostmortemReviewService(
            self.postmortem_rca,
            self.audit,
            settings.state_file.parent / "postmortem_review_packs",
        )
        self.git_readiness = GitReadinessService(
            settings.state_file.parent / "git_packs",
        )
        self.api_contract = ApiContractService(
            settings.state_file.parent / "api_contracts",
        )
        self.access_control = AccessControlService(
            settings.state_file.parent / "access_review_packs",
        )
        self.runtime_demo = RuntimeDemoService(
            settings.state_file.parent / "runtime_packs",
        )
        self.scenarios = ScenarioCatalogService(
            self.tickets,
            self.workflow,
            self.audit,
            Path("sample_data/scenarios.json"),
            Path("data/scenario_packs"),
        )
        self.evidence_retention = EvidenceRetentionService(
            self.store,
            self.audit,
            settings.state_file.parent / "evidence_packs",
        )
        self.capacity_planning = CapacityPlanningService(
            self.store,
            self.tickets,
            self.audit,
            Path("sample_data/scenarios.json"),
            settings.state_file.parent / "capacity_plans",
        )
        self.data_residency = DataResidencyService(
            self.store,
            self.tickets,
            self.audit,
            Path("sample_data/customers.json"),
            Path("sample_data/data_residency_rules.json"),
            settings.state_file.parent / "data_residency_packs",
        )
        self.risk_register = EnterpriseRiskRegisterService(
            self.finance_impact,
            self.evidence_retention,
            self.capacity_planning,
            self.data_residency,
            self.access_control,
            self.knowledge_quality,
            self.runbook_coverage,
            self.leadership,
            self.release,
            self.ops,
            self.audit,
            settings.state_file.parent / "risk_registers",
        )
        self.provider_readiness = ProviderReadinessService(
            settings,
            self.audit,
            settings.state_file.parent / "provider_readiness_packs",
        )
        self.daily_ops_brief = ExecutiveDailyOpsBriefService(
            self.store,
            self.analytics,
            self.ops,
            self.customers,
            self.capacity_planning,
            self.leadership,
            self.risk_register,
            self.audit,
            settings.state_file.parent / "daily_ops_briefs",
        )
        self.autonomy_governance = AutonomyGovernanceService(
            self.store,
            self.tickets,
            self.workflow,
            self.audit,
            Path("sample_data/scenarios.json"),
            settings.state_file.parent / "autonomy_governance_packs",
        )
        self.workflow_recovery = WorkflowRecoveryService(
            self.store,
            self.tickets,
            self.approvals,
            self.workflow,
            self.audit,
            Path("sample_data/scenarios.json"),
            settings.state_file.parent / "workflow_recovery_packs",
        )
        self.support_ops = SupportOperationsService(
            self.store,
            self.tickets,
            self.workflow,
            self.playbooks,
            self.audit,
            Path("sample_data/scenarios.json"),
            settings.state_file.parent / "support_ops_packs",
        )
        self.support_ops_sandbox = SupportOpsSandboxService(
            self.support_ops,
            self.audit,
            settings.state_file.parent / "support_ops_sandbox",
        )
        self.tool_governance = ToolGovernanceService(
            self.store,
            self.workflow,
            self.audit,
            settings.state_file.parent / "tool_governance_packs",
        )
