# Evaluation

The included pytest suite covers the core behavior expected of the control tower:

- ticket classification
- SLA risk scoring and escalation routing
- KB retrieval
- retry exhaustion and human review
- approval creation, approval, and rejection
- trace output for required workflow nodes
- metrics aggregation
- auth behavior
- health endpoint

## Manual Eval Ideas

Use `sample_data/tickets.json` as seed cases:

- Enterprise SSO outage should classify as authentication or incident, score high SLA risk, draft engineering escalation, and pause for approval.
- Billing invoice question should classify as billing, retrieve billing KB, draft customer reply, and pause for approval.
- API/webhook latency should retrieve API KB and draft an engineering escalation for enterprise impact.

## Tool Failure Eval

Create a ticket whose body contains `force-kb-failure`. The fake KB adapter will fail every search attempt. The run should record failed tool calls, set `failure_state`, and remain in human review/approval rather than silently drafting with unsupported context.

