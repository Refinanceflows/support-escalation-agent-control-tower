Support teams lose time and increase customer risk when urgent tickets, SLA threats, internal knowledge, and engineering escalations are handled manually.

This control tower uses a LangGraph agent workflow to triage tickets, retrieve cited KB context, draft customer/engineering responses, and pause every risky action for human approval.

# Support Escalation Agent Control Tower

`support-escalation-agent-control-tower` / `agent-escalation-tower` is a local-first portfolio implementation of an AI-assisted support escalation control tower. It helps support teams ingest tickets, classify intent, detect SLA risk, retrieve internal KB context, draft customer and engineering responses, pause for human approval, and preserve trace/audit/metrics evidence for every run.

The default mode uses deterministic local/mock providers, so a fresh clone runs without paid LLM keys. OpenAI or Azure OpenAI can be wired later behind the included provider interface without changing workflow code.

## What Is Included

- Python 3.11+, FastAPI, Pydantic, pydantic-settings, async services
- LangGraph workflow orchestration with a documented sequential fallback if LangGraph cannot import
- Required workflow nodes:
  `intake_classifier`, `sla_risk_scorer`, `knowledge_retriever`, `customer_reply_drafter`, `engineering_escalation_drafter`, `qa_evaluator`, `human_approval`, `finalizer`
- File-based durable state for tickets, runs, traces, approvals, audit events, and metrics
- Fake Zendesk, Jira, Slack, and internal KB adapters
- Local mock LLM provider behind an interface
- API key auth, structured logs, request trace IDs, audit events, token/latency/cost metrics
- Streamlit dashboard for queue, approvals, trace timeline, and metrics
- Sample tickets and KB fixtures
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

1. Get a token from `POST /auth/demo-token`.
2. Ingest sample tickets with `POST /tickets/ingest-samples`.
3. Analyze a ticket with `POST /tickets/{ticket_id}/analyze`.
4. Inspect `GET /runs/{run_id}` and `GET /runs/{run_id}/trace`.
5. Review `GET /approvals`.
6. Approve with `POST /runs/{run_id}/approve` or reject with `POST /runs/{run_id}/reject`.
7. Check `GET /metrics/agent-performance` and `GET /audit/events`.

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
- `CONTROL_TOWER_STATE_FILE`: JSON persistence path
- `CONTROL_TOWER_MAX_TOOL_ATTEMPTS`: KB/tool retry limit
- `CONTROL_TOWER_LOW_CONFIDENCE_THRESHOLD`: confidence threshold for review
- `CONTROL_TOWER_SLA_HIGH_RISK_THRESHOLD`: escalation threshold

## Repository Layout

```text
app/
  api/             FastAPI routes
  adapters/        Fake and provider adapter interfaces
  core/            config, logging, auth, storage
  models/          Pydantic domain models
  services/        ticket, workflow, retrieval, approval, trace, metrics, audit
dashboard/         Streamlit control tower
docs/              architecture, API, workflow, evals, deployment notes
sample_data/       tickets and KB fixtures
tests/             pytest coverage
```
