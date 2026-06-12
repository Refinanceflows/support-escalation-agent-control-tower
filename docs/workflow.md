# Workflow

The workflow uses LangGraph when available. If LangGraph cannot import in a constrained local environment, the app keeps the same graph abstraction and executes a documented sequential fallback with the same node names and state contract.

## Nodes

1. `intake_classifier`
   Classifies category, priority, sentiment, confidence, and rationale.

2. `sla_risk_scorer`
   Scores SLA risk using priority, customer tier, outage terms, breach terms, and production impact.

3. `playbook_recommender`
   Ranks local operational playbooks using ticket text, tags, classification, SLA risk, priority, and customer tier. The run state stores top recommendations with confidence, match reasons, checklist steps, owner roles, escalation policy, and customer update template.

4. `knowledge_retriever`
   Searches the internal KB adapter with retry handling and records every tool call.

5. `customer_reply_drafter`
   Drafts a customer-safe reply using local mock LLM behavior and retrieved KB context.

6. `engineering_escalation_drafter`
   Drafts a Jira-ready escalation when SLA risk, incident, auth, API, or integration signals warrant it.

7. `qa_evaluator`
   Checks confidence, KB failures, risky categories, and high-SLA-risk conditions.

8. `human_approval`
   Creates a pending approval. The system always pauses before customer replies or engineering tickets.

9. `finalizer`
   During initial analysis, marks the run as awaiting approval without dispatching external actions. After approval, it sends fake Zendesk/Jira/Slack actions and writes each dispatch to the local integration outbox. After rejection, it records rejection.

## Failure Handling

Tool failures retry up to `CONTROL_TOWER_MAX_TOOL_ATTEMPTS`. Exhausted retries set `failure_state`, lower QA confidence, and force human review. The trace endpoint shows every failed attempt.

`POST /drills/tool-failure` demonstrates this behavior with a deterministic ticket containing `force-kb-failure`. The drill records each failed KB attempt, leaves the run awaiting human approval, and returns the failure timeline for reliability review.

## Integration Outbox

Approved runs persist fake external actions in `outbox` before or alongside the fake adapter call. Supported action types are:

- `customer_reply`
- `zendesk_update`
- `engineering_escalation`
- `jira_issue`
- `slack_alert`

Each event includes trace/run/ticket identifiers, destination, payload, dispatch status, and creation time. This gives interviewers an inspectable record of what would have gone to Zendesk, Jira, and Slack without requiring external accounts.

## SLA Breach Simulation

`POST /drills/sla-breach-simulation` creates or reuses deterministic local tickets with breached, critical, warning, and watch SLA windows. Each ticket is analyzed through the same workflow, paused at approval, and returned as a manager queue with `minutes_to_sla`, `risk_level`, `recommended_action`, `run_id`, and `approval_id`.

The simulator uses only local fixtures and fake providers. Azure OpenAI, Zendesk, Jira, and Slack remain optional integration targets and are not required for the drill.

## Incident Brief Export

`POST /runs/{run_id}/incident-brief` packages one run into Markdown and JSON under the ignored runtime briefs folder. The brief is meant for leadership review or engineering handoff and includes customer impact, classification, SLA risk, KB citations, customer reply draft, engineering escalation draft, approval status, trace summary, outbox status, and recommended next steps.

Pending runs show `pending_approval_no_dispatch` in the outbox section. Approved runs include the local fake dispatch records written by the finalizer.

## Playbook Recommendation and Remediation

The local playbook library lives in `sample_data/playbooks.json` and covers SSO outage, webhook regression, billing dispute, privacy export, and API key rotation scenarios. `POST /playbooks/recommend` can rank playbooks for a stored `ticket_id` or an inline ticket payload.

Analyzed runs include `state.playbook_recommendations`, so dashboard and demo handoffs can show the top playbook without another service call. `POST /runs/{run_id}/remediation-checklist` exports the selected playbook into Markdown and JSON under the ignored local checklists folder, normally `data/checklists/`. The export includes ticket context, classification, SLA risk, selected playbook, owner-role assignments for each checklist step, approval status, and the next customer update template.

## Ops Analytics and Weekly Review

`GET /analytics/ops-snapshot` reads only local state and report files to summarize operational trends across tickets, runs, approvals, outbox dispatches, drills, and incident briefs. It reports counts by ticket category, SLA risk, final action, approval status, outbox destination/action, and failure type, plus average latency, tokens, and cost.

The snapshot also includes top risky tickets and recommended operational actions so a support lead can decide what to clear first.

`POST /analytics/weekly-review` writes a Markdown and JSON report under the ignored local reports folder, normally `data/reports/`. The report includes summary metrics, SLA queue highlights, failure drill summary when present, outbox dispatch summary, incident brief paths when present, top risky tickets, and next actions.

These analytics endpoints do not call Azure, Zendesk, Jira, Slack, or any external service. They are local demo surfaces for support leadership review.

## SLO Budget and Optimization Recommendations

`GET /ops/slo-budget` turns the local metrics stream into production-style SLO budget status. It checks deterministic thresholds for agent workflow latency, token usage per run, estimated cost per run, workflow failure count, pending approvals, and outbox dispatch delay. Every metric returns its thresholds, current value, `pass`/`warn`/`fail` status, and an optimization recommendation.

`POST /ops/optimization-report` writes Markdown and JSON under `data/optimization_reports/`. The report packages the same SLO statuses with top slow nodes, high-token nodes, failure hotspots, approval bottlenecks, and recommended fixes. This gives the demo an operator-facing loop from observability to concrete tuning work without requiring external APM, billing, or queueing systems.

## Executive Daily Ops Brief Pack

`GET /ops/daily-brief` composes local control-tower evidence into a daily command-center summary for support leadership. It aggregates ops analytics, SLO budget, customer health, capacity planning, leadership KPI scorecard, and the enterprise risk register to summarize SLA exposure, blocked approvals, engineer load, critical accounts, top risky tickets, control signals, and owner actions.

`POST /ops/daily-brief-pack` writes Markdown and JSON under `data/daily_ops_briefs/`. The pack adds an executive decision table, local evidence links, endpoint list, verification commands, and explicit local/mock limitations. It remains deterministic and does not call CRM, billing, BI, workforce management, Zendesk, Jira, Slack, Azure, OpenAI, GitHub, or external systems.

## Autonomous Support Operations Pack

`GET /ops/crew-plan` turns the latest, selected, or deterministic sample run into an operations crew plan. It assigns support leader, account team, engineering escalation owner, and operations commander roles; selects a process mode such as standard triage, SLA war room, engineering escalation, or customer communications review; and returns delegated tasks with evidence references, review gates, run transparency, artifact handoffs, and scenario coverage.

`POST /ops/crew-pack` writes Markdown and JSON under `data/support_ops_packs/`. The pack packages the crew plan, delegation board, review-gate summary, artifact handoff packet, local proof commands, and limitations. It borrows role-crew, task-delegation, process-mode, artifact-handoff, review-gate, and run-transparency patterns while remaining local/mock only and never dispatching customer or engineering actions.

## Support Ops Worker Sandbox

`GET /ops/crew-sandbox` executes a deterministic local dry run over the delegated tasks from the crew plan. It assigns tasks to support lead, account team, engineering owner, and operations commander workers; enforces local tool-call and token budgets; records synthetic tool transcripts; reports worker scale-out decisions; and verifies isolation, budget, dispatch-boundary, execution, and transcript gates.

`POST /ops/crew-sandbox-pack` writes Markdown and JSON under `data/support_ops_sandbox/`. The pack is reviewer evidence for task-sandbox, worker scale-out, run-transparency, review-gate, and tool-transcript patterns. It remains local/mock only: no external LLM, Zendesk, Jira, Slack, GitHub, browser, shell worker, or network provider is invoked, and no customer or engineering action is dispatched.

## Support Ops Crew Readiness

`GET /ops/crew-readiness-drill` evaluates the support-ops crew planner and worker sandbox across deterministic scenario fixtures. It verifies process-mode coverage, role delegation coverage, review-gate health, task-sandbox transcript coverage, and zero external calls.

`POST /ops/crew-readiness-pack` writes Markdown and JSON under `data/support_ops_readiness/`. The pack packages scenario results, the role coverage matrix, process-mode coverage, readiness gates, sandbox transcript audit, proof commands, and limitations. It borrows role-crew, task-delegation, process-mode, review-gate, task-sandbox, and run-transparency patterns while staying local/mock only.

## Agent Communication Bus Audit

`GET /ops/agent-bus-audit` audits the local supervisor JSONL bus when files exist. It reports the registered conductor, CLI worker, verifier, repo-radar, and UI-bridge roles; message file health; sender/recipient routes; handoff ledger; review gates; operator queue; recent message previews; and local proof commands.

`POST /ops/agent-bus-pack` writes Markdown and JSON under `data/agent_bus_packs/`. The pack is read-only evidence for agent-role, task-delegation, review-gate, artifact-handoff, task-sandbox, and run-transparency patterns. It does not send or acknowledge bus messages, automate the Codex desktop UI, mutate git state, or call GitHub, Azure, OpenAI, Zendesk, Jira, Slack, browser, or network providers.

`GET /observability/trace-eval-lab` inspects local run traces, workflow checkpoints, retrieval grounding, QA confidence, token/cost provider events, and the bundled eval dataset. It compares a baseline local policy with a stricter fallback-guarded policy so support leaders can see routing accuracy, approval recall, unsafe auto-action count, and external-call count before enabling broader automation.

`POST /observability/eval-pack` writes Markdown and JSON under `data/observability_eval_packs/`. The pack packages trace diagnostics, retrieval diagnostics, experiment comparison, deployment gate, acceptance criteria, and local proof commands. It is deterministic and local-only; it does not call hosted evaluators, model providers, APM, Zendesk, Jira, Slack, GitHub, or external networks.

## Runbook QA and Operator Readiness Pack

`POST /ops/runbook-qa` evaluates whether a run is complete enough for operator handoff. It checks ticket summary, classification, SLA risk, customer impact, KB citations/context, drafted reply, engineering escalation, approval state, trace ID, outbox dispatches, failure drill result, remediation owners, SLO budget, optimization recommendations, and customer/account health.

The endpoint accepts an optional `run_id`. Without one, it uses the latest local run; if no run exists, it bootstraps a deterministic sample run so a fresh clone can still demonstrate the readiness surface.

`POST /ops/operator-readiness-pack` writes Markdown and JSON under `data/operator_packs/`. The pack includes the Runbook QA result, critical metrics, endpoint list, local demo command, JD skills demonstrated, and five interviewer talking points. It remains local/mock only and reuses existing artifacts instead of calling external systems.

## Runbook Coverage and Gap Pack

`GET /runbooks/coverage-audit` maps active tickets plus scenario fixtures to local KB articles and playbook recommendations. It reports coverage score, readiness status, per-ticket KB/runbook mapping, missing dedicated runbook gaps, owner assignments, endpoint evidence, verification commands, and local-only limitations.

`POST /runbooks/gap-pack` writes Markdown and JSON under `data/runbook_gap_packs/`. The pack turns missing or partial runbook coverage into owner-ready remediation tasks with affected ticket IDs, suggested playbook outlines, acceptance criteria, local commands, JD skills demonstrated, and interviewer talking points. It remains local/mock only and does not call external KB, Zendesk, Jira, Slack, Azure, OpenAI, or GitHub systems.

## Provider Readiness Guard Pack

`GET /providers/readiness` audits the configured LLM provider without calling external networks. It verifies that `LocalMockLlmProvider` remains the active default for CI and demos, reports optional `OpenAIChatProvider` and `AzureOpenAIChatProvider` activation posture, redacts credential presence, checks fallback guardrails, and lists production activation tasks.

`POST /providers/readiness-pack` writes Markdown and JSON under `data/provider_readiness_packs/`. The pack includes provider checks, an activation checklist, acceptance criteria, local commands, JD skills demonstrated, and interviewer talking points. It remains audit-only and does not call OpenAI, Azure OpenAI, Zendesk, Jira, Slack, GitHub, or any external service.

## Durable Workflow Recovery Pack

Each workflow node now writes a checkpoint into the persisted run state with the node name, status, latency, state keys, approval status, final action, and a resume token. This keeps the local LangGraph path durable enough for reviewer inspection and operator recovery without requiring cloud queues or paid providers.

`GET /workflows/durability-audit` audits recent runs for checkpoint coverage, pending-approval resume readiness, dispatch-boundary safety, and operator recovery actions. `POST /workflows/durability-pack` writes Markdown and JSON under `data/workflow_recovery_packs/` with the recovery decision table, acceptance criteria, and limitations. Recovery remains explicit: operators approve, reject, replay, or repair; the service does not auto-resume partial external actions.

## Local Launch Checklist and Smoke Matrix

`GET /ops/smoke-matrix` is the reviewer-facing smoke surface. It lists the key local endpoints, whether they require an API key, expected status codes, sample `curl.exe` and PowerShell commands, artifact expectations, and a launch readiness summary.

`POST /ops/launch-checklist` writes Markdown and JSON under `data/launch_checklists/`. The checklist packages install and run commands, the API smoke matrix, one-command demo path, eval commands, expected/generated artifacts, troubleshooting notes, JD skills demonstrated, and five interviewer talking points. It remains fully local/mock and is intended to make a fresh GitHub clone easy to demo.

## Portfolio Evidence Index and Interview Pack

`GET /portfolio/evidence-index` is the recruiter/interviewer evidence map. It returns a deterministic Portfolio Evidence score/count and maps JD skill areas to implemented features, endpoints, tests/evals, artifact directories, demo commands, verification commands, and local proof paths. Required coverage includes the stateful workflow, human approval, fake Zendesk/Jira/Slack adapters, retry/failure handling, observability/traces, metrics, launch checklist, KB quality, policy guardrails, replay, and leadership/incident artifacts.

`POST /portfolio/interview-pack` writes Markdown and JSON under `data/portfolio_packs/`. The Interview Pack includes a 3-minute demo script, 8-10 technical talking points, architecture walk-through, failure mode story, local verification commands, metrics/eval summary, artifact inventory, and resume/GitHub README bullets. It remains local/mock only and does not require Azure, OpenAI, Zendesk, Jira, Slack, or any external account.

## Release Candidate Quality Gate and Publish Pack

`GET /release/quality-gate` is the final Release Candidate release gate before publishing the repo. It returns status, score, blockers, warnings, verification checklist, CI/docs/test/eval/demo/API coverage, artifact coverage, local-only runtime notes, and publish readiness.

`POST /release/publish-pack` writes Markdown and JSON under `data/release_packs/`. The GitHub Publish Pack includes the embedded gate, release summary, setup commands, demo commands, verification commands, expected outputs, endpoint inventory, artifact inventory, screenshot/manual verification placeholders, GitHub repo checklist, commit/push readiness notes, recruiter review notes, and known limitations. It remains local/mock only and does not call GitHub or external integrations.

## Reviewer Quickstart and Walkthrough Pack

`GET /reviewer/quickstart` is the minutes-to-review entrypoint. It returns exact local setup commands, run commands, one-command demo, verification commands, endpoint walkthrough order, agent workflow walkthrough, artifact proof map, expected outputs, troubleshooting, role-specific reviewer notes, and local/mock runtime counts.

`POST /reviewer/walkthrough-pack` writes Markdown and JSON under `data/reviewer_packs/`. The Walkthrough Pack includes a recruiter-friendly story, engineer deep-dive path, command checklist, API/workflow proof tour, artifacts to inspect, limitations, GitHub README blurb, and the embedded Reviewer Quickstart. It remains local/mock only and is designed to make GitHub review possible without reading the whole codebase first.

## Artifact Inventory and README Checklist Pack

`GET /artifacts/inventory` is the reviewer-facing index of generated local proof. It returns every expected artifact directory, latest Markdown/JSON files when present, producer endpoint and PowerShell command, ignored status from `.gitignore`, reviewer purpose, file counts, and freshness notes. It includes existing packs such as demo, operator, launch, portfolio, release, reviewer, audit, replay, policy, leadership, KB, incident, account, and optimization artifacts plus `data/artifact_indexes/`.

`POST /artifacts/readme-checklist` writes Markdown and JSON under `data/artifact_indexes/`. The README Checklist Pack includes the Artifact Inventory, README Badge suggestions, README Checklist suggestions, local commands, reviewer proof checklist, and cleanup/regeneration notes. It is deterministic and local/mock only; reviewers can delete `data/artifact_indexes/` and regenerate it with the endpoint or the one-command demo.

## Dashboard Smoke and UI Verification Pack

`GET /ui/dashboard-smoke` is the no-browser dashboard verification surface. It inspects `dashboard/streamlit_app.py` and `app/api/routes.py` for expected Streamlit view labels, endpoint references, generated artifact tabs, local run commands, and limitations. The same checks are available from `scripts/dashboard_smoke.py`, which prints a PASS/FAIL summary plus the checked views and endpoints.

`POST /ui/verification-pack` writes Markdown and JSON under `data/ui_verification/`. The UI Verification Pack includes Dashboard Smoke results, the Streamlit run command, reviewer checklist, screenshot placeholders, troubleshooting notes, and limitations. It remains local/mock only and does not start Streamlit, open a browser, or call external services.

## Runtime Demo Server Pack

`GET /runtime/demo-readiness` is the fresh-clone runtime handoff for reviewers who need to start FastAPI and Streamlit without guessing commands. It returns install and start commands, `scripts/runtime_check.py`, optional `scripts/start_demo.ps1`, expected ports, environment defaults, dependency checks, required-file checks, safe read-only socket/netstat checks, health URLs, smoke URLs, troubleshooting, and known limitations.

`POST /runtime/demo-pack` writes Markdown and JSON under `data/runtime_packs/`. The Runtime Demo Server Pack includes the embedded readiness report, exact start and manual stop commands, health checks, demo flow order, screenshot checklist placeholders, troubleshooting, recruiter explanation, and engineer explanation. It remains local/mock only, never kills processes, and does not call Azure, OpenAI, Zendesk, Jira, Slack, GitHub, or external services.

`GET /compliance/data-residency-audit` is the local data residency and PII exposure check before production adapter expansion. It reviews tickets, workflow drafts, approvals, outbox payloads, customer region/segment fixtures, and `sample_data/data_residency_rules.json` for email, invoice, tenant, request ID, credential, privacy deletion, EU-region, regulated-segment, and outbox exposure signals.

`POST /compliance/data-residency-pack` writes Markdown and JSON under `data/data_residency_packs/`. The pack includes the review queue, executive summary, control checks, owner actions, acceptance criteria, local commands, and local/mock limitations. It does not call DLP, CRM, contract, storage, Azure, OpenAI, Zendesk, Jira, Slack, GitHub, or external compliance systems.

## Final Handoff and README Consistency

`GET /handoff/final-audit` is the README Consistency final audit. It compares local README endpoint mentions and `docs/api.md` coverage against implemented FastAPI routes, verifies architecture/evaluation/workflow coverage, confirms demo output claims, checks required scripts and the Dashboard Smoke script, verifies generated artifact directory docs for `data/final_handoff/`, and checks local/mock Azure limitation clarity.

`POST /handoff/final-pack` writes Markdown and JSON under `data/final_handoff/`. The Final Handoff Pack includes the final audit results, exact clone/run commands, end-to-end verification order, endpoint inventory summary, artifact inventory summary, dashboard smoke summary, recruiter-facing final README blurb, and limitations. It remains local/mock only and does not call GitHub, Azure, OpenAI, Zendesk, Jira, Slack, or external services.

## On-Call Handoff and Customer Communications

`GET /handoff/on-call-summary` returns the latest or scenario-derived On-Call Handoff. It includes owners, severity, status, SLA deadline, trace links, approval and guardrail status, customer communication readiness, customer update drafts, engineering incident ticket summary, and risk/gap checklist.

`POST /handoff/customer-comms-pack` writes Markdown and JSON under `data/customer_comms_packs/`. The Customer Communications Simulation Pack includes customer update drafts, internal handoff, engineering ticket draft, SLA/customer-impact timeline, approval checklist, trace IDs, local proof commands, and Scenario Dataset coverage for high SLA risk, low-confidence approval pause, tool failure/retry, billing/privacy, and outage/API incidents. It is local/mock only and drafts communications without dispatching to Zendesk, Jira, Slack, Azure, OpenAI, GitHub, or external services.

## Customer Communication Quality

`GET /communications/quality-audit` evaluates drafted customer replies before approval or dispatch. It uses role-crew reviewers for empathy, specificity, policy compliance, and escalation clarity; returns role playbook handoffs, a pre-dispatch review gate, run transparency, artifact handoffs, required revisions, and deterministic Scenario Dataset coverage.

`POST /communications/quality-pack` writes Markdown and JSON under `data/communication_quality_packs/`. The pack is a reviewer artifact for support leads and engineering managers to inspect customer-facing draft quality, guardrail blockers, role-review findings, and trace-backed handoff evidence. It remains local/mock only and does not send customer communications.

## Engineering Escalation Quality

`GET /escalations/quality-audit` evaluates drafted engineering escalations before Jira or Slack-facing dispatch. It uses role-crew reviewers for actionability, reproduction evidence, customer impact, routing governance, and noise control; returns human-in-the-loop gate status, trace-backed handoffs, required revisions, and deterministic Scenario Dataset coverage.

`POST /escalations/quality-pack` writes Markdown and JSON under `data/escalation_quality_packs/`. The pack is a reviewer artifact for support engineering leads to inspect whether an escalation is justified, grounded, and actionable before internal dispatch. It remains local/mock only and does not create Jira issues, Slack alerts, Azure/OpenAI calls, GitHub operations, or external service traffic.

## Postmortem RCA and Corrective Actions

`GET /incidents/postmortem-summary` returns the latest or deterministic sample Postmortem RCA summary. It connects tickets, runs, traces, approvals, outbox/customer comms state, on-call handoff readiness, and Scenario Dataset coverage into incident summary, severity, timeline, root cause category, contributing factors, impacted customer/account, approval/comms status, trace links, corrective actions, recurrence risk, customer follow-up state, readiness, and proof commands.

`POST /incidents/rca-pack` writes Markdown and JSON under `data/rca_packs/`. The pack includes postmortem narrative, timeline, trace/audit evidence, corrective action owners, due dates, recurrence risk, customer follow-up state, proof commands, limitations, and deterministic RCA coverage for outage/API incident, tool failure/retry, privacy/data export, billing/customer risk, and low-confidence ambiguity needing human review.

`GET /incidents/postmortem-review-board` turns the RCA corrective actions into a closure board. It assigns each action to a closure lane, delegated crew, role playbook, required artifact, owner signoff, and closure gate. It also exposes run transparency and review cadence so operators can see what remains before the postmortem can close.

`POST /incidents/postmortem-review-pack` writes Markdown and JSON under `data/postmortem_review_packs/`. The pack includes the action board, closure owner summary, review-gate summary, artifact handoff packet, proof commands, and local/mock limitations. It borrows role-crew, task-delegation, role-playbook, review-gate, artifact-handoff, and run-transparency patterns while keeping live dispatch and external tools disabled.

## Escalation Finance Impact

`POST /finance/impact-summary` estimates the business impact of a supplied, latest, or deterministic sample run. It uses local ticket/run state, trace volume, approval/outbox state, customer health, and `sample_data/customers.json` ARR metadata to calculate support cost, SLA penalty exposure, engineering effort, customer ARR at risk, direct cost, total exposure, risk flags, and owner actions.

`POST /finance/impact-pack` writes Markdown and JSON under `data/finance_impact_packs/`. The pack includes the finance summary, executive decision table, finance controls, local proof commands, assumptions, and limitations. It remains local/mock only and does not call CRM, billing, finance, Azure, OpenAI, Zendesk, Jira, Slack, or external systems.

## Enterprise Risk Register

`GET /risk/register` consolidates existing local control outputs into an owner-prioritized Enterprise Risk Register. It reads finance impact, evidence retention, capacity planning, data residency, access control, KB quality, runbook coverage, leadership scorecard, release gate, and SLO budget signals, then returns a risk score, readiness status, risk rows, owner action plan, control signal summary, endpoint evidence, commands, and limitations.

`POST /risk/register-pack` writes Markdown and JSON under `data/risk_registers/`. The pack includes executive summary, owner action plan, control signals, risk acceptance criteria, review cadence, local verification commands, and local/mock limitations. It remains local-only and does not call CRM, billing, GRC, HR, Zendesk, Jira, Slack, GitHub, Azure, OpenAI, or external systems.

## Evidence Retention and Chain of Custody

`GET /evidence/retention-audit` inspects local state and generated artifacts to verify that recent escalation runs have trace, approval, outbox, audit-event, and generated-pack evidence. It also computes a SHA-256 manifest for the latest Markdown/JSON artifacts under local `data/` proof directories.

`POST /evidence/retention-pack` writes Markdown and JSON under `data/evidence_packs/`. The pack includes a custody review table, recent run evidence map, artifact custody summary, hash manifest sample, findings, owner actions, local verification commands, and explicit local-only limitations. It does not call external archive, CRM, billing, GitHub, Azure, OpenAI, Zendesk, Jira, Slack, or SaaS systems.

## Capacity Planning

`GET /capacity/forecast` maps local active tickets, scenario fixtures, and run history into support queue load, projected effort hours, required FTE, available FTE, staffing gaps, owner assignments, endpoint evidence, local commands, and limitations. It keeps workforce planning deterministic and local/mock while showing how an AI support control tower would reason about safe operating capacity.

`POST /capacity/staffing-plan` writes Markdown and JSON under `data/capacity_plans/`. The plan includes the demand summary, queue forecast, staffing gaps, owner assignments, remediation actions, acceptance criteria, local verification commands, JD skills, and interviewer talking points. It does not call workforce management, HR, BI, CRM, Zendesk, Jira, Slack, Azure, OpenAI, or external services.

## Git Readiness and Branch Hygiene

`GET /git/readiness` is the local GitHub Push Readiness gate. It uses only read-only git inspection to report repo detection, current branch, tracked/untracked/modified/ignored summary, generated artifact directories that should stay ignored, source/doc/test/dashboard files changed, suspicious large/generated files, GitHub Actions workflow presence, README final handoff mention, `.env.example`, dirty-worktree guidance, and recommended commit groups.

`POST /git/push-plan` writes Markdown and JSON under `data/git_packs/`. The Branch Hygiene Pack includes exact non-destructive review commands, suggested commit grouping, do-not-commit generated artifact notes, pre-push verification checklist, repo limitations, and a recruiter/GitHub README publish blurb. It remains local/mock only and does not stage, commit, push, reset, checkout, clean, delete files, or call GitHub APIs.

## CI Doctor and Audit Pack

`GET /ops/ci-doctor` is the local maintainability doctor for the repository itself. It checks that the pytest, ruff, eval, and demo commands are represented; GitHub Actions and Docker Compose are present; `.env.example`, README sections, docs, generated artifact ignores, and dependency files are in place; local/mock provider notes are documented; and a suspicious secret-pattern scan can be reviewed.

The secret scan is deliberately local and redacted. It scans committed repo surfaces, skips generated or environment-heavy folders such as `data/`, `.git/`, `.venv/`, `.pytest_cache/`, and `.ruff_cache/`, and reports only file, line, pattern name, and a redacted snippet. It is useful for publish readiness, but it is not a substitute for production-grade CI secret scanning.

`POST /ops/audit-pack` writes Markdown and JSON under `data/audit_packs/`. The Audit Pack embeds the CI Doctor result, dependency inventory, secret scan summary, local verification commands, publish-safety checklist, remediation notes, and recruiter/interviewer explanation. It remains fully local/mock and does not call GitHub, PyPI, vulnerability databases, or external secret-scanning services.

## Change Risk Simulator and Escalation Replay Lab

Replay Lab is a deterministic counterfactual layer over stored run state. It does not call Zendesk, Jira, Slack, Azure, OpenAI, or the fake adapters. Instead, it clones a past run, applies scenario modifiers, recomputes operator-facing risk decisions, and returns an original-vs-replay comparison.

Supported modifiers are:

- `sla_pressure`: `normal`, `high`, or `critical`
- `kb_context`: `full`, `missing`, or `conflicting`
- `adapter_health`: `healthy`, `degraded`, or `failing`
- `confidence_override`: optional float from `0.0` to `1.0`
- `approval_policy`: `strict`, `standard`, or `auto_internal_only`

`POST /runs/{run_id}/replay-lab` targets one run. `POST /replay-lab/run` can accept a `run_id`, use the latest local run, or bootstrap a deterministic sample. The response compares classification, SLA risk, final action, approval requirement, failure state, tool attempts, latency/token/cost estimates, changed decisions, risk score, and recommended operator action.

`POST /replay-lab/report` writes Markdown and JSON under `data/replay_reports/` with modifiers, trace IDs, risk flags, local verification commands, JD skills demonstrated, and five interviewer talking points. This lets operators ask, "Would this automation change still be safe if the KB were missing, SLA pressure rose, or the adapter degraded?"

## Agent Policy Guardrail Center

The Policy Guardrail Center turns the run and Replay Lab context into an approval policy decision for automation actions. It is deterministic and local-only: no external policy engine, Azure service, Zendesk, Jira, or Slack account is required.

`POST /policies/simulate` accepts an optional `run_id`, Replay Lab `modifiers`, `requested_actions`, and `replay_risk_threshold`. Without a `run_id`, it uses the latest local run or bootstraps the same deterministic sample path used by Replay Lab.

Default approval policy rules evaluate:

- low confidence
- high or critical SLA pressure
- enterprise or VIP customer tier
- external customer reply/Zendesk update vs internal Jira, Slack, and engineering escalation actions
- degraded or failing adapter health
- Replay Lab risk above threshold
- missing or conflicting KB context

The response returns the policy decision, required approval type, approval chain, blocked actions, allowed actions, matched rules with evidence, warnings, and recommended operator action.

`POST /policies/export` writes Markdown and JSON under `data/policy_packs/`. The pack includes simulated policies, matched rules, approval matrix, sample scenario outcomes, local verification commands, JD skills demonstrated, and five interviewer talking points so support managers can explain why an automation policy would or would not be approved.

`POST /policies/change-simulation` reads the local scenario corpus, runs each ticket through the normal workflow, and compares baseline vs proposed policy knobs: `confidence_cutoff`, `sla_high_risk_threshold`, and `auto_approval_max_blast_radius`. The response reports approval-volume deltas, blocked-review deltas, SLA routing accuracy, changed scenario routes, blast-radius factors, and a rollout recommendation.

`POST /policies/change-pack` writes Markdown and JSON under `data/policy_change_packs/`. The pack is reviewer-facing evidence for policy-change management: approval thresholds, confidence cutoffs, SLA routing changes, blast-radius scoring, scenario-level before/after decisions, local verification commands, and interviewer talking points.

## Access Control Matrix and Review Pack

`GET /security/access-matrix` inspects the local FastAPI route inventory, public/protected route dependency metadata, endpoint domains, and HTTP methods. It returns a least-privilege matrix that maps each endpoint to proposed roles, production scopes, owner roles, sensitivity labels, human-approval markers, and findings.

`POST /security/access-review-pack` writes Markdown and JSON under `data/access_review_packs/`. The pack is local reviewer evidence for production authz planning: role definitions, domain ownership, route-level scopes, findings for the shared demo key, least-privilege acceptance criteria, production backlog items, verification commands, and explicit local-only limitations.

## Customer Impact Timeline and Executive Incident Narrative

`POST /incidents/timeline` is the executive story layer over the local control tower evidence. It accepts an optional `run_id`; without one, it uses the latest local run or bootstraps a deterministic sample incident. The service builds a time-ordered Customer Impact Timeline from the ticket, workflow trace, human approvals, outbox dispatches, incident brief, remediation checklist, weekly review, account brief, SLO posture, Replay Lab output, and policy guardrail decision.

The timeline response separates internal owner work from external customer-visible actions, annotates the story with policy and replay risk, lists unresolved risks, suggests owner next steps, and links the evidence artifacts that were generated locally.

`POST /incidents/executive-narrative` writes Markdown and JSON under `data/incident_narratives/`. The export includes executive summary, timeline, customer impact, decisions made, approval evidence, policy guardrail decision, replay risk, SLO posture, owner actions, local commands, JD skills demonstrated, and five interviewer talking points. It remains fully local/mock and does not call external systems.

## Leadership Scorecard and Review Pack

`GET /leadership/scorecard` is the executive automation KPI layer over the local corpus. It aggregates tickets, runs, traces, approvals, outbox dispatches, drills, ops analytics, SLO budget, customer health, Replay Lab, policy guardrails, incident artifacts, and operator readiness into deterministic category scores.

The scorecard categories are automation safety, approval health, SLA risk, escalation quality, retry/failure behavior, policy blocks, replay risk, customer impact, and operator readiness. Each category returns a 0-100 score, status, local sample values, risk flags, and recommended actions. The response also includes trend-ish local values, artifact links, KPI definitions, local commands, and an overall readiness status for support leadership.

`POST /leadership/review-pack` writes Markdown and JSON under `data/leadership_reviews/`. The pack includes the scorecard, KPI definitions, local evidence links, top risks, next actions, verification commands, JD skills demonstrated, and five interviewer talking points. It remains fully local/mock; no BI warehouse, CRM, Zendesk, Jira, Slack, Azure, or OpenAI dependency is required.

## Knowledge Quality Auditor and KB Refresh Plan

`GET /knowledge/quality-audit` is the support-lead view of whether the internal KB is ready for agentic escalation. It reads the sample KB snippets, stored workflow `kb_results`, ticket categories, Replay Lab KB-context modifiers, policy guardrail grounding rules, incident narrative artifacts, and Leadership Scorecard signals.

The audit returns a deterministic coverage score, freshness/coverage/citation/conflict metrics, weak or missing articles, impacted ticket types, owner recommendations, risk flags, and readiness status. It treats missing review dates, missing citations, policy conflicts, missing workflow grounding, and high-impact incident/API/auth/security gaps as readiness risks.

`POST /knowledge/refresh-plan` writes Markdown and JSON under `data/kb_refresh_plans/`. The export converts audit findings into owner-ready article refresh tasks with owners, acceptance criteria, impacted workflows, local commands, JD skills demonstrated, and five interviewer talking points. It remains fully local/mock and does not call an external KB, search index, or document system.

## Customer Health and Account Brief

`GET /customers/health` groups local tickets by explicit `customer` or `account` metadata, falling back to a readable email-domain account for older tickets. When an account exists in `sample_data/customers.json`, the summary includes segment, tier, and region metadata.

The health score is deterministic and local. It starts at 100 and subtracts weighted risk points for open/analyzing work, pending approval, escalated tickets, high SLA risk, recent workflow failures, and active playbook recommendations. Scores map to `healthy`, `watch`, `at_risk`, or `critical`, with a recommended action for customer success and support leadership.

`POST /customers/{customer_id_or_name}/account-brief` writes Markdown and JSON under `data/account_briefs/`. The brief packages the account health row with active tickets, recent runs, recommended playbooks, pending approvals, outbox summary, and next actions. It reuses the same local state as tickets, approvals, outbox, playbooks, and runs, so no CRM or external support tool is required.

`GET /customers/renewal-risk` layers a local renewal-risk model on top of account health. It combines fake renewal inputs from `sample_data/account_health_inputs.json`, local ticket and workflow sentiment, SLA drag from approvals/failures/escalations, blocker severity, ARR metadata from `sample_data/customers.json`, and owner actions. The output is deterministic and mock-only.

`GET /customers/renewal-control-board` adds the governance layer on top of renewal risk. High and critical accounts get human-in-the-loop decisions, blocked automation actions, primary owners, deterministic resume tokens, evidence references, and durable review checkpoints for risk triage, support evidence review, blocker owner assignment, and commercial approval.

`POST /customers/renewal-control-pack` writes Markdown and JSON under `data/renewal_control_packs/`. The pack is the operator-facing proof artifact for the governance board and includes review queue, acceptance criteria, blocked-action policy, local verification endpoints, and limitations. It does not send customer commitments or mutate any CRM.

`GET /customers/renewal-handoff-gate` evaluates whether high-risk renewal accounts are ready for human renewal review. It checks generated renewal review/control artifacts, owner assignments, blocker clearance plans, support evidence, commercial review gates, role playbook coverage, blocked external commitments, and resumable run transparency.

`POST /customers/renewal-handoff-pack` writes Markdown and JSON under `data/renewal_handoff_packs/`. The pack is a local artifact handoff for support leads, CSMs, blocker owners, and commercial owners. It implements review gates, artifact handoffs, role playbooks, and run transparency without approving commitments or mutating CRM, billing, Zendesk, Jira, Slack, Azure, OpenAI, or external services.

`POST /customers/{customer_id_or_name}/renewal-review` writes Markdown and JSON under `data/renewal_reviews/`. The review packages executive summary, support evidence, renewal blockers, SLA drag components, customer-success review fields, owner actions, assumptions, and limitations for an account renewal meeting without calling CRM, billing, Zendesk, Jira, Slack, Azure, OpenAI, or external services.

## Routing

High-SLA-risk tickets draft an engineering escalation. Low-confidence or risky actions also require approval. Because all outbound customer and engineering actions require approval, the approval gate is universal by design.
