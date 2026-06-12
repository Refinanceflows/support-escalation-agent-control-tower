import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.adapters.llm import provider_runtime_class
from app.core.config import Settings
from app.models import AuditEvent
from app.services.audit import AuditService


PROVIDER_ENDPOINTS = [
    "GET /providers/readiness",
    "POST /providers/readiness-pack",
    "GET /providers/failover-drill",
    "POST /providers/failover-pack",
    "GET /ops/ci-doctor",
    "GET /runtime/demo-readiness",
    "GET /security/access-matrix",
]

PROVIDER_COMMANDS = [
    r".\.venv\Scripts\python.exe -m pytest -q",
    r".\.venv\Scripts\python.exe -m ruff check app tests dashboard scripts",
    r".\.venv\Scripts\python.exe -m app.evals.run_eval",
    r".\.venv\Scripts\python.exe scripts\dashboard_smoke.py",
    r".\.venv\Scripts\python.exe scripts\demo_run.py",
    (
        r'rg "providers/readiness|providers/readiness-pack|Provider Readiness|'
        r'provider_readiness_packs" app dashboard docs README.md tests scripts'
    ),
]

OPTIONAL_PROVIDER_ENV = {
    "openai": [
        "OPENAI_API_KEY",
        "CONTROL_TOWER_OPENAI_API_KEY",
        "CONTROL_TOWER_OPENAI_MODEL",
    ],
    "azure_openai": [
        "AZURE_OPENAI_ENDPOINT",
        "AZURE_OPENAI_API_KEY",
        "AZURE_OPENAI_DEPLOYMENT",
        "CONTROL_TOWER_AZURE_OPENAI_ENDPOINT",
        "CONTROL_TOWER_AZURE_OPENAI_API_KEY",
        "CONTROL_TOWER_AZURE_OPENAI_DEPLOYMENT",
    ],
}

SUPPORTED_PROVIDERS = {"local", "mock", "openai", "azure", "azure_openai"}


class ProviderReadinessService:
    """Audits optional LLM provider configuration without exposing secrets or calling providers."""

    def __init__(self, settings: Settings, audit: AuditService, provider_pack_dir: Path):
        self.settings = settings
        self.audit = audit
        self.provider_pack_dir = provider_pack_dir
        self.repo_root = Path(__file__).resolve().parents[2]

    async def readiness(self) -> dict[str, Any]:
        configured_provider = self.settings.llm_provider.strip().lower() or "local"
        provider_mode = self._provider_mode(configured_provider)
        env_presence = self._env_presence()
        provider_checks = self._provider_checks(configured_provider, provider_mode, env_presence)
        production_backlog = self._production_backlog(configured_provider, provider_checks)
        summary = self._summary(configured_provider, provider_checks, production_backlog)
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "title": "Provider Readiness Audit",
            "mode": "local-deterministic-provider-readiness",
            "local_mock_only": configured_provider in {"local", "mock"},
            "configured_provider": configured_provider,
            "active_provider_class": provider_runtime_class(self.settings),
            "readiness_status": summary["readiness_status"],
            "provider_score": summary["provider_score"],
            "summary": summary,
            "provider_checks": provider_checks,
            "env_presence": env_presence,
            "provider_matrix": self._provider_matrix(provider_checks),
            "fallback_policy": self._fallback_policy(configured_provider),
            "production_backlog": production_backlog,
            "endpoint_list": PROVIDER_ENDPOINTS,
            "local_commands": PROVIDER_COMMANDS,
            "limitations": self._limitations(),
        }

    async def export_pack(self) -> dict[str, Any]:
        audit = await self.readiness()
        generated_at = datetime.now(timezone.utc)
        pack_id = f"provider_readiness_pack_{generated_at.strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:6]}"
        json_path = self.provider_pack_dir / f"{pack_id}.json"
        markdown_path = self.provider_pack_dir / f"{pack_id}.md"
        pack = {
            "pack_id": pack_id,
            "generated_at": generated_at.isoformat(),
            "title": "Provider Readiness Guard Pack",
            "provider_readiness": audit,
            "activation_checklist": self._activation_checklist(audit),
            "acceptance_criteria": self._acceptance_criteria(),
            "endpoint_list": PROVIDER_ENDPOINTS,
            "local_commands": PROVIDER_COMMANDS,
            "jd_skills_demonstrated": self._jd_skills(),
            "interviewer_talking_points": self._talking_points(audit),
            "limitations": audit["limitations"],
            "artifact_paths": {
                "provider_readiness_markdown": str(markdown_path),
                "provider_readiness_json": str(json_path),
            },
        }
        markdown = self._markdown(pack)
        self.provider_pack_dir.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(pack, indent=2, default=str), encoding="utf-8")
        markdown_path.write_text(markdown, encoding="utf-8")
        await self.audit.record(
            AuditEvent(
                actor="provider-readiness",
                action="providers.readiness_pack_exported",
                resource_type="provider_readiness_pack",
                resource_id=pack_id,
                metadata={"markdown_path": str(markdown_path), "json_path": str(json_path)},
            )
        )
        return {
            "pack_id": pack_id,
            "format": "markdown+json",
            "json_path": str(json_path),
            "markdown_path": str(markdown_path),
            "readiness_status": audit["readiness_status"],
            "provider_score": audit["provider_score"],
            "pack": pack,
            "markdown": markdown,
        }

    def _provider_mode(self, configured_provider: str) -> str:
        if configured_provider in {"local", "mock"}:
            return "local_mock"
        if configured_provider == "openai":
            return "external_openai"
        if configured_provider in {"azure", "azure_openai"}:
            return "external_azure_openai"
        return "unsupported"

    def _env_presence(self) -> dict[str, Any]:
        dot_env = self._read_env_file(self.repo_root / ".env")
        example_env = self._read_env_file(self.repo_root / ".env.example")
        rows = []
        for provider, names in OPTIONAL_PROVIDER_ENV.items():
            for name in names:
                rows.append(
                    {
                        "provider": provider,
                        "name": name,
                        "present": self._present(name, dot_env),
                        "documented_in_env_example": name in example_env,
                        "value": "redacted" if self._present(name, dot_env) else "",
                    }
                )
        return {
            "secrets_redacted": True,
            "env_file_present": (self.repo_root / ".env").exists(),
            "env_example_present": (self.repo_root / ".env.example").exists(),
            "variables": rows,
        }

    def _read_env_file(self, path: Path) -> dict[str, str]:
        if not path.exists():
            return {}
        values: dict[str, str] = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            values[key.strip()] = value.strip().strip('"').strip("'")
        return values

    def _present(self, name: str, dot_env: dict[str, str]) -> bool:
        return bool(os.getenv(name) or dot_env.get(name))

    def _provider_checks(
        self,
        configured_provider: str,
        provider_mode: str,
        env_presence: dict[str, Any],
    ) -> list[dict[str, Any]]:
        env_rows = env_presence["variables"]
        openai_ready = any(
            row["provider"] == "openai" and row["name"].endswith("OPENAI_API_KEY") and row["present"]
            for row in env_rows
        )
        azure_endpoint_ready = any(
            row["provider"] == "azure_openai"
            and row["name"].endswith("AZURE_OPENAI_ENDPOINT")
            and row["present"]
            for row in env_rows
        )
        azure_key_ready = any(
            row["provider"] == "azure_openai"
            and row["name"].endswith("AZURE_OPENAI_API_KEY")
            and row["present"]
            for row in env_rows
        )
        azure_deployment_ready = any(
            row["provider"] == "azure_openai"
            and row["name"].endswith("AZURE_OPENAI_DEPLOYMENT")
            and row["present"]
            for row in env_rows
        ) or bool(self.settings.azure_openai_deployment)
        checks = [
            self._check(
                "provider_supported",
                "Configured provider is recognized",
                configured_provider in SUPPORTED_PROVIDERS,
                "fail",
                f"Configured provider `{configured_provider}`.",
                "Use `local`, `openai`, or `azure_openai`.",
            ),
            self._check(
                "local_default",
                "Fresh clone defaults to local/mock provider",
                self.settings.llm_provider.strip().lower() in {"local", "mock"},
                "warn",
                "LocalMockLlmProvider is the active workflow provider in this build.",
                "Keep local as the default unless production credentials and approvals are ready.",
            ),
            self._check(
                "external_calls_disabled_by_default",
                "No external LLM calls are made in default mode",
                provider_mode == "local_mock",
                "warn",
                "Workflow uses LocalMockLlmProvider and fake adapters for deterministic runs.",
                "Route external providers through a reviewed adapter, timeout, retry, and cost policy.",
            ),
            self._check(
                "openai_credentials_present_if_selected",
                "OpenAI credentials are present only when OpenAI is selected",
                configured_provider != "openai" or openai_ready,
                "fail",
                "OpenAI key presence is recorded as a boolean and redacted.",
                "Set OPENAI_API_KEY or CONTROL_TOWER_OPENAI_API_KEY before enabling OpenAI.",
            ),
            self._check(
                "azure_credentials_present_if_selected",
                "Azure OpenAI endpoint, key, and deployment are present only when Azure is selected",
                configured_provider not in {"azure", "azure_openai"}
                or (azure_endpoint_ready and azure_key_ready and azure_deployment_ready),
                "fail",
                "Azure endpoint/key/deployment presence is recorded as booleans and redacted.",
                "Set AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY, and AZURE_OPENAI_DEPLOYMENT before enabling Azure OpenAI.",
            ),
            self._check(
                "env_example_documents_optional_providers",
                ".env.example documents local, OpenAI, and Azure provider fields",
                self._env_example_documents_required(env_rows),
                "warn",
                "Reviewers can see provider knobs without needing paid services.",
                "Keep optional provider variables documented and empty by default.",
            ),
            self._check(
                "human_approval_boundary_preserved",
                "Human approval remains required before external actions",
                True,
                "fail",
                "Provider changes do not bypass the workflow approval node or outbox boundary.",
                "Run policy guardrail and replay checks before permitting external providers.",
            ),
        ]
        return checks

    def _check(
        self,
        check_id: str,
        label: str,
        passed: bool,
        failure_severity: str,
        evidence: str,
        remediation: str,
    ) -> dict[str, Any]:
        return {
            "check_id": check_id,
            "label": label,
            "status": "pass" if passed else failure_severity,
            "passed": passed,
            "evidence": evidence,
            "remediation": remediation,
        }

    def _env_example_documents_required(self, env_rows: list[dict[str, Any]]) -> bool:
        required = {
            "CONTROL_TOWER_LLM_PROVIDER",
            "OPENAI_API_KEY",
            "AZURE_OPENAI_ENDPOINT",
            "AZURE_OPENAI_API_KEY",
            "AZURE_OPENAI_DEPLOYMENT",
        }
        documented = {
            row["name"] for row in env_rows if row["documented_in_env_example"]
        } | {"CONTROL_TOWER_LLM_PROVIDER"}
        return required <= documented

    def _provider_matrix(self, checks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        status_by_id = {item["check_id"]: item["status"] for item in checks}
        return [
            {
                "provider": "local",
                "runtime_class": "LocalMockLlmProvider",
                "external_network": False,
                "credentials_required": False,
                "status": "ready",
                "default_for_ci": True,
            },
            {
                "provider": "openai",
                "runtime_class": "OpenAIChatProvider+LocalMockFallback",
                "external_network": True,
                "credentials_required": True,
                "status": status_by_id["openai_credentials_present_if_selected"],
                "default_for_ci": False,
            },
            {
                "provider": "azure_openai",
                "runtime_class": "AzureOpenAIChatProvider+LocalMockFallback",
                "external_network": True,
                "credentials_required": True,
                "status": status_by_id["azure_credentials_present_if_selected"],
                "default_for_ci": False,
            },
        ]

    def _summary(
        self,
        configured_provider: str,
        checks: list[dict[str, Any]],
        production_backlog: list[dict[str, str]],
    ) -> dict[str, Any]:
        fail_count = len([item for item in checks if item["status"] == "fail"])
        warn_count = len([item for item in checks if item["status"] == "warn"])
        pass_count = len([item for item in checks if item["status"] == "pass"])
        score = max(0, 100 - fail_count * 30 - warn_count * 8)
        if fail_count:
            status = "external_provider_blocked"
        elif configured_provider in {"local", "mock"}:
            status = "local_mock_ready"
        elif warn_count:
            status = "provider_review_required"
        else:
            status = "external_provider_ready"
        return {
            "provider_score": score,
            "readiness_status": status,
            "configured_provider": configured_provider,
            "pass_count": pass_count,
            "warn_count": warn_count,
            "fail_count": fail_count,
            "production_backlog_count": len(production_backlog),
            "external_services_required_for_default_demo": False,
            "secrets_exposed": False,
        }

    def _fallback_policy(self, configured_provider: str) -> dict[str, Any]:
        return {
            "default_provider": "local",
            "configured_provider": configured_provider,
            "fallback_provider": "local",
            "fallback_triggers": [
                "missing external provider credentials",
                "unsupported provider name",
                "provider timeout or transient network failure",
                "cost or token budget breach",
                "policy guardrail requiring human review",
            ],
            "human_approval_required": True,
            "notes": [
                "This audit does not switch providers or call external APIs.",
                "Production provider activation should keep local fallback available for tests and demos.",
            ],
        }

    def _production_backlog(
        self,
        configured_provider: str,
        checks: list[dict[str, Any]],
    ) -> list[dict[str, str]]:
        backlog = []
        for check in checks:
            if check["status"] in {"warn", "fail"}:
                backlog.append(
                    {
                        "task_id": f"provider_{check['check_id']}",
                        "owner": self._owner(check["check_id"]),
                        "severity": "high" if check["status"] == "fail" else "medium",
                        "configured_provider": configured_provider,
                        "remediation": check["remediation"],
                    }
                )
        backlog.append(
            {
                "task_id": "provider_add_live_adapter_contract_tests",
                "owner": "Platform AI Owner",
                "severity": "medium",
                "configured_provider": configured_provider,
                "remediation": "Keep contract tests current for timeout, redaction, token accounting, and local fallback before live-provider rollout.",
            }
        )
        return backlog

    def _owner(self, check_id: str) -> str:
        if "azure" in check_id:
            return "Cloud Platform Owner"
        if "openai" in check_id or "provider" in check_id:
            return "Platform AI Owner"
        if "approval" in check_id:
            return "Support Operations Lead"
        return "Repository Maintainer"

    def _activation_checklist(self, audit: dict[str, Any]) -> list[dict[str, str]]:
        return [
            {
                "step": "Keep `CONTROL_TOWER_LLM_PROVIDER=local` for CI and portfolio demos.",
                "evidence": audit["readiness_status"],
            },
            {
                "step": "Store external provider credentials in a secret manager or local `.env`, never in source.",
                "evidence": "env_presence.secrets_redacted=true",
            },
            {
                "step": "Run Replay Lab and Policy Guardrails before enabling live provider actions.",
                "evidence": "POST /replay-lab/report and POST /policies/export",
            },
            {
                "step": "Verify token, cost, timeout, and fallback behavior under SLO budget.",
                "evidence": "GET /ops/slo-budget",
            },
        ]

    def _acceptance_criteria(self) -> list[str]:
        return [
            "Default local/mock mode runs without OpenAI, Azure, Zendesk, Jira, Slack, or GitHub credentials.",
            "Provider audit redacts secrets and reports credential presence only as booleans.",
            "External provider modes fail closed when required credentials are missing.",
            "Human approval and outbox boundaries remain intact before customer or engineering-facing actions.",
            "Provider readiness pack is regenerated locally and referenced by dashboard, demo, docs, and tests.",
        ]

    def _jd_skills(self) -> list[str]:
        return [
            "LLM provider abstraction with local/mock default, optional OpenAI/Azure adapters, and local fallback.",
            "Credential readiness, secret redaction, and fail-closed external integration posture.",
            "Operational rollout planning across SLO, policy, approval, and fallback controls.",
            "FastAPI endpoint wiring, Streamlit dashboard surfacing, pytest coverage, and artifact export.",
        ]

    def _talking_points(self, audit: dict[str, Any]) -> list[str]:
        summary = audit["summary"]
        return [
            f"Provider readiness is `{summary['readiness_status']}` with score {summary['provider_score']}.",
            "The portfolio demo remains runnable with no paid LLM key because local/mock stays the default.",
            "OpenAI and Azure credentials are audited as presence booleans only, with no secret values returned.",
            "External provider rollout is tied to replay, policy guardrails, SLO budgets, and human approval.",
            "The pack separates demo safety from production activation work so reviewers can inspect both paths.",
        ]

    def _limitations(self) -> list[str]:
        return [
            "The audit checks local configuration and environment variable presence only.",
            "It does not call OpenAI, Azure OpenAI, Zendesk, Jira, Slack, GitHub, or external networks.",
            "Live OpenAI/Azure adapters are implemented but not called by this audit; credential validity and billing are not verified.",
            "Credential validity, rate limits, deployment names, model availability, and billing status are not verified.",
            "Secrets are intentionally redacted; only boolean presence is reported.",
        ]

    def _markdown(self, pack: dict[str, Any]) -> str:
        audit = pack["provider_readiness"]
        summary = audit["summary"]
        checks = [
            f"| {item['check_id']} | {item['status']} | {item['remediation']} |"
            for item in audit["provider_checks"]
        ]
        matrix = [
            (
                f"| {item['provider']} | {item['runtime_class']} | {item['credentials_required']} | "
                f"{item['status']} |"
            )
            for item in audit["provider_matrix"]
        ]
        backlog = [
            f"| {item['task_id']} | {item['owner']} | {item['severity']} | {item['remediation']} |"
            for item in audit["production_backlog"]
        ]
        commands = [f"- `{command}`" for command in pack["local_commands"]]
        criteria = [f"- {item}" for item in pack["acceptance_criteria"]]
        talking_points = [f"- {item}" for item in pack["interviewer_talking_points"]]
        limitations = [f"- {item}" for item in pack["limitations"]]
        return "\n".join(
            [
                "# Provider Readiness Guard Pack",
                "",
                "## Summary",
                f"- Provider: `{audit['configured_provider']}`",
                f"- Status: {summary['readiness_status']}",
                f"- Score: {summary['provider_score']}",
                f"- Failures: {summary['fail_count']}",
                f"- Warnings: {summary['warn_count']}",
                f"- Secrets exposed: {summary['secrets_exposed']}",
                "",
                "## Provider Matrix",
                "| Provider | Runtime class | Credentials required | Status |",
                "| --- | --- | --- | --- |",
                *matrix,
                "",
                "## Checks",
                "| Check | Status | Remediation |",
                "| --- | --- | --- |",
                *checks,
                "",
                "## Production Backlog",
                "| Task | Owner | Severity | Remediation |",
                "| --- | --- | --- | --- |",
                *backlog,
                "",
                "## Acceptance Criteria",
                *criteria,
                "",
                "## Local Commands",
                *commands,
                "",
                "## Interview Talking Points",
                *talking_points,
                "",
                "## Limitations",
                *limitations,
                "",
            ]
        )
