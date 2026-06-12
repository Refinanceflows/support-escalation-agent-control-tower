# API

Base URL: `http://localhost:8000`

Auth: send `x-api-key: demo-control-tower-key` or `Authorization: Bearer demo-control-tower-key`.

## Endpoints

- `POST /auth/demo-token`
  Returns the local demo token.

- `POST /tickets/ingest`
  Creates a ticket.

- `POST /tickets/ingest-samples`
  Loads the bundled local sample tickets for deterministic demos.

- `GET /tickets`
  Lists tickets.

- `POST /tickets/{ticket_id}/analyze`
  Starts an agent run for a ticket. The run executes all workflow nodes and pauses at approval before dispatching customer replies or engineering tickets.

- `GET /runs/{run_id}`
  Returns run state, classification, SLA risk, KB results, drafts, QA result, approval ID, metrics, final action, and failure state.

- `GET /runs/{run_id}/trace`
  Returns node and tool trace events.

- `POST /runs/{run_id}/replay-lab`
  Runs the Change Risk Simulator / Escalation Replay Lab for one stored run. The optional body accepts `modifiers` with `sla_pressure` (`normal`, `high`, `critical`), `kb_context` (`full`, `missing`, `conflicting`), `adapter_health` (`healthy`, `degraded`, `failing`), optional `confidence_override`, and `approval_policy` (`strict`, `standard`, `auto_internal_only`). The response compares original vs replay classification, SLA risk, final action, approval requirement, failure state, tool attempts, latency/token/cost estimates, changed decisions, risk score, and recommended operator action.

- `POST /replay-lab/run`
  Same replay comparison, but accepts an optional `run_id` in the body and falls back to the latest run or a deterministic sample when omitted.

- `POST /replay-lab/report`
  Writes Markdown and JSON under the ignored replay report folder, normally `data/replay_reports/`. The report includes comparison, modifiers, trace IDs, risk flags, local verification commands, JD skills demonstrated, and five interviewer talking points.

- `POST /policies/simulate`
  Runs the Agent Policy Guardrail Center approval policy simulator for a supplied `run_id`, the latest local run, or a deterministic sample fallback when omitted. The optional body accepts Replay Lab `modifiers`, `requested_actions`, and `replay_risk_threshold`. The response includes policy decision, required approval type, approval chain, blocked actions, allowed actions, matched rules, warnings, recommended operator action, approval matrix, and replay summary. Default rules cover low confidence, high/critical SLA pressure, enterprise/VIP customer tier, external reply vs internal action, degraded/failing adapters, replay risk above threshold, and missing/conflicting KB context.

- `POST /policies/export`
  Writes Markdown and JSON under the ignored policy pack folder, normally `data/policy_packs/`. The pack includes simulated policies, primary matched rules, approval matrix, sample scenario outcomes, local verification commands, JD skills demonstrated, and five interviewer talking points.

- `POST /policies/change-simulation`
  Compares baseline and proposed policy knobs over the deterministic scenario corpus. Inputs include `confidence_cutoff`, `sla_high_risk_threshold`, `auto_approval_max_blast_radius`, and optional `scenario_limit`. Output includes approval-volume deltas, SLA routing impact, scenario-level before/after decisions, and blast-radius scoring.

- `POST /policies/change-pack`
  Writes Markdown and JSON under `data/policy_change_packs/` with approval threshold, confidence cutoff, SLA routing, blast-radius, local verification, and reviewer talking-point evidence.

- `POST /policies/rollout-plan`
  Converts the local policy-change simulation into a deterministic rollout gate. The response includes go/no-go status, failed review gates, role signoffs, canary phases, rollback triggers, run transparency, artifact handoffs, proof commands, and local/mock limitations. It never changes live policy configuration or dispatches external actions.

- `POST /policies/rollout-pack`
  Writes Markdown and JSON under `data/policy_rollout_packs/` with the rollout gate, canary rollout plan, role signoffs, rollback triggers, artifact handoffs, local verification commands, and reviewer acceptance criteria.

- `POST /incidents/timeline`
  Builds the Customer Impact Timeline for a supplied `run_id`, the latest local run, or a deterministic sample fallback when omitted. The response includes ordered timeline events, customer impact summary, internal/external action split, policy guardrail annotations, Replay Lab annotations, unresolved risks, owner next steps, impact status, and evidence artifact links. It reuses existing local exports such as incident brief, remediation checklist, weekly review, account brief, optimization report, and replay report.

- `POST /incidents/executive-narrative`
  Writes Markdown and JSON under the ignored narrative folder, normally `data/incident_narratives/`. The optional body can include `run_id`; otherwise it uses the latest/sample fallback. The export includes the timeline, executive summary, customer impact, decisions made, approval evidence, policy guardrail decision, replay risk, SLO posture, owner actions, local commands, JD skills demonstrated, and five interviewer talking points.

- `GET /incidents/postmortem-summary`
  Returns the latest or deterministic sample Postmortem RCA summary with incident summary, severity, timeline, root cause category, contributing factors, impacted customer/account, approval and communications status, trace links, corrective actions, customer follow-up state, recurrence risk, readiness summary, proof commands, and Scenario Dataset RCA coverage.

- `POST /incidents/rca-pack`
  Writes Markdown and JSON under the ignored RCA folder, normally `data/rca_packs/`. The optional body can include `run_id`; otherwise it uses the latest/sample fallback. The pack includes a postmortem narrative, timeline, trace/audit evidence, action owners, due dates, recurrence risk, customer follow-up state, deterministic RCA coverage across outage/API, tool failure/retry, privacy/data export, billing/customer risk, and low-confidence human-review scenarios, proof commands, and limitations.

- `GET /incidents/postmortem-review-board`
  Returns the Postmortem Review Board for a supplied, latest, or deterministic sample run. The response includes corrective-action lanes, owner signoffs, role playbooks, closure gates, review cadence, run transparency, artifact handoffs, and local proof commands.

- `POST /incidents/postmortem-review-pack`
  Writes Markdown and JSON under the ignored review folder, normally `data/postmortem_review_packs/`. The optional body can include `run_id`; otherwise it uses the latest/sample fallback. The pack includes closure owner summary, review-gate summary, artifact handoff packet, proof commands, and limitations.

- `POST /finance/impact-summary`
  Returns local deterministic finance impact estimates for a supplied `run_id`, the latest local run, or a deterministic sample fallback when omitted. The response includes ticket/customer context, support cost, SLA penalty exposure, engineering effort, customer ARR at risk, finance rollup, risk flags, recommended actions, dashboard metrics, assumptions, local commands, and limitations. It does not call CRM, billing, finance, Azure, OpenAI, Zendesk, Jira, Slack, or external systems.

- `POST /finance/impact-pack`
  Writes Markdown and JSON under the ignored finance impact folder, normally `data/finance_impact_packs/`. The pack includes the finance impact summary, executive decision table, finance controls, local verification commands, and explicit local-only limitations. The optional body can include `run_id`; otherwise it uses the latest/sample fallback.

- `GET /leadership/scorecard`
  Returns the Support Automation KPI Scorecard for leadership review. The response includes numeric scores for automation safety, approval health, SLA risk, escalation quality, retry/failure behavior, policy blocks, replay risk, customer impact, and operator readiness. It also includes trend-ish local values, risk flags, recommended actions, artifact links, KPI definitions, local commands, and readiness status.

- `POST /leadership/review-pack`
  Writes Markdown and JSON under the ignored leadership review folder, normally `data/leadership_reviews/`. The pack includes the scorecard, KPI definitions, local evidence links, top risks, recommended next actions, local verification commands, JD skills demonstrated, and five interviewer talking points. It remains fully local/mock and does not call external BI, warehouse, or support systems.

- `GET /knowledge/quality-audit`
  Returns the Knowledge Quality Auditor result for support leadership. The response includes `kb_coverage_score`, readiness status, freshness/coverage/conflict/citation metrics, weak or missing articles, impacted ticket types, owner recommendations, risk flags, local commands, and evidence sources from local KB snippets, workflow retrieval outputs, ticket categories, Replay Lab KB-context modifiers, policy guardrails, incident narratives, and the leadership scorecard.

- `POST /knowledge/refresh-plan`
  Writes Markdown and JSON under the ignored KB refresh folder, normally `data/kb_refresh_plans/`. The plan includes article refresh tasks, owners, acceptance criteria, impacted workflows, local verification commands, JD skills demonstrated, and five interviewer talking points. It remains fully local/mock and does not call an external knowledge-base system.

- `GET /runbooks/coverage-audit`
  Returns the Runbook Coverage audit across active tickets, scenario fixtures, local KB articles, and the playbook library. The response includes coverage score, readiness status, per-ticket KB/runbook mapping, missing dedicated runbook gaps, owner assignments, selected process mode, role playbooks, delegated remediation tasks, review gates, artifact handoffs, run transparency, endpoint list, local commands, and local-only limitations.

- `POST /runbooks/gap-pack`
  Writes Markdown and JSON under the ignored runbook gap folder, normally `data/runbook_gap_packs/`. The pack includes the ticket coverage map, missing runbook gaps, owner-ready remediation tasks, role playbooks, delegated coverage tasks, review gates, artifact handoffs, run transparency, acceptance criteria, endpoint evidence, local verification commands, JD skills demonstrated, and five interviewer talking points.

- `GET /providers/readiness`
  Returns the Provider Readiness audit for the configured LLM mode. The response includes local/mock default status, active provider class, optional OpenAI/Azure adapter classes, redacted credential presence, provider matrix, fallback policy, production activation backlog, endpoint evidence, local commands, and limitations. It does not call OpenAI, Azure OpenAI, Zendesk, Jira, Slack, GitHub, or external networks.

- `POST /providers/readiness-pack`
  Writes Markdown and JSON under the ignored provider readiness folder, normally `data/provider_readiness_packs/`. The pack includes provider checks, activation checklist, acceptance criteria, production backlog, local verification commands, JD skills demonstrated, interviewer talking points, and secret-redaction limitations.

- `GET /providers/failover-drill`
  Runs the Provider Failover drill without external calls. It exercises local/mock default behavior, OpenAI and Azure missing-credential fallback, simulated provider timeout fallback, and fallback-disabled fail-closed behavior. The response includes scenario results, control checks, token/cost visibility, activation decisions, repo-radar patterns, proof commands, and limitations.

- `POST /providers/failover-pack`
  Writes Markdown and JSON under the ignored provider failover folder, normally `data/provider_failover_packs/`. The pack includes the failover drill, deployment gate, acceptance criteria, local proof commands, and local-only limitations.

- `GET /governance/autonomy-audit`
  Returns the Autonomy Governance audit for existing local runs. The response includes bounded workflow node checks, trusted tool allowlist status, retry budget visibility, human-approval-before-dispatch checks, token/cost observability, run-level findings, owner actions, repo-radar patterns, local commands, and local/mock limitations.

- `POST /governance/autonomy-pack`
  Writes Markdown and JSON under the ignored autonomy governance folder, normally `data/autonomy_governance_packs/`. The pack includes the autonomy audit, decision table, acceptance criteria, reviewer artifact paths, proof commands, and limitations.

- `GET /workflows/durability-audit`
  Returns the Durable Workflow Recovery audit for persisted local runs. The response includes checkpoint coverage, latest resume tokens, HITL resume readiness, dispatch-boundary safety, operator recovery queue, repo-radar patterns, local commands, and local/mock limitations.

- `POST /workflows/durability-pack`
  Writes Markdown and JSON under the ignored workflow recovery folder, normally `data/workflow_recovery_packs/`. The pack includes the durability audit, recovery decision table, operator acceptance criteria, reviewer artifact paths, proof commands, and limitations.

- `POST /playbooks/recommend`
  Accepts either `ticket_id` or an inline `ticket` payload plus optional `top_n`. Returns ranked playbooks with match reasons, confidence, checklist steps, owner roles, escalation policy, and customer update template. If a stored ticket has already been analyzed, the recommender uses its classification and SLA risk context.

- `POST /runs/{run_id}/incident-brief`
  Exports a Markdown and JSON incident brief for a run. The response includes file paths plus structured content with customer impact, classification, SLA risk, KB citations, customer reply draft, engineering escalation draft, approval status, trace summary, outbox status, and recommended next steps. Local files are written under the ignored runtime briefs folder, normally `data/briefs/`.

- `POST /runs/{run_id}/remediation-checklist`
  Exports a Markdown and JSON remediation checklist for a run. The response includes file paths plus structured content with ticket context, classification, SLA risk, selected playbook, checklist steps, owner roles, approval status, and next customer update template. Local files are written under the ignored runtime checklists folder, normally `data/checklists/`. The optional body can include `playbook_id` to force a specific playbook.

- `POST /runs/{run_id}/approve`
  Approves pending drafts and dispatches fake Zendesk/Jira/Slack actions.

- `POST /runs/{run_id}/reject`
  Rejects pending drafts and marks the run rejected.

- `GET /approvals`
  Lists pending approvals.

- `GET /integrations/outbox`
  Lists persisted fake external dispatch records for Zendesk, Jira, and Slack. Each row includes `trace_id`, `run_id`, `ticket_id`, `action_type`, `destination`, `payload`, `status`, and `created_at`.

- `GET /integrations/outbox/{outbox_id}`
  Returns one outbox dispatch record.

- `POST /drills/tool-failure`
  Runs a deterministic local failure drill by ingesting a low-confidence ticket that forces KB retries to fail. The response includes the run, approval, full trace, and failed tool-call timeline.

- `POST /drills/sla-breach-simulation`
  Creates or reuses local SLA simulator tickets, analyzes them, and returns a prioritized queue. Each row includes `ticket_id`, `customer_tier`, `minutes_to_sla`, `risk_level`, `recommended_action`, `run_id`, and `approval_id`.

- `GET /metrics/agent-performance`
  Returns run counts, approval counts, outbox dispatch counts, failure-drill counts, failure counts, average latency/token/cost metrics, node metrics, and estimated cost.

- `GET /analytics/ops-snapshot`
  Returns a leadership snapshot across local tickets, runs, approvals, outbox, drills, reports, and incident briefs. The response includes counts by ticket category, ticket status, SLA risk, final action, approval status, outbox destination/action, and failure type; average latency/tokens/cost; top risky tickets; SLA queue highlights; failure drill summary; outbox dispatch summary; incident brief paths; and recommended operational actions.

- `POST /analytics/weekly-review`
  Writes Markdown and JSON under the ignored local reports folder, normally `data/reports/`. The report includes summary metrics, SLA queue highlights, failure drill summary when present, outbox dispatch summary, incident brief paths when present, top risky tickets, and next actions.

- `GET /ops/slo-budget`
  Returns deterministic local SLO status for agent workflow latency, token usage per run, estimated cost per run, workflow failure count, pending approvals, and outbox dispatch delay. Each metric includes `thresholds`, `current_value`, `status` as `pass`, `warn`, or `fail`, and a `recommendation`.

- `POST /ops/optimization-report`
  Writes Markdown and JSON under the ignored local optimization reports folder, normally `data/optimization_reports/`. The report includes SLO statuses, top slow nodes, high-token nodes, failure hotspots, approval bottlenecks, and recommended fixes.

- `GET /ops/ci-doctor`
  Returns the Local CI Doctor for publish-safety review. The response includes structured checks for the pytest command, ruff command, eval command, demo command, GitHub Actions workflow presence, Docker Compose presence, `.env.example`, README required sections, docs presence, generated artifact ignores, dependency files, local/mock provider notes, and a redacted suspicious secret-pattern scan summary. It is deterministic, local-only, and does not call GitHub, PyPI, secret-scanning vendors, or external services.

- `POST /ops/audit-pack`
  Writes Markdown and JSON under the ignored local audit folder, normally `data/audit_packs/`. The Audit Pack includes the CI Doctor result, dependency inventory, secret scan summary, local verification commands, publish-safety checklist, remediation notes, and recruiter/interviewer explanation.

- `GET /ops/daily-brief`
  Returns the Executive Daily Ops Brief command-center summary. The response includes SLA exposure, blocked approvals, engineer load, critical accounts, top risky tickets, control signals, recommended owner actions, local evidence links, endpoints, commands, and local/mock limitations.

- `POST /ops/daily-brief-pack`
  Writes Markdown and JSON under the ignored local daily ops folder, normally `data/daily_ops_briefs/`. The pack includes the daily brief, executive decision table, SLA exposure, blocked approvals, engineer load, critical accounts, control signals, evidence links, verification commands, and limitations.

- `GET /ops/crew-plan`
  Returns the Autonomous Support Operations crew plan for a selected/latest/sample run. The response includes support leader, account team, engineering owner, and operations commander role crews; delegated task board; selected process mode; review gates; artifact handoffs; run transparency; scenario coverage; repo-radar patterns; proof commands; and local/mock limitations.

- `POST /ops/crew-pack`
  Writes Markdown and JSON under the ignored local support ops folder, normally `data/support_ops_packs/`. The pack includes the crew plan, delegation board, review-gate summary, artifact handoff packet, local proof commands, and limitations. It never dispatches customer or engineering actions.

- `GET /ops/crew-sandbox`
  Runs a deterministic local worker sandbox over the selected/latest/sample support-ops plan. The response includes worker assignments, dry-run task executions, local tool transcripts, token/tool budgets, scale-out decisions, issue-to-handoff loop stages, verification gates, proof commands, and local/mock limitations.

- `POST /ops/crew-sandbox-pack`
  Writes Markdown and JSON under the ignored local support ops sandbox folder, normally `data/support_ops_sandbox/`. The pack includes the sandbox run, worker assignment board, transcript summary, verification summary, local proof commands, and limitations. It never calls external workers, providers, customer systems, or engineering systems.

- `GET /ops/crew-readiness-drill`
  Runs a deterministic scenario-wide readiness drill over the support-ops crew planner and worker sandbox. The response includes process-mode coverage, scenario results, required role coverage, review gates, sandbox transcript audit, repo-radar pattern coverage, proof commands, and local/mock limitations.

- `POST /ops/crew-readiness-pack`
  Writes Markdown and JSON under the ignored local support ops readiness folder, normally `data/support_ops_readiness/`. The pack includes the readiness drill, scenario result table, role coverage matrix, process-mode coverage, readiness gate summary, local proof commands, and limitations.

- `GET /tools/registry`
  Returns the Tool Governance Registry. The response includes local tool manifests, owners, risk tiers, data exposure, approval boundaries, failure modes, observed usage, unknown tool references, marketplace intake policy, owner actions, proof commands, and local/mock limitations.

- `POST /tools/governance-pack`
  Writes Markdown and JSON under the ignored local tool governance folder, normally `data/tool_governance_packs/`. The pack includes the registry, approval matrix, production acceptance criteria, proof commands, and limitations. It does not call external tool marketplaces, SaaS tools, Azure, OpenAI, Slack, Jira, Zendesk, GitHub, or external networks.

- `GET /ops/agent-bus-audit`
  Returns the Agent Communication Bus audit. The response reads local JSONL inbox/outbox files when present, reports registered agent roles, message files, message routes, a handoff ledger, review gates, operator queue, recent message previews, repo-radar patterns, proof commands, and local/mock limitations. It is read-only and does not send, delete, acknowledge, or route messages.

- `POST /ops/agent-bus-pack`
  Writes Markdown and JSON under the ignored local agent bus folder, normally `data/agent_bus_packs/`. The pack includes the bus audit, review-gate summary, handoff acceptance criteria, proof commands, and limitations. It does not automate the Codex desktop UI or call GitHub, Azure, OpenAI, Zendesk, Jira, Slack, browser, or network providers.

- `GET /observability/trace-eval-lab`
  Returns the Trace Eval Lab for local support escalation runs. The response includes trace diagnostics, retrieval grounding, token/cost visibility, baseline-vs-strict eval experiment comparison, control checks, repo-radar patterns, proof commands, and local/mock limitations.

- `POST /observability/eval-pack`
  Writes Markdown and JSON under the ignored local observability eval folder, normally `data/observability_eval_packs/`. The pack includes trace diagnostics, retrieval diagnostics, experiment comparison, deployment gate, acceptance criteria, proof commands, and limitations. It does not call hosted evaluators, model providers, APM, Zendesk, Jira, Slack, GitHub, or external networks.

- `GET /ops/smoke-matrix`
  Returns the Local Launch Checklist smoke matrix for GitHub reviewers. Each row includes endpoint, purpose, auth requirement, expected status, sample `curl.exe` and PowerShell `Invoke-RestMethod` commands, artifact expectation, and the overall launch readiness summary.

- `POST /ops/launch-checklist`
  Writes Markdown and JSON under the ignored local launch checklist folder, normally `data/launch_checklists/`. The checklist includes install/run commands, API smoke matrix, demo command, eval commands, generated artifact expectations and latest paths, troubleshooting notes, JD skills demonstrated, and five interviewer talking points.

- `GET /portfolio/evidence-index`
  Returns the Portfolio Evidence Index for recruiter/interviewer review. The response includes `evidence_score`, `evidence_count`, covered skill count, JD skill evidence, implemented features, endpoints, tests/evals, artifacts, demo commands, verification commands, local proof paths, runtime counts, and latest generated artifact paths. It remains fully local/mock and does not call Azure, OpenAI, Zendesk, Jira, Slack, or external systems.

- `POST /portfolio/interview-pack`
  Writes Markdown and JSON under the ignored local portfolio folder, normally `data/portfolio_packs/`. The Interview Pack includes a 3-minute demo script, 8-10 technical talking points, architecture walk-through, failure mode story, local verification commands, metrics/eval summary, artifact inventory, resume/GitHub README bullets, and the embedded Portfolio Evidence Index.

- `GET /release/quality-gate`
  Returns the Release Candidate quality gate for GitHub publish readiness. The response includes status, score, blockers, warnings, verification checklist, CI/docs/test/eval/demo/API coverage, artifact coverage, endpoint inventory, local-only runtime notes, and publish readiness. It is a deterministic local release gate and does not call GitHub, Azure, OpenAI, Zendesk, Jira, or Slack.

- `POST /release/publish-pack`
  Writes Markdown and JSON under the ignored local release folder, normally `data/release_packs/`. The Publish Pack includes the embedded Release Candidate gate, release summary, setup/demo commands, verification commands, expected outputs, endpoint inventory, artifact inventory, screenshot/manual verification placeholders, GitHub repo checklist, commit/push readiness notes, recruiter review notes, and known limitations.

- `GET /reviewer/quickstart`
  Returns the Reviewer Quickstart for GitHub reviewers. The response includes exact local setup commands, run commands, one-command demo, verification commands, endpoint walkthrough order, agent workflow walkthrough, artifact proof map, expected outputs, troubleshooting, role-specific reviewer notes, and local/mock runtime counts.

- `POST /reviewer/walkthrough-pack`
  Writes Markdown and JSON under the ignored local reviewer folder, normally `data/reviewer_packs/`. The Walkthrough Pack includes a recruiter-friendly story, engineer deep-dive path, command checklist, API/workflow proof tour, artifacts to inspect, limitations, GitHub README blurb, and the embedded Reviewer Quickstart.

- `GET /artifacts/inventory`
  Returns the Artifact Inventory for GitHub reviewers. The response lists generated artifact directories, resolved local directories, latest Markdown/JSON files, producer endpoints and PowerShell commands, `.gitignore` ignored status, reviewer purpose, file counts, local verification commands, and freshness notes. It remains deterministic and local-only.

- `POST /artifacts/readme-checklist`
  Writes Markdown and JSON under the ignored local artifact index folder, normally `data/artifact_indexes/`. The README Checklist Pack includes the Artifact Inventory, README badge suggestions, README checklist suggestions, local commands, reviewer proof checklist, and cleanup/regeneration notes.

- `GET /ui/dashboard-smoke`
  Returns Dashboard Smoke source checks for GitHub reviewers. The response includes expected Streamlit view labels, endpoint references, generated artifact tabs, local run commands, pass/fail check details, and limitations. It inspects local source files only and does not launch Streamlit, a browser, or external services.

- `POST /ui/verification-pack`
  Writes Markdown and JSON under the ignored local UI verification folder, normally `data/ui_verification/`. The UI Verification Pack includes the Dashboard Smoke results, Streamlit run command, reviewer checklist, screenshot placeholders, troubleshooting notes, and limitations.

- `GET /handoff/final-audit`
  Returns the README Consistency Final Audit for final portfolio review. The response includes structured checks for README endpoint mentions, docs/api coverage, architecture/evaluation/workflow coverage, demo output claims, required scripts, dashboard smoke script presence, generated artifact directory docs, local/mock Azure limitation clarity, endpoint inventory summary, artifact inventory summary, dashboard smoke summary, and local-only notes. It inspects local source files only and does not call GitHub, Azure, OpenAI, Zendesk, Jira, Slack, or external services.

- `POST /handoff/final-pack`
  Writes Markdown and JSON under the ignored local final handoff folder, normally `data/final_handoff/`. The Final Handoff Pack includes final audit results, exact clone/run commands, end-to-end verification order, endpoint inventory summary, artifact inventory summary, dashboard smoke summary, recruiter-facing final README blurb, artifact paths, and local/mock limitations.

- `GET /handoff/on-call-summary`
  Returns the latest or scenario-derived On-Call Handoff summary. The response includes owners, severity, current status, SLA deadline, trace links, customer communication readiness, approval and guardrail status, customer update drafts, engineering incident ticket summary, and a risk/gap checklist.

- `POST /handoff/customer-comms-pack`
  Writes Markdown and JSON under the ignored local customer communications folder, normally `data/customer_comms_packs/`. The pack includes customer update drafts, internal on-call handoff, engineering ticket draft, SLA/customer-impact timeline, approval checklist, guardrail status, trace IDs, deterministic coverage across Scenario Dataset paths, local proof commands, and limitations. It drafts only; it does not dispatch customer-visible communications.

- `GET /communications/quality-audit`
  Scores the latest or `run_id`-selected customer reply draft for empathy, specificity, policy compliance, and escalation clarity. The response includes role-crew reviewers, role playbook handoffs, a pre-dispatch review gate, run transparency, artifact handoffs, scenario coverage, required revisions, local proof commands, and limitations.

- `POST /communications/quality-pack`
  Writes Markdown and JSON under the ignored local communication quality folder, normally `data/communication_quality_packs/`. The pack packages the communication quality audit, reviewer actions, role-crew review, artifact handoffs, and run transparency for support lead review. It is local/mock only and never dispatches customer-visible messages.

- `GET /escalations/quality-audit`
  Scores the latest or `run_id`-selected engineering escalation draft for actionability, reproduction evidence, customer impact, routing governance, and noise control. The response includes human-in-the-loop review gates, role-crew findings, trace-backed evidence, scenario coverage, required revisions, local proof commands, and limitations.

- `POST /escalations/quality-pack`
  Writes Markdown and JSON under the ignored local escalation quality folder, normally `data/escalation_quality_packs/`. The pack packages the escalation audit, reviewer actions, role-crew handoffs, artifact handoffs, and run transparency for support engineering review. It is local/mock only and never creates Jira issues or Slack alerts.

- `GET /git/readiness`
  Returns GitHub Push Readiness and Branch Hygiene checks from read-only local git inspection. The response includes git repo detection, current branch, tracked/untracked/modified/ignored summary, generated artifact directories that should stay ignored, changed source/doc/test/dashboard buckets, suspicious large/generated files, required GitHub Actions workflow presence, README final handoff mention, `.env.example` presence, dirty-worktree guidance, and recommended commit groups. It does not call GitHub APIs or mutate the repository.

- `POST /git/push-plan`
  Writes Markdown and JSON under the ignored local git pack folder, normally `data/git_packs/`. The Branch Hygiene pack includes exact non-destructive review commands, suggested commit grouping, do-not-commit generated artifact notes, pre-push verification checklist, repo limitations, and a recruiter/GitHub README publish blurb. It does not stage, commit, push, reset, checkout, clean, delete files, or call GitHub APIs.

- `GET /api/contract-audit`
  Returns the API Contract Audit for fresh-clone reviewers. The response is derived from the local OpenAPI schema and FastAPI route dependency metadata, then cross-checks auth-protected endpoint count, important README/docs coverage, dashboard smoke alignment, generated artifact endpoint coverage, demo flow endpoint coverage, missing docs warnings, deprecated/duplicate route warnings, and local-only limitations.

- `POST /api/reviewer-collection`
  Writes Markdown and JSON under the ignored local API contract folder, normally `data/api_contracts/`. The Reviewer Collection includes endpoint inventory grouped by domain, sample `curl.exe` and PowerShell commands with `X-API-Key`, demo-token flow, expected status codes, auth notes, generated artifact endpoints, one-command verification order, and recruiter/engineer explanations.

- `GET /runtime/demo-readiness`
  Returns source-only Runtime Demo readiness for fresh-clone reviewers. The response includes install and start commands, `scripts\runtime_check.py`, optional `scripts\start_demo.ps1`, expected FastAPI and Streamlit ports, environment defaults, dependency and file checks, safe read-only socket/netstat port checks, health URLs, smoke URLs, known limitations, and troubleshooting. It does not require a running external service and does not kill processes.

- `POST /runtime/demo-pack`
  Writes Markdown and JSON under the ignored local runtime pack folder, normally `data/runtime_packs/`. The Runtime Demo Server Pack includes exact start commands, stop commands for manual use, health checks, demo flow order, screenshot checklist placeholders, troubleshooting, recruiter and engineer explanations, known limitations, artifact paths, and the embedded readiness report.

- `GET /scenarios/catalog`
  Returns the Scenario Dataset catalog from `sample_data/scenarios.json`. The response includes scenario metadata, expected classification, SLA, approval, escalation, low-confidence review, failure/tool-retry outcomes, required domain presence, and scenario coverage summary.

- `POST /scenarios/eval-pack`
  Runs deterministic local checks over the Scenario Dataset and writes Markdown plus JSON under the ignored local scenario pack folder, normally `data/scenario_packs/`. The pack includes classification accuracy, SLA routing, approval pause coverage, escalation coverage, low-confidence review coverage, failure/tool-retry coverage, generated artifact paths, and gaps/warnings.

- `GET /evidence/retention-audit`
  Returns local evidence retention readiness across recent runs, traces, approvals, outbox records, audit events, generated Markdown/JSON artifacts, and SHA-256 hash manifest coverage. It is source/local-state only and does not call external archive, CRM, billing, GitHub, Azure, OpenAI, Zendesk, Jira, or Slack systems.

- `POST /evidence/retention-pack`
  Writes Markdown and JSON under the ignored evidence pack folder, normally `data/evidence_packs/`. The pack includes custody review table, owner actions, findings, local verification commands, artifact hash sample, and local-only chain-of-custody limitations.

- `GET /capacity/forecast`
  Returns a local deterministic support capacity forecast across active tickets, scenario fixtures, and run history. The response includes queue-level ticket load, projected effort hours, required FTE, available FTE, capacity gaps, owner assignments, endpoint evidence, local commands, and limitations.

- `POST /capacity/staffing-plan`
  Writes Markdown and JSON under the ignored capacity planning folder, normally `data/capacity_plans/`. The plan includes demand summary, queue forecast, staffing gaps, owner assignments, remediation actions, acceptance criteria, local verification commands, JD skills, interviewer talking points, artifact paths, and local/mock limitations.

- `GET /compliance/data-residency-audit`
  Returns a local deterministic Data Residency and PII Exposure audit across support tickets, workflow drafts, approval records, outbox payloads, account region/segment metadata, and fake fixture rules. The response includes readiness status, residency score, account exposure queue, data-flow map, control checks, owner actions, endpoint list, local commands, and limitations. It does not call DLP, CRM, storage, Azure, OpenAI, Zendesk, Jira, Slack, GitHub, or external compliance systems.

- `POST /compliance/data-residency-pack`
  Writes Markdown and JSON under the ignored data residency folder, normally `data/data_residency_packs/`. The pack includes executive summary, review queue, control owner actions, acceptance criteria, local verification commands, and local/mock limitations.

- `GET /security/access-matrix`
  Returns a local least-privilege access matrix over FastAPI/OpenAPI route metadata. The response includes public/protected endpoint counts, proposed roles, domain ownership, endpoint production scopes, human-approval markers, findings, sample commands, and local/demo auth limitations.

- `POST /security/access-review-pack`
  Writes Markdown and JSON under the ignored access review folder, normally `data/access_review_packs/`. The pack includes the access matrix, least-privilege acceptance criteria, production authorization backlog, reviewer walkthrough, local verification commands, and local/mock limitations.

- `GET /risk/register`
  Returns the Enterprise Risk Register with risk score, open risk counts, owner action plan, control signal summary, endpoint evidence, and local/mock limitations across finance, evidence, capacity, data residency, access, KB, runbook, leadership, release, and SLO controls.

- `POST /risk/register-pack`
  Writes Markdown and JSON under the ignored risk register folder, normally `data/risk_registers/`. The pack includes an executive summary, owner actions, control signals, risk acceptance criteria, review cadence, local commands, artifact paths, and local/mock limitations.

- `POST /ops/runbook-qa`
  Evaluates operator handoff completeness for a supplied `run_id`, the latest local run, or a deterministic sample fallback when no run exists. The response includes score, pass/fail status, missing sections, warnings, linked artifact paths, and recommended fixes for ticket summary, classification, SLA risk, customer impact, KB context, drafts, approval state, trace ID, outbox, failure drill, remediation owners, SLO budget, optimization recommendations, and customer/account health.

- `POST /ops/operator-readiness-pack`
  Writes Markdown and JSON under the ignored local operator pack folder, normally `data/operator_packs/`. The pack includes the Runbook QA result, critical metrics, endpoint list, local demo command, JD skills demonstrated, and five interviewer talking points. The optional body can include `run_id`.

- `POST /demo/scenario-run`
  Runs the complete deterministic local interview scenario using existing services. The response includes the primary ticket/run, generated artifact paths, API endpoints exercised, summary metrics, key metrics, and links to trace, approval, outbox, ops, customer health, and SLO views. It covers ticket analysis, trace, approval, outbox dispatch, failure drill, SLA simulation, incident brief, weekly review, remediation checklist, customer health, account brief, SLO budget, and optimization report.

- `POST /demo/evidence-pack`
  Runs the local scenario and writes Markdown plus JSON under the ignored demo pack folder, normally `data/demo_packs/`. The pack includes summary, generated artifact paths, API endpoints exercised, key metrics, summary metrics, links, and interview talking points.

- `GET /customers/health`
  Returns account health summaries grouped from local ticket state and `sample_data/customers.json` metadata when available. Each row includes `customer`, `account`, ticket counts, open/pending/escalated counts, high-SLA-risk count, recent failure count, pending approval count, recommended playbook count, deterministic `health_score` from 0-100, `risk_level`, and `recommended_action`.

- `POST /customers/{customer_id_or_name}/account-brief`
  Writes Markdown and JSON under the ignored local account brief folder, normally `data/account_briefs/`. The brief includes customer health, active tickets, recent runs, recommended playbooks, pending approvals, outbox summary, and next actions. The path parameter can be the returned `customer_id` slug or the account/customer name.

- `GET /customers/renewal-risk`
  Returns a local deterministic renewal-risk queue. It joins customer health, `sample_data/account_health_inputs.json`, `sample_data/customers.json` ARR metadata, ticket sentiment, workflow SLA state, approval state, and fake blocker inputs. Each account includes renewal window, support sentiment, SLA drag, blocker register, owner actions, ARR at risk, and recommended action.

- `GET /customers/renewal-control-board`
  Returns a local deterministic control board over the renewal-risk queue. It applies human-in-the-loop and governance policy to high-risk accounts, including required human decisions, blocked automation actions, durable review checkpoints, deterministic resume tokens, evidence references, primary owners, and next operator actions.

- `POST /customers/renewal-control-pack`
  Writes Markdown and JSON under the ignored local renewal control folder, normally `data/renewal_control_packs/`. The pack includes the control board, review queue, blocked-action policy, operator acceptance criteria, local verification endpoints, and limitations.

- `GET /customers/renewal-handoff-gate`
  Returns a local deterministic renewal handoff readiness gate for high-risk accounts. It checks generated renewal review/control artifacts, owner assignments, blocker clearance plans, support evidence readiness, commercial review gates, role playbook coverage, blocked external commitments, and resumable run transparency.

- `POST /customers/renewal-handoff-pack`
  Writes Markdown and JSON under the ignored local renewal handoff folder, normally `data/renewal_handoff_packs/`. The pack includes the handoff gate, queue, role playbook, artifact handoff checks, blocked external commitment actions, local verification endpoints, and limitations.

- `POST /customers/{customer_id_or_name}/renewal-review`
  Writes Markdown and JSON under the ignored local renewal review folder, normally `data/renewal_reviews/`. The review includes executive summary, renewal risk, support evidence, pending approvals, outbox summary, blocker register, customer-success review, assumptions, and limitations. The path parameter can be the returned `customer_id` slug or the account/customer name.

- `GET /audit/events`
  Returns audit events.

- `GET /health`
  Returns service health.

## Example

```bash
curl -X POST http://localhost:8000/tickets/ingest \
  -H "content-type: application/json" \
  -H "x-api-key: demo-control-tower-key" \
  -d '{
    "subject": "Enterprise SSO outage blocking all agents",
    "body": "SAML SSO login is down for all support agents and SLA breach is near.",
    "priority": "urgent",
    "customer_tier": "enterprise",
    "tags": ["auth", "sso", "outage"]
  }'
```

After approving a run, inspect the local integration outbox:

```bash
curl http://localhost:8000/integrations/outbox \
  -H "x-api-key: demo-control-tower-key"
```

Run the reliability drill:

```bash
curl -X POST http://localhost:8000/drills/tool-failure \
  -H "x-api-key: demo-control-tower-key"
```

Run Replay Lab with changed conditions:

```bash
curl -X POST http://localhost:8000/replay-lab/run \
  -H "content-type: application/json" \
  -H "x-api-key: demo-control-tower-key" \
  -d '{
    "modifiers": {
      "sla_pressure": "critical",
      "kb_context": "missing",
      "adapter_health": "degraded",
      "confidence_override": 0.48,
      "approval_policy": "strict"
    }
  }'

curl -X POST http://localhost:8000/replay-lab/report \
  -H "content-type: application/json" \
  -H "x-api-key: demo-control-tower-key" \
  -d '{"run_id": "{run_id}", "modifiers": {"adapter_health": "failing"}}'
```

Simulate and export approval policy guardrails:

```bash
curl -X POST http://localhost:8000/policies/simulate \
  -H "content-type: application/json" \
  -H "x-api-key: demo-control-tower-key" \
  -d '{
    "run_id": "{run_id}",
    "modifiers": {
      "sla_pressure": "critical",
      "kb_context": "conflicting",
      "adapter_health": "degraded",
      "confidence_override": 0.44,
      "approval_policy": "strict"
    },
    "requested_actions": ["customer_reply", "jira_issue", "slack_alert"],
    "replay_risk_threshold": 70
  }'

curl -X POST http://localhost:8000/policies/export \
  -H "content-type: application/json" \
  -H "x-api-key: demo-control-tower-key" \
  -d '{"run_id": "{run_id}", "modifiers": {"sla_pressure": "critical"}}'
```

Build the Customer Impact Timeline and export the executive narrative:

```bash
curl -X POST http://localhost:8000/incidents/timeline \
  -H "content-type: application/json" \
  -H "x-api-key: demo-control-tower-key" \
  -d '{"run_id": "{run_id}"}'

curl -X POST http://localhost:8000/incidents/executive-narrative \
  -H "content-type: application/json" \
  -H "x-api-key: demo-control-tower-key" \
  -d '{"run_id": "{run_id}"}'
```

Review leadership automation KPIs and export the review pack:

```bash
curl http://localhost:8000/leadership/scorecard \
  -H "x-api-key: demo-control-tower-key"

curl -X POST http://localhost:8000/leadership/review-pack \
  -H "x-api-key: demo-control-tower-key"
```

Estimate finance impact and export the executive pack:

```bash
curl -X POST http://localhost:8000/finance/impact-summary \
  -H "content-type: application/json" \
  -H "x-api-key: demo-control-tower-key" \
  -d '{"run_id": "{run_id}"}'

curl -X POST http://localhost:8000/finance/impact-pack \
  -H "content-type: application/json" \
  -H "x-api-key: demo-control-tower-key" \
  -d '{"run_id": "{run_id}"}'
```

Audit KB readiness and export a KB refresh plan:

```bash
curl http://localhost:8000/knowledge/quality-audit \
  -H "x-api-key: demo-control-tower-key"

curl -X POST http://localhost:8000/knowledge/refresh-plan \
  -H "x-api-key: demo-control-tower-key"
```

Run the SLA simulator and export a brief:

```bash
curl -X POST http://localhost:8000/drills/sla-breach-simulation \
  -H "x-api-key: demo-control-tower-key"

curl -X POST http://localhost:8000/runs/{run_id}/incident-brief \
  -H "x-api-key: demo-control-tower-key"
```

Recommend a playbook and export a remediation checklist:

```bash
curl -X POST http://localhost:8000/playbooks/recommend \
  -H "content-type: application/json" \
  -H "x-api-key: demo-control-tower-key" \
  -d '{"ticket_id": "{ticket_id}", "top_n": 3}'

curl -X POST http://localhost:8000/runs/{run_id}/remediation-checklist \
  -H "content-type: application/json" \
  -H "x-api-key: demo-control-tower-key" \
  -d '{"playbook_id": "pb_sso_outage"}'
```

Export the weekly ops review:

```bash
curl http://localhost:8000/analytics/ops-snapshot \
  -H "x-api-key: demo-control-tower-key"

curl -X POST http://localhost:8000/analytics/weekly-review \
  -H "x-api-key: demo-control-tower-key"
```

Inspect SLO budget and export optimization recommendations:

```bash
curl http://localhost:8000/ops/slo-budget \
  -H "x-api-key: demo-control-tower-key"

curl -X POST http://localhost:8000/ops/optimization-report \
  -H "x-api-key: demo-control-tower-key"
```

Run the CI Doctor and export the Dependency/Secrets Audit Pack:

```bash
curl http://localhost:8000/ops/ci-doctor \
  -H "x-api-key: demo-control-tower-key"

curl -X POST http://localhost:8000/ops/audit-pack \
  -H "x-api-key: demo-control-tower-key"
```

Run Runbook QA and export an operator readiness pack:

```bash
curl -X POST http://localhost:8000/ops/runbook-qa \
  -H "content-type: application/json" \
  -H "x-api-key: demo-control-tower-key" \
  -d '{"run_id": "{run_id}"}'

curl -X POST http://localhost:8000/ops/operator-readiness-pack \
  -H "content-type: application/json" \
  -H "x-api-key: demo-control-tower-key" \
  -d '{"run_id": "{run_id}"}'
```

Review Runbook Coverage and export a gap pack:

```bash
curl http://localhost:8000/runbooks/coverage-audit \
  -H "x-api-key: demo-control-tower-key"

curl -X POST http://localhost:8000/runbooks/gap-pack \
  -H "x-api-key: demo-control-tower-key"
```

Review the Smoke Matrix and export the Launch Checklist:

```bash
curl http://localhost:8000/ops/smoke-matrix \
  -H "x-api-key: demo-control-tower-key"

curl -X POST http://localhost:8000/ops/launch-checklist \
  -H "x-api-key: demo-control-tower-key"
```

Review the Release Candidate gate and export the Publish Pack:

```bash
curl http://localhost:8000/release/quality-gate \
  -H "x-api-key: demo-control-tower-key"

curl -X POST http://localhost:8000/release/publish-pack \
  -H "x-api-key: demo-control-tower-key"
```

Review customer health and export an account brief:

```bash
curl http://localhost:8000/customers/health \
  -H "x-api-key: demo-control-tower-key"

curl -X POST http://localhost:8000/customers/northstar-health/account-brief \
  -H "x-api-key: demo-control-tower-key"
```

Run the full interview scenario or export the evidence pack:

```bash
curl -X POST http://localhost:8000/demo/scenario-run \
  -H "x-api-key: demo-control-tower-key"

curl -X POST http://localhost:8000/demo/evidence-pack \
  -H "x-api-key: demo-control-tower-key"
```

Run Dashboard Smoke and export the UI Verification Pack:

```bash
curl http://localhost:8000/ui/dashboard-smoke \
  -H "x-api-key: demo-control-tower-key"

curl -X POST http://localhost:8000/ui/verification-pack \
  -H "x-api-key: demo-control-tower-key"
```

Review the On-Call Handoff and export the Customer Communications pack:

```bash
curl http://localhost:8000/handoff/on-call-summary \
  -H "x-api-key: demo-control-tower-key"

curl -X POST http://localhost:8000/handoff/customer-comms-pack \
  -H "x-api-key: demo-control-tower-key"
```

Review the Postmortem RCA and export the Corrective Action Tracking Pack:

```bash
curl http://localhost:8000/incidents/postmortem-summary \
  -H "x-api-key: demo-control-tower-key"

curl -X POST http://localhost:8000/incidents/rca-pack \
  -H "x-api-key: demo-control-tower-key"
```

Run the OpenAPI-derived API Contract Audit and export the Reviewer Collection:

```bash
curl http://localhost:8000/api/contract-audit \
  -H "x-api-key: demo-control-tower-key"

curl -X POST http://localhost:8000/api/reviewer-collection \
  -H "x-api-key: demo-control-tower-key"
```

Review least-privilege access and export the Access Control Review Pack:

```bash
curl http://localhost:8000/security/access-matrix \
  -H "x-api-key: demo-control-tower-key"

curl -X POST http://localhost:8000/security/access-review-pack \
  -H "x-api-key: demo-control-tower-key"
```

Review the Enterprise Risk Register and export the owner action pack:

```bash
curl http://localhost:8000/risk/register \
  -H "x-api-key: demo-control-tower-key"

curl -X POST http://localhost:8000/risk/register-pack \
  -H "x-api-key: demo-control-tower-key"
```

Run Runtime Demo readiness and export the Runtime Demo Server Pack:

```bash
curl http://localhost:8000/runtime/demo-readiness

curl -X POST http://localhost:8000/runtime/demo-pack \
  -H "x-api-key: demo-control-tower-key"
```

Review the Scenario Dataset and export the Eval Coverage Pack:

```bash
curl http://localhost:8000/scenarios/catalog \
  -H "x-api-key: demo-control-tower-key"

curl -X POST http://localhost:8000/scenarios/eval-pack \
  -H "x-api-key: demo-control-tower-key"
```

Review evidence retention and export the chain-of-custody pack:

```bash
curl http://localhost:8000/evidence/retention-audit \
  -H "x-api-key: demo-control-tower-key"

curl -X POST http://localhost:8000/evidence/retention-pack \
  -H "x-api-key: demo-control-tower-key"
```
