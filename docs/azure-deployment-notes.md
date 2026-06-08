# Azure Deployment Notes

This project is local-first but can be deployed on Azure with modest changes.

## Suggested Azure Shape

- Azure Container Apps or Azure App Service for the FastAPI container
- Azure Container Apps or App Service for the Streamlit dashboard
- Azure Blob Storage, Azure Files, Cosmos DB, or PostgreSQL replacing the JSON state store
- Azure Key Vault for API keys and optional Azure OpenAI credentials
- Azure Monitor / Application Insights for logs and traces

## Azure OpenAI

The current `LlmProvider` boundary supports adding an Azure OpenAI implementation without changing workflow nodes. Required environment variables are stubbed in `.env.example`:

- `AZURE_OPENAI_ENDPOINT`
- `AZURE_OPENAI_API_KEY`

The local mock provider should remain the default so CI and fresh clones do not require paid keys.

## Production Hardening

Before production use:

- replace demo API key auth with enterprise identity or managed API gateway auth
- move state to a transactional store
- enforce RBAC on approvals
- add PII redaction for trace and audit records
- add secret scanning and dependency vulnerability scanning
- route audit events to immutable storage

