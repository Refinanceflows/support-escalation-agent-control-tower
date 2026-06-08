# API

Base URL: `http://localhost:8000`

Auth: send `x-api-key: demo-control-tower-key` or `Authorization: Bearer demo-control-tower-key`.

## Endpoints

- `POST /auth/demo-token`
  Returns the local demo token.

- `POST /tickets/ingest`
  Creates a ticket.

- `GET /tickets`
  Lists tickets.

- `POST /tickets/{ticket_id}/analyze`
  Starts an agent run for a ticket. The run executes all workflow nodes and pauses at approval before dispatching customer replies or engineering tickets.

- `GET /runs/{run_id}`
  Returns run state, classification, SLA risk, KB results, drafts, QA result, approval ID, metrics, final action, and failure state.

- `GET /runs/{run_id}/trace`
  Returns node and tool trace events.

- `POST /runs/{run_id}/approve`
  Approves pending drafts and dispatches fake Zendesk/Jira/Slack actions.

- `POST /runs/{run_id}/reject`
  Rejects pending drafts and marks the run rejected.

- `GET /approvals`
  Lists pending approvals.

- `GET /metrics/agent-performance`
  Returns run counts, approval queue size, node metrics, tokens, latency, and estimated cost.

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

