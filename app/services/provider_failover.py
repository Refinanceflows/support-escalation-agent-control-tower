import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.adapters.fake import LocalMockLlmProvider
from app.adapters.llm import BlockingLlmProvider, ExternalProviderCallError, FallbackLlmProvider
from app.models import AuditEvent, KnowledgeArticle, Ticket
from app.services.audit import AuditService
from app.services.provider_readiness import ProviderReadinessService


PROVIDER_FAILOVER_COMMANDS = [
    r".\.venv\Scripts\python.exe -m pytest -q",
    r".\.venv\Scripts\python.exe -m ruff check app tests dashboard scripts",
    r".\.venv\Scripts\python.exe -m app.evals.run_eval",
    r".\.venv\Scripts\python.exe scripts\dashboard_smoke.py",
    r".\.venv\Scripts\python.exe scripts\demo_run.py",
    (
        r'rg "providers/failover-drill|providers/failover-pack|Provider Failover|'
        r'provider_failover_packs|fallback drill|fail-closed" app dashboard docs README.md tests scripts'
    ),
]


class _TimeoutPrimaryProvider:
    provider_name = "simulated_timeout_primary"

    async def draft_customer_reply(self, ticket: Ticket, context: list[KnowledgeArticle]) -> dict[str, Any]:
        raise ExternalProviderCallError("Simulated provider timeout before draft generation.")

    async def draft_engineering_escalation(
        self,
        ticket: Ticket,
        classification: dict[str, Any],
        sla_risk: dict[str, Any],
        context: list[KnowledgeArticle],
    ) -> dict[str, Any]:
        raise ExternalProviderCallError("Simulated provider timeout before escalation draft generation.")


class ProviderFailoverService:
    """Runs deterministic provider fallback and fail-closed drills without external calls."""

    def __init__(
        self,
        readiness: ProviderReadinessService,
        audit: AuditService,
        provider_failover_dir: Path,
    ):
        self.readiness = readiness
        self.audit = audit
        self.provider_failover_dir = provider_failover_dir

    async def failover_drill(self) -> dict[str, Any]:
        readiness = await self.readiness.readiness()
        scenarios = [
            await self._scenario_local_default(),
            await self._scenario_missing_openai_credentials(),
            await self._scenario_missing_azure_credentials(),
            await self._scenario_primary_timeout(),
            await self._scenario_fallback_disabled(),
        ]
        controls = self._control_checks(scenarios, readiness)
        summary = self._summary(scenarios, controls)
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "title": "Provider Failover Drill",
            "mode": "local-deterministic-provider-failover",
            "local_mock_only": True,
            "readiness_status": summary["readiness_status"],
            "failover_score": summary["failover_score"],
            "summary": summary,
            "provider_readiness_summary": readiness["summary"],
            "provider_scenarios": scenarios,
            "control_checks": controls,
            "activation_decision_table": self._decision_table(scenarios),
            "repo_radar_patterns": [
                "provider flexibility",
                "governance",
                "autonomous loop controls",
                "human-in-the-loop",
                "agent cost tracking",
            ],
            "endpoint_list": [
                "GET /providers/failover-drill",
                "POST /providers/failover-pack",
                "GET /providers/readiness",
                "POST /providers/readiness-pack",
                "GET /governance/autonomy-audit",
            ],
            "local_commands": PROVIDER_FAILOVER_COMMANDS,
            "limitations": self._limitations(),
        }

    async def export_pack(self) -> dict[str, Any]:
        drill = await self.failover_drill()
        generated_at = datetime.now(timezone.utc)
        pack_id = f"provider_failover_pack_{generated_at.strftime('%Y%m%d_%H%M%S')}_{uuid4().hex[:6]}"
        json_path = self.provider_failover_dir / f"{pack_id}.json"
        markdown_path = self.provider_failover_dir / f"{pack_id}.md"
        pack = {
            "pack_id": pack_id,
            "generated_at": generated_at.isoformat(),
            "title": "Provider Failover and Fallback Drill Pack",
            "failover_drill": drill,
            "deployment_gate": self._deployment_gate(drill),
            "acceptance_criteria": self._acceptance_criteria(),
            "artifact_paths": {
                "provider_failover_markdown": str(markdown_path),
                "provider_failover_json": str(json_path),
            },
            "local_commands": PROVIDER_FAILOVER_COMMANDS,
            "limitations": drill["limitations"],
        }
        markdown = self._markdown(pack)
        self.provider_failover_dir.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(pack, indent=2, default=str), encoding="utf-8")
        markdown_path.write_text(markdown, encoding="utf-8")
        await self.audit.record(
            AuditEvent(
                actor="provider-failover",
                action="providers.failover_pack_exported",
                resource_type="provider_failover_pack",
                resource_id=pack_id,
                metadata={
                    "status": drill["readiness_status"],
                    "markdown_path": str(markdown_path),
                    "json_path": str(json_path),
                },
            )
        )
        return {
            "pack_id": pack_id,
            "format": "markdown+json",
            "status": drill["readiness_status"],
            "failover_score": drill["failover_score"],
            "json_path": str(json_path),
            "markdown_path": str(markdown_path),
            "pack": pack,
            "markdown": markdown,
        }

    async def _scenario_local_default(self) -> dict[str, Any]:
        provider = LocalMockLlmProvider()
        result = await provider.draft_customer_reply(self._ticket(), self._context())
        return self._scenario(
            "local_default",
            "local",
            "Local mock provider handles drafts without credentials or network.",
            result,
            expected_provider="local",
            expected_fallback=False,
        )

    async def _scenario_missing_openai_credentials(self) -> dict[str, Any]:
        provider = FallbackLlmProvider(
            primary=LocalMockLlmProvider(),
            fallback=LocalMockLlmProvider(),
            reason="OpenAI provider selected without an API key.",
        )
        result = await provider.draft_customer_reply(self._ticket(), self._context())
        return self._scenario(
            "openai_missing_credentials",
            "openai",
            "OpenAI activation without credentials falls back to local.",
            result,
            expected_provider="local",
            expected_fallback=True,
        )

    async def _scenario_missing_azure_credentials(self) -> dict[str, Any]:
        provider = FallbackLlmProvider(
            primary=LocalMockLlmProvider(),
            fallback=LocalMockLlmProvider(),
            reason="Azure OpenAI provider selected without endpoint, API key, or deployment.",
        )
        result = await provider.draft_engineering_escalation(
            self._ticket(),
            {"category": "api_integrations"},
            {"level": "high", "score": 0.91},
            self._context(),
        )
        return self._scenario(
            "azure_missing_credentials",
            "azure_openai",
            "Azure activation without a complete endpoint/key/deployment falls back to local.",
            result,
            expected_provider="local",
            expected_fallback=True,
        )

    async def _scenario_primary_timeout(self) -> dict[str, Any]:
        provider = FallbackLlmProvider(primary=_TimeoutPrimaryProvider(), fallback=LocalMockLlmProvider())
        result = await provider.draft_customer_reply(self._ticket(), self._context())
        return self._scenario(
            "primary_timeout",
            "external_provider_timeout",
            "A simulated live-provider timeout returns a local fallback draft.",
            result,
            expected_provider="local",
            expected_fallback=True,
        )

    async def _scenario_fallback_disabled(self) -> dict[str, Any]:
        provider = BlockingLlmProvider("Fallback disabled and OpenAI credentials are missing.")
        try:
            await provider.draft_customer_reply(self._ticket(), self._context())
        except Exception as exc:  # noqa: BLE001 - this is the fail-closed branch under test.
            return {
                "scenario_id": "fallback_disabled_missing_credentials",
                "configured_provider": "openai",
                "description": "When fallback is disabled and credentials are missing, draft generation is blocked.",
                "status": "blocked",
                "provider": "blocked",
                "fallback_used": False,
                "fail_closed": True,
                "tokens": 0,
                "cost_usd": 0.0,
                "external_call": False,
                "human_approval_required": True,
                "evidence": str(exc),
                "passed": True,
            }
        return {
            "scenario_id": "fallback_disabled_missing_credentials",
            "configured_provider": "openai",
            "description": "Fallback-disabled missing credentials should block draft generation.",
            "status": "unexpected_success",
            "provider": "unknown",
            "fallback_used": False,
            "fail_closed": False,
            "tokens": 0,
            "cost_usd": 0.0,
            "external_call": False,
            "human_approval_required": True,
            "evidence": "Blocking provider returned without an error.",
            "passed": False,
        }

    def _scenario(
        self,
        scenario_id: str,
        configured_provider: str,
        description: str,
        result: dict[str, Any],
        expected_provider: str,
        expected_fallback: bool,
    ) -> dict[str, Any]:
        provider = str(result.get("provider") or expected_provider)
        fallback_used = bool(result.get("fallback_used", False))
        tokens = int(result.get("tokens", 0) or 0)
        cost = float(result.get("cost_usd", 0.0) or 0.0)
        return {
            "scenario_id": scenario_id,
            "configured_provider": configured_provider,
            "description": description,
            "status": "pass" if provider == expected_provider and fallback_used == expected_fallback else "review",
            "provider": provider,
            "fallback_used": fallback_used,
            "fallback_reason": result.get("fallback_reason", ""),
            "fail_closed": False,
            "tokens": tokens,
            "cost_usd": round(cost, 6),
            "external_call": False,
            "human_approval_required": True,
            "draft_preview": str(result.get("text", ""))[:180],
            "passed": provider == expected_provider and fallback_used == expected_fallback and tokens > 0,
        }

    def _control_checks(
        self,
        scenarios: list[dict[str, Any]],
        readiness: dict[str, Any],
    ) -> list[dict[str, Any]]:
        return [
            self._control(
                "local_default_ready",
                "Local/mock provider remains demo-ready",
                readiness["summary"]["external_services_required_for_default_demo"] is False
                and any(row["scenario_id"] == "local_default" and row["passed"] for row in scenarios),
                "Platform AI Owner",
                "Keep local/mock mode as CI and portfolio default.",
            ),
            self._control(
                "missing_credentials_fallback",
                "OpenAI and Azure missing-credential scenarios fall back to local",
                all(
                    row["provider"] == "local" and row["fallback_used"] and row["passed"]
                    for row in scenarios
                    if row["scenario_id"] in {"openai_missing_credentials", "azure_missing_credentials"}
                ),
                "Platform AI Owner",
                "Preserve local fallback for optional providers until production credentials are approved.",
            ),
            self._control(
                "runtime_timeout_fallback",
                "Provider runtime failures return a local fallback draft",
                any(row["scenario_id"] == "primary_timeout" and row["passed"] for row in scenarios),
                "AI Reliability Owner",
                "Keep timeout handling and fallback telemetry around live provider calls.",
            ),
            self._control(
                "fallback_disabled_fails_closed",
                "Fallback-disabled missing credentials block draft generation",
                any(
                    row["scenario_id"] == "fallback_disabled_missing_credentials"
                    and row["fail_closed"]
                    and row["passed"]
                    for row in scenarios
                ),
                "Security Owner",
                "Fail closed when live-provider credentials are missing and fallback is disabled.",
            ),
            self._control(
                "no_external_network_calls",
                "Failover drill makes no external network calls",
                all(not row["external_call"] for row in scenarios),
                "Security Owner",
                "Keep provider failover drill deterministic and local-only.",
            ),
            self._control(
                "cost_token_visible",
                "Fallback scenarios expose token and cost accounting",
                all("tokens" in row and "cost_usd" in row for row in scenarios),
                "Support Operations Lead",
                "Keep token/cost telemetry in provider events and governance packs.",
            ),
        ]

    def _control(
        self,
        control_id: str,
        label: str,
        passed: bool,
        owner: str,
        remediation: str,
    ) -> dict[str, Any]:
        return {
            "control_id": control_id,
            "label": label,
            "status": "pass" if passed else "review",
            "owner": owner,
            "remediation": remediation,
        }

    def _summary(
        self,
        scenarios: list[dict[str, Any]],
        controls: list[dict[str, Any]],
    ) -> dict[str, Any]:
        passed_scenarios = len([row for row in scenarios if row["passed"]])
        passed_controls = len([row for row in controls if row["status"] == "pass"])
        score = round((passed_scenarios / len(scenarios)) * 50 + (passed_controls / len(controls)) * 50)
        review_controls = len(controls) - passed_controls
        return {
            "readiness_status": "ready" if score >= 95 and review_controls == 0 else "review",
            "failover_score": score,
            "scenario_count": len(scenarios),
            "passed_scenario_count": passed_scenarios,
            "review_control_count": review_controls,
            "fallback_used_count": len([row for row in scenarios if row["fallback_used"]]),
            "fail_closed_count": len([row for row in scenarios if row["fail_closed"]]),
            "external_call_count": len([row for row in scenarios if row["external_call"]]),
            "estimated_cost_usd": round(sum(float(row["cost_usd"]) for row in scenarios), 6),
            "token_count": sum(int(row["tokens"]) for row in scenarios),
        }

    def _decision_table(self, scenarios: list[dict[str, Any]]) -> list[dict[str, str]]:
        return [
            {
                "signal": "Local default scenario passes",
                "decision": "default_demo_ready",
                "current_state": self._state_for(scenarios, "local_default"),
            },
            {
                "signal": "External provider missing credentials",
                "decision": "use_local_fallback_or_block_when_disabled",
                "current_state": ", ".join(
                    self._state_for(scenarios, item)
                    for item in ["openai_missing_credentials", "azure_missing_credentials"]
                ),
            },
            {
                "signal": "Runtime timeout before draft",
                "decision": "use_local_fallback",
                "current_state": self._state_for(scenarios, "primary_timeout"),
            },
            {
                "signal": "Fallback disabled",
                "decision": "fail_closed",
                "current_state": self._state_for(scenarios, "fallback_disabled_missing_credentials"),
            },
        ]

    def _state_for(self, scenarios: list[dict[str, Any]], scenario_id: str) -> str:
        row = next(item for item in scenarios if item["scenario_id"] == scenario_id)
        return f"{row['status']} provider={row['provider']} fallback={row['fallback_used']}"

    def _deployment_gate(self, drill: dict[str, Any]) -> dict[str, Any]:
        review_items = [item for item in drill["control_checks"] if item["status"] != "pass"]
        return {
            "gate": "provider_activation",
            "status": "approved_for_local_demo" if drill["readiness_status"] == "ready" else "review_required",
            "review_item_count": len(review_items),
            "required_before_live_provider": [
                "Credential validity check in a non-production environment",
                "Timeout, retry, fallback, and token/cost contract tests",
                "Policy guardrail simulation for customer and engineering actions",
                "Human approval confirmation before dispatch",
            ],
        }

    def _acceptance_criteria(self) -> list[str]:
        return [
            "Default local/mock mode works without paid provider credentials.",
            "OpenAI and Azure missing-credential scenarios fall back to deterministic local drafting when fallback is enabled.",
            "Fallback-disabled external-provider mode fails closed before draft generation.",
            "Runtime provider errors are observable and do not bypass human approval.",
            "The drill exports local Markdown/JSON artifacts and never calls external providers.",
        ]

    def _limitations(self) -> list[str]:
        return [
            "The drill uses deterministic local provider stubs and does not validate real OpenAI or Azure credentials.",
            "It does not call external networks, billing APIs, model deployment endpoints, Zendesk, Jira, Slack, or GitHub.",
            "Production rollout still needs live-provider contract tests, rate-limit handling, secret storage, and tenant-aware policy.",
            "Fallback results prove local behavior only; production latency, billing, quota, and model quality are out of scope.",
        ]

    def _ticket(self) -> Ticket:
        return Ticket(
            ticket_id="tkt_provider_failover",
            subject="Provider failover drill for enterprise escalation draft",
            body="Enterprise account reports API callback failures while the support team verifies provider fallback behavior.",
            customer="Northstar Bank",
            priority="high",
            customer_tier="enterprise",
            tags=["api", "provider-failover", "sla"],
        )

    def _context(self) -> list[KnowledgeArticle]:
        return [
            KnowledgeArticle(
                article_id="KB-API-001",
                title="API incident escalation policy",
                content="Escalate API callback failures with reproduction steps, customer impact, and approval state.",
                tags=["api", "escalation"],
                score=1.0,
            )
        ]

    def _markdown(self, pack: dict[str, Any]) -> str:
        drill = pack["failover_drill"]
        summary = drill["summary"]
        scenario_rows = [
            (
                f"| `{row['scenario_id']}` | `{row['configured_provider']}` | {row['status']} | "
                f"{row['provider']} | {row['fallback_used']} | {row['fail_closed']} | {row['external_call']} |"
            )
            for row in drill["provider_scenarios"]
        ]
        control_rows = [
            f"| `{item['control_id']}` | {item['status']} | {item['owner']} | {item['remediation']} |"
            for item in drill["control_checks"]
        ]
        decision_rows = [
            f"| {item['signal']} | `{item['decision']}` | {item['current_state']} |"
            for item in drill["activation_decision_table"]
        ]
        criteria = [f"- {item}" for item in pack["acceptance_criteria"]]
        commands = [f"- `{command}`" for command in pack["local_commands"]]
        limitations = [f"- {item}" for item in pack["limitations"]]
        return "\n".join(
            [
                f"# Provider Failover and Fallback Drill Pack: {pack['pack_id']}",
                "",
                "## Summary",
                f"- Status: {drill['readiness_status']}",
                f"- Score: {drill['failover_score']}",
                f"- Scenarios: {summary['passed_scenario_count']}/{summary['scenario_count']} passed",
                f"- Fallbacks used: {summary['fallback_used_count']}",
                f"- Fail-closed paths: {summary['fail_closed_count']}",
                f"- External calls: {summary['external_call_count']}",
                "",
                "## Provider Scenarios",
                "| Scenario | Configured Provider | Status | Actual Provider | Fallback | Fail Closed | External Call |",
                "| --- | --- | --- | --- | --- | --- | --- |",
                *scenario_rows,
                "",
                "## Control Checks",
                "| Control | Status | Owner | Remediation |",
                "| --- | --- | --- | --- |",
                *control_rows,
                "",
                "## Activation Decision Table",
                "| Signal | Decision | Current State |",
                "| --- | --- | --- |",
                *decision_rows,
                "",
                "## Deployment Gate",
                f"- Status: {pack['deployment_gate']['status']}",
                f"- Review items: {pack['deployment_gate']['review_item_count']}",
                "",
                "## Acceptance Criteria",
                *criteria,
                "",
                "## Local Commands",
                *commands,
                "",
                "## Limitations",
                *limitations,
                "",
            ]
        )
