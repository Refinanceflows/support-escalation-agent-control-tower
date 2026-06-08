# Architecture

The control tower is organized as an async FastAPI application with explicit service boundaries.

## Components

- **FastAPI API layer** exposes ticket, run, approval, metrics, audit, and health endpoints.
- **AgentWorkflowService** owns the LangGraph workflow and run lifecycle.
- **TicketService** persists and lists support tickets.
- **KnowledgeRetrievalService** retrieves KB context with retry/failure handling.
- **ApprovalService** creates and resolves human approval gates.
- **TraceService** persists node transitions, tool calls, latency, and failures.
- **MetricsService** aggregates node counts, latency, token use, and estimated cost.
- **AuditService** records operational events.
- **Adapters** isolate fake Zendesk, Jira, Slack, KB, and LLM provider behavior.

## Persistence

The default persistence layer is a JSON state file configured by `CONTROL_TOWER_STATE_FILE`. It stores:

- tickets
- workflow runs
- trace events
- approvals
- audit events
- aggregate metrics

This keeps local setup dependency-free while still persisting state across process restarts.

## Provider Boundary

The project runs locally with `LocalMockLlmProvider`. Optional OpenAI or Azure OpenAI adapters can be added behind `LlmProvider` without changing workflow nodes.

## Security and Observability

All business endpoints require `x-api-key` or `Authorization: Bearer`. `/health` and `/auth/demo-token` are open for local demo use.

Every request gets an `x-trace-id`. Workflow runs get their own durable trace ID and trace events for node starts, node completions, tool calls, errors, latency, token use, cost, final action, and failure state.

