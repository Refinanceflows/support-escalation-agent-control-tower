Support teams lose time and increase customer risk when urgent tickets, SLA threats, internal knowledge, and engineering escalations are handled manually.

This control tower uses a LangGraph agent workflow to triage tickets, retrieve cited KB context, draft customer/engineering responses, and pause every risky action for human approval.

# Support Escalation Agent Control Tower

`support-escalation-agent-control-tower` / `agent-escalation-tower` is a local-first portfolio implementation of an AI-assisted support escalation control tower. It helps support teams ingest tickets, classify intent, detect SLA risk, retrieve internal KB context, draft customer and engineering responses, pause for human approval, and preserve trace/audit/metrics evidence for every run.

The default mode uses deterministic local/mock providers, so a fresh clone runs without paid LLM keys. Optional OpenAI and Azure OpenAI adapters are available behind the provider interface, with local fallback and human-approval boundaries preserved.

## What Is Included

- Python 3.11+, FastAPI, Pydantic, pydantic-settings, async services
- LangGraph workflow orchestration with a documented sequential fallback if LangGraph cannot import
- Required workflow nodes:
  `intake_classifier`, `sla_risk_scorer`, `playbook_recommender`, `knowledge_retriever`, `customer_reply_drafter`, `engineering_escalation_drafter`, `qa_evaluator`, `human_approval`, `finalizer`
- SQLite-backed durable state for tickets, runs, traces, approvals, audit events, and metrics
- Fake Zendesk, Jira, Slack, and internal KB adapters
- Persistent local integration outbox for approved fake customer replies, Zendesk updates, Jira issues, engineering escalations, and Slack alerts
- Deterministic KB failure drill that proves retry exhaustion, trace evidence, and human-review approval gating
- SLA breach simulator that creates or reuses local sample tickets, ranks managers' risk queue, and links every row to a run and approval
- Incident brief export to local Markdown/JSON with customer impact, SLA risk, citations, drafts, approval, trace, outbox, and next steps
- Support playbook recommender with SSO outage, webhook regression, billing dispute, privacy export, and API key rotation playbooks
- Remediation checklist export to local Markdown/JSON with ticket context, selected playbook, owners, approval state, and next customer update
- Ops analytics snapshot across tickets, runs, approvals, outbox, SLA risk, failures, latency, tokens, and cost
- Weekly review export to ignored local Markdown/JSON reports for support leadership demos
- Customer health scoring by account with ticket, SLA, approval, failure, playbook, and outbox signals
- Account brief export to local Markdown/JSON for customer success and support leadership review
- SLO budget monitor for latency, tokens, cost, failures, approvals, and outbox dispatch delay
- Optimization report export with slow nodes, high-token nodes, failure hotspots, approval bottlenecks, and recommended fixes
- Interview scenario runner and evidence pack export that links the complete local demo into Markdown/JSON artifacts
- Runbook QA scoring for operator handoff completeness across incident brief, checklist, weekly review, account brief, SLO, optimization, traces, approvals, outbox, and failure drills
- Operator readiness pack export under `data/operator_packs/` with QA result, critical metrics, endpoint list, demo command, JD skills, and interviewer talking points
- Executive Daily Ops Brief Pack under `data/daily_ops_briefs/`, summarizing SLA exposure, blocked approvals, engineer load, critical accounts, control signals, and owner actions for daily command-center review
- Change Risk Simulator / Escalation Replay Lab for replaying a past or sample run under higher SLA pressure, missing/conflicting KB context, adapter degradation/failure, confidence overrides, and approval policy changes
- Replay report export under `data/replay_reports/` with original-vs-replay comparison, trace IDs, risk flags, verification commands, JD skills, and interviewer talking points
- Agent Policy Guardrail Center with approval policy simulation for low confidence, SLA pressure, enterprise/VIP tier, external vs internal actions, adapter health, replay risk, and KB grounding
- Policy pack export under `data/policy_packs/` with simulated policies, matched rules, approval matrix, sample outcomes, verification commands, JD skills, and interviewer talking points
- Agent Policy Simulation Pack export under `data/policy_change_packs/` with approval threshold, confidence cutoff, SLA routing, blast-radius, scenario delta, and rollout recommendation evidence
- Customer Impact Timeline and Executive Incident Narrative export under `data/incident_narratives/`, connecting ticket intake, triage, approval, dispatch, policy, replay, SLO, account health, and owner next steps into one incident story
- Postmortem RCA + Corrective Action Tracking Pack under `data/rca_packs/`, with root cause classification, contributing factors, corrective action owners, due dates, customer follow-up state, recurrence risk, trace/audit links, proof commands, and deterministic scenario coverage
- Postmortem Review Board and Corrective Action Review Pack under `data/postmortem_review_packs/`, converting RCA actions into role-owned closure lanes, delegated crews, signoffs, closure gates, run transparency, and artifact handoffs
- Escalation Finance Impact estimates for support cost, SLA penalty exposure, engineering effort, and customer ARR at risk, plus Markdown/JSON executive pack export under `data/finance_impact_packs/`
- Leadership Scorecard for automation KPI review across safety, approvals, SLA risk, escalation quality, failures, policy blocks, replay risk, customer impact, and operator readiness
- Leadership review pack export under `data/leadership_reviews/` with KPI definitions, evidence links, top risks, next actions, local commands, JD skills, and interviewer talking points
- Knowledge Quality Auditor for KB freshness, coverage, conflicting guidance, missing citations, high-impact gaps, impacted ticket types, owner recommendations, and readiness status
- KB refresh plan export under `data/kb_refresh_plans/` with article tasks, owners, acceptance criteria, impacted workflows, local commands, JD skills, and five interviewer talking points
- Runbook Coverage audit and Gap Pack export under `data/runbook_gap_packs/`, mapping tickets and scenarios to KB/runbook coverage, missing runbook categories, owner assignments, process modes, review gates, artifact handoffs, run transparency, endpoint evidence, and remediation tasks
- Local Launch Checklist and API Smoke Matrix for GitHub reviewers, including setup commands, endpoint checks, artifact expectations, eval commands, troubleshooting notes, JD skills, and interviewer talking points
- Portfolio Evidence Index mapping JD skills to local features, endpoints, tests/evals, artifacts, demo commands, and proof paths
- Interview Pack export under `data/portfolio_packs/` with a 3-minute demo script, technical talking points, architecture walk-through, failure story, verification commands, metrics/eval summary, artifact inventory, and resume/GitHub bullets
- Release Candidate quality gate and GitHub Publish Pack export under `data/release_packs/`, with CI/docs/test/eval/demo/API/artifact coverage, publish readiness, verification commands, expected outputs, endpoint inventory, GitHub checklist, recruiter notes, and limitations
- Local CI Doctor and Dependency/Secrets Audit Pack under `data/audit_packs/`, with deterministic checks for test/lint/eval/demo commands, GitHub Actions, Docker Compose, docs, ignored artifacts, dependency files, local/mock notes, and a redacted secret scan
- Reviewer Quickstart and Walkthrough Pack under `data/reviewer_packs/`, with exact setup commands, one-command demo, verification commands, endpoint walkthrough, agent workflow walkthrough, artifact proof map, recruiter story, engineer proof tour, GitHub README blurb, and limitations
- Artifact Inventory and README Checklist Pack under `data/artifact_indexes/`, with generated directories, latest files, producer endpoints/commands, ignored status, reviewer purpose, freshness notes, badge suggestions, and a reviewer proof checklist
- README Consistency Final Audit and Final Handoff Pack under `data/final_handoff/`, with structured checks that README/docs/API/demo/dashboard claims match implemented routes, scripts, generated artifact docs, and local/mock limitations
- On-Call Handoff + Customer Communications Simulation Pack under `data/customer_comms_packs/`, with owner handoff, customer update drafts, engineering ticket draft, SLA/customer-impact timeline, approval checklist, guardrail status, trace IDs, scenario coverage, and communication readiness
- Customer Communication Quality Pack under `data/communication_quality_packs/`, scoring drafted replies for empathy, specificity, policy compliance, escalation clarity, role-crew review, review gates, run transparency, and artifact handoffs
- Engineering Escalation Quality Pack under `data/escalation_quality_packs/`, scoring Jira-ready escalation drafts for actionability, reproduction evidence, customer impact, routing governance, and noise control before internal dispatch
- GitHub Push Readiness + Branch Hygiene Pack under `data/git_packs/`, with read-only local git checks, changed-file grouping, ignored artifact verification, suspicious generated/large file review, pre-push verification commands, and recruiter/GitHub README publish blurb
- API Contract Audit and Reviewer Collection Pack under `data/api_contracts/`, with OpenAPI route counts, auth-protected endpoint counts, docs/dashboard/demo/artifact coverage, endpoint inventory, sample curl/PowerShell commands, and local-only limitations
- Runtime Demo Server Pack under `data/runtime_packs/`, with source-only readiness checks, exact FastAPI/Streamlit commands, read-only port/process checks, health URLs, screenshot placeholders, troubleshooting, and recruiter/engineer explanations
- Scenario Dataset catalog and Eval Coverage Pack under `data/scenario_packs/`, with richer fake enterprise tickets across security, billing, privacy exports, outages, webhook/API failures, onboarding, renewal risk, and ambiguity
- Evidence Retention and Chain-of-Custody Pack under `data/evidence_packs/`, auditing local trace, approval, outbox, audit-event, generated-artifact, and SHA-256 hash coverage
- Support Capacity Forecast and Staffing Plan under `data/capacity_plans/`, mapping active tickets, scenario fixtures, and run history to queue load, FTE gaps, owners, and remediation actions
- Data Residency and PII Exposure Pack under `data/data_residency_packs/`, auditing local tickets, drafts, approvals, outbox payloads, account regions, regulated segments, and sensitive support data before production adapters are enabled
- Access Control Review Pack under `data/access_review_packs/`, mapping FastAPI endpoints to least-privilege roles, production scopes, findings, and production authz acceptance criteria
- Enterprise Risk Register Pack under `data/risk_registers/`, consolidating finance, compliance, capacity, evidence, access, KB, runbook, SLO, leadership, and release risks into owner actions
- Provider Readiness Guard Pack under `data/provider_readiness_packs/`, auditing local/mock default posture, optional OpenAI/Azure adapter readiness, secret redaction, fallback policy, and production activation tasks
- Autonomy Governance and Tool Trust Pack under `data/autonomy_governance_packs/`, auditing autonomous loop budgets, trusted tool usage, HITL dispatch boundaries, token/cost visibility, findings, and owner actions
- Durable Workflow Recovery Pack under `data/workflow_recovery_packs/`, auditing persisted node checkpoints, resume tokens, HITL recovery readiness, and operator recovery queues
- Autonomous Support Operations Pack under `data/support_ops_packs/`, building role crews, delegated task boards, process modes, review gates, run transparency, and artifact handoffs for support leaders, account teams, and engineering escalation owners
- Support Ops Worker Sandbox Pack under `data/support_ops_sandbox/`, simulating delegated task execution with local workers, task budgets, tool transcripts, worker scale-out decisions, verification gates, and dispatch guardrails
- Tool Governance and Marketplace Trust Pack under `data/tool_governance_packs/`, auditing local tool manifests, owners, risk tiers, data exposure, HITL boundaries, failure modes, unknown tools, and tool intake gates
- Local mock LLM provider behind an interface
- API key auth, structured logs, request trace IDs, audit events, token/latency/cost metrics
  - Streamlit dashboard for queue, approvals, trace timeline, outbox payloads, reliability drills, SLA simulation, incident briefs, incident narratives, Postmortem RCA, Postmortem Review Board, Finance Impact, Evidence Retention, Capacity Planning, Data Residency, Access Control, Risk Register, Provider Readiness, Executive Daily Ops Brief, Autonomy Governance, Durable Workflows, Support Ops Crews, Support Ops Sandbox, playbooks/remediation, customer health/account briefs, ops analytics, SLO optimization, Replay Lab, Policy Guardrails, Policy Change Simulation, Policy Rollout Review Gate, Operator QA / Readiness Pack, Leadership Scorecard, Knowledge Quality, Runbook Coverage, Portfolio Pack, Release Pack, CI Doctor / Audit Pack, Reviewer Quickstart, Artifact Inventory, UI Verification, Final Handoff, On-Call Handoff, Git Readiness, API Contract, Runtime Demo, Scenario Dataset, and metrics
- Sample tickets, scenario catalog, playbooks, and KB fixtures
- Docker Compose, GitHub Actions CI, `.env.example`, Makefile, pytest suite

## Quick Start

```bash
python -m venv .venv
.venv\Scripts\activate
python -m pip install -e ".[dev]"
copy .env.example .env
uvicorn app.main:app --reload --port 8000
```

In another terminal:

```bash
curl -X POST http://localhost:8000/auth/demo-token
curl -X POST http://localhost:8000/tickets/ingest-samples -H "x-api-key: demo-control-tower-key"
```

Open the API docs at [http://localhost:8000/docs](http://localhost:8000/docs).

Run the dashboard:

```bash
streamlit run dashboard/streamlit_app.py
```

Run the dashboard smoke source check without launching a browser:

```powershell
.\.venv\Scripts\python.exe scripts\dashboard_smoke.py
```

Run the runtime readiness source check without a running server:

```powershell
.\.venv\Scripts\python.exe scripts\runtime_check.py
```

Run tests:

```bash
pytest
```

TRD command set:

```bash
make install
make test
make dev
make dashboard
make demo
make eval
```

Windows equivalents:

```powershell
python -m pip install -e ".[dev]"
pytest
uvicorn app.main:app --reload --port 8000
streamlit run dashboard/streamlit_app.py
python scripts/demo_run.py
python -m app.evals.run_eval
```

Docker:

```bash
docker compose up --build
```

API: `http://localhost:8000`
Dashboard: `http://localhost:8501`

## Demo Flow

One-command interview demo:

```powershell
python scripts/demo_run.py
```

The command calls `POST /demo/evidence-pack`, `POST /ops/operator-readiness-pack`, `POST /policies/export`, `GET /leadership/scorecard`, `POST /leadership/review-pack`, `GET /knowledge/quality-audit`, `POST /knowledge/refresh-plan`, `GET /runbooks/coverage-audit`, `POST /runbooks/gap-pack`, `GET /ops/smoke-matrix`, `POST /ops/launch-checklist`, `GET /portfolio/evidence-index`, `POST /portfolio/interview-pack`, `GET /release/quality-gate`, `POST /release/publish-pack`, `GET /reviewer/quickstart`, `POST /reviewer/walkthrough-pack`, `GET /ops/ci-doctor`, `POST /ops/audit-pack`, `GET /artifacts/inventory`, `POST /artifacts/readme-checklist`, `GET /ui/dashboard-smoke`, `POST /ui/verification-pack`, `GET /handoff/final-audit`, `POST /handoff/final-pack`, `GET /git/readiness`, `POST /git/push-plan`, `GET /api/contract-audit`, `POST /api/reviewer-collection`, `GET /runtime/demo-readiness`, `POST /runtime/demo-pack`, `GET /scenarios/catalog`, `POST /scenarios/eval-pack`, `GET /incidents/postmortem-summary`, `POST /incidents/rca-pack`, `POST /finance/impact-summary`, `POST /finance/impact-pack`, `GET /evidence/retention-audit`, `POST /evidence/retention-pack`, `GET /capacity/forecast`, `POST /capacity/staffing-plan`, `GET /compliance/data-residency-audit`, `POST /compliance/data-residency-pack`, `GET /security/access-matrix`, `POST /security/access-review-pack`, `GET /risk/register`, `POST /risk/register-pack`, `GET /providers/readiness`, `POST /providers/readiness-pack`, `GET /governance/autonomy-audit`, `POST /governance/autonomy-pack`, `GET /workflows/durability-audit`, `POST /workflows/durability-pack`, `GET /tools/registry`, `POST /tools/governance-pack`, `GET /ops/daily-brief`, and `POST /ops/daily-brief-pack` when the API is running, or falls back to an in-process local app. It runs the complete deterministic scenario and writes the evidence pack under `data/demo_packs/`, the operator readiness pack under `data/operator_packs/`, the Replay Lab report under `data/replay_reports/`, the approval policy pack under `data/policy_packs/`, the executive incident narrative under `data/incident_narratives/`, the RCA Pack under `data/rca_packs/`, the Finance Impact Pack under `data/finance_impact_packs/`, the Evidence Retention Pack under `data/evidence_packs/`, the Capacity Staffing Plan under `data/capacity_plans/`, the Data Residency Pack under `data/data_residency_packs/`, the Access Control Review Pack under `data/access_review_packs/`, the Enterprise Risk Register Pack under `data/risk_registers/`, the Provider Readiness Guard Pack under `data/provider_readiness_packs/`, the Autonomy Governance Pack under `data/autonomy_governance_packs/`, the Durable Workflow Recovery Pack under `data/workflow_recovery_packs/`, the Tool Governance Pack under `data/tool_governance_packs/`, the Executive Daily Ops Brief Pack under `data/daily_ops_briefs/`, the leadership review pack under `data/leadership_reviews/`, the KB refresh plan under `data/kb_refresh_plans/`, the Runbook Coverage Gap Pack under `data/runbook_gap_packs/`, the launch checklist under `data/launch_checklists/`, the Interview Pack under `data/portfolio_packs/`, the Publish Pack under `data/release_packs/`, the Walkthrough Pack under `data/reviewer_packs/`, the Audit Pack under `data/audit_packs/`, the README Checklist Pack under `data/artifact_indexes/`, the UI Verification Pack under `data/ui_verification/`, the Final Handoff Pack under `data/final_handoff/`, the Branch Hygiene Push Plan under `data/git_packs/`, the Reviewer Collection under `data/api_contracts/`, the Runtime Demo Server Pack under `data/runtime_packs/`, the Scenario Dataset Eval Coverage Pack under `data/scenario_packs/`, and linked incident brief, remediation checklist, weekly review, account brief, and optimization report artifacts. The console output includes launch readiness, launch checklist path, portfolio evidence score/count, Interview Pack path, release gate status/score, Publish Pack path, reviewer quickstart status/proof count, Walkthrough Pack path, CI Doctor status/score, secret scan findings, Audit Pack path, artifact inventory count, README Checklist path, Dashboard Smoke status/check count, UI Verification Pack path, final audit status/score, Final Handoff Pack path, Git readiness status/branch, Push Plan path, API Contract Audit status, Reviewer Collection path, Runtime Demo readiness and pack path, Scenario Dataset scenario coverage, Scenario Eval Pack path, Postmortem RCA status/root cause/action count, RCA Pack path, Finance Impact Pack path, Evidence Retention Pack path, Capacity Staffing Plan path, Data Residency Pack path, Access Control status/score, Access Review Pack path, Risk Register status/score/open risk count, Risk Register Pack path, Provider Readiness status/score, Autonomy Governance status/score, Workflow Durability status/score/checkpoint count, Tool Governance status/score/tool count, Daily Ops Brief status/high-SLA/approval/account counts, finance exposure, evidence retention score/hash count, replay risk score, policy decision, approval requirement, leadership readiness, KB readiness, KB refresh plan path, Runbook Coverage score/gap count, Runbook Gap Pack path, incident impact status, recommended operator action, and report paths.

1. Get a token from `POST /auth/demo-token`.
2. Ingest sample tickets with `POST /tickets/ingest-samples`.
3. Analyze a ticket with `POST /tickets/{ticket_id}/analyze`.
4. Inspect `GET /runs/{run_id}` and `GET /runs/{run_id}/trace`.
5. Review `GET /approvals`.
6. Approve with `POST /runs/{run_id}/approve` or reject with `POST /runs/{run_id}/reject`.
7. Inspect `GET /integrations/outbox` to see the fake Zendesk/Jira/Slack dispatch payloads.
8. Run `POST /drills/tool-failure` to see KB retry failure and approval gating.
9. Run `POST /drills/sla-breach-simulation` to get a prioritized SLA queue.
10. Export `POST /runs/{run_id}/incident-brief` for a leadership or engineering handoff.
11. Call `POST /playbooks/recommend` or inspect the run state for ranked playbooks.
12. Export `POST /runs/{run_id}/remediation-checklist` for owner-ready action steps.
13. Check `GET /analytics/ops-snapshot` for operational trends and recommended actions.
14. Export `POST /analytics/weekly-review` for a local weekly leadership report.
15. Review `GET /customers/health` for account-level risk.
16. Export `POST /customers/{customer_id_or_name}/account-brief`.
17. Check `GET /ops/slo-budget` for production-minded SLO status.
18. Export `POST /ops/optimization-report` for local optimization recommendations.
19. Run `POST /ops/runbook-qa` to score handoff completeness for a supplied, latest, or deterministic sample run.
20. Export `POST /ops/operator-readiness-pack` to write a Markdown/JSON readiness pack under `data/operator_packs/`.
20a. Review `GET /ops/daily-brief` for the executive daily command-center summary across SLA exposure, blocked approvals, engineer load, critical accounts, and control signals.
20b. Export `POST /ops/daily-brief-pack` to write the Executive Daily Ops Brief Pack under `data/daily_ops_briefs/`.
20c. Review `GET /ops/crew-plan` for role crews, delegated task boards, process modes, review gates, run transparency, and artifact handoffs.
20d. Export `POST /ops/crew-pack` to write the Autonomous Support Operations Pack under `data/support_ops_packs/`.
20e. Review `GET /ops/crew-sandbox` for deterministic local worker assignment, task budgets, tool transcripts, worker scale-out, and dispatch-boundary gates.
20f. Export `POST /ops/crew-sandbox-pack` to write the Support Ops Worker Sandbox Pack under `data/support_ops_sandbox/`.
 21. Run `POST /runs/{run_id}/replay-lab` or `POST /replay-lab/run` to compare original vs replay outcomes under changed risk conditions.
22. Export `POST /replay-lab/report` to write a Markdown/JSON Change Risk / Escalation Replay report under `data/replay_reports/`.
23. Run `POST /policies/simulate` to preview the approval policy decision for replies, Jira, Slack, and engineering escalation actions.
24. Export `POST /policies/export` to write a Markdown/JSON Policy Guardrail Pack under `data/policy_packs/`.
24a. Run `POST /policies/change-simulation` to compare approval thresholds, confidence cutoffs, SLA routing thresholds, and blast-radius scoring across the local scenario corpus.
24b. Export `POST /policies/change-pack` to write an Agent Policy Simulation Pack under `data/policy_change_packs/`.
24c. Run `POST /policies/rollout-plan` to convert those deltas into fail-closed review gates, canary phases, role signoffs, rollback triggers, and run-transparency evidence.
24d. Export `POST /policies/rollout-pack` to write a Policy Rollout Review Pack under `data/policy_rollout_packs/`.
25. Run `POST /incidents/timeline` to build the Customer Impact Timeline for a supplied, latest, or deterministic sample run.
26. Export `POST /incidents/executive-narrative` to write a Markdown/JSON executive incident story under `data/incident_narratives/`.
27. Review `GET /incidents/postmortem-summary` for root cause, corrective actions, customer follow-up state, recurrence risk, trace links, and scenario coverage.
28. Export `POST /incidents/rca-pack` to write the Postmortem RCA + Corrective Action Tracking Pack under `data/rca_packs/`.
28a. Review `GET /incidents/postmortem-review-board` for corrective-action owner lanes, role playbooks, delegated crews, closure gates, signoffs, run transparency, and artifact handoffs.
28b. Export `POST /incidents/postmortem-review-pack` to write the Postmortem Corrective Action Review Pack under `data/postmortem_review_packs/`.
28c. Review `POST /finance/impact-summary` for local support cost, SLA penalty exposure, engineering effort, and customer ARR at risk.
28d. Export `POST /finance/impact-pack` to write the Escalation Finance Impact Pack under `data/finance_impact_packs/`.
28c. Review `GET /governance/autonomy-audit` for autonomous loop budget, tool trust, HITL boundary, token/cost, and owner-action controls.
28d. Export `POST /governance/autonomy-pack` to write the Autonomy Governance and Tool Trust Pack under `data/autonomy_governance_packs/`.
28e. Review `GET /workflows/durability-audit` for persisted checkpoints, resume tokens, HITL recovery readiness, and operator recovery queues.
28f. Export `POST /workflows/durability-pack` to write the Durable Workflow Recovery Pack under `data/workflow_recovery_packs/`.
28g. Review `GET /tools/registry` for tool manifests, owners, data exposure, approval boundaries, observed usage, and unknown-tool findings.
28h. Export `POST /tools/governance-pack` to write the Tool Governance and Marketplace Trust Pack under `data/tool_governance_packs/`.
29. Review `GET /leadership/scorecard` for the executive automation KPI scorecard.
30. Export `POST /leadership/review-pack` to write a Markdown/JSON leadership review under `data/leadership_reviews/`.
31. Review `GET /knowledge/quality-audit` for KB coverage, freshness, citation, conflict, and readiness signals.
32. Export `POST /knowledge/refresh-plan` to write a Markdown/JSON KB refresh plan under `data/kb_refresh_plans/`.
32a. Review `GET /runbooks/coverage-audit` for ticket-to-KB/runbook coverage, missing runbook gaps, owner assignments, role playbooks, process mode, review gates, artifact handoffs, run transparency, endpoint evidence, and limitations.
32b. Export `POST /runbooks/gap-pack` to write a Markdown/JSON Runbook Coverage Gap Pack under `data/runbook_gap_packs/` with delegated owner tasks and reviewer gates.
33. Run `POST /demo/scenario-run` to orchestrate the full interview scenario and return artifact paths plus summary metrics.
34. Export `POST /demo/evidence-pack` to write the concise Markdown/JSON interview pack.
35. Review `GET /ops/smoke-matrix` for endpoint checks, expected statuses, commands, artifact expectations, and launch readiness.
36. Export `POST /ops/launch-checklist` to write the GitHub reviewer checklist under `data/launch_checklists/`.
37. Review `GET /portfolio/evidence-index` for the structured Portfolio Evidence map and evidence score.
38. Export `POST /portfolio/interview-pack` to write the recruiter/interviewer-ready Interview Pack under `data/portfolio_packs/`.
39. Review `GET /release/quality-gate` for the Release Candidate gate status, score, blockers/warnings, coverage, checklist, runtime notes, and publish readiness.
40. Export `POST /release/publish-pack` to write the GitHub-ready Publish Pack under `data/release_packs/`.
41. Review `GET /reviewer/quickstart` for exact local setup, one-command demo, verification commands, endpoint walkthrough order, agent workflow walkthrough, artifact proof map, expected outputs, troubleshooting, and role-specific reviewer notes.
42. Export `POST /reviewer/walkthrough-pack` to write the recruiter and engineer Walkthrough Pack under `data/reviewer_packs/`.
43. Review `GET /ops/ci-doctor` for deterministic CI/docs/tests/env/Docker/dependency/local-mock/secret scan checks.
44. Export `POST /ops/audit-pack` to write the Dependency/Secrets Audit Pack under `data/audit_packs/`.
45. Review `GET /artifacts/inventory` for generated artifact directories, latest files, producer endpoints/commands, ignored status, reviewer purpose, and freshness notes.
46. Export `POST /artifacts/readme-checklist` to write the README Checklist Pack and reviewer proof checklist under `data/artifact_indexes/`.
47. Run `GET /ui/dashboard-smoke` or `scripts/dashboard_smoke.py` for Dashboard Smoke source wiring across dashboard tabs, endpoints, and generated artifact tabs.
48. Export `POST /ui/verification-pack` to write the UI Verification Pack under `data/ui_verification/` with reviewer checklist, screenshot placeholders, troubleshooting, and limitations.
49. Review `GET /handoff/final-audit` for README Consistency final audit checks across README/docs/API/demo/dashboard scripts, generated artifact docs, and local/mock Azure limitations.
50. Export `POST /handoff/final-pack` to write the Final Handoff Pack under `data/final_handoff/`.
51. Review `GET /handoff/on-call-summary` for On-Call Handoff owners, severity, SLA deadline, trace links, approval/guardrail state, and communication readiness.
52. Export `POST /handoff/customer-comms-pack` to write the Customer Communications Simulation Pack under `data/customer_comms_packs/`.
53. Review `GET /git/readiness` for GitHub Push Readiness and Branch Hygiene checks across the local branch, dirty worktree, ignored generated artifacts, GitHub Actions workflow, `.env.example`, README final handoff mention, suspicious files, and recommended commit groups.
54. Export `POST /git/push-plan` to write the local-only Push Plan under `data/git_packs/`.
55. Review `GET /api/contract-audit` for OpenAPI route counts, API-key protection, docs/API coverage, dashboard smoke alignment, generated artifact endpoint coverage, demo flow coverage, and local-only limitations.
56. Export `POST /api/reviewer-collection` to write the API Contract Reviewer Collection under `data/api_contracts/`.
57. Review `GET /runtime/demo-readiness` for exact FastAPI/Streamlit commands, ports, environment defaults, dependency checks, read-only port/process checks, health URLs, smoke URLs, troubleshooting, and limitations.
58. Export `POST /runtime/demo-pack` to write the Runtime Demo Server Pack under `data/runtime_packs/`.
59. Review `GET /scenarios/catalog` for the scenario catalog, expected outcomes, and scenario coverage summary.
60. Export `POST /scenarios/eval-pack` to write the Scenario Dataset Eval Coverage Pack under `data/scenario_packs/`.
61. Review `GET /evidence/retention-audit` for local trace, approval, outbox, audit-event, artifact, and hash custody coverage.
62. Export `POST /evidence/retention-pack` to write the Evidence Retention and Chain-of-Custody Pack under `data/evidence_packs/`.
63. Review `GET /capacity/forecast` for local support queue load, required FTE, available FTE, and staffing gaps.
64. Export `POST /capacity/staffing-plan` to write the Capacity Forecast and Staffing Plan under `data/capacity_plans/`.
65. Review `GET /compliance/data-residency-audit` for local PII, restricted-region, regulated-segment, approval, and outbox exposure risks.
66. Export `POST /compliance/data-residency-pack` to write the Data Residency and PII Exposure Pack under `data/data_residency_packs/`.
67. Review `GET /security/access-matrix` for least-privilege role mapping, production scopes, findings, and local demo auth limitations.
68. Export `POST /security/access-review-pack` to write the Access Control Review Pack under `data/access_review_packs/`.
69. Review `GET /risk/register` for a consolidated owner-prioritized risk register across local finance, compliance, capacity, access, evidence, KB, runbook, SLO, leadership, and release controls.
70. Export `POST /risk/register-pack` to write the Enterprise Risk Register Pack under `data/risk_registers/`.
71. Review `GET /providers/readiness` for local/mock default posture, optional OpenAI/Azure credential readiness, fallback policy, and secret redaction.
72. Export `POST /providers/readiness-pack` to write the Provider Readiness Guard Pack under `data/provider_readiness_packs/`.
73. Review `GET /tools/registry` for tool manifests, owners, risk tiers, data exposure, HITL boundaries, observed usage, and marketplace intake policy.
74. Export `POST /tools/governance-pack` to write the Tool Governance and Marketplace Trust Pack under `data/tool_governance_packs/`.
75. Check `GET /health`, `GET /tickets`, `GET /metrics/agent-performance`, `GET /integrations/outbox/{outbox_id}`, and `GET /audit/events`.

## Scope Guardrails

This project intentionally stays focused on escalation operations:

- triage and classification
- SLA risk detection
- internal KB retrieval
- draft customer replies
- draft engineering escalations
- human approval before dispatch
- trace, audit, and performance monitoring

It does not become a full helpdesk SaaS, CRM, or customer chat widget.

## Configuration

See `.env.example`.

Important variables:

- `CONTROL_TOWER_API_KEYS`: comma-separated accepted API keys
- `CONTROL_TOWER_DEMO_API_KEY`: key returned by demo token endpoint
- `CONTROL_TOWER_STATE_FILE`: SQLite persistence path
- `CONTROL_TOWER_MAX_TOOL_ATTEMPTS`: KB/tool retry limit
- `CONTROL_TOWER_LOW_CONFIDENCE_THRESHOLD`: confidence threshold for review
- `CONTROL_TOWER_SLA_HIGH_RISK_THRESHOLD`: escalation threshold
- `CONTROL_TOWER_LLM_PROVIDER`: local/mock default; set `openai` or `azure_openai` only when optional credentials, timeout, token budget, and fallback controls are configured
- `CONTROL_TOWER_OPENAI_API_KEY`, `OPENAI_API_KEY`, `CONTROL_TOWER_OPENAI_MODEL`, `CONTROL_TOWER_OPENAI_BASE_URL`: optional OpenAI adapter settings
- `CONTROL_TOWER_AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_ENDPOINT`, `CONTROL_TOWER_AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_API_KEY`, `CONTROL_TOWER_AZURE_OPENAI_DEPLOYMENT`, `AZURE_OPENAI_DEPLOYMENT`, `CONTROL_TOWER_AZURE_OPENAI_API_VERSION`: optional Azure OpenAI adapter settings
- `CONTROL_TOWER_LLM_TIMEOUT_SECONDS`, `CONTROL_TOWER_LLM_MAX_TOKENS`, `CONTROL_TOWER_LLM_FALLBACK_ENABLED`: optional live-provider guardrails

## Reliability Surfaces

- `GET /integrations/outbox`: persistent local event log for approved fake dispatches.
- `GET /integrations/outbox/{outbox_id}`: one dispatch payload and destination.
- `POST /drills/tool-failure`: local production-readiness drill with KB retry failures, trace timeline, and pending human approval.
- `POST /drills/sla-breach-simulation`: deterministic manager queue of breached, critical, warning, and watch tickets.
- `POST /runs/{run_id}/incident-brief`: writes Markdown and JSON under the local ignored briefs directory.
- `POST /playbooks/recommend`: returns ranked operational playbooks with confidence, reasons, owners, and checklist steps.
- `POST /runs/{run_id}/remediation-checklist`: writes Markdown and JSON under the local ignored checklists directory, normally `data/checklists/`.
- `GET /analytics/ops-snapshot`: aggregates ticket categories, SLA risk, final actions, approvals, outbox destinations, failures, and average latency/token/cost.
- `POST /analytics/weekly-review`: writes Markdown and JSON under the local ignored reports directory, normally `data/reports/`.
- `GET /customers/health`: groups local tickets into account health summaries with deterministic 0-100 scores and recommended actions.
- `POST /customers/{customer_id_or_name}/account-brief`: writes Markdown and JSON under `data/account_briefs/` with health, active tickets, recent runs, playbooks, approvals, outbox summary, and next actions.
- `GET /customers/renewal-risk`: combines local account health, fake renewal inputs, support sentiment, SLA drag, blockers, and ARR metadata into a renewal-risk queue.
- `GET /customers/renewal-control-board`: turns renewal risk into a HITL governance board with blocked automation actions, review checkpoints, owners, and deterministic resume tokens.
- `POST /customers/renewal-control-pack`: writes Markdown and JSON under `data/renewal_control_packs/` with the renewal control board, review queue, acceptance criteria, and local verification commands.
- `POST /customers/{customer_id_or_name}/renewal-review`: writes Markdown and JSON under `data/renewal_reviews/` with renewal risk, support evidence, blocker register, owner actions, and limitations.
- `GET /ops/slo-budget`: returns deterministic SLO status for workflow latency, token usage, cost, failures, pending approvals, and outbox dispatch delay.
- `POST /ops/optimization-report`: writes Markdown and JSON under `data/optimization_reports/` with SLO statuses, top slow nodes, high-token nodes, failure hotspots, approval bottlenecks, and recommended fixes.
- `GET /ops/ci-doctor`: returns the Local CI Doctor with structured checks for pytest, ruff, eval, demo, GitHub Actions, Docker Compose, `.env.example`, README sections, docs, ignored generated artifacts, dependency files, local/mock provider notes, and a redacted secret scan summary.
- `POST /ops/audit-pack`: writes Markdown and JSON under `data/audit_packs/` with CI Doctor results, dependency inventory, secret scan summary, verification commands, publish-safety checklist, remediation notes, and recruiter/interviewer explanation.
- `GET /ops/daily-brief`: returns the Executive Daily Ops Brief with SLA exposure, blocked approvals, engineer load, critical accounts, top risky tickets, control signals, and owner actions.
- `POST /ops/daily-brief-pack`: writes Markdown and JSON under `data/daily_ops_briefs/` with the daily command-center brief, decision table, local evidence links, verification commands, and limitations.
- `GET /ops/crew-plan`: returns the Autonomous Support Operations crew plan with support leader, account team, engineering owner, and operations commander crews, delegated tasks, selected process mode, review gates, run transparency, scenario coverage, and limitations.
- `POST /ops/crew-pack`: writes Markdown and JSON under `data/support_ops_packs/` with the crew plan, delegation board, review-gate summary, artifact handoff packet, local proof commands, and local/mock limitations.
- `GET /ops/crew-sandbox`: runs a deterministic local worker sandbox over the delegated support-ops tasks, returning worker assignments, tool transcripts, budget checks, scale-out decisions, issue-to-handoff loop stages, and verification gates.
- `POST /ops/crew-sandbox-pack`: writes Markdown and JSON under `data/support_ops_sandbox/` with the sandbox run, worker assignment board, transcript summary, verification summary, local proof commands, and local/mock limitations.
- `GET /tools/registry`: returns the Tool Governance Registry with manifest owners, risk tiers, data exposure, approval boundaries, failure modes, observed usage, unknown tool references, marketplace intake policy, owner actions, and limitations.
- `POST /tools/governance-pack`: writes Markdown and JSON under `data/tool_governance_packs/` with the registry, approval matrix, production acceptance criteria, local commands, and local/mock limitations.
- `POST /ops/runbook-qa`: scores required operator handoff sections and returns pass/fail, missing sections, warnings, artifact paths, and recommended fixes. If no `run_id` is supplied, it uses the latest local run or bootstraps a deterministic sample.
- `POST /ops/operator-readiness-pack`: writes Markdown and JSON under `data/operator_packs/` with Runbook QA, critical metrics, endpoint list, local demo command, JD skills demonstrated, and five interviewer talking points.
- `POST /runs/{run_id}/replay-lab`: replays a specific run under scenario modifiers and returns original vs replay comparison for classification, SLA risk, final action, approval requirement, failure state, tool attempts, latency/token/cost estimates, changed decisions, risk score, and recommended operator action.
- `POST /replay-lab/run`: fallback/sample-capable Escalation Replay endpoint. With no body, it uses the latest run or bootstraps a deterministic sample.
- `POST /replay-lab/report`: writes Markdown and JSON under `data/replay_reports/` with modifiers, trace IDs, risk flags, local verification commands, JD skills demonstrated, and five interviewer talking points.
- `POST /policies/simulate`: returns an approval policy decision, required approval type, blocked actions, allowed actions, matched rules, warnings, and recommended operator action for a supplied, latest, or sample run.
- `POST /policies/export`: writes Markdown and JSON under `data/policy_packs/` with simulated policies, matched rules, approval matrix, sample scenario outcomes, local verification commands, JD skills demonstrated, and five interviewer talking points.
- `POST /policies/change-simulation`: compares baseline and proposed approval thresholds, confidence cutoffs, and SLA high-risk thresholds over the local scenario corpus with blast-radius scoring.
- `POST /policies/change-pack`: writes Markdown and JSON under `data/policy_change_packs/` with scenario-level policy-change deltas, SLA routing impact, rollout recommendation, and reviewer talking points.
- `POST /policies/rollout-plan`: turns policy-change deltas into deterministic go/no-go gates, canary rollout phases, role signoffs, rollback triggers, run transparency, and artifact handoffs.
- `POST /policies/rollout-pack`: writes Markdown and JSON under `data/policy_rollout_packs/` for reviewer approval before policy promotion.
- `POST /incidents/timeline`: returns ordered Customer Impact Timeline events, impact summary, internal/external action split, policy/replay annotations, unresolved risks, owner next steps, and evidence artifact links for a supplied, latest, or sample run.
- `POST /incidents/executive-narrative`: writes Markdown and JSON under `data/incident_narratives/` with executive summary, timeline, approval evidence, policy decision, replay risk, SLO posture, JD skills, and interviewer talking points.
- `GET /incidents/postmortem-summary`: returns Postmortem RCA summary with severity, root cause category, contributing factors, approval/comms state, trace links, corrective actions, recurrence risk, customer follow-up state, readiness, and RCA scenario coverage.
- `POST /incidents/rca-pack`: writes Markdown and JSON under `data/rca_packs/` with postmortem narrative, timeline, trace/audit evidence, action owners, due dates, recurrence risk, customer follow-up state, proof commands, and limitations.
- `GET /incidents/postmortem-review-board`: returns a Postmortem Review Board with corrective-action lanes, owner signoffs, role playbooks, closure gates, review cadence, run transparency, and artifact handoffs.
- `POST /incidents/postmortem-review-pack`: writes Markdown and JSON under `data/postmortem_review_packs/` with the action board, closure owner summary, review-gate summary, artifact handoff packet, proof commands, and limitations.
- `POST /finance/impact-summary`: returns local deterministic finance impact estimates for a supplied, latest, or sample run, including support cost, SLA penalty exposure, engineering effort, ARR at risk, assumptions, limitations, risk flags, and recommended actions.
- `POST /finance/impact-pack`: writes Markdown and JSON under `data/finance_impact_packs/` with the Escalation Finance Impact Pack, executive decision table, finance controls, local commands, and local-only limitations.
- `GET /leadership/scorecard`: returns the local automation KPI scorecard with numeric category scores, trend-ish sample values, risk flags, recommended actions, artifact links, KPI definitions, and readiness status.
- `POST /leadership/review-pack`: writes Markdown and JSON under `data/leadership_reviews/` with scorecard, KPI definitions, local evidence links, top risks, next actions, local commands, JD skills demonstrated, and five interviewer talking points.
- `GET /knowledge/quality-audit`: returns the local KB readiness audit with coverage score, freshness/coverage/conflict/citation metrics, weak or missing articles, impacted ticket types, owner recommendations, risk flags, evidence sources, and readiness status.
- `POST /knowledge/refresh-plan`: writes Markdown and JSON under `data/kb_refresh_plans/` with article refresh tasks, owners, acceptance criteria, impacted workflows, local commands, JD skills demonstrated, and five interviewer talking points.
- `GET /runbooks/coverage-audit`: maps active/sample tickets and scenario fixtures to KB articles and runbook recommendations, returning coverage score, missing dedicated runbook gaps, owner assignments, selected process mode, role playbooks, delegated tasks, review gates, artifact handoffs, run transparency, endpoint evidence, and limitations.
- `POST /runbooks/gap-pack`: writes Markdown and JSON under `data/runbook_gap_packs/` with ticket coverage map, runbook gaps, owner-ready remediation tasks, delegated coverage tasks, acceptance criteria, review gates, artifact handoffs, local commands, JD skills, and interviewer talking points.
- `POST /demo/scenario-run`: runs the complete local interview scenario and returns linked artifact paths, endpoints exercised, and summary metrics.
- `POST /demo/evidence-pack`: writes Markdown and JSON under `data/demo_packs/` with the scenario summary, generated artifact paths, key metrics, endpoints exercised, and interview talking points.
- `GET /ops/smoke-matrix`: returns the API smoke matrix with expected status codes, sample curl and PowerShell commands, artifact expectations, and launch readiness.
- `POST /ops/launch-checklist`: writes Markdown and JSON under `data/launch_checklists/` with setup, smoke checks, demo path, eval commands, expected artifacts, troubleshooting, JD skills, and five interviewer talking points.
- `GET /portfolio/evidence-index`: returns the Portfolio Evidence Index with evidence score/count, JD skill evidence, endpoints, tests/evals, artifacts, demo commands, local proof paths, and local-only runtime counts.
- `POST /portfolio/interview-pack`: writes Markdown and JSON under `data/portfolio_packs/` with a 3-minute demo script, 8-10 technical talking points, architecture walk-through, failure mode story, local verification commands, metrics/eval summary, artifact inventory, and resume/GitHub README bullets.
- `GET /release/quality-gate`: returns the Release Candidate release gate with status, score, blockers, warnings, verification checklist, CI/docs/test/eval/demo/API coverage, artifact coverage, local-only runtime notes, and publish readiness.
- `POST /release/publish-pack`: writes Markdown and JSON under `data/release_packs/` with release summary, setup/demo/verification commands, expected outputs, endpoint inventory, artifact inventory, screenshot placeholders, GitHub repo checklist, commit/push readiness notes, recruiter review notes, and known limitations.
- `GET /reviewer/quickstart`: returns the Reviewer Quickstart with exact local setup commands, one-command demo, verification commands, endpoint walkthrough order, agent workflow walkthrough, artifact proof map, expected outputs, troubleshooting notes, and role-specific reviewer notes.
- `POST /reviewer/walkthrough-pack`: writes Markdown and JSON under `data/reviewer_packs/` with a recruiter-friendly story, engineer deep-dive path, command checklist, API/workflow proof tour, artifacts to inspect, limitations, and GitHub README blurb.
- `GET /artifacts/inventory`: returns the Artifact Inventory with generated artifact directories, latest files, producer endpoints/commands, ignored status, reviewer purpose, local commands, and freshness notes.
- `POST /artifacts/readme-checklist`: writes Markdown and JSON under `data/artifact_indexes/` with the Artifact Inventory, README Badge/Checklist suggestions, local commands, reviewer proof checklist, and cleanup/regeneration notes.
- `GET /ui/dashboard-smoke`: returns Dashboard Smoke source checks for expected Streamlit views, endpoint references, generated artifact tabs, local run commands, and local/mock limitations.
- `POST /ui/verification-pack`: writes Markdown and JSON under `data/ui_verification/` with Dashboard Smoke results, the Streamlit run command, reviewer checklist, screenshot placeholders, troubleshooting, and limitations.
- `GET /handoff/final-audit`: returns the README Consistency Final Audit with structured checks for README endpoint mentions, docs/api coverage, architecture/evaluation/workflow coverage, demo output claims, required scripts, dashboard smoke script presence, generated artifact directory docs, and local/mock Azure limitation clarity.
- `POST /handoff/final-pack`: writes Markdown and JSON under `data/final_handoff/` with final audit results, exact clone/run commands, end-to-end verification order, endpoint inventory summary, artifact inventory summary, dashboard smoke summary, recruiter-facing final README blurb, and limitations.
- `GET /handoff/on-call-summary`: returns latest or scenario-derived On-Call Handoff details with owners, severity, status, SLA deadline, trace links, approval/guardrail state, risk gaps, engineering ticket draft, customer updates, and communication readiness.
- `POST /handoff/customer-comms-pack`: writes Markdown and JSON under `data/customer_comms_packs/` with customer update drafts, internal handoff, engineering ticket draft, SLA/customer-impact timeline, approval checklist, trace IDs, local proof commands, and Scenario Dataset coverage across high SLA risk, low confidence, tool retry, billing/privacy, and outage/API paths.
- `GET /communications/quality-audit`: scores the latest or selected run's customer reply draft for empathy, specificity, policy compliance, escalation clarity, review-gate status, role-crew findings, run transparency, and required revisions.
- `POST /communications/quality-pack`: writes Markdown and JSON under `data/communication_quality_packs/` with communication quality scores, role playbook handoffs, artifact handoffs, reviewer actions, scenario coverage, and local proof commands.
- `GET /escalations/quality-audit`: scores the latest or selected run's engineering escalation draft for actionability, reproduction evidence, customer impact, routing governance, noise control, human approval readiness, trace-backed evidence, and required revisions.
- `POST /escalations/quality-pack`: writes Markdown and JSON under `data/escalation_quality_packs/` with escalation quality scores, role playbook handoffs, artifact handoffs, reviewer actions, scenario coverage, and local proof commands.
- `GET /git/readiness`: returns GitHub Push Readiness and Branch Hygiene checks from read-only local git inspection, including repo/branch detection, tracked/untracked/modified/ignored summary, generated artifact ignore checks, changed source/doc/test/dashboard buckets, suspicious large/generated files, GitHub Actions workflow presence, README final handoff mention, `.env.example`, dirty-worktree guidance, and recommended commit groups.
- `POST /git/push-plan`: writes Markdown and JSON under `data/git_packs/` with exact non-destructive review commands, suggested commit grouping, do-not-commit generated artifact notes, pre-push verification checklist, repo limitations, and recruiter/GitHub README publish blurb. It does not stage, commit, push, reset, checkout, clean, delete files, or call GitHub APIs.
- `GET /api/contract-audit`: returns the OpenAPI-derived API Contract Audit with route counts, auth-protected endpoint counts, docs/api coverage for important endpoints, dashboard smoke alignment, generated artifact endpoint coverage, demo flow endpoint coverage, missing docs warnings, duplicate/deprecated route warnings, and local-only limitations.
- `POST /api/reviewer-collection`: writes Markdown and JSON under `data/api_contracts/` with endpoint inventory grouped by domain, sample curl/PowerShell commands using `X-API-Key`, demo-token flow, expected status codes, auth notes, generated artifact endpoints, one-command verification order, and recruiter/engineer explanation.
- `GET /runtime/demo-readiness`: returns source-only Runtime Demo readiness with install/start commands, expected ports, environment defaults, dependency and file checks, safe read-only socket/netstat checks, health/smoke URLs, known limitations, and troubleshooting.
- `POST /runtime/demo-pack`: writes Markdown and JSON under `data/runtime_packs/` with exact start/stop commands, health checks, demo flow order, screenshot checklist placeholders, troubleshooting, recruiter and engineer explanations, and the embedded readiness report.
- `GET /scenarios/catalog`: returns the Scenario Dataset catalog with metadata, expected classification/SLA/approval/escalation outcomes, required domain presence, and scenario coverage summary.
- `POST /scenarios/eval-pack`: runs deterministic local checks over `sample_data/scenarios.json` and writes Markdown/JSON under `data/scenario_packs/` with classification accuracy, SLA routing, approval pause coverage, escalation coverage, low-confidence review coverage, failure/tool-retry coverage, and gaps/warnings.
- `GET /evidence/retention-audit`: returns local evidence retention readiness across recent runs, traces, approvals, outbox events, audit events, generated artifacts, and SHA-256 hash manifest coverage.
- `POST /evidence/retention-pack`: writes Markdown and JSON under `data/evidence_packs/` with custody review table, owner actions, findings, local commands, and local-only chain-of-custody limitations.
- `GET /capacity/forecast`: returns local deterministic capacity planning across active tickets, scenario fixtures, and run history, including queue load, projected effort, required FTE, available FTE, staffing gaps, owners, commands, and limitations.
- `POST /capacity/staffing-plan`: writes Markdown and JSON under `data/capacity_plans/` with queue forecast, staffing gaps, owner assignments, remediation actions, acceptance criteria, local commands, and local/mock limitations.
- `GET /compliance/data-residency-audit`: returns a local deterministic data residency and PII exposure audit across tickets, workflow drafts, approvals, outbox payloads, customer region/segment metadata, control checks, owner actions, commands, and limitations.
- `POST /compliance/data-residency-pack`: writes Markdown and JSON under `data/data_residency_packs/` with review queue, executive summary, owner actions, acceptance criteria, and local/mock limitations.
- `GET /security/access-matrix`: returns a local least-privilege access matrix over the FastAPI route inventory, including public/protected endpoint counts, role mappings, production scopes, owner roles, findings, and demo-key limitations.
- `POST /security/access-review-pack`: writes Markdown and JSON under `data/access_review_packs/` with the access matrix, acceptance criteria, production authz backlog, reviewer walkthrough, and local verification commands.
- `GET /risk/register`: returns the local Enterprise Risk Register with risk score, owner action plan, control signal summary, endpoints, limitations, and risks from finance, compliance, capacity, access, evidence, KB, runbook, SLO, leadership, and release controls.
- `POST /risk/register-pack`: writes Markdown and JSON under `data/risk_registers/` with executive summary, owner action plan, control signals, acceptance criteria, local commands, and local/mock limitations.
- `GET /providers/readiness`: returns local provider readiness for the configured LLM mode, local/mock default, optional OpenAI/Azure adapter classes, credential presence, fallback policy, redacted env audit, production backlog, commands, and limitations.
- `POST /providers/readiness-pack`: writes Markdown and JSON under `data/provider_readiness_packs/` with provider checks, activation checklist, acceptance criteria, production backlog, local commands, JD skills, and limitations.
- `GET /metrics/agent-performance`: includes approval count, outbox dispatch count, failure count, failure-drill count, average node latency, average tokens per run, and average cost per run.

## Repository Layout

```text
app/
  api/             FastAPI routes
  adapters/        Fake and provider adapter interfaces
  core/            config, logging, auth, storage
  models/          Pydantic domain models
  services/        ticket, workflow, retrieval, scenario catalog/evals, playbook, approval, trace, metrics, audit, customer health, ops SLOs, reviewer quickstart, UI verification, API contract audit, runtime demo readiness, data residency, access control, provider readiness
dashboard/         Streamlit control tower
docs/              architecture, API, workflow, evals, deployment notes
sample_data/       tickets, scenarios, customers, playbooks, and KB fixtures
tests/             pytest coverage
```
