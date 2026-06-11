import ast
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DASHBOARD_SOURCE = Path("dashboard/streamlit_app.py")
API_ROUTES_SOURCE = Path("app/api/routes.py")

DASHBOARD_RUN_COMMAND = r".\.venv\Scripts\streamlit.exe run dashboard\streamlit_app.py"
API_RUN_COMMAND = r".\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000"
DASHBOARD_SMOKE_COMMAND = r".\.venv\Scripts\python.exe scripts\dashboard_smoke.py"
VERIFICATION_PACK_COMMAND = (
    "Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/ui/verification-pack "
    "-Headers @{'x-api-key'='demo-control-tower-key'}"
)

EXPECTED_VIEWS = [
    "Ticket Queue",
    "Analyze Ticket",
    "Run Timeline",
    "Trace Inspector",
    "Approval Panel",
    "Outbox",
    "Reliability",
    "SLA Simulator",
    "Incident Brief",
    "Playbooks / Remediation",
    "Customer Health / Account Brief",
    "Ops Analytics",
    "SLO / Optimization",
    "Demo Scenario / Evidence Pack",
    "Metrics",
    "Audit Events",
    "Operator QA / Readiness Pack",
    "Replay Lab",
    "Policy Guardrails",
    "Incident Narrative",
    "Postmortem RCA",
    "Leadership Scorecard",
    "Knowledge Quality",
    "Launch Checklist",
    "Portfolio Pack",
    "Release Pack",
    "CI Doctor / Audit Pack",
    "Reviewer Quickstart",
    "Artifact Inventory",
    "UI Verification",
    "Final Handoff",
    "On-Call Handoff",
    "Git Readiness",
    "API Contract",
    "Runtime Demo",
    "Scenario Dataset",
    "Finance Impact",
    "Runbook Coverage",
    "Evidence Retention",
    "Capacity Planning",
    "Data Residency",
    "Access Control",
    "Risk Register",
    "Provider Readiness",
    "Executive Daily Ops Brief",
    "Autonomy Governance",
    "Durable Workflows",
    "Escalation Quality",
    "Communication Quality",
    "Support Ops Crews",
    "Support Ops Sandbox",
    "Tool Governance",
]

EXPECTED_ENDPOINTS = [
    {
        "endpoint": "GET /ui/dashboard-smoke",
        "purpose": "Returns deterministic dashboard source smoke checks.",
        "dashboard_reference_required": True,
        "route_required": True,
    },
    {
        "endpoint": "POST /ui/verification-pack",
        "purpose": "Writes the UI Verification Pack under ignored local data.",
        "dashboard_reference_required": True,
        "route_required": True,
    },
    {
        "endpoint": "GET /ops/smoke-matrix",
        "purpose": "Launch smoke matrix tab source reference.",
        "dashboard_reference_required": True,
        "route_required": True,
    },
    {
        "endpoint": "POST /ops/launch-checklist",
        "purpose": "Launch Checklist artifact export.",
        "dashboard_reference_required": True,
        "route_required": True,
    },
    {
        "endpoint": "POST /demo/evidence-pack",
        "purpose": "Demo Evidence Pack artifact export.",
        "dashboard_reference_required": True,
        "route_required": True,
    },
    {
        "endpoint": "POST /ops/operator-readiness-pack",
        "purpose": "Operator Readiness Pack artifact export.",
        "dashboard_reference_required": True,
        "route_required": True,
    },
    {
        "endpoint": "POST /replay-lab/report",
        "purpose": "Replay Lab report export.",
        "dashboard_reference_required": True,
        "route_required": True,
    },
    {
        "endpoint": "POST /policies/export",
        "purpose": "Policy Guardrails pack export.",
        "dashboard_reference_required": True,
        "route_required": True,
    },
    {
        "endpoint": "POST /policies/change-simulation",
        "purpose": "Policy change simulation preview.",
        "dashboard_reference_required": True,
        "route_required": True,
    },
    {
        "endpoint": "POST /policies/change-pack",
        "purpose": "Agent Policy Simulation Pack export.",
        "dashboard_reference_required": True,
        "route_required": True,
    },
    {
        "endpoint": "POST /policies/rollout-plan",
        "purpose": "Policy rollout go/no-go gate with role signoffs, canary phases, and rollback triggers.",
        "dashboard_reference_required": True,
        "route_required": True,
    },
    {
        "endpoint": "POST /policies/rollout-pack",
        "purpose": "Policy Rollout Review Pack export.",
        "dashboard_reference_required": True,
        "route_required": True,
    },
    {
        "endpoint": "POST /incidents/executive-narrative",
        "purpose": "Incident Narrative artifact export.",
        "dashboard_reference_required": True,
        "route_required": True,
    },
    {
        "endpoint": "GET /incidents/postmortem-summary",
        "purpose": "Postmortem RCA summary with root cause and corrective actions.",
        "dashboard_reference_required": True,
        "route_required": True,
    },
    {
        "endpoint": "POST /incidents/rca-pack",
        "purpose": "Postmortem RCA + Corrective Action Tracking Pack export.",
        "dashboard_reference_required": True,
        "route_required": True,
    },
    {
        "endpoint": "GET /incidents/postmortem-review-board",
        "purpose": "Postmortem corrective-action review board with owner signoffs and closure gates.",
        "dashboard_reference_required": True,
        "route_required": True,
    },
    {
        "endpoint": "POST /incidents/postmortem-review-pack",
        "purpose": "Postmortem Corrective Action Review Pack export.",
        "dashboard_reference_required": True,
        "route_required": True,
    },
    {
        "endpoint": "POST /finance/impact-summary",
        "purpose": "Escalation Finance Impact estimate with support cost, SLA exposure, engineering effort, and ARR risk.",
        "dashboard_reference_required": True,
        "route_required": True,
    },
    {
        "endpoint": "POST /finance/impact-pack",
        "purpose": "Escalation Finance Impact Pack export.",
        "dashboard_reference_required": True,
        "route_required": True,
    },
    {
        "endpoint": "POST /leadership/review-pack",
        "purpose": "Leadership Review Pack export.",
        "dashboard_reference_required": True,
        "route_required": True,
    },
    {
        "endpoint": "POST /knowledge/refresh-plan",
        "purpose": "Knowledge Quality refresh plan export.",
        "dashboard_reference_required": True,
        "route_required": True,
    },
    {
        "endpoint": "GET /runbooks/coverage-audit",
        "purpose": "Runbook Coverage audit across tickets, KB articles, playbooks, and scenarios.",
        "dashboard_reference_required": True,
        "route_required": True,
    },
    {
        "endpoint": "POST /runbooks/gap-pack",
        "purpose": "Runbook Coverage Gap Pack export.",
        "dashboard_reference_required": True,
        "route_required": True,
    },
    {
        "endpoint": "POST /portfolio/interview-pack",
        "purpose": "Portfolio Interview Pack export.",
        "dashboard_reference_required": True,
        "route_required": True,
    },
    {
        "endpoint": "POST /release/publish-pack",
        "purpose": "Release Publish Pack export.",
        "dashboard_reference_required": True,
        "route_required": True,
    },
    {
        "endpoint": "POST /ops/audit-pack",
        "purpose": "CI Doctor Audit Pack export.",
        "dashboard_reference_required": True,
        "route_required": True,
    },
    {
        "endpoint": "POST /reviewer/walkthrough-pack",
        "purpose": "Reviewer Walkthrough Pack export.",
        "dashboard_reference_required": True,
        "route_required": True,
    },
    {
        "endpoint": "POST /artifacts/readme-checklist",
        "purpose": "Artifact Inventory README Checklist export.",
        "dashboard_reference_required": True,
        "route_required": True,
    },
    {
        "endpoint": "GET /handoff/final-audit",
        "purpose": "README Consistency final audit.",
        "dashboard_reference_required": True,
        "route_required": True,
    },
    {
        "endpoint": "POST /handoff/final-pack",
        "purpose": "Final Handoff Pack export.",
        "dashboard_reference_required": True,
        "route_required": True,
    },
    {
        "endpoint": "GET /handoff/on-call-summary",
        "purpose": "On-Call Handoff summary and communication readiness.",
        "dashboard_reference_required": True,
        "route_required": True,
    },
    {
        "endpoint": "POST /handoff/customer-comms-pack",
        "purpose": "Customer Communications Simulation Pack export.",
        "dashboard_reference_required": True,
        "route_required": True,
    },
    {
        "endpoint": "GET /communications/quality-audit",
        "purpose": "Customer Communication Quality audit for drafted replies.",
        "dashboard_reference_required": True,
        "route_required": True,
    },
    {
        "endpoint": "POST /communications/quality-pack",
        "purpose": "Customer Communication Quality Pack export.",
        "dashboard_reference_required": True,
        "route_required": True,
    },
    {
        "endpoint": "GET /escalations/quality-audit",
        "purpose": "Engineering Escalation Quality audit for Jira-ready handoff drafts.",
        "dashboard_reference_required": True,
        "route_required": True,
    },
    {
        "endpoint": "POST /escalations/quality-pack",
        "purpose": "Engineering Escalation Quality Pack export.",
        "dashboard_reference_required": True,
        "route_required": True,
    },
    {
        "endpoint": "GET /git/readiness",
        "purpose": "Local GitHub Push Readiness and Branch Hygiene checks.",
        "dashboard_reference_required": True,
        "route_required": True,
    },
    {
        "endpoint": "POST /git/push-plan",
        "purpose": "GitHub Push Readiness + Branch Hygiene Pack export.",
        "dashboard_reference_required": True,
        "route_required": True,
    },
    {
        "endpoint": "GET /api/contract-audit",
        "purpose": "OpenAPI-derived API Contract Audit checks.",
        "dashboard_reference_required": True,
        "route_required": True,
    },
    {
        "endpoint": "POST /api/reviewer-collection",
        "purpose": "API Contract Reviewer Collection export.",
        "dashboard_reference_required": True,
        "route_required": True,
    },
    {
        "endpoint": "GET /runtime/demo-readiness",
        "purpose": "Runtime Demo readiness command, dependency, and read-only port checks.",
        "dashboard_reference_required": True,
        "route_required": True,
    },
    {
        "endpoint": "POST /runtime/demo-pack",
        "purpose": "Runtime Demo Server Pack export.",
        "dashboard_reference_required": True,
        "route_required": True,
    },
    {
        "endpoint": "GET /scenarios/catalog",
        "purpose": "Scenario Dataset catalog and expected outcome coverage.",
        "dashboard_reference_required": True,
        "route_required": True,
    },
    {
        "endpoint": "POST /scenarios/eval-pack",
        "purpose": "Scenario Dataset Eval Coverage Pack export.",
        "dashboard_reference_required": True,
        "route_required": True,
    },
    {
        "endpoint": "GET /customers/renewal-risk",
        "purpose": "Renewal risk workbench summary across local account health, sentiment, SLA drag, and blockers.",
        "dashboard_reference_required": True,
        "route_required": True,
    },
    {
        "endpoint": "GET /customers/renewal-control-board",
        "purpose": "Renewal control board with HITL decisions, blocked automation actions, checkpoints, and owners.",
        "dashboard_reference_required": True,
        "route_required": True,
    },
    {
        "endpoint": "POST /customers/renewal-control-pack",
        "purpose": "Renewal Control and HITL Governance Pack export.",
        "dashboard_reference_required": True,
        "route_required": True,
    },
    {
        "endpoint": "POST /customers/{customer_id_or_name}/renewal-review",
        "purpose": "Renewal Risk Review artifact export.",
        "dashboard_reference_required": True,
        "route_required": True,
    },
    {
        "endpoint": "GET /evidence/retention-audit",
        "purpose": "Evidence retention readiness across traces, approvals, outbox, audit events, artifacts, and hashes.",
        "dashboard_reference_required": True,
        "route_required": True,
    },
    {
        "endpoint": "POST /evidence/retention-pack",
        "purpose": "Evidence Retention and Chain-of-Custody Pack export.",
        "dashboard_reference_required": True,
        "route_required": True,
    },
    {
        "endpoint": "GET /capacity/forecast",
        "purpose": "Support load and staffing capacity forecast.",
        "dashboard_reference_required": True,
        "route_required": True,
    },
    {
        "endpoint": "POST /capacity/staffing-plan",
        "purpose": "Support Capacity Forecast and Staffing Plan export.",
        "dashboard_reference_required": True,
        "route_required": True,
    },
    {
        "endpoint": "GET /compliance/data-residency-audit",
        "purpose": "Data residency and PII exposure audit across local support evidence.",
        "dashboard_reference_required": True,
        "route_required": True,
    },
    {
        "endpoint": "POST /compliance/data-residency-pack",
        "purpose": "Data Residency and PII Exposure Pack export.",
        "dashboard_reference_required": True,
        "route_required": True,
    },
    {
        "endpoint": "GET /security/access-matrix",
        "purpose": "Least-privilege access matrix over the local FastAPI route inventory.",
        "dashboard_reference_required": True,
        "route_required": True,
    },
    {
        "endpoint": "POST /security/access-review-pack",
        "purpose": "Access Control Review Pack export with role scopes and production authz backlog.",
        "dashboard_reference_required": True,
        "route_required": True,
    },
    {
        "endpoint": "GET /risk/register",
        "purpose": "Enterprise Risk Register across finance, compliance, capacity, access, evidence, and release controls.",
        "dashboard_reference_required": True,
        "route_required": True,
    },
    {
        "endpoint": "POST /risk/register-pack",
        "purpose": "Enterprise Risk Register Pack export with owner action plan and acceptance criteria.",
        "dashboard_reference_required": True,
        "route_required": True,
    },
    {
        "endpoint": "GET /providers/readiness",
        "purpose": "Provider readiness audit for local/mock, OpenAI, and Azure OpenAI activation posture.",
        "dashboard_reference_required": True,
        "route_required": True,
    },
    {
        "endpoint": "POST /providers/readiness-pack",
        "purpose": "Provider Readiness Guard Pack export with activation checklist and production backlog.",
        "dashboard_reference_required": True,
        "route_required": True,
    },
    {
        "endpoint": "GET /governance/autonomy-audit",
        "purpose": "Autonomy Governance audit for loop budgets, tool trust, HITL boundaries, token/cost, and run findings.",
        "dashboard_reference_required": True,
        "route_required": True,
    },
    {
        "endpoint": "POST /governance/autonomy-pack",
        "purpose": "Autonomy Governance and Tool Trust Pack export.",
        "dashboard_reference_required": True,
        "route_required": True,
    },
    {
        "endpoint": "GET /workflows/durability-audit",
        "purpose": "Durable workflow checkpoint and recovery readiness audit.",
        "dashboard_reference_required": True,
        "route_required": True,
    },
    {
        "endpoint": "POST /workflows/durability-pack",
        "purpose": "Durable Workflow Recovery Pack export.",
        "dashboard_reference_required": True,
        "route_required": True,
    },
    {
        "endpoint": "GET /ops/daily-brief",
        "purpose": "Executive Daily Ops Brief command-center summary.",
        "dashboard_reference_required": True,
        "route_required": True,
    },
    {
        "endpoint": "POST /ops/daily-brief-pack",
        "purpose": "Executive Daily Ops Brief Pack export.",
        "dashboard_reference_required": True,
        "route_required": True,
    },
    {
        "endpoint": "GET /ops/crew-plan",
        "purpose": "Autonomous Support Operations role-crew and task-delegation plan.",
        "dashboard_reference_required": True,
        "route_required": True,
    },
    {
        "endpoint": "POST /ops/crew-pack",
        "purpose": "Autonomous Support Operations Pack export.",
        "dashboard_reference_required": True,
        "route_required": True,
    },
    {
        "endpoint": "GET /ops/crew-sandbox",
        "purpose": "Local worker sandbox run with task transcripts and budget gates.",
        "dashboard_reference_required": True,
        "route_required": True,
    },
    {
        "endpoint": "POST /ops/crew-sandbox-pack",
        "purpose": "Support Ops Worker Sandbox Pack export.",
        "dashboard_reference_required": True,
        "route_required": True,
    },
    {
        "endpoint": "GET /tools/registry",
        "purpose": "Tool manifest registry with owners, risk tiers, data exposure, approval boundaries, and usage evidence.",
        "dashboard_reference_required": True,
        "route_required": True,
    },
    {
        "endpoint": "POST /tools/governance-pack",
        "purpose": "Tool Governance and Marketplace Trust Pack export.",
        "dashboard_reference_required": True,
        "route_required": True,
    },
]

GENERATED_ARTIFACT_TABS = [
    {
        "tab_label": "Demo Scenario / Evidence Pack",
        "producer_endpoint": "POST /demo/evidence-pack",
        "artifact_directory": "data/demo_packs",
    },
    {
        "tab_label": "Operator QA / Readiness Pack",
        "producer_endpoint": "POST /ops/operator-readiness-pack",
        "artifact_directory": "data/operator_packs",
    },
    {
        "tab_label": "Replay Lab",
        "producer_endpoint": "POST /replay-lab/report",
        "artifact_directory": "data/replay_reports",
    },
    {
        "tab_label": "Policy Guardrails",
        "producer_endpoint": "POST /policies/export",
        "artifact_directory": "data/policy_packs",
    },
    {
        "tab_label": "Policy Guardrails",
        "producer_endpoint": "POST /policies/change-pack",
        "artifact_directory": "data/policy_change_packs",
    },
    {
        "tab_label": "Policy Guardrails",
        "producer_endpoint": "POST /policies/rollout-pack",
        "artifact_directory": "data/policy_rollout_packs",
    },
    {
        "tab_label": "Provider Readiness",
        "producer_endpoint": "POST /providers/readiness-pack",
        "artifact_directory": "data/provider_readiness_packs",
    },
    {
        "tab_label": "Customer Health / Account Brief",
        "producer_endpoint": "POST /customers/{customer_id_or_name}/renewal-review",
        "artifact_directory": "data/renewal_reviews",
    },
    {
        "tab_label": "Customer Health / Account Brief",
        "producer_endpoint": "POST /customers/renewal-control-pack",
        "artifact_directory": "data/renewal_control_packs",
    },
    {
        "tab_label": "Incident Narrative",
        "producer_endpoint": "POST /incidents/executive-narrative",
        "artifact_directory": "data/incident_narratives",
    },
    {
        "tab_label": "Postmortem RCA",
        "producer_endpoint": "POST /incidents/rca-pack",
        "artifact_directory": "data/rca_packs",
    },
    {
        "tab_label": "Postmortem RCA",
        "producer_endpoint": "POST /incidents/postmortem-review-pack",
        "artifact_directory": "data/postmortem_review_packs",
    },
    {
        "tab_label": "Finance Impact",
        "producer_endpoint": "POST /finance/impact-pack",
        "artifact_directory": "data/finance_impact_packs",
    },
    {
        "tab_label": "Leadership Scorecard",
        "producer_endpoint": "POST /leadership/review-pack",
        "artifact_directory": "data/leadership_reviews",
    },
    {
        "tab_label": "Knowledge Quality",
        "producer_endpoint": "POST /knowledge/refresh-plan",
        "artifact_directory": "data/kb_refresh_plans",
    },
    {
        "tab_label": "Runbook Coverage",
        "producer_endpoint": "POST /runbooks/gap-pack",
        "artifact_directory": "data/runbook_gap_packs",
    },
    {
        "tab_label": "Launch Checklist",
        "producer_endpoint": "POST /ops/launch-checklist",
        "artifact_directory": "data/launch_checklists",
    },
    {
        "tab_label": "Portfolio Pack",
        "producer_endpoint": "POST /portfolio/interview-pack",
        "artifact_directory": "data/portfolio_packs",
    },
    {
        "tab_label": "Release Pack",
        "producer_endpoint": "POST /release/publish-pack",
        "artifact_directory": "data/release_packs",
    },
    {
        "tab_label": "CI Doctor / Audit Pack",
        "producer_endpoint": "POST /ops/audit-pack",
        "artifact_directory": "data/audit_packs",
    },
    {
        "tab_label": "Reviewer Quickstart",
        "producer_endpoint": "POST /reviewer/walkthrough-pack",
        "artifact_directory": "data/reviewer_packs",
    },
    {
        "tab_label": "Artifact Inventory",
        "producer_endpoint": "POST /artifacts/readme-checklist",
        "artifact_directory": "data/artifact_indexes",
    },
    {
        "tab_label": "UI Verification",
        "producer_endpoint": "POST /ui/verification-pack",
        "artifact_directory": "data/ui_verification",
    },
    {
        "tab_label": "Final Handoff",
        "producer_endpoint": "POST /handoff/final-pack",
        "artifact_directory": "data/final_handoff",
    },
    {
        "tab_label": "On-Call Handoff",
        "producer_endpoint": "POST /handoff/customer-comms-pack",
        "artifact_directory": "data/customer_comms_packs",
    },
    {
        "tab_label": "Communication Quality",
        "producer_endpoint": "POST /communications/quality-pack",
        "artifact_directory": "data/communication_quality_packs",
    },
    {
        "tab_label": "Escalation Quality",
        "producer_endpoint": "POST /escalations/quality-pack",
        "artifact_directory": "data/escalation_quality_packs",
    },
    {
        "tab_label": "Git Readiness",
        "producer_endpoint": "POST /git/push-plan",
        "artifact_directory": "data/git_packs",
    },
    {
        "tab_label": "API Contract",
        "producer_endpoint": "POST /api/reviewer-collection",
        "artifact_directory": "data/api_contracts",
    },
    {
        "tab_label": "Runtime Demo",
        "producer_endpoint": "POST /runtime/demo-pack",
        "artifact_directory": "data/runtime_packs",
    },
    {
        "tab_label": "Scenario Dataset",
        "producer_endpoint": "POST /scenarios/eval-pack",
        "artifact_directory": "data/scenario_packs",
    },
    {
        "tab_label": "Evidence Retention",
        "producer_endpoint": "POST /evidence/retention-pack",
        "artifact_directory": "data/evidence_packs",
    },
    {
        "tab_label": "Capacity Planning",
        "producer_endpoint": "POST /capacity/staffing-plan",
        "artifact_directory": "data/capacity_plans",
    },
    {
        "tab_label": "Data Residency",
        "producer_endpoint": "POST /compliance/data-residency-pack",
        "artifact_directory": "data/data_residency_packs",
    },
    {
        "tab_label": "Access Control",
        "producer_endpoint": "POST /security/access-review-pack",
        "artifact_directory": "data/access_review_packs",
    },
    {
        "tab_label": "Risk Register",
        "producer_endpoint": "POST /risk/register-pack",
        "artifact_directory": "data/risk_registers",
    },
    {
        "tab_label": "Executive Daily Ops Brief",
        "producer_endpoint": "POST /ops/daily-brief-pack",
        "artifact_directory": "data/daily_ops_briefs",
    },
    {
        "tab_label": "Autonomy Governance",
        "producer_endpoint": "POST /governance/autonomy-pack",
        "artifact_directory": "data/autonomy_governance_packs",
    },
    {
        "tab_label": "Durable Workflows",
        "producer_endpoint": "POST /workflows/durability-pack",
        "artifact_directory": "data/workflow_recovery_packs",
    },
    {
        "tab_label": "Support Ops Crews",
        "producer_endpoint": "POST /ops/crew-pack",
        "artifact_directory": "data/support_ops_packs",
    },
    {
        "tab_label": "Support Ops Sandbox",
        "producer_endpoint": "POST /ops/crew-sandbox-pack",
        "artifact_directory": "data/support_ops_sandbox",
    },
    {
        "tab_label": "Tool Governance",
        "producer_endpoint": "POST /tools/governance-pack",
        "artifact_directory": "data/tool_governance_packs",
    },
]

TROUBLESHOOTING = [
    "If the dashboard smoke script fails on a missing tab, inspect the literal st.tabs list in dashboard/streamlit_app.py.",
    "If an endpoint route is missing, confirm app/api/routes.py declares the protected FastAPI route.",
    "If the dashboard cannot call the API, start FastAPI first and confirm CONTROL_TOWER_API_BASE_URL points to the same port.",
    "If artifacts are missing, run POST /ui/verification-pack or scripts/demo_run.py to regenerate ignored local files.",
]

LIMITATIONS = [
    "The smoke checks inspect source wiring and endpoint references; they do not launch Streamlit or a browser.",
    "Screenshot placeholders are intentionally manual so reviewers can capture their own local dashboard state.",
    "Generated Markdown/JSON under data/ui_verification are ignored local proof artifacts and should be regenerated, not committed.",
    "The pack verifies local/mock dashboard coverage only and does not call Azure, OpenAI, Zendesk, Jira, Slack, or GitHub.",
]


class UIVerificationService:
    def __init__(self, ui_verification_dir: Path):
        self.ui_verification_dir = ui_verification_dir
        self.data_root = ui_verification_dir.parent
        self.repo_root = Path(__file__).resolve().parents[2]

    async def dashboard_smoke(self) -> dict[str, Any]:
        return self.dashboard_smoke_sync()

    async def export_verification_pack(self) -> dict[str, Any]:
        smoke = self.dashboard_smoke_sync()
        generated_at = datetime.now(timezone.utc)
        pack_id = f"ui_verification_{generated_at.strftime('%Y%m%d_%H%M%S')}"
        json_path = self.ui_verification_dir / f"{pack_id}.json"
        markdown_path = self.ui_verification_dir / f"{pack_id}.md"
        pack = {
            "pack_id": pack_id,
            "generated_at": generated_at.isoformat(),
            "title": "UI Verification Pack",
            "dashboard_smoke": smoke,
            "streamlit_run_command": DASHBOARD_RUN_COMMAND,
            "local_run_commands": self._local_run_commands(),
            "reviewer_checklist": self._reviewer_checklist(smoke),
            "screenshot_placeholders": self._screenshot_placeholders(),
            "troubleshooting": TROUBLESHOOTING,
            "limitations": LIMITATIONS,
            "artifact_paths": {
                "ui_verification_markdown": str(markdown_path),
                "ui_verification_json": str(json_path),
            },
        }
        markdown = self._markdown(pack)
        self.ui_verification_dir.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(pack, indent=2, default=str), encoding="utf-8")
        markdown_path.write_text(markdown, encoding="utf-8")
        return {
            "pack_id": pack_id,
            "format": "markdown+json",
            "status": smoke["status"],
            "json_path": str(json_path),
            "markdown_path": str(markdown_path),
            "pack": pack,
            "markdown": markdown,
        }

    def dashboard_smoke_sync(self) -> dict[str, Any]:
        dashboard_path = self.repo_root / DASHBOARD_SOURCE
        routes_path = self.repo_root / API_ROUTES_SOURCE
        dashboard_text = self._read_text(dashboard_path)
        routes_text = self._read_text(routes_path)
        actual_tabs = self._extract_tabs(dashboard_text)
        expected_views = self._view_checks(actual_tabs)
        endpoint_references = self._endpoint_checks(dashboard_text, routes_text)
        generated_artifact_tabs = self._artifact_tab_checks(actual_tabs, dashboard_text)
        checks = [
            *self._checks_from_views(expected_views),
            *self._checks_from_endpoints(endpoint_references),
            *self._checks_from_artifact_tabs(generated_artifact_tabs),
        ]
        failed = [check for check in checks if check["status"] == "fail"]
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "title": "Dashboard Smoke",
            "mode": "local-deterministic-dashboard-source-smoke",
            "status": "fail" if failed else "pass",
            "local_mock_only": True,
            "dashboard_source": str(DASHBOARD_SOURCE),
            "api_routes_source": str(API_ROUTES_SOURCE),
            "summary": {
                "total_checks": len(checks),
                "passed_checks": len(checks) - len(failed),
                "failed_checks": len(failed),
                "view_count": len(expected_views),
                "endpoint_count": len(endpoint_references),
                "generated_artifact_tab_count": len(generated_artifact_tabs),
            },
            "expected_views": expected_views,
            "endpoint_references": endpoint_references,
            "generated_artifact_tabs": generated_artifact_tabs,
            "local_run_commands": self._local_run_commands(),
            "limitations": LIMITATIONS,
            "checks": checks,
        }

    def _read_text(self, path: Path) -> str:
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8")

    def _extract_tabs(self, dashboard_text: str) -> list[str]:
        if not dashboard_text:
            return []
        try:
            tree = ast.parse(dashboard_text)
        except SyntaxError:
            return []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and self._is_tabs_call(node):
                if node.args and isinstance(node.args[0], ast.List):
                    return [
                        item.value
                        for item in node.args[0].elts
                        if isinstance(item, ast.Constant) and isinstance(item.value, str)
                    ]
        return []

    def _is_tabs_call(self, node: ast.Call) -> bool:
        return (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "tabs"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "st"
        )

    def _view_checks(self, actual_tabs: list[str]) -> list[dict[str, Any]]:
        return [
            {
                "label": label,
                "present": label in actual_tabs,
                "position": actual_tabs.index(label) + 1 if label in actual_tabs else None,
            }
            for label in EXPECTED_VIEWS
        ]

    def _endpoint_checks(self, dashboard_text: str, routes_text: str) -> list[dict[str, Any]]:
        rows = []
        for item in EXPECTED_ENDPOINTS:
            method, path = item["endpoint"].split(" ", 1)
            rows.append(
                {
                    **item,
                    "method": method,
                    "path": path,
                    "dashboard_reference_present": path in dashboard_text,
                    "route_present": self._route_present(method, path, routes_text),
                    "expected_status": 200,
                    "requires_api_key": path != "/health",
                }
            )
        return rows

    def _route_present(self, method: str, path: str, routes_text: str) -> bool:
        decorator = f'@router.{method.lower()}("{path}"'
        return decorator in routes_text

    def _artifact_tab_checks(
        self,
        actual_tabs: list[str],
        dashboard_text: str,
    ) -> list[dict[str, Any]]:
        rows = []
        for item in GENERATED_ARTIFACT_TABS:
            endpoint_path = item["producer_endpoint"].split(" ", 1)[1]
            rows.append(
                {
                    **item,
                    "tab_present": item["tab_label"] in actual_tabs,
                    "endpoint_reference_present": endpoint_path in dashboard_text,
                    "ignored_local_artifact": item["artifact_directory"].startswith("data/"),
                }
            )
        return rows

    def _checks_from_views(self, views: list[dict[str, Any]]) -> list[dict[str, str]]:
        return [
            {
                "name": f"dashboard view: {view['label']}",
                "status": "pass" if view["present"] else "fail",
                "detail": "Tab label is present in st.tabs." if view["present"] else "Tab label is missing.",
            }
            for view in views
        ]

    def _checks_from_endpoints(self, endpoints: list[dict[str, Any]]) -> list[dict[str, str]]:
        checks = []
        for endpoint in endpoints:
            checks.append(
                {
                    "name": f"dashboard endpoint reference: {endpoint['endpoint']}",
                    "status": "pass"
                    if endpoint["dashboard_reference_present"] or not endpoint["dashboard_reference_required"]
                    else "fail",
                    "detail": "Endpoint path appears in dashboard source.",
                }
            )
            checks.append(
                {
                    "name": f"api route: {endpoint['endpoint']}",
                    "status": "pass" if endpoint["route_present"] or not endpoint["route_required"] else "fail",
                    "detail": "Endpoint route decorator appears in app/api/routes.py.",
                }
            )
        return checks

    def _checks_from_artifact_tabs(self, tabs: list[dict[str, Any]]) -> list[dict[str, str]]:
        return [
            {
                "name": f"generated artifact tab: {tab['tab_label']}",
                "status": "pass" if tab["tab_present"] and tab["endpoint_reference_present"] else "fail",
                "detail": f"{tab['producer_endpoint']} -> {tab['artifact_directory']}",
            }
            for tab in tabs
        ]

    def _local_run_commands(self) -> dict[str, str | list[str]]:
        return {
            "api": API_RUN_COMMAND,
            "dashboard": DASHBOARD_RUN_COMMAND,
            "dashboard_smoke": DASHBOARD_SMOKE_COMMAND,
            "verification_pack": VERIFICATION_PACK_COMMAND,
            "acceptance": [
                r".\.venv\Scripts\python.exe -m pytest -q",
                r".\.venv\Scripts\python.exe -m ruff check app tests dashboard scripts",
                r".\.venv\Scripts\python.exe -m app.evals.run_eval",
                DASHBOARD_SMOKE_COMMAND,
                r".\.venv\Scripts\python.exe scripts\demo_run.py",
            ],
        }

    def _reviewer_checklist(self, smoke: dict[str, Any]) -> list[dict[str, str]]:
        return [
            {
                "item": "Run dashboard smoke script",
                "command": DASHBOARD_SMOKE_COMMAND,
                "expected": f"PASS with {smoke['summary']['total_checks']} source checks.",
            },
            {
                "item": "Export UI Verification Pack",
                "command": "POST /ui/verification-pack",
                "expected": "Markdown and JSON are written under data/ui_verification.",
            },
            {
                "item": "Start dashboard locally",
                "command": DASHBOARD_RUN_COMMAND,
                "expected": "Streamlit opens with a UI Verification tab.",
            },
            {
                "item": "Capture screenshots manually",
                "command": "Open UI Verification, Launch Checklist, Reviewer Quickstart, and Artifact Inventory tabs.",
                "expected": "Replace placeholders in the pack with local screenshot filenames if needed.",
            },
        ]

    def _screenshot_placeholders(self) -> list[dict[str, str]]:
        return [
            {
                "view": "UI Verification",
                "placeholder": "screenshots/ui-verification-dashboard-smoke.png",
                "what_to_capture": "Smoke status, failed count, endpoint table, and pack path.",
            },
            {
                "view": "Launch Checklist",
                "placeholder": "screenshots/launch-checklist-smoke-matrix.png",
                "what_to_capture": "Launch readiness metrics and smoke matrix rows.",
            },
            {
                "view": "Reviewer Quickstart",
                "placeholder": "screenshots/reviewer-quickstart-proof-map.png",
                "what_to_capture": "Verification commands and artifact proof map.",
            },
            {
                "view": "Artifact Inventory",
                "placeholder": "screenshots/artifact-inventory-latest-files.png",
                "what_to_capture": "Generated artifact directory freshness and ignored status.",
            },
            {
                "view": "Runtime Demo",
                "placeholder": "screenshots/runtime-demo-server-pack.png",
                "what_to_capture": "Readiness status, commands, port checks, and generated pack paths.",
            },
            {
                "view": "Scenario Dataset",
                "placeholder": "screenshots/scenario-dataset-coverage-pack.png",
                "what_to_capture": "Scenario catalog domains, expected outcomes, eval status, and generated pack paths.",
            },
            {
                "view": "On-Call Handoff",
                "placeholder": "screenshots/on-call-handoff-customer-comms-pack.png",
                "what_to_capture": "Communication readiness, SLA timeline, approval checklist, and generated pack paths.",
            },
            {
                "view": "Postmortem RCA",
                "placeholder": "screenshots/postmortem-rca-corrective-actions.png",
                "what_to_capture": "Root cause, corrective action owners, recurrence risk, scenario coverage, and generated pack paths.",
            },
            {
                "view": "Postmortem RCA",
                "placeholder": "screenshots/postmortem-review-board-closure-gates.png",
                "what_to_capture": "Postmortem review board, owner signoffs, closure gates, action priorities, and generated review pack paths.",
            },
            {
                "view": "Finance Impact",
                "placeholder": "screenshots/finance-impact-exposure-rollup.png",
                "what_to_capture": "Financial exposure, direct cost, ARR at risk, support minutes, engineering hours, and generated pack paths.",
            },
            {
                "view": "Evidence Retention",
                "placeholder": "screenshots/evidence-retention-custody-manifest.png",
                "what_to_capture": "Evidence score, run completeness, artifact custody, hash manifest, and generated pack paths.",
            },
            {
                "view": "Capacity Planning",
                "placeholder": "screenshots/capacity-planning-staffing-plan.png",
                "what_to_capture": "Capacity score, staffing gaps, queue forecast, owner actions, and generated pack paths.",
            },
            {
                "view": "Data Residency",
                "placeholder": "screenshots/data-residency-review-queue.png",
                "what_to_capture": "Residency score, PII exposure queue, local data flow map, owner actions, and generated pack paths.",
            },
            {
                "view": "Risk Register",
                "placeholder": "screenshots/risk-register-owner-actions.png",
                "what_to_capture": "Risk score, open risks, owner action plan, control signals, and generated pack paths.",
            },
            {
                "view": "Executive Daily Ops Brief",
                "placeholder": "screenshots/executive-daily-ops-brief.png",
                "what_to_capture": "Daily status, SLA exposure, blocked approvals, critical accounts, engineer load, and generated pack paths.",
            },
            {
                "view": "Autonomy Governance",
                "placeholder": "screenshots/autonomy-governance-tool-trust.png",
                "what_to_capture": "Governance score, loop budget controls, tool trust findings, owner actions, and generated pack paths.",
            },
            {
                "view": "Durable Workflows",
                "placeholder": "screenshots/durable-workflows-recovery-queue.png",
                "what_to_capture": "Durability score, checkpoint controls, resume tokens, recovery queue, and generated pack paths.",
            },
            {
                "view": "Escalation Quality",
                "placeholder": "screenshots/escalation-quality-review-gate.png",
                "what_to_capture": "Engineering escalation gate, actionability score, reviewer actions, and generated pack paths.",
            },
            {
                "view": "Tool Governance",
                "placeholder": "screenshots/tool-governance-registry.png",
                "what_to_capture": "Tool governance score, manifest controls, approval matrix, unknown-tool queue, and generated pack paths.",
            },
        ]

    def _markdown(self, pack: dict[str, Any]) -> str:
        smoke = pack["dashboard_smoke"]
        summary = smoke["summary"]
        view_rows = [
            f"| {item['label']} | {'yes' if item['present'] else 'no'} | {item['position'] or ''} |"
            for item in smoke["expected_views"]
        ]
        endpoint_rows = [
            (
                f"| `{item['endpoint']}` | {item['dashboard_reference_present']} | "
                f"{item['route_present']} | {item['purpose']} |"
            )
            for item in smoke["endpoint_references"]
        ]
        artifact_rows = [
            (
                f"| {item['tab_label']} | `{item['producer_endpoint']}` | "
                f"`{item['artifact_directory']}` | {item['tab_present']} |"
            )
            for item in smoke["generated_artifact_tabs"]
        ]
        checklist_rows = [
            f"- [ ] **{item['item']}**: `{item['command']}` Expected: {item['expected']}"
            for item in pack["reviewer_checklist"]
        ]
        screenshot_rows = [
            f"- **{item['view']}**: `{item['placeholder']}` - {item['what_to_capture']}"
            for item in pack["screenshot_placeholders"]
        ]
        troubleshooting_rows = [f"- {item}" for item in pack["troubleshooting"]]
        limitation_rows = [f"- {item}" for item in pack["limitations"]]
        return "\n".join(
            [
                f"# UI Verification Pack: {pack['pack_id']}",
                "",
                "## Dashboard Smoke",
                f"- Status: **{smoke['status']}**",
                f"- Total checks: {summary['total_checks']}",
                f"- Passed checks: {summary['passed_checks']}",
                f"- Failed checks: {summary['failed_checks']}",
                f"- Dashboard source: `{smoke['dashboard_source']}`",
                "",
                "## Streamlit Run Command",
                f"`{pack['streamlit_run_command']}`",
                "",
                "## Reviewer Checklist",
                *checklist_rows,
                "",
                "## Expected Views",
                "| View | Present | Position |",
                "| --- | --- | ---: |",
                *view_rows,
                "",
                "## Endpoint References",
                "| Endpoint | Dashboard Reference | API Route | Purpose |",
                "| --- | --- | --- | --- |",
                *endpoint_rows,
                "",
                "## Generated Artifact Tabs",
                "| Tab | Producer | Artifact Directory | Present |",
                "| --- | --- | --- | --- |",
                *artifact_rows,
                "",
                "## Screenshot Placeholders",
                *screenshot_rows,
                "",
                "## Troubleshooting",
                *troubleshooting_rows,
                "",
                "## Limitations",
                *limitation_rows,
                "",
            ]
        )
