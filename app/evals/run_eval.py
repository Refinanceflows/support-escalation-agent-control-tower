import asyncio
import json
import time
from pathlib import Path

from app.core.config import Settings
from app.models import TicketCreate
from app.services.factory import ServiceContainer


ROOT = Path(__file__).resolve().parents[2]


async def run_eval() -> None:
    dataset = json.loads((ROOT / "sample_data" / "eval_dataset.json").read_text(encoding="utf-8"))
    state_file = ROOT / "data" / "eval_control_tower_state.db"
    if state_file.exists():
        state_file.unlink()
    settings = Settings(
        state_file=state_file,
        api_keys="eval-key",
        demo_api_key="eval-key",
        max_tool_attempts=2,
    )
    container = ServiceContainer(settings)

    total = len(dataset)
    correct_classification = 0
    correct_routing = 0
    approval_pauses = 0
    tool_failures = 0
    started = time.perf_counter()

    for row in dataset:
        ticket = await container.tickets.ingest(TicketCreate(**row["ticket"]))
        run = await container.workflow.analyze_ticket(ticket.ticket_id)
        state = run.state
        if state["classification"]["category"] == row["expected_category"]:
            correct_classification += 1

        expected_escalation = row["expected_route"] == "engineering_escalation"
        actual_escalation = bool(state.get("drafts", {}).get("engineering_escalation"))
        if expected_escalation == actual_escalation:
            correct_routing += 1

        approval_pauses += 1 if run.status == "awaiting_approval" else 0
        tool_failures += 1 if run.failure_state else 0

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    metrics = await container.metrics.agent_performance()
    node_metrics = metrics.get("node_metrics", {})
    token_usage = sum(item.get("tokens", 0) for item in node_metrics.values())
    estimated_cost = metrics.get("estimated_cost_usd", 0.0)
    scenario_pack = await container.scenarios.export_eval_pack()
    scenario_summary = scenario_pack["eval_summary"]
    runbook_audit = await container.runbook_coverage.coverage_audit()
    runbook_gap_pack = await container.runbook_coverage.export_gap_pack()
    capacity_forecast = await container.capacity_planning.forecast()
    capacity_plan = await container.capacity_planning.export_staffing_plan()
    provider_readiness = await container.provider_readiness.readiness()
    provider_pack = await container.provider_readiness.export_pack()
    provider_failover = await container.provider_failover.failover_drill()
    provider_failover_pack = await container.provider_failover.export_pack()
    communication_quality = await container.communication_quality.quality_audit()
    communication_quality_pack = await container.communication_quality.export_quality_pack()
    escalation_quality = await container.escalation_quality.quality_audit()
    escalation_quality_pack = await container.escalation_quality.export_quality_pack()
    support_ops_sandbox = await container.support_ops_sandbox.sandbox_run()
    support_ops_sandbox_pack = await container.support_ops_sandbox.export_sandbox_pack()
    support_ops_readiness = await container.support_ops_readiness.readiness_drill()
    support_ops_readiness_pack = await container.support_ops_readiness.export_readiness_pack()
    passed = (
        correct_classification == total
        and correct_routing == total
        and approval_pauses >= total
        and scenario_summary["status"] == "pass"
        and runbook_audit["coverage_score"] >= 50
        and runbook_audit["runbook_gaps"]
        and capacity_forecast["demand_summary"]["ticket_count"] >= total
        and capacity_forecast["queue_forecast"]
        and provider_readiness["readiness_status"] == "local_mock_ready"
        and provider_readiness["summary"]["secrets_exposed"] is False
        and provider_failover["readiness_status"] == "ready"
        and provider_failover["summary"]["external_call_count"] == 0
        and provider_failover["summary"]["fail_closed_count"] >= 1
        and communication_quality["overall_score"] >= 60
        and communication_quality["scenario_coverage"]["coverage_status"] == "pass"
        and escalation_quality["overall_score"] >= 60
        and escalation_quality["scenario_coverage"]["coverage_status"] == "pass"
        and support_ops_sandbox["benchmark_discipline"]["score"] >= 90
        and support_ops_sandbox["benchmark_discipline"]["status"] == "pass"
        and all(
            not event["external_call"]
            for task_run in support_ops_sandbox["task_runs"]
            for event in task_run["transcript"]
        )
        and support_ops_readiness["readiness_score"] >= 90
        and support_ops_readiness["process_mode_coverage"]["coverage_status"] == "pass"
        and support_ops_readiness["summary"]["external_call_count"] == 0
    )

    print(f"Number of eval tickets: {total}")
    print(f"Classification accuracy: {correct_classification}/{total}")
    print(f"SLA escalation routing accuracy: {correct_routing}/{total}")
    print(f"Approval-pause count: {approval_pauses}")
    print(f"Tool failure handling count: {tool_failures}")
    print(f"Average workflow latency: {round(elapsed_ms / total, 2)} ms")
    print(f"Token usage: {token_usage}")
    print(f"Estimated cost: ${estimated_cost:.6f}")
    print(f"Scenario Dataset scenarios: {scenario_summary['scenario_count']}")
    print(
        "Scenario Dataset classification accuracy: "
        f"{scenario_summary['classification_accuracy']['correct']}/"
        f"{scenario_summary['classification_accuracy']['total']}"
    )
    print(
        "Scenario Dataset SLA routing: "
        f"{scenario_summary['sla_routing']['correct']}/"
        f"{scenario_summary['sla_routing']['total']}"
    )
    print(f"Scenario Dataset Eval Pack: {scenario_pack['markdown_path']}")
    print(f"Runbook Coverage score: {runbook_audit['coverage_score']}")
    print(f"Runbook Coverage gaps: {len(runbook_audit['runbook_gaps'])}")
    print(f"Runbook Coverage process mode: {runbook_audit['selected_process_mode']['mode_id']}")
    print(
        "Runbook Coverage review gates:",
        f"failed={runbook_audit['run_transparency']['failed_gate_count']}",
    )
    print(f"Runbook Gap Pack: {runbook_gap_pack['markdown_path']}")
    print(f"Capacity Forecast score: {capacity_forecast['capacity_score']}")
    print(f"Capacity Forecast gaps: {len(capacity_forecast['staffing_gaps'])}")
    print(f"Capacity Staffing Plan: {capacity_plan['markdown_path']}")
    print(f"Provider Readiness status: {provider_readiness['readiness_status']}")
    print(f"Provider Readiness score: {provider_readiness['provider_score']}")
    print(f"Provider Readiness Pack: {provider_pack['markdown_path']}")
    print(f"Provider Failover status: {provider_failover['readiness_status']}")
    print(f"Provider Failover score: {provider_failover['failover_score']}")
    print(f"Provider Failover external calls: {provider_failover['summary']['external_call_count']}")
    print(f"Provider Failover Pack: {provider_failover_pack['markdown_path']}")
    print(f"Communication Quality status: {communication_quality['status']}")
    print(f"Communication Quality score: {communication_quality['overall_score']}")
    print(f"Communication Quality Pack: {communication_quality_pack['markdown_path']}")
    print(f"Escalation Quality status: {escalation_quality['status']}")
    print(f"Escalation Quality score: {escalation_quality['overall_score']}")
    print(f"Escalation Quality Pack: {escalation_quality_pack['markdown_path']}")
    print(f"Support Ops Sandbox status: {support_ops_sandbox['benchmark_discipline']['status']}")
    print(f"Support Ops Sandbox score: {support_ops_sandbox['benchmark_discipline']['score']}")
    print(f"Support Ops Sandbox Pack: {support_ops_sandbox_pack['markdown_path']}")
    print(f"Support Ops Readiness status: {support_ops_readiness['readiness_status']}")
    print(f"Support Ops Readiness score: {support_ops_readiness['readiness_score']}")
    print(f"Support Ops Readiness modes: {support_ops_readiness['process_mode_coverage']['actual_modes']}")
    print(f"Support Ops Readiness Pack: {support_ops_readiness_pack['markdown_path']}")
    print(f"Pass/fail summary: {'PASS' if passed else 'FAIL'}")
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(run_eval())
