import os
from typing import Any

import requests
import streamlit as st


API_BASE = os.getenv("CONTROL_TOWER_API_BASE_URL", "http://127.0.0.1:8000")
API_KEY = os.getenv("CONTROL_TOWER_API_KEY", "demo-control-tower-key")
HEADERS = {"x-api-key": API_KEY}
RENEWAL_REVIEW_ENDPOINT_TEMPLATE = "/customers/{customer_id_or_name}/renewal-review"
RENEWAL_REVIEW_ARTIFACT_DIRECTORY = "data/renewal_reviews"


def api(method: str, path: str, payload: dict[str, Any] | None = None) -> Any:
    response = requests.request(
        method,
        f"{API_BASE}{path}",
        json=payload,
        headers=HEADERS,
        timeout=20,
    )
    response.raise_for_status()
    return response.json()


st.set_page_config(page_title="Escalation Control Tower", layout="wide")
st.title("Support Escalation Agent Control Tower")

health = requests.get(f"{API_BASE}/health", timeout=5).json()
st.caption(f"API: {API_BASE} | status: {health.get('status')}")

tabs = st.tabs(
    [
        "Ticket Queue",
        "Analyze Ticket",
        "Run Timeline",
        "Trace Inspector",
        "Approval Panel",
        "Outbox",
        "Reliability",
        "SLA Simulator",
        "Incident Brief",
        "Playbooks / Remediation",
        "Customer Health / Account Brief",
        "Ops Analytics",
        "SLO / Optimization",
        "Demo Scenario / Evidence Pack",
        "Metrics",
        "Audit Events",
        "Operator QA / Readiness Pack",
        "Replay Lab",
        "Policy Guardrails",
        "Incident Narrative",
        "Leadership Scorecard",
        "Knowledge Quality",
        "Launch Checklist",
        "Portfolio Pack",
        "Release Pack",
        "CI Doctor / Audit Pack",
        "Reviewer Quickstart",
        "Artifact Inventory",
        "UI Verification",
        "Final Handoff",
        "Git Readiness",
        "API Contract",
        "Runtime Demo",
        "Scenario Dataset",
        "On-Call Handoff",
        "Postmortem RCA",
        "Finance Impact",
        "Runbook Coverage",
        "Evidence Retention",
        "Capacity Planning",
        "Data Residency",
        "Access Control",
        "Risk Register",
        "Provider Readiness",
        "Executive Daily Ops Brief",
        "Autonomy Governance",
        "Durable Workflows",
        "Escalation Quality",
        "Communication Quality",
        "Support Ops Crews",
        "Support Ops Sandbox",
        "Support Ops Readiness",
        "Tool Governance",
        "Agent Bus",
        "Trace Eval Lab",
    ]
)

with tabs[0]:
    col1, col2 = st.columns([1, 4])
    if col1.button("Load Samples", use_container_width=True):
        api("POST", "/tickets/ingest-samples")
        st.rerun()
    tickets = api("GET", "/tickets")
    col2.metric("Open tickets", len(tickets))
    st.dataframe(
        [
            {
                "ticket_id": item["ticket_id"],
                "subject": item["subject"],
                "priority": item["priority"],
                "tier": item["customer_tier"],
                "status": item["status"],
                "tags": ", ".join(item.get("tags", [])),
            }
            for item in tickets
        ],
        use_container_width=True,
        hide_index=True,
    )

with tabs[1]:
    tickets = api("GET", "/tickets")
    labels = {f"{item['subject']} | {item['ticket_id']}": item["ticket_id"] for item in tickets}
    if labels:
        selected = st.selectbox("Ticket", list(labels))
        if st.button("Analyze", type="primary"):
            run = api("POST", f"/tickets/{labels[selected]}/analyze")
            st.session_state["run_id"] = run["run_id"]
            st.success(f"Run created: {run['run_id']}")
    run_id = st.text_input("Run ID", value=st.session_state.get("run_id", ""))
    if run_id:
        st.json(api("GET", f"/runs/{run_id}"))

with tabs[2]:
    run_id = st.text_input("Timeline run ID", value=st.session_state.get("run_id", ""))
    if run_id:
        trace = api("GET", f"/runs/{run_id}/trace")
        for event in trace:
            st.markdown(
                f"**{event.get('node') or 'workflow'}** · `{event['event_type']}` · "
                f"`{event['status']}` · {round(event.get('latency_ms', 0), 2)} ms"
            )
            if event.get("message"):
                st.caption(event["message"])

with tabs[3]:
    run_id = st.text_input("Trace run ID", value=st.session_state.get("run_id", ""))
    if run_id:
        st.dataframe(api("GET", f"/runs/{run_id}/trace"), use_container_width=True, hide_index=True)

with tabs[4]:
    approvals = api("GET", "/approvals")
    st.dataframe(
        [
            {
                "approval_id": item["approval_id"],
                "run_id": item["run_id"],
                "status": item["status"],
                "reason": item["reason"],
            }
            for item in approvals
        ],
        use_container_width=True,
        hide_index=True,
    )
    if approvals:
        selected = st.selectbox("Pending approval", [f"{a['approval_id']} | {a['run_id']}" for a in approvals])
        approval = approvals[[f"{a['approval_id']} | {a['run_id']}" for a in approvals].index(selected)]
        st.text_area("Customer reply", approval["customer_reply"], height=160)
        if approval["engineering_escalation"]:
            st.text_area("Engineering escalation", approval["engineering_escalation"], height=220)
        note = st.text_input("Reviewer note", value="Reviewed in dashboard")
        left, right = st.columns(2)
        if left.button("Approve", type="primary", use_container_width=True):
            api("POST", f"/runs/{approval['run_id']}/approve", {"decided_by": "dashboard", "note": note})
            st.rerun()
        if right.button("Reject", use_container_width=True):
            api("POST", f"/runs/{approval['run_id']}/reject", {"decided_by": "dashboard", "note": note})
            st.rerun()

with tabs[5]:
    outbox = api("GET", "/integrations/outbox")
    st.metric("Recorded dispatches", len(outbox))
    st.dataframe(
        [
            {
                "created_at": item["created_at"],
                "action_type": item["action_type"],
                "destination": item["destination"],
                "status": item["status"],
                "run_id": item["run_id"],
                "ticket_id": item["ticket_id"],
            }
            for item in outbox
        ],
        use_container_width=True,
        hide_index=True,
    )
    if outbox:
        selected = st.selectbox(
            "Dispatch payload",
            [f"{item['action_type']} | {item['id']}" for item in outbox],
        )
        event = outbox[[f"{item['action_type']} | {item['id']}" for item in outbox].index(selected)]
        st.json(event)

with tabs[6]:
    if st.button("Run KB Failure Drill", type="primary"):
        drill = api("POST", "/drills/tool-failure")
        st.session_state["drill_run_id"] = drill["run"]["run_id"]
        st.success(f"Drill run created: {drill['run']['run_id']}")
    drill_run_id = st.text_input(
        "Failure drill run ID",
        value=st.session_state.get("drill_run_id", st.session_state.get("run_id", "")),
    )
    if drill_run_id:
        trace = api("GET", f"/runs/{drill_run_id}/trace")
        failures = [
            event
            for event in trace
            if event["event_type"] == "tool_call" and event["status"] == "error"
        ]
        c1, c2 = st.columns(2)
        c1.metric("Failed tool attempts", len(failures))
        c2.metric("Trace events", len(trace))
        for event in trace:
            st.markdown(
                f"**{event.get('node') or 'workflow'}** | `{event['event_type']}` | `{event['status']}`"
            )
            if event.get("metadata"):
                st.caption(event["metadata"])
            if event.get("message"):
                st.caption(event["message"])

with tabs[7]:
    if st.button("Run SLA Breach Simulation", type="primary"):
        simulation = api("POST", "/drills/sla-breach-simulation")
        st.session_state["sla_simulation"] = simulation
        if simulation["queue"]:
            st.session_state["run_id"] = simulation["queue"][0]["run_id"]
        st.success(f"Prioritized {len(simulation['queue'])} SLA-risk tickets")
    simulation = st.session_state.get("sla_simulation")
    if simulation:
        st.dataframe(simulation["queue"], use_container_width=True, hide_index=True)
        selected = st.selectbox(
            "Export brief for simulated run",
            [f"{item['risk_level']} | {item['run_id']}" for item in simulation["queue"]],
        )
        selected_run = simulation["queue"][
            [f"{item['risk_level']} | {item['run_id']}" for item in simulation["queue"]].index(
                selected
            )
        ]["run_id"]
        st.session_state["run_id"] = selected_run
        if st.button("Export Incident Brief", use_container_width=True):
            brief = api("POST", f"/runs/{selected_run}/incident-brief")
            st.session_state["incident_brief"] = brief
            st.success(f"Brief exported: {brief['markdown_path']}")

with tabs[8]:
    run_id = st.text_input("Brief run ID", value=st.session_state.get("run_id", ""))
    if st.button("Export Brief", type="primary", disabled=not run_id):
        brief = api("POST", f"/runs/{run_id}/incident-brief")
        st.session_state["incident_brief"] = brief
    brief = st.session_state.get("incident_brief")
    if brief:
        st.caption(f"Markdown: {brief['markdown_path']}")
        st.caption(f"JSON: {brief['json_path']}")
        st.download_button(
            "Download Markdown",
            data=brief["markdown"],
            file_name=f"{brief['run_id']}.md",
            mime="text/markdown",
        )
        st.markdown(brief["markdown"])
        with st.expander("Structured JSON"):
            st.json(brief["brief"])

with tabs[9]:
    run_id = st.text_input("Playbook run ID", value=st.session_state.get("run_id", ""))
    ticket_id = ""
    run = None
    if run_id:
        run = api("GET", f"/runs/{run_id}")
        ticket_id = run["ticket_id"]
        recommendations = run["state"].get("playbook_recommendations", [])
        if not recommendations:
            recommendations = api(
                "POST",
                "/playbooks/recommend",
                {"ticket_id": ticket_id, "top_n": 3},
            )["recommendations"]
        st.subheader("Recommended Playbooks")
        st.dataframe(
            [
                {
                    "rank": index + 1,
                    "playbook": item["title"],
                    "confidence": item["confidence"],
                    "severity": item["severity"],
                    "owners": ", ".join(item["owner_roles"]),
                    "reasons": " ".join(item["match_reasons"]),
                }
                for index, item in enumerate(recommendations)
            ],
            use_container_width=True,
            hide_index=True,
        )
        if recommendations:
            selected = st.selectbox(
                "Selected playbook",
                [f"{item['title']} | {item['id']}" for item in recommendations],
            )
            selected_playbook_id = recommendations[
                [f"{item['title']} | {item['id']}" for item in recommendations].index(selected)
            ]["id"]
            if st.button("Export Remediation Checklist", type="primary"):
                checklist = api(
                    "POST",
                    f"/runs/{run_id}/remediation-checklist",
                    {"playbook_id": selected_playbook_id},
                )
                st.session_state["remediation_checklist"] = checklist
                st.success(f"Checklist exported: {checklist['markdown_path']}")
    else:
        tickets = api("GET", "/tickets")
        labels = {f"{item['subject']} | {item['ticket_id']}": item["ticket_id"] for item in tickets}
        if labels:
            selected_ticket = st.selectbox("Ticket for recommendation", list(labels))
            if st.button("Recommend Playbooks", type="primary"):
                recs = api(
                    "POST",
                    "/playbooks/recommend",
                    {"ticket_id": labels[selected_ticket], "top_n": 3},
                )
                st.session_state["playbook_recommendations"] = recs
        if st.session_state.get("playbook_recommendations"):
            st.json(st.session_state["playbook_recommendations"])

    checklist = st.session_state.get("remediation_checklist")
    if checklist:
        st.caption(f"Markdown: {checklist['markdown_path']}")
        st.caption(f"JSON: {checklist['json_path']}")
        st.download_button(
            "Download Checklist",
            data=checklist["markdown"],
            file_name=f"{checklist['checklist']['checklist_id']}.md",
            mime="text/markdown",
        )
        st.markdown(checklist["markdown"])
        with st.expander("Checklist JSON"):
            st.json(checklist["checklist"])

with tabs[10]:
    health = api("GET", "/customers/health")
    renewal = api("GET", "/customers/renewal-risk")
    renewal_control = api("GET", "/customers/renewal-control-board")
    renewal_handoff = api("GET", "/customers/renewal-handoff-gate")
    customers = health["customers"]
    if customers:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Accounts", len(customers))
        c2.metric("Critical or at risk", sum(1 for item in customers if item["risk_level"] in {"critical", "at_risk"}))
        c3.metric("Pending approvals", sum(item["pending_approval_count"] for item in customers))
        c4.metric("High SLA risks", sum(item["high_sla_risk_count"] for item in customers))

        st.dataframe(customers, use_container_width=True, hide_index=True)
        st.subheader("Renewal Risk")
        renewal_summary = renewal["summary"]
        r1, r2, r3, r4 = st.columns(4)
        r1.metric("Renewal accounts", renewal_summary["account_count"])
        r2.metric("Critical or high", renewal_summary["critical_or_high_count"])
        r3.metric("ARR at risk", f"${renewal_summary['arr_at_risk_usd']:,.0f}")
        r4.metric("SLA drag", f"{renewal_summary.get('total_sla_drag_minutes', 0)} min")
        control_summary = renewal_control["summary"]
        g1, g2, g3, g4 = st.columns(4)
        g1.metric("Control status", control_summary["status"])
        g2.metric("Review required", control_summary["review_required_count"])
        g3.metric("Blocked actions", control_summary["blocked_automation_action_count"])
        g4.metric("Pending checkpoints", control_summary["pending_checkpoint_count"])
        handoff_summary = renewal_handoff["summary"]
        h1, h2, h3, h4 = st.columns(4)
        h1.metric("Handoff status", handoff_summary["status"])
        h2.metric("Blocked handoffs", handoff_summary["blocked_count"])
        h3.metric("Ready handoffs", handoff_summary["ready_count"])
        h4.metric("Avg readiness", handoff_summary["average_readiness_score"])
        st.dataframe(
            [
                {
                    "account": item["account"],
                    "risk": item["renewal_risk_level"],
                    "score": item["renewal_risk_score"],
                    "arr_at_risk": item["arr_at_risk_usd"],
                    "window_days": item["renewal_window_days"],
                    "sentiment": item["support_sentiment"]["label"],
                    "sla_drag": item["sla_drag"]["total_minutes"],
                    "recommended_action": item["recommended_action"],
                }
                for item in renewal["accounts"]
            ],
            use_container_width=True,
            hide_index=True,
        )
        st.subheader("Renewal Control Board")
        st.dataframe(
            [
                {
                    "account": item["account"],
                    "review_status": item["review_status"],
                    "approval": item["required_approval_type"],
                    "owner": item["primary_owner"],
                    "blocked_actions": len(item["blocked_automation_actions"]),
                    "pending_checkpoints": sum(
                        1
                        for checkpoint in item["durable_review_checkpoints"]
                        if checkpoint["status"] == "pending"
                    ),
                    "next_action": item["next_operator_action"],
                }
                for item in renewal_control["control_board"]
            ],
            use_container_width=True,
            hide_index=True,
        )
        st.subheader("Renewal Handoff Gate")
        st.dataframe(
            [
                {
                    "account": item["account"],
                    "handoff_status": item["handoff_status"],
                    "readiness_score": item["readiness_score"],
                    "failed_checks": item["failed_check_count"],
                    "owner": item["primary_owner"],
                    "next_action": item["next_operator_action"],
                }
                for item in renewal_handoff["accounts"]
            ],
            use_container_width=True,
            hide_index=True,
        )
        if st.button("Export Renewal Control Pack"):
            control_pack = api("POST", "/customers/renewal-control-pack")
            st.session_state["renewal_control_pack"] = control_pack
            st.success(f"Renewal control pack exported: {control_pack['markdown_path']}")
        if st.button("Export Renewal Handoff Pack"):
            handoff_pack = api("POST", "/customers/renewal-handoff-pack")
            st.session_state["renewal_handoff_pack"] = handoff_pack
            st.success(f"Renewal handoff pack exported: {handoff_pack['markdown_path']}")
        handoff_pack = st.session_state.get("renewal_handoff_pack")
        if handoff_pack:
            st.caption(f"Handoff Markdown: {handoff_pack['markdown_path']}")
            st.caption(f"Handoff JSON: {handoff_pack['json_path']}")
            st.download_button(
                "Download Renewal Handoff Pack",
                data=handoff_pack["markdown"],
                file_name=f"{handoff_pack['pack_id']}.md",
                mime="text/markdown",
            )
            with st.expander("Renewal Handoff Markdown"):
                st.markdown(handoff_pack["markdown"])
            with st.expander("Renewal Handoff JSON"):
                st.json(handoff_pack["pack"])
        control_pack = st.session_state.get("renewal_control_pack")
        if control_pack:
            st.caption(f"Control Markdown: {control_pack['markdown_path']}")
            st.caption(f"Control JSON: {control_pack['json_path']}")
            st.download_button(
                "Download Renewal Control Pack",
                data=control_pack["markdown"],
                file_name=f"{control_pack['pack_id']}.md",
                mime="text/markdown",
            )
            with st.expander("Renewal Control Markdown"):
                st.markdown(control_pack["markdown"])
            with st.expander("Renewal Control JSON"):
                st.json(control_pack["pack"])
        selected = st.selectbox(
            "Account",
            [f"{item['account']} | {item['health_score']} | {item['risk_level']}" for item in customers],
        )
        account = customers[
            [f"{item['account']} | {item['health_score']} | {item['risk_level']}" for item in customers].index(
                selected
            )
        ]
        if st.button("Export Account Brief", type="primary"):
            brief = api("POST", f"/customers/{account['customer_id']}/account-brief")
            st.session_state["account_brief"] = brief
            st.success(f"Account brief exported: {brief['markdown_path']}")
        brief = st.session_state.get("account_brief")
        if brief:
            st.caption(f"Markdown: {brief['markdown_path']}")
            st.caption(f"JSON: {brief['json_path']}")
            st.download_button(
                "Download Account Brief",
                data=brief["markdown"],
                file_name=f"{brief['customer_id']}.md",
                mime="text/markdown",
            )
            st.markdown(brief["markdown"])
            with st.expander("Account Brief JSON"):
                st.json(brief["brief"])
        if st.button("Export Renewal Review"):
            review = api("POST", f"/customers/{account['customer_id']}/renewal-review")
            st.session_state["renewal_review"] = review
            st.success(f"Renewal review exported: {review['markdown_path']}")
        review = st.session_state.get("renewal_review")
        if review:
            st.caption(f"Renewal Markdown: {review['markdown_path']}")
            st.caption(f"Renewal JSON: {review['json_path']}")
            st.download_button(
                "Download Renewal Review",
                data=review["markdown"],
                file_name=f"{review['customer_id']}-renewal.md",
                mime="text/markdown",
            )
            with st.expander("Renewal Review Markdown", expanded=True):
                st.markdown(review["markdown"])
            with st.expander("Renewal Review JSON"):
                st.json(review["review"])
    else:
        st.info("No customer health rows yet.")

with tabs[11]:
    snapshot = api("GET", "/analytics/ops-snapshot")
    summary = snapshot["summary_metrics"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Tickets", summary["ticket_count"])
    c2.metric("Runs", summary["run_count"])
    c3.metric("Pending approvals", summary["pending_approval_count"])
    c4.metric("Failures", summary["failure_count"])
    r1, r2, r3 = st.columns(3)
    r1.metric("Outbox dispatches", summary["outbox_dispatch_count"])
    r2.metric("Avg latency/run", f"{snapshot['averages']['latency_ms_per_run']} ms")
    r3.metric("Avg cost/run", f"${snapshot['averages']['cost_usd_per_run']:.6f}")

    st.subheader("Top Risky Tickets")
    st.dataframe(snapshot["top_risky_tickets"], use_container_width=True, hide_index=True)
    st.subheader("Recommended Actions")
    for action in snapshot["recommended_operational_actions"]:
        st.markdown(f"- {action}")

    left, right = st.columns([1, 1])
    with left:
        st.subheader("Counts")
        st.json(snapshot["counts"])
    with right:
        st.subheader("SLA Highlights")
        st.dataframe(snapshot["sla_queue_highlights"], use_container_width=True, hide_index=True)

    if st.button("Export Weekly Review", type="primary"):
        review = api("POST", "/analytics/weekly-review")
        st.session_state["weekly_review"] = review
        st.success(f"Weekly review exported: {review['markdown_path']}")
    review = st.session_state.get("weekly_review")
    if review:
        st.caption(f"Markdown: {review['markdown_path']}")
        st.caption(f"JSON: {review['json_path']}")
        st.download_button(
            "Download Weekly Review",
            data=review["markdown"],
            file_name=f"{review['report_id']}.md",
            mime="text/markdown",
        )
        with st.expander("Weekly Review Markdown", expanded=True):
            st.markdown(review["markdown"])
        with st.expander("Structured Snapshot"):
            st.json(snapshot)

with tabs[12]:
    slo = api("GET", "/ops/slo-budget")
    metrics = slo["metrics"]
    c1, c2, c3 = st.columns(3)
    c1.metric("Overall SLO", slo["overall_status"].upper())
    c2.metric("Failures", metrics["failure_count"]["current_value"])
    c3.metric("Pending approvals", metrics["pending_approvals"]["current_value"])
    r1, r2, r3 = st.columns(3)
    r1.metric(
        "Workflow latency",
        f"{metrics['agent_workflow_latency_ms']['current_value']} ms/run",
    )
    r2.metric(
        "Token usage",
        f"{metrics['token_usage_per_run']['current_value']} tokens/run",
    )
    r3.metric(
        "Outbox delay",
        f"{metrics['outbox_dispatch_delay_minutes']['current_value']} min",
    )
    st.dataframe(
        [
            {
                "metric": metric,
                "status": item["status"],
                "current_value": item["current_value"],
                "unit": item["unit"],
                "pass_at_or_below": item["thresholds"]["pass_at_or_below"],
                "warn_at_or_below": item["thresholds"]["warn_at_or_below"],
                "recommendation": item["recommendation"],
            }
            for metric, item in metrics.items()
        ],
        use_container_width=True,
        hide_index=True,
    )

    if st.button("Export Optimization Report", type="primary"):
        report = api("POST", "/ops/optimization-report")
        st.session_state["optimization_report"] = report
        st.success(f"Optimization report exported: {report['markdown_path']}")
    report = st.session_state.get("optimization_report")
    if report:
        st.caption(f"Markdown: {report['markdown_path']}")
        st.caption(f"JSON: {report['json_path']}")
        st.download_button(
            "Download Optimization Report",
            data=report["markdown"],
            file_name=f"{report['report_id']}.md",
            mime="text/markdown",
        )
        st.markdown(report["markdown"])
        with st.expander("Optimization Report JSON"):
            st.json(report["report"])

with tabs[13]:
    left, right = st.columns(2)
    if left.button("Run Demo Scenario", type="primary", use_container_width=True):
        scenario = api("POST", "/demo/scenario-run")
        st.session_state["demo_scenario"] = scenario
        st.session_state["run_id"] = scenario["summary_metrics"]["run_id"]
        st.success(f"Scenario complete: {scenario['scenario_id']}")
    if right.button("Export Evidence Pack", use_container_width=True):
        pack = api("POST", "/demo/evidence-pack")
        st.session_state["demo_evidence_pack"] = pack
        st.session_state["demo_scenario"] = pack["scenario"]
        st.session_state["run_id"] = pack["scenario"]["summary_metrics"]["run_id"]
        st.success(f"Evidence pack exported: {pack['markdown_path']}")

    scenario = st.session_state.get("demo_scenario")
    if scenario:
        metrics = scenario["summary_metrics"]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Run status", metrics["run_status"])
        c2.metric("Trace events", metrics["trace_event_count"])
        c3.metric("Outbox dispatches", metrics["outbox_dispatch_count"])
        c4.metric("SLO", metrics["slo_overall_status"].upper())
        st.subheader("Generated Artifacts")
        st.dataframe(
            [
                {"artifact": name, "path": path}
                for name, path in sorted(scenario["artifact_paths"].items())
            ],
            use_container_width=True,
            hide_index=True,
        )
        st.subheader("Endpoints Exercised")
        st.dataframe(
            [{"endpoint": endpoint} for endpoint in scenario["endpoints_exercised"]],
            use_container_width=True,
            hide_index=True,
        )
        with st.expander("Scenario JSON"):
            st.json(scenario)

    pack = st.session_state.get("demo_evidence_pack")
    if pack:
        st.caption(f"Markdown: {pack['markdown_path']}")
        st.caption(f"JSON: {pack['json_path']}")
        st.download_button(
            "Download Evidence Pack",
            data=pack["markdown"],
            file_name=f"{pack['pack_id']}.md",
            mime="text/markdown",
        )
        st.markdown(pack["markdown"])
        with st.expander("Evidence Pack JSON"):
            st.json(pack["pack"])

with tabs[14]:
    metrics = api("GET", "/metrics/agent-performance")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Runs", metrics["run_count"])
    c2.metric("Completed", metrics["completed_runs"])
    c3.metric("Pending approvals", metrics["pending_approvals"])
    c4.metric("Estimated cost", f"${metrics['estimated_cost_usd']:.6f}")
    r1, r2, r3 = st.columns(3)
    r1.metric("Outbox dispatches", metrics.get("outbox_dispatch_count", 0))
    r2.metric("Failure drills", metrics.get("failure_drill_count", 0))
    r3.metric("Tool failures", metrics.get("tool_failure_count", 0))
    st.json(metrics)

with tabs[15]:
    st.dataframe(api("GET", "/audit/events"), use_container_width=True, hide_index=True)

with tabs[16]:
    run_id = st.text_input("Operator QA run ID", value=st.session_state.get("run_id", ""))
    left, right = st.columns(2)
    if left.button("Run Runbook QA", type="primary", use_container_width=True):
        payload = {"run_id": run_id} if run_id else None
        qa = api("POST", "/ops/runbook-qa", payload)
        st.session_state["runbook_qa"] = qa
        st.session_state["run_id"] = qa["run_id"]
    if right.button("Export Readiness Pack", use_container_width=True):
        payload = {"run_id": run_id} if run_id else None
        pack = api("POST", "/ops/operator-readiness-pack", payload)
        st.session_state["operator_readiness_pack"] = pack
        st.session_state["runbook_qa"] = pack["pack"]["runbook_qa"]
        st.session_state["run_id"] = pack["pack"]["runbook_qa"]["run_id"]
        st.success(f"Readiness Pack exported: {pack['markdown_path']}")

    qa = st.session_state.get("runbook_qa")
    if qa:
        c1, c2, c3 = st.columns(3)
        c1.metric("Readiness score", qa["score"])
        c2.metric("Status", qa["status"].upper())
        c3.metric("Missing sections", len(qa["missing_sections"]))
        st.subheader("Required Sections")
        st.dataframe(
            [
                {
                    "section": item["label"],
                    "present": item["present"],
                    "evidence": item["evidence"],
                }
                for item in qa["sections"].values()
            ],
            use_container_width=True,
            hide_index=True,
        )
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Recommended Fixes")
            for fix in qa["recommended_fixes"]:
                st.markdown(f"- {fix}")
        with col2:
            st.subheader("Warnings")
            for warning in qa["warnings"] or ["None"]:
                st.markdown(f"- {warning}")
        st.subheader("Linked Artifacts")
        st.dataframe(
            [
                {"artifact": name, "path": path}
                for name, path in sorted(qa["linked_artifact_paths"].items())
            ],
            use_container_width=True,
            hide_index=True,
        )
        with st.expander("Runbook QA JSON"):
            st.json(qa)

    pack = st.session_state.get("operator_readiness_pack")
    if pack:
        st.caption(f"Markdown: {pack['markdown_path']}")
        st.caption(f"JSON: {pack['json_path']}")
        st.download_button(
            "Download Readiness Pack",
            data=pack["markdown"],
            file_name=f"{pack['pack_id']}.md",
            mime="text/markdown",
        )
        st.markdown(pack["markdown"])
        with st.expander("Readiness Pack JSON"):
            st.json(pack["pack"])

with tabs[17]:
    run_id = st.text_input("Replay run ID", value=st.session_state.get("run_id", ""))
    c1, c2, c3 = st.columns(3)
    sla_pressure = c1.selectbox("SLA pressure", ["normal", "high", "critical"], index=1)
    kb_context = c2.selectbox("KB context", ["full", "missing", "conflicting"], index=0)
    adapter_health = c3.selectbox("Adapter health", ["healthy", "degraded", "failing"], index=1)
    p1, p2 = st.columns(2)
    approval_policy = p1.selectbox(
        "Approval policy",
        ["standard", "strict", "auto_internal_only"],
    )
    confidence_enabled = p2.checkbox("Override confidence")
    confidence_override = p2.slider("Confidence", 0.0, 1.0, 0.45, 0.01) if confidence_enabled else None
    replay_payload = {
        "run_id": run_id or None,
        "modifiers": {
            "sla_pressure": sla_pressure,
            "kb_context": kb_context,
            "adapter_health": adapter_health,
            "confidence_override": confidence_override,
            "approval_policy": approval_policy,
        },
    }
    left, right = st.columns(2)
    if left.button("Run Replay", type="primary", use_container_width=True):
        path = f"/runs/{run_id}/replay-lab" if run_id else "/replay-lab/run"
        payload = {"modifiers": replay_payload["modifiers"]} if run_id else replay_payload
        replay = api("POST", path, payload)
        st.session_state["replay_lab"] = replay
        st.session_state["run_id"] = replay["source_run_id"]
    if right.button("Export Replay Report", use_container_width=True):
        report = api("POST", "/replay-lab/report", replay_payload)
        st.session_state["replay_lab_report"] = report
        st.session_state["replay_lab"] = report["report"]["comparison"]
        st.success(f"Replay report exported: {report['markdown_path']}")

    replay = st.session_state.get("replay_lab")
    if replay:
        comparison = replay["comparison"]
        r1, r2, r3, r4 = st.columns(4)
        r1.metric("Risk score", comparison["risk_score"])
        r2.metric("Changed decisions", len(comparison["changed_decisions"]))
        r3.metric("Replay SLA", replay["replay"]["sla_risk"]["level"])
        r4.metric("Approval", "required" if replay["replay"]["approval_required"] else "not required")
        st.subheader("Recommended Operator Action")
        st.info(comparison["recommended_operator_action"])
        st.subheader("Original vs Replay")
        st.dataframe(
            [
                {
                    "decision": "classification",
                    "original": replay["original"]["classification"]["category"],
                    "replay": replay["replay"]["classification"]["category"],
                },
                {
                    "decision": "SLA risk",
                    "original": replay["original"]["sla_risk"]["level"],
                    "replay": replay["replay"]["sla_risk"]["level"],
                },
                {
                    "decision": "final action",
                    "original": replay["original"]["final_action"],
                    "replay": replay["replay"]["final_action"],
                },
                {
                    "decision": "tool attempts",
                    "original": replay["original"]["tool_attempts"]["count"],
                    "replay": replay["replay"]["tool_attempts"]["count"],
                },
            ],
            use_container_width=True,
            hide_index=True,
        )
        st.subheader("Changed Decisions")
        st.dataframe(comparison["changed_decisions"], use_container_width=True, hide_index=True)
        st.subheader("Risk Flags")
        st.write(", ".join(comparison["risk_flags"]) or "None")
        with st.expander("Replay Lab JSON"):
            st.json(replay)

    report = st.session_state.get("replay_lab_report")
    if report:
        st.caption(f"Markdown: {report['markdown_path']}")
        st.caption(f"JSON: {report['json_path']}")
        st.download_button(
            "Download Replay Report",
            data=report["markdown"],
            file_name=f"{report['report_id']}.md",
            mime="text/markdown",
        )
        st.markdown(report["markdown"])

with tabs[18]:
    run_id = st.text_input("Policy run ID", value=st.session_state.get("run_id", ""))
    c1, c2, c3 = st.columns(3)
    sla_pressure = c1.selectbox(
        "Policy SLA pressure",
        ["normal", "high", "critical"],
        index=1,
    )
    kb_context = c2.selectbox("Policy KB context", ["full", "missing", "conflicting"], index=0)
    adapter_health = c3.selectbox(
        "Policy adapter health",
        ["healthy", "degraded", "failing"],
        index=1,
    )
    p1, p2, p3 = st.columns(3)
    approval_policy = p1.selectbox(
        "Policy mode",
        ["standard", "strict", "auto_internal_only"],
    )
    replay_risk_threshold = p2.slider("Replay risk threshold", 0, 100, 70, 5)
    confidence_override = p3.slider("Confidence override", 0.0, 1.0, 0.46, 0.01)
    actions = st.multiselect(
        "Requested actions",
        [
            "customer_reply",
            "zendesk_update",
            "jira_issue",
            "slack_alert",
            "engineering_escalation",
        ],
        default=[
            "customer_reply",
            "zendesk_update",
            "jira_issue",
            "slack_alert",
            "engineering_escalation",
        ],
    )
    policy_payload = {
        "run_id": run_id or None,
        "modifiers": {
            "sla_pressure": sla_pressure,
            "kb_context": kb_context,
            "adapter_health": adapter_health,
            "confidence_override": confidence_override,
            "approval_policy": approval_policy,
        },
        "requested_actions": actions,
        "replay_risk_threshold": replay_risk_threshold,
    }
    left, right = st.columns(2)
    if left.button("Simulate Policy", type="primary", use_container_width=True):
        simulation = api("POST", "/policies/simulate", policy_payload)
        st.session_state["policy_simulation"] = simulation
        st.session_state["run_id"] = simulation["source_run_id"]
    if right.button("Export Policy Pack", use_container_width=True):
        pack = api("POST", "/policies/export", policy_payload)
        st.session_state["policy_pack"] = pack
        st.session_state["policy_simulation"] = pack["pack"]["primary_simulation"]
        st.session_state["run_id"] = pack["pack"]["primary_simulation"]["source_run_id"]
        st.success(f"Policy pack exported: {pack['markdown_path']}")

    simulation = st.session_state.get("policy_simulation")
    if simulation:
        s1, s2, s3, s4 = st.columns(4)
        s1.metric("Decision", simulation["policy_decision"])
        s2.metric("Approval", simulation["required_approval_type"])
        s3.metric("Blocked", len(simulation["blocked_actions"]))
        s4.metric("Replay risk", simulation["replay_summary"]["risk_score"])
        st.subheader("Recommended Operator Action")
        st.info(simulation["recommended_operator_action"])
        st.subheader("Matched Rules")
        st.dataframe(simulation["matched_rules"], use_container_width=True, hide_index=True)
        st.subheader("Action Split")
        a1, a2 = st.columns(2)
        with a1:
            st.caption("Blocked actions")
            st.write(", ".join(simulation["blocked_actions"]) or "None")
        with a2:
            st.caption("Allowed actions")
            st.write(", ".join(simulation["allowed_actions"]) or "None")
        st.subheader("Approval Matrix")
        st.dataframe(simulation["approval_matrix"], use_container_width=True, hide_index=True)
        with st.expander("Policy Simulation JSON"):
            st.json(simulation)

    pack = st.session_state.get("policy_pack")
    if pack:
        st.caption(f"Markdown: {pack['markdown_path']}")
        st.caption(f"JSON: {pack['json_path']}")
        st.download_button(
            "Download Policy Pack",
            data=pack["markdown"],
            file_name=f"{pack['pack_id']}.md",
            mime="text/markdown",
        )
        st.markdown(pack["markdown"])

    st.divider()
    st.subheader("Policy Change Simulation")
    b1, b2, b3 = st.columns(3)
    baseline_confidence = b1.slider("Baseline confidence cutoff", 0.0, 1.0, 0.62, 0.01)
    baseline_sla = b2.slider("Baseline SLA high threshold", 0.0, 1.0, 0.70, 0.01)
    baseline_blast = b3.slider("Baseline auto-approval blast max", 0, 100, 35, 1)
    p1, p2, p3 = st.columns(3)
    proposed_confidence = p1.slider("Proposed confidence cutoff", 0.0, 1.0, 0.72, 0.01)
    proposed_sla = p2.slider("Proposed SLA high threshold", 0.0, 1.0, 0.65, 0.01)
    proposed_blast = p3.slider("Proposed auto-approval blast max", 0, 100, 25, 1)
    scenario_limit = st.slider("Policy-change scenario limit", 1, 25, 9, 1)
    change_payload = {
        "baseline": {
            "confidence_cutoff": baseline_confidence,
            "sla_high_risk_threshold": baseline_sla,
            "auto_approval_max_blast_radius": baseline_blast,
        },
        "proposed": {
            "confidence_cutoff": proposed_confidence,
            "sla_high_risk_threshold": proposed_sla,
            "auto_approval_max_blast_radius": proposed_blast,
        },
        "scenario_limit": scenario_limit,
    }
    change_left, change_right = st.columns(2)
    if change_left.button("Run Policy Change Simulation", use_container_width=True):
        change_simulation = api("POST", "/policies/change-simulation", change_payload)
        st.session_state["policy_change_simulation"] = change_simulation
    if change_right.button("Export Policy Change Pack", use_container_width=True):
        change_pack = api("POST", "/policies/change-pack", change_payload)
        st.session_state["policy_change_pack"] = change_pack
        st.session_state["policy_change_simulation"] = change_pack["pack"]["simulation"]
        st.success(f"Policy change pack exported: {change_pack['markdown_path']}")

    change_simulation = st.session_state.get("policy_change_simulation")
    if change_simulation:
        summary = change_simulation["summary"]
        blast = change_simulation["blast_radius"]
        sla = change_simulation["sla_routing"]
        d1, d2, d3, d4 = st.columns(4)
        d1.metric("Auto delta", summary["deltas"]["auto_allowed_count"])
        d2.metric("Review delta", summary["deltas"]["blocked_for_review_count"])
        d3.metric("Blast risk", blast["overall_change_risk_score"])
        d4.metric("SLA changes", sla["changed_route_count"])
        st.info(summary["recommendation"])
        st.dataframe(
            [
                {
                    "scenario": row["scenario_id"],
                    "expected_sla": row["expected_sla_level"],
                    "baseline_decision": row["baseline"]["decision"],
                    "proposed_decision": row["proposed"]["decision"],
                    "sla_route": f"{row['baseline']['sla_route']} -> {row['proposed']['sla_route']}",
                    "proposed_blast": row["proposed"]["blast_radius_score"],
                    "changed": ", ".join(row["changed"]) or "none",
                }
                for row in change_simulation["scenario_results"]
            ],
            use_container_width=True,
            hide_index=True,
        )
        with st.expander("Policy Change Simulation JSON"):
            st.json(change_simulation)

    change_pack = st.session_state.get("policy_change_pack")
    if change_pack:
        st.caption(f"Markdown: {change_pack['markdown_path']}")
        st.caption(f"JSON: {change_pack['json_path']}")
        st.download_button(
            "Download Policy Change Pack",
            data=change_pack["markdown"],
            file_name=f"{change_pack['pack_id']}.md",
            mime="text/markdown",
        )
        st.markdown(change_pack["markdown"])

    st.divider()
    st.subheader("Policy Rollout Review Gate")
    r1, r2, r3 = st.columns(3)
    process_mode = r1.selectbox("Rollout process mode", ["shadow", "canary", "full"], index=1)
    max_new_auto = r2.slider("Max new auto-allowed", 0, 10, 0, 1)
    max_sla_regressions = r3.slider("Max SLA regressions", 0, 10, 0, 1)
    max_change_risk = st.slider("Max change risk score", 0, 100, 30, 1)
    rollout_payload = {
        **change_payload,
        "process_mode": process_mode,
        "max_new_auto_allowed": max_new_auto,
        "max_sla_regressions": max_sla_regressions,
        "max_change_risk_score": max_change_risk,
    }
    rollout_left, rollout_right = st.columns(2)
    if rollout_left.button("Run Rollout Gate", use_container_width=True):
        rollout_plan = api("POST", "/policies/rollout-plan", rollout_payload)
        st.session_state["policy_rollout_plan"] = rollout_plan
    if rollout_right.button("Export Rollout Pack", use_container_width=True):
        rollout_pack = api("POST", "/policies/rollout-pack", rollout_payload)
        st.session_state["policy_rollout_pack"] = rollout_pack
        st.session_state["policy_rollout_plan"] = rollout_pack["pack"]["rollout_plan"]
        st.success(f"Policy rollout pack exported: {rollout_pack['markdown_path']}")

    rollout_plan = st.session_state.get("policy_rollout_plan")
    if rollout_plan:
        summary = rollout_plan["summary"]
        g1, g2, g3, g4 = st.columns(4)
        g1.metric("Rollout status", rollout_plan["status"])
        g2.metric("Failed gates", summary["failed_gate_count"])
        g3.metric("Change risk", summary["change_risk_score"])
        g4.metric("SLA regressions", summary["sla_regression_count"])
        st.info(summary["recommendation"])
        st.dataframe(rollout_plan["review_gates"], use_container_width=True, hide_index=True)
        st.subheader("Canary rollout")
        st.dataframe(rollout_plan["canary_rollout"], use_container_width=True, hide_index=True)
        st.subheader("Role signoffs")
        st.dataframe(rollout_plan["role_signoffs"], use_container_width=True, hide_index=True)
        st.subheader("Rollback triggers")
        st.dataframe(rollout_plan["rollback_triggers"], use_container_width=True, hide_index=True)
        with st.expander("Policy Rollout JSON"):
            st.json(rollout_plan)

    rollout_pack = st.session_state.get("policy_rollout_pack")
    if rollout_pack:
        st.caption(f"Markdown: {rollout_pack['markdown_path']}")
        st.caption(f"JSON: {rollout_pack['json_path']}")
        st.download_button(
            "Download Policy Rollout Pack",
            data=rollout_pack["markdown"],
            file_name=f"{rollout_pack['pack_id']}.md",
            mime="text/markdown",
        )
        st.markdown(rollout_pack["markdown"])

    st.divider()
    st.subheader("Policy Drift Monitor")
    dleft, dright = st.columns(2)
    drift_max_runs = dleft.slider("Drift max runs", 1, 100, 20, 1)
    drift_include_pending = dright.checkbox("Include pending approvals", value=True)
    drift_payload = {
        "baseline": change_payload["baseline"],
        "current": change_payload["proposed"],
        "max_runs": drift_max_runs,
        "include_pending": drift_include_pending,
    }
    drift_left, drift_right = st.columns(2)
    if drift_left.button("Run Drift Audit", use_container_width=True):
        drift_audit = api("POST", "/policies/drift-audit", drift_payload)
        st.session_state["policy_drift_audit"] = drift_audit
    if drift_right.button("Export Drift Pack", use_container_width=True):
        drift_pack = api("POST", "/policies/drift-pack", drift_payload)
        st.session_state["policy_drift_pack"] = drift_pack
        st.session_state["policy_drift_audit"] = drift_pack["pack"]["drift_audit"]
        st.success(f"Policy drift pack exported: {drift_pack['markdown_path']}")

    drift_audit = st.session_state.get("policy_drift_audit")
    if drift_audit:
        summary = drift_audit["summary"]
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Drift status", drift_audit["status"])
        m2.metric("Evaluated runs", summary["evaluated_run_count"])
        m3.metric("Drifted runs", summary["drifted_run_count"])
        m4.metric("New auto-allow", summary["new_auto_allowed_count"])
        st.dataframe(drift_audit["review_gates"], use_container_width=True, hide_index=True)
        st.dataframe(
            [
                {
                    "run_id": row["run_id"],
                    "ticket_id": row["ticket_id"],
                    "severity": row["severity"],
                    "decision": f"{row['baseline']['decision']} -> {row['current']['decision']}",
                    "sla_route": f"{row['baseline']['sla_route']} -> {row['current']['sla_route']}",
                    "changed": ", ".join(row["changed_fields"]) or "none",
                    "action": row["recommended_action"],
                }
                for row in drift_audit["drift_rows"]
            ],
            use_container_width=True,
            hide_index=True,
        )
        with st.expander("Policy Drift JSON"):
            st.json(drift_audit)

    drift_pack = st.session_state.get("policy_drift_pack")
    if drift_pack:
        st.caption(f"Markdown: {drift_pack['markdown_path']}")
        st.caption(f"JSON: {drift_pack['json_path']}")
        st.download_button(
            "Download Policy Drift Pack",
            data=drift_pack["markdown"],
            file_name=f"{drift_pack['pack_id']}.md",
            mime="text/markdown",
        )
        st.markdown(drift_pack["markdown"])

with tabs[19]:
    run_id = st.text_input("Incident narrative run ID", value=st.session_state.get("run_id", ""))
    left, right = st.columns(2)
    narrative_payload = {"run_id": run_id} if run_id else None
    if left.button("Build Customer Impact Timeline", type="primary", use_container_width=True):
        timeline = api("POST", "/incidents/timeline", narrative_payload)
        st.session_state["incident_timeline"] = timeline
        st.session_state["run_id"] = timeline["run_id"]
    if right.button("Export Executive Narrative", use_container_width=True):
        narrative = api("POST", "/incidents/executive-narrative", narrative_payload)
        st.session_state["executive_incident_narrative"] = narrative
        st.session_state["incident_timeline"] = narrative["narrative"]
        st.session_state["run_id"] = narrative["run_id"]
        st.success(f"Narrative exported: {narrative['markdown_path']}")

    timeline = st.session_state.get("incident_timeline")
    if timeline:
        if "timeline" in timeline and "events" not in timeline:
            timeline_rows = timeline["timeline"]
            impact = timeline["customer_impact"]
            policy = timeline["policy_guardrail_decision"]
            replay = timeline["replay_risk"]
            owner_actions = timeline["owner_actions"]
            unresolved = timeline["unresolved_risks"]
            artifacts = timeline["evidence_artifact_links"]
            run_display = timeline["run_id"]
            impact_status = timeline["impact_status"]
        else:
            timeline_rows = timeline["events"]
            impact = timeline["customer_impact_summary"]
            policy = timeline["policy_annotations"]
            replay = timeline["replay_annotations"]
            owner_actions = timeline["owner_next_steps"]
            unresolved = timeline["unresolved_risks"]
            artifacts = timeline["evidence_artifact_links"]
            run_display = timeline["run_id"]
            impact_status = timeline["impact_status"]

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Run", run_display)
        c2.metric("Impact status", impact_status)
        c3.metric("Policy", policy["policy_decision"])
        c4.metric("Replay risk", replay["risk_score"])
        st.subheader("Customer Impact")
        st.json(impact)
        st.subheader("Customer Impact Timeline")
        st.dataframe(
            [
                {
                    "sequence": item["sequence"],
                    "timestamp": item["timestamp"],
                    "phase": item["phase"],
                    "visibility": item["visibility"],
                    "actor": item["actor"],
                    "summary": item["summary"],
                }
                for item in timeline_rows
            ],
            use_container_width=True,
            hide_index=True,
        )
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Owner Actions")
            st.dataframe(owner_actions, use_container_width=True, hide_index=True)
        with c2:
            st.subheader("Unresolved Risks")
            st.dataframe(unresolved, use_container_width=True, hide_index=True)
        st.subheader("Policy and Replay Annotations")
        st.json({"policy": policy, "replay": replay})
        st.subheader("Evidence Artifacts")
        st.dataframe(
            [{"artifact": name, "path": path} for name, path in sorted(artifacts.items())],
            use_container_width=True,
            hide_index=True,
        )
        with st.expander("Timeline JSON"):
            st.json(timeline)

    narrative = st.session_state.get("executive_incident_narrative")
    if narrative:
        st.caption(f"Markdown: {narrative['markdown_path']}")
        st.caption(f"JSON: {narrative['json_path']}")
        st.download_button(
            "Download Executive Narrative",
            data=narrative["markdown"],
            file_name=f"{narrative['narrative_id']}.md",
            mime="text/markdown",
        )
        st.markdown(narrative["markdown"])

with tabs[20]:
    left, right = st.columns(2)
    if left.button("Refresh Scorecard", type="primary", use_container_width=True):
        st.session_state["leadership_scorecard"] = api("GET", "/leadership/scorecard")
    if right.button("Export Review Pack", use_container_width=True):
        review = api("POST", "/leadership/review-pack")
        st.session_state["leadership_review_pack"] = review
        st.session_state["leadership_scorecard"] = review["review"]["scorecard"]
        st.success(f"Leadership review exported: {review['markdown_path']}")

    scorecard = st.session_state.get("leadership_scorecard") or api(
        "GET",
        "/leadership/scorecard",
    )
    st.session_state["leadership_scorecard"] = scorecard
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Overall score", scorecard["overall_score"])
    c2.metric("Readiness", scorecard["readiness_status"])
    c3.metric("Runs", scorecard["sample_window"]["run_count"])
    c4.metric("Outbox", scorecard["sample_window"]["outbox_dispatch_count"])

    st.subheader("Automation KPI Categories")
    st.dataframe(
        [
            {
                "category": name,
                "score": category["score"],
                "status": category["status"],
                "risk_flags": ", ".join(category["risk_flags"]),
            }
            for name, category in scorecard["kpi_categories"].items()
        ],
        use_container_width=True,
        hide_index=True,
    )
    st.subheader("Trend-ish Local Values")
    st.json(scorecard["trendish_local_values"])
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Top Risks")
        for risk in scorecard["risk_flags"] or ["None"]:
            st.markdown(f"- {risk}")
    with col2:
        st.subheader("Recommended Actions")
        for action in scorecard["recommended_actions"]:
            st.markdown(f"- {action}")
    st.subheader("Local Evidence Links")
    st.dataframe(
        [{"artifact": name, "path": path} for name, path in sorted(scorecard["artifact_links"].items())],
        use_container_width=True,
        hide_index=True,
    )

    review = st.session_state.get("leadership_review_pack")
    if review:
        st.caption(f"Markdown: {review['markdown_path']}")
        st.caption(f"JSON: {review['json_path']}")
        st.download_button(
            "Download Leadership Review",
            data=review["markdown"],
            file_name=f"{review['review_id']}.md",
            mime="text/markdown",
        )
        st.markdown(review["markdown"])
        with st.expander("Leadership Review JSON"):
            st.json(review["review"])

with tabs[21]:
    left, right = st.columns(2)
    if left.button("Run Knowledge Quality Audit", type="primary", use_container_width=True):
        st.session_state["knowledge_quality_audit"] = api("GET", "/knowledge/quality-audit")
    if right.button("Export KB Refresh Plan", use_container_width=True):
        plan = api("POST", "/knowledge/refresh-plan")
        st.session_state["kb_refresh_plan"] = plan
        st.session_state["knowledge_quality_audit"] = plan["plan"]["source_audit"]
        st.success(f"KB refresh plan exported: {plan['markdown_path']}")

    audit = st.session_state.get("knowledge_quality_audit") or api("GET", "/knowledge/quality-audit")
    st.session_state["knowledge_quality_audit"] = audit
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("KB coverage score", audit["kb_coverage_score"])
    c2.metric("Readiness", audit["readiness_status"])
    c3.metric("Freshness", f"{audit['metrics']['freshness']['freshness_percent']}%")
    c4.metric("Citation coverage", f"{audit['metrics']['citations']['citation_percent']}%")

    st.subheader("Knowledge Quality Metrics")
    st.json(audit["metrics"])
    st.subheader("Weak or Missing Articles")
    st.dataframe(audit["weak_or_missing_articles"], use_container_width=True, hide_index=True)
    st.subheader("Impacted Ticket Types")
    st.dataframe(audit["impacted_ticket_types"], use_container_width=True, hide_index=True)

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Risk Flags")
        for flag in audit["risk_flags"] or ["None"]:
            st.markdown(f"- {flag}")
    with col2:
        st.subheader("Owner Recommendations")
        for item in audit["owner_recommendations"]:
            st.markdown(f"- **{item['owner']}**: {item['recommendation']}")

    st.subheader("Evidence Sources")
    st.json(audit["evidence_sources"])

    plan = st.session_state.get("kb_refresh_plan")
    if plan:
        st.caption(f"Markdown: {plan['markdown_path']}")
        st.caption(f"JSON: {plan['json_path']}")
        st.download_button(
            "Download KB Refresh Plan",
            data=plan["markdown"],
            file_name=f"{plan['plan_id']}.md",
            mime="text/markdown",
        )
        st.markdown(plan["markdown"])
        with st.expander("KB Refresh Plan JSON"):
            st.json(plan["plan"])

with tabs[22]:
    smoke = st.session_state.get("smoke_matrix") or api("GET", "/ops/smoke-matrix")
    st.session_state["smoke_matrix"] = smoke
    summary = smoke["readiness_summary"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Launch readiness", summary["status"].upper())
    c2.metric("Smoke checks", summary["total_checks"])
    c3.metric("Protected checks", summary["protected_checks"])
    c4.metric("Artifact checks", summary["artifact_writing_checks"])

    st.subheader("Smoke Matrix")
    st.dataframe(
        [
            {
                "endpoint": row["endpoint"],
                "expected_status": row["expected_status"],
                "requires_api_key": row["requires_api_key"],
                "artifact": row["artifact_expectation"]["path"],
                "curl": row["sample_commands"]["curl"],
            }
            for row in smoke["matrix"]
        ],
        use_container_width=True,
        hide_index=True,
    )

    left, right = st.columns(2)
    if left.button("Refresh Smoke Matrix", use_container_width=True):
        st.session_state["smoke_matrix"] = api("GET", "/ops/smoke-matrix")
        st.rerun()
    if right.button("Export Launch Checklist", type="primary", use_container_width=True):
        checklist = api("POST", "/ops/launch-checklist")
        st.session_state["launch_checklist"] = checklist
        st.success(f"Launch checklist exported: {checklist['markdown_path']}")

    checklist = st.session_state.get("launch_checklist")
    if checklist:
        st.caption(f"Markdown: {checklist['markdown_path']}")
        st.caption(f"JSON: {checklist['json_path']}")
        st.download_button(
            "Download Launch Checklist",
            data=checklist["markdown"],
            file_name=f"{checklist['checklist_id']}.md",
            mime="text/markdown",
        )
        st.subheader("Generated Artifacts")
        st.dataframe(
            checklist["checklist"]["generated_artifacts"],
            use_container_width=True,
            hide_index=True,
        )
        st.markdown(checklist["markdown"])
        with st.expander("Launch Checklist JSON"):
            st.json(checklist["checklist"])

with tabs[23]:
    left, right = st.columns(2)
    if left.button("Refresh Portfolio Evidence", type="primary", use_container_width=True):
        st.session_state["portfolio_evidence"] = api("GET", "/portfolio/evidence-index")
    if right.button("Export Interview Pack", use_container_width=True):
        pack = api("POST", "/portfolio/interview-pack")
        st.session_state["portfolio_interview_pack"] = pack
        st.session_state["portfolio_evidence"] = pack["pack"]["evidence_index"]
        st.success(f"Interview Pack exported: {pack['markdown_path']}")

    evidence = st.session_state.get("portfolio_evidence") or api("GET", "/portfolio/evidence-index")
    st.session_state["portfolio_evidence"] = evidence
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Evidence score", evidence["evidence_score"])
    c2.metric("Skill areas", evidence["evidence_count"])
    c3.metric("Covered", evidence["covered_skill_count"])
    c4.metric("Local/mock", "yes" if evidence["local_mock_only"] else "no")

    st.subheader("Skill Coverage")
    st.dataframe(
        [
            {
                "skill": item["jd_skill"],
                "status": item["coverage_status"],
                "score": item["item_score"],
                "endpoints": ", ".join(item["endpoints"]),
                "proof paths": ", ".join(item["local_proof_paths"]),
            }
            for item in evidence["jd_skill_evidence"]
        ],
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("Local Verification Commands")
    for command in evidence["verification_commands"]:
        st.code(command)

    st.subheader("Artifact Inventory")
    st.dataframe(
        [
            {
                "artifact": item["name"],
                "directory": item["directory"],
                "producer": item["producer"],
                "latest": item["latest_path"],
            }
            for item in evidence["artifact_inventory"]
        ],
        use_container_width=True,
        hide_index=True,
    )

    pack = st.session_state.get("portfolio_interview_pack")
    if pack:
        st.caption(f"Markdown: {pack['markdown_path']}")
        st.caption(f"JSON: {pack['json_path']}")
        st.download_button(
            "Download Interview Pack",
            data=pack["markdown"],
            file_name=f"{pack['pack_id']}.md",
            mime="text/markdown",
        )
        st.subheader("Technical Talking Points")
        for point in pack["pack"]["technical_talking_points"]:
            st.markdown(f"- {point}")
        st.markdown(pack["markdown"])
        with st.expander("Interview Pack JSON"):
            st.json(pack["pack"])

with tabs[24]:
    left, right = st.columns(2)
    if left.button("Refresh Release Gate", type="primary", use_container_width=True):
        st.session_state["release_gate"] = api("GET", "/release/quality-gate")
    if right.button("Export Publish Pack", use_container_width=True):
        publish_pack = api("POST", "/release/publish-pack")
        st.session_state["release_publish_pack"] = publish_pack
        st.session_state["release_gate"] = publish_pack["pack"]["quality_gate"]
        st.success(f"Publish Pack exported: {publish_pack['markdown_path']}")

    gate = st.session_state.get("release_gate") or api("GET", "/release/quality-gate")
    st.session_state["release_gate"] = gate
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Gate status", gate["status"])
    c2.metric("Score", gate["score"])
    c3.metric("Blockers", len(gate["blockers"]))
    c4.metric("Warnings", len(gate["warnings"]))

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Blockers")
        for blocker in gate["blockers"] or ["None"]:
            st.markdown(f"- {blocker}")
    with col2:
        st.subheader("Warnings")
        for warning in gate["warnings"] or ["None"]:
            st.markdown(f"- {warning}")

    st.subheader("Verification Commands")
    for item in gate["verification_checklist"]:
        st.code(item["command"])
        st.caption(item["expected"])

    st.subheader("Coverage")
    st.dataframe(
        [
            {"area": name, "status": item["status"]}
            for name, item in gate["coverage"].items()
        ],
        use_container_width=True,
        hide_index=True,
    )

    publish_pack = st.session_state.get("release_publish_pack")
    if publish_pack:
        st.caption(f"Markdown: {publish_pack['markdown_path']}")
        st.caption(f"JSON: {publish_pack['json_path']}")
        st.download_button(
            "Download Publish Pack",
            data=publish_pack["markdown"],
            file_name=f"{publish_pack['pack_id']}.md",
            mime="text/markdown",
        )
        st.markdown(publish_pack["markdown"])
        with st.expander("Publish Pack JSON"):
            st.json(publish_pack["pack"])

with tabs[25]:
    left, right = st.columns(2)
    if left.button("Refresh CI Doctor", type="primary", use_container_width=True):
        st.session_state["ci_doctor"] = api("GET", "/ops/ci-doctor")
    if right.button("Export Audit Pack", use_container_width=True):
        audit_pack = api("POST", "/ops/audit-pack")
        st.session_state["audit_pack"] = audit_pack
        st.session_state["ci_doctor"] = audit_pack["pack"]["ci_doctor"]
        st.success(f"Audit Pack exported: {audit_pack['markdown_path']}")

    doctor = st.session_state.get("ci_doctor") or api("GET", "/ops/ci-doctor")
    st.session_state["ci_doctor"] = doctor
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Doctor status", doctor["status"])
    c2.metric("Score", doctor["score"])
    c3.metric("Blockers", len(doctor["blockers"]))
    c4.metric("Secret findings", doctor["secret_scan_summary"]["finding_count"])

    st.subheader("CI Doctor Checks")
    st.dataframe(
        [
            {
                "check": item["label"],
                "status": item["status"],
            }
            for item in doctor["checks"].values()
        ],
        use_container_width=True,
        hide_index=True,
    )

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Local Verification Commands")
        for command in doctor["local_verification_commands"]:
            st.code(command)
    with col2:
        st.subheader("Publish-Safety Checklist")
        st.dataframe(doctor["publish_safety_checklist"], use_container_width=True, hide_index=True)

    st.subheader("Dependency Inventory")
    st.json(doctor["dependency_inventory"])

    st.subheader("Secret Scan Summary")
    st.json(doctor["secret_scan_summary"])

    audit_pack = st.session_state.get("audit_pack")
    if audit_pack:
        st.caption(f"Markdown: {audit_pack['markdown_path']}")
        st.caption(f"JSON: {audit_pack['json_path']}")
        st.download_button(
            "Download Audit Pack",
            data=audit_pack["markdown"],
            file_name=f"{audit_pack['pack_id']}.md",
            mime="text/markdown",
        )
        st.markdown(audit_pack["markdown"])
        with st.expander("Audit Pack JSON"):
            st.json(audit_pack["pack"])

with tabs[26]:
    left, right = st.columns(2)
    if left.button("Refresh Reviewer Quickstart", type="primary", use_container_width=True):
        st.session_state["reviewer_quickstart"] = api("GET", "/reviewer/quickstart")
    if right.button("Export Walkthrough Pack", use_container_width=True):
        pack = api("POST", "/reviewer/walkthrough-pack")
        st.session_state["reviewer_walkthrough_pack"] = pack
        st.session_state["reviewer_quickstart"] = pack["pack"]["quickstart"]
        st.success(f"Walkthrough Pack exported: {pack['markdown_path']}")

    quickstart = st.session_state.get("reviewer_quickstart") or api("GET", "/reviewer/quickstart")
    st.session_state["reviewer_quickstart"] = quickstart
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Status", quickstart["status"])
    c2.metric("Proof entries", quickstart["artifact_proof_count"])
    c3.metric("Endpoints", len(quickstart["endpoint_walkthrough_order"]))
    c4.metric("Local/mock", "yes" if quickstart["local_mock_only"] else "no")

    st.subheader("Local Setup")
    for command in quickstart["local_setup_commands"]:
        st.code(command)
    st.subheader("One-Command Demo")
    st.code(quickstart["one_command_demo"])

    st.subheader("Verification Commands")
    for command, expected in zip(
        quickstart["verification_commands"],
        quickstart["expected_outputs"],
        strict=False,
    ):
        st.code(command)
        st.caption(expected)

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Endpoint Walkthrough")
        st.dataframe(
            [{"order": index + 1, "endpoint": endpoint} for index, endpoint in enumerate(quickstart["endpoint_walkthrough_order"])],
            use_container_width=True,
            hide_index=True,
        )
    with col2:
        st.subheader("Agent Workflow")
        st.dataframe(
            [
                {
                    "step": item["step"],
                    "reviewer_focus": item["reviewer_focus"],
                    "proof": ", ".join(item["proof"]),
                }
                for item in quickstart["agent_workflow_walkthrough"]
            ],
            use_container_width=True,
            hide_index=True,
        )

    st.subheader("Artifact Proof Map")
    st.dataframe(
        [
            {
                "artifact": item["name"],
                "directory": item["directory"],
                "producer": item["producer"],
                "latest": ", ".join(item["latest_paths"]) or "not generated yet",
            }
            for item in quickstart["artifact_proof_map"]
        ],
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("Role-Specific Reviewer Notes")
    st.json(quickstart["role_specific_reviewer_notes"])

    pack = st.session_state.get("reviewer_walkthrough_pack")
    if pack:
        st.caption(f"Markdown: {pack['markdown_path']}")
        st.caption(f"JSON: {pack['json_path']}")
        st.download_button(
            "Download Walkthrough Pack",
            data=pack["markdown"],
            file_name=f"{pack['pack_id']}.md",
            mime="text/markdown",
        )
        st.markdown(pack["markdown"])
        with st.expander("Walkthrough Pack JSON"):
            st.json(pack["pack"])

with tabs[27]:
    left, right = st.columns(2)
    if left.button("Refresh Artifact Inventory", type="primary", use_container_width=True):
        st.session_state["artifact_inventory"] = api("GET", "/artifacts/inventory")
    if right.button("Export README Checklist Pack", use_container_width=True):
        pack = api("POST", "/artifacts/readme-checklist")
        st.session_state["readme_checklist_pack"] = pack
        st.session_state["artifact_inventory"] = api("GET", "/artifacts/inventory")
        st.success(f"README Checklist exported: {pack['markdown_path']}")

    inventory = st.session_state.get("artifact_inventory") or api("GET", "/artifacts/inventory")
    st.session_state["artifact_inventory"] = inventory
    artifacts = inventory["artifacts"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Artifact dirs", inventory.get("artifact_count", len(artifacts)))
    c2.metric("Generated dirs", inventory.get("generated_artifact_directory_count", 0))
    c3.metric("Missing dirs", inventory.get("missing_artifact_directory_count", 0))
    c4.metric("Local/mock", "yes" if inventory.get("local_mock_only", True) else "no")

    st.subheader("Artifact Inventory")
    st.dataframe(
        [
            {
                "artifact": item["name"],
                "directory": item["directory"],
                "producer": item["producer"],
                "latest": item["latest_path"],
                "freshness": item["freshness"]["status"],
                "ignored": item["ignored_status"]["ignored_by_default"],
                "purpose": item["reviewer_purpose"],
            }
            for item in artifacts
        ],
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("Local Commands")
    commands = inventory.get("local_commands", {})
    if commands.get("demo"):
        st.code(commands["demo"])
    for command in commands.get("verify", []):
        st.code(command)

    pack = st.session_state.get("readme_checklist_pack")
    if pack:
        st.caption(f"Markdown: {pack['markdown_path']}")
        st.caption(f"JSON: {pack['json_path']}")
        st.download_button(
            "Download README Checklist",
            data=pack["markdown"],
            file_name=f"{pack['checklist_id']}.md",
            mime="text/markdown",
        )
        st.markdown(pack["markdown"])
        with st.expander("README Checklist JSON"):
            st.json(pack["pack"])

with tabs[28]:
    left, right = st.columns(2)
    if left.button("Refresh Dashboard Smoke", type="primary", use_container_width=True):
        st.session_state["dashboard_smoke"] = api("GET", "/ui/dashboard-smoke")
    if right.button("Export UI Verification Pack", use_container_width=True):
        pack = api("POST", "/ui/verification-pack")
        st.session_state["ui_verification_pack"] = pack
        st.session_state["dashboard_smoke"] = pack["pack"]["dashboard_smoke"]
        st.success(f"UI Verification exported: {pack['markdown_path']}")

    smoke = st.session_state.get("dashboard_smoke") or api("GET", "/ui/dashboard-smoke")
    st.session_state["dashboard_smoke"] = smoke
    summary = smoke["summary"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Dashboard smoke", smoke["status"].upper())
    c2.metric("Checks", summary["total_checks"])
    c3.metric("Failed", summary["failed_checks"])
    c4.metric("Views", summary["view_count"])

    st.subheader("Expected Views")
    st.dataframe(
        [
            {
                "view": item["label"],
                "present": item["present"],
                "position": item["position"],
            }
            for item in smoke["expected_views"]
        ],
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("Endpoint References")
    st.dataframe(
        [
            {
                "endpoint": item["endpoint"],
                "dashboard_reference": item["dashboard_reference_present"],
                "api_route": item["route_present"],
                "purpose": item["purpose"],
            }
            for item in smoke["endpoint_references"]
        ],
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("Generated Artifact Tabs")
    st.dataframe(
        [
            {
                "tab": item["tab_label"],
                "producer": item["producer_endpoint"],
                "artifact": item["artifact_directory"],
                "present": item["tab_present"],
            }
            for item in smoke["generated_artifact_tabs"]
        ],
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("Local Run Commands")
    commands = smoke["local_run_commands"]
    st.code(commands["api"])
    st.code(commands["dashboard"])
    st.code(commands["dashboard_smoke"])

    pack = st.session_state.get("ui_verification_pack")
    if pack:
        st.caption(f"Markdown: {pack['markdown_path']}")
        st.caption(f"JSON: {pack['json_path']}")
        st.download_button(
            "Download UI Verification Pack",
            data=pack["markdown"],
            file_name=f"{pack['pack_id']}.md",
            mime="text/markdown",
        )
        st.markdown(pack["markdown"])
        with st.expander("UI Verification JSON"):
            st.json(pack["pack"])

with tabs[29]:
    left, right = st.columns(2)
    if left.button("Refresh Final Audit", type="primary", use_container_width=True):
        st.session_state["final_audit"] = api("GET", "/handoff/final-audit")
    if right.button("Export Final Handoff Pack", use_container_width=True):
        pack = api("POST", "/handoff/final-pack")
        st.session_state["final_handoff_pack"] = pack
        st.session_state["final_audit"] = pack["pack"]["final_audit"]
        st.success(f"Final Handoff exported: {pack['markdown_path']}")

    audit = st.session_state.get("final_audit") or api("GET", "/handoff/final-audit")
    st.session_state["final_audit"] = audit
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Final audit", audit["status"])
    c2.metric("Score", audit["score"])
    c3.metric("Blockers", len(audit["blockers"]))
    c4.metric("Warnings", len(audit["warnings"]))

    st.subheader("README Consistency Checks")
    st.dataframe(
        [
            {
                "check": name,
                "status": item["status"],
                "detail": item["label"],
            }
            for name, item in audit["checks"].items()
        ],
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("Endpoint Inventory Summary")
    st.json(audit["endpoint_inventory_summary"])

    st.subheader("Dashboard Smoke Summary")
    st.json(audit["dashboard_smoke_summary"])

    pack = st.session_state.get("final_handoff_pack")
    if pack:
        st.caption(f"Markdown: {pack['markdown_path']}")
        st.caption(f"JSON: {pack['json_path']}")
        st.download_button(
            "Download Final Handoff Pack",
            data=pack["markdown"],
            file_name=f"{pack['pack_id']}.md",
            mime="text/markdown",
        )
        st.subheader("End-to-End Verification Order")
        st.dataframe(pack["pack"]["end_to_end_verification_order"], use_container_width=True, hide_index=True)
        st.markdown(pack["markdown"])
        with st.expander("Final Handoff JSON"):
            st.json(pack["pack"])

with tabs[30]:
    left, right = st.columns(2)
    if left.button("Refresh Git Readiness", type="primary", use_container_width=True):
        st.session_state["git_readiness"] = api("GET", "/git/readiness")
    if right.button("Export Push Plan", use_container_width=True):
        pack = api("POST", "/git/push-plan")
        st.session_state["git_push_plan"] = pack
        st.session_state["git_readiness"] = pack["pack"]["readiness"]
        st.success(f"Push Plan exported: {pack['markdown_path']}")

    readiness = st.session_state.get("git_readiness") or api("GET", "/git/readiness")
    st.session_state["git_readiness"] = readiness
    summary = readiness["summary"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Readiness", readiness["status"])
    c2.metric("Branch", readiness["current_branch"] or "unknown")
    c3.metric("Changed", summary["changed_count"])
    c4.metric("Ignored", summary["ignored_count"])

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Branch Hygiene")
        st.json(readiness["git"])
    with col2:
        st.subheader("Required Publish Checks")
        st.json(
            {
                "github_actions_workflow": readiness["github_actions_workflow"],
                "readme_final_handoff_mention": readiness["readme_final_handoff_mention"],
                "env_example": readiness["env_example"],
            }
        )

    st.subheader("Changed File Groups")
    st.dataframe(
        [
            {
                "group": group,
                "count": len(paths),
                "paths": ", ".join(paths[:8]),
            }
            for group, paths in readiness["changed_file_groups"].items()
        ],
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("Generated Artifact Directories")
    st.dataframe(
        [
            {
                "directory": item["directory"],
                "exists": item["exists"],
                "ignored": item["ignored"],
                "file_count": item["file_count"],
            }
            for item in readiness["generated_artifact_directories"]
        ],
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("Suspicious Large / Generated Files")
    st.dataframe(
        [
            {
                "path": item["path"],
                "state": item["state"],
                "size_bytes": item["size_bytes"],
                "reasons": ", ".join(item["reasons"]),
            }
            for item in readiness["suspicious_large_or_generated_files"]
        ],
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("Recommended Commit Groups")
    st.dataframe(
        [
            {
                "group": item["group"],
                "message": item["suggested_commit_message"],
                "path_count": len(item["paths"]),
                "review_note": item["review_note"],
            }
            for item in readiness["recommended_commit_groups"]
        ],
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("Dirty Worktree Guidance")
    for item in readiness["dirty_worktree_guidance"]:
        st.markdown(f"- {item}")

    st.subheader("Verification Commands")
    for command in readiness["verification_commands"]:
        st.code(command)

    pack = st.session_state.get("git_push_plan")
    if pack:
        st.caption(f"Markdown: {pack['markdown_path']}")
        st.caption(f"JSON: {pack['json_path']}")
        st.download_button(
            "Download Push Plan",
            data=pack["markdown"],
            file_name=f"{pack['pack_id']}.md",
            mime="text/markdown",
        )
        st.markdown(pack["markdown"])
        with st.expander("Push Plan JSON"):
            st.json(pack["pack"])

with tabs[31]:
    left, right = st.columns(2)
    if left.button("Refresh Contract Audit", type="primary", use_container_width=True):
        st.session_state["api_contract_audit"] = api("GET", "/api/contract-audit")
    if right.button("Export Reviewer Collection", use_container_width=True):
        collection = api("POST", "/api/reviewer-collection")
        st.session_state["api_reviewer_collection"] = collection
        st.session_state["api_contract_audit"] = collection["collection"]["contract_audit"]
        st.success(f"Reviewer Collection exported: {collection['markdown_path']}")

    audit = st.session_state.get("api_contract_audit") or api("GET", "/api/contract-audit")
    st.session_state["api_contract_audit"] = audit
    summary = audit["summary"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Contract", audit["status"])
    c2.metric("OpenAPI routes", summary["openapi_route_count"])
    c3.metric("Protected", summary["auth_protected_endpoint_count"])
    c4.metric("Docs warnings", summary["missing_docs_warning_count"])

    st.subheader("OpenAPI")
    st.json(audit["openapi"])

    st.subheader("Docs / API Coverage")
    st.dataframe(
        audit["docs_api_coverage"]["important_endpoint_coverage"],
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("Dashboard Smoke Alignment")
    st.json(audit["dashboard_smoke_alignment"])

    st.subheader("Generated Artifact Endpoint Coverage")
    st.dataframe(
        audit["generated_artifact_endpoint_coverage"],
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("Demo Flow Endpoint Coverage")
    st.dataframe(
        audit["demo_flow_endpoint_coverage"]["endpoints"],
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("Endpoint Inventory")
    st.dataframe(audit["endpoint_inventory"], use_container_width=True, hide_index=True)

    st.subheader("Verification Commands")
    for command in audit["verification_commands"]:
        st.code(command)

    st.subheader("Local-Only Limitations")
    for limitation in audit["local_only_limitations"]:
        st.markdown(f"- {limitation}")

    collection = st.session_state.get("api_reviewer_collection")
    if collection:
        st.caption(f"Markdown: {collection['markdown_path']}")
        st.caption(f"JSON: {collection['json_path']}")
        st.download_button(
            "Download Reviewer Collection",
            data=collection["markdown"],
            file_name=f"{collection['collection_id']}.md",
            mime="text/markdown",
        )
        st.markdown(collection["markdown"])
        with st.expander("Reviewer Collection JSON"):
            st.json(collection["collection"])

with tabs[32]:
    left, right = st.columns(2)
    if left.button("Refresh Runtime Readiness", type="primary", use_container_width=True):
        st.session_state["runtime_demo_readiness"] = api("GET", "/runtime/demo-readiness")
    if right.button("Export Runtime Demo Pack", use_container_width=True):
        pack = api("POST", "/runtime/demo-pack")
        st.session_state["runtime_demo_pack"] = pack
        st.session_state["runtime_demo_readiness"] = pack["pack"]["readiness"]
        st.success(f"Runtime Demo Pack exported: {pack['markdown_path']}")

    readiness = st.session_state.get("runtime_demo_readiness") or api("GET", "/runtime/demo-readiness")
    st.session_state["runtime_demo_readiness"] = readiness
    summary = readiness["summary"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Runtime", readiness["status"])
    c2.metric("Checks", summary["total_checks"])
    c3.metric("Warnings", summary["warning_checks"])
    c4.metric("Failed", summary["failed_checks"])

    st.subheader("Start Commands")
    commands = readiness["run_commands"]
    for command in commands["start"]:
        st.code(command)
    st.code(commands["runtime_check"])
    st.code(commands["demo_run"])

    st.subheader("Expected Ports")
    st.dataframe(readiness["expected_ports"], use_container_width=True, hide_index=True)

    st.subheader("Dependency Checks")
    st.dataframe(
        [
            {
                "dependency": item["name"],
                "status": item["status"],
                "declared": item["source_declared"],
                "importable": item["import_available"],
                "note": item["note"],
            }
            for item in readiness["dependency_checks"]
        ],
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("Read-Only Port Checks")
    st.dataframe(
        [
            {
                "service": item["name"],
                "port": item["port"],
                "status": item["status"],
                "listening": item["listening"],
                "note": item["note"],
            }
            for item in readiness["process_port_checks"]["socket_connect_checks"]
        ],
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("Health URLs")
    for url in readiness["health_urls"]:
        st.code(url)

    st.subheader("Known Limitations")
    for limitation in readiness["known_limitations"]:
        st.markdown(f"- {limitation}")

    pack = st.session_state.get("runtime_demo_pack")
    if pack:
        st.caption(f"Markdown: {pack['markdown_path']}")
        st.caption(f"JSON: {pack['json_path']}")
        st.download_button(
            "Download Runtime Demo Pack",
            data=pack["markdown"],
            file_name=f"{pack['pack_id']}.md",
            mime="text/markdown",
        )
        st.markdown(pack["markdown"])
        with st.expander("Runtime Demo Pack JSON"):
            st.json(pack["pack"])

with tabs[33]:
    left, right = st.columns(2)
    if left.button("Refresh Scenario Catalog", type="primary", use_container_width=True):
        st.session_state["scenario_catalog"] = api("GET", "/scenarios/catalog")
    if right.button("Export Scenario Eval Pack", use_container_width=True):
        pack = api("POST", "/scenarios/eval-pack")
        st.session_state["scenario_eval_pack"] = pack
        st.session_state["scenario_catalog"] = {
            "coverage_summary": pack["pack"]["coverage_summary"],
            "scenario_count": pack["pack"]["scenario_count"],
            "scenarios": pack["pack"]["scenario_results"],
        }
        st.success(f"Scenario Eval Pack exported: {pack['markdown_path']}")

    catalog = st.session_state.get("scenario_catalog") or api("GET", "/scenarios/catalog")
    st.session_state["scenario_catalog"] = catalog
    coverage = catalog["coverage_summary"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Scenarios", catalog["scenario_count"])
    c2.metric("Domains", coverage["domain_count"])
    c3.metric("Escalations", coverage["escalation_expected_count"])
    c4.metric("Failure paths", coverage["failure_state_expected_count"])

    st.subheader("Scenario Catalog")
    st.dataframe(
        [
            {
                "scenario_id": item["scenario_id"],
                "domain": item["domain"],
                "customer": item.get("customer") or "",
                "category": item.get("expected_outcomes", item.get("expected", {})).get(
                    "classification_category"
                ),
                "sla": item.get("expected_outcomes", item.get("expected", {})).get("sla_level"),
                "approval": item.get("expected_outcomes", item.get("expected", {})).get(
                    "approval_pause"
                ),
                "escalation": item.get("expected_outcomes", item.get("expected", {})).get(
                    "engineering_escalation"
                ),
            }
            for item in catalog["scenarios"]
        ],
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("Scenario Coverage")
    st.json(coverage)

    pack = st.session_state.get("scenario_eval_pack")
    if pack:
        summary = pack["eval_summary"]
        s1, s2, s3, s4 = st.columns(4)
        s1.metric("Eval status", summary["status"].upper())
        s2.metric("Passed", summary["passed_scenario_count"])
        s3.metric("Classification", f"{summary['classification_accuracy']['accuracy_percent']}%")
        s4.metric("SLA routing", f"{summary['sla_routing']['accuracy_percent']}%")
        st.caption(f"Markdown: {pack['markdown_path']}")
        st.caption(f"JSON: {pack['json_path']}")
        st.download_button(
            "Download Scenario Eval Pack",
            data=pack["markdown"],
            file_name=f"{pack['pack_id']}.md",
            mime="text/markdown",
        )
        st.subheader("Scenario Results")
        st.dataframe(pack["pack"]["scenario_results"], use_container_width=True, hide_index=True)
        st.markdown(pack["markdown"])
        with st.expander("Scenario Eval Pack JSON"):
            st.json(pack["pack"])

with tabs[34]:
    left, right = st.columns(2)
    if left.button("Refresh On-Call Summary", type="primary", use_container_width=True):
        st.session_state["on_call_handoff"] = api("GET", "/handoff/on-call-summary")
    if right.button("Export Customer Communications Pack", use_container_width=True):
        pack = api("POST", "/handoff/customer-comms-pack")
        st.session_state["customer_comms_pack"] = pack
        st.session_state["on_call_handoff"] = pack["pack"]["on_call_handoff_summary"]
        st.success(f"Customer Communications exported: {pack['markdown_path']}")

    summary = st.session_state.get("on_call_handoff") or api("GET", "/handoff/on-call-summary")
    st.session_state["on_call_handoff"] = summary
    readiness = summary["customer_communication_readiness"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Severity", summary["severity"].upper())
    c2.metric("Status", summary["status"])
    c3.metric("SLA", summary["sla"]["risk_level"])
    c4.metric("Communication readiness", readiness["status"])

    st.subheader("Owners")
    st.json(summary["owners"])

    st.subheader("Customer Updates")
    st.dataframe(
        [
            {
                "type": item["type"],
                "status": item["status"],
                "subject": item["subject"],
                "requires_approval": item["requires_approval"],
            }
            for item in summary["latest_drafts"]
        ],
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("Approval and Guardrail Status")
    st.json(summary["approval_and_guardrail_status"])

    st.subheader("Risk / Gap Checklist")
    st.dataframe(summary["risk_gap_checklist"], use_container_width=True, hide_index=True)

    st.subheader("Trace Links")
    st.json(summary["trace_links"])

    pack = st.session_state.get("customer_comms_pack")
    if pack:
        st.caption(f"Markdown: {pack['markdown_path']}")
        st.caption(f"JSON: {pack['json_path']}")
        st.download_button(
            "Download Customer Communications Pack",
            data=pack["markdown"],
            file_name=f"{pack['pack_id']}.md",
            mime="text/markdown",
        )
        st.subheader("Scenario Coverage")
        st.dataframe(pack["pack"]["scenario_coverage"]["scenarios"], use_container_width=True, hide_index=True)
        st.markdown(pack["markdown"])
        with st.expander("Customer Communications JSON"):
            st.json(pack["pack"])

with tabs[35]:
    left, right = st.columns(2)
    if left.button("Refresh Postmortem RCA", type="primary", use_container_width=True):
        st.session_state["postmortem_rca"] = api("GET", "/incidents/postmortem-summary")
    if right.button("Export RCA Pack", use_container_width=True):
        pack = api("POST", "/incidents/rca-pack")
        st.session_state["rca_pack"] = pack
        st.session_state["postmortem_rca"] = pack["pack"]["postmortem_summary"]
        st.success(f"RCA Pack exported: {pack['markdown_path']}")
    review_left, review_right = st.columns(2)
    if review_left.button("Refresh Postmortem Review Board", type="secondary", use_container_width=True):
        st.session_state["postmortem_review_board"] = api("GET", "/incidents/postmortem-review-board")
    if review_right.button("Export Postmortem Review Pack", use_container_width=True):
        pack = api("POST", "/incidents/postmortem-review-pack")
        st.session_state["postmortem_review_pack"] = pack
        st.session_state["postmortem_review_board"] = pack["pack"]["review_board"]
        st.success(f"Postmortem Review Pack exported: {pack['markdown_path']}")

    summary = st.session_state.get("postmortem_rca") or api("GET", "/incidents/postmortem-summary")
    st.session_state["postmortem_rca"] = summary
    readiness = summary["readiness_summary"]
    root = summary["root_cause_category"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Severity", summary["severity"].upper())
    c2.metric("RCA readiness", readiness["status"])
    c3.metric("Root cause", root["category"])
    c4.metric("Open actions", readiness["open_corrective_action_count"])

    st.subheader("Incident Summary")
    st.json(summary["incident_summary"])

    st.subheader("Root Cause")
    st.json(root)

    st.subheader("Corrective Action Tracking")
    st.dataframe(summary["corrective_actions"], use_container_width=True, hide_index=True)

    st.subheader("Customer Follow-up State")
    st.json(summary["customer_follow_up_state"])

    st.subheader("Trace Links")
    st.json(summary["trace_links"])

    st.subheader("Scenario Coverage")
    st.dataframe(summary["scenario_coverage"]["scenarios"], use_container_width=True, hide_index=True)

    st.subheader("Proof Commands")
    for command in summary["local_proof_commands"]:
        st.code(command)

    st.subheader("Postmortem Review Board")
    review_board = st.session_state.get("postmortem_review_board") or api(
        "GET",
        "/incidents/postmortem-review-board",
    )
    st.session_state["postmortem_review_board"] = review_board
    r1, r2, r3, r4 = st.columns(4)
    r1.metric("Review status", review_board["review_status"])
    r2.metric("Closure score", review_board["closure_score"])
    r3.metric("Process mode", review_board["process_mode"]["mode_id"])
    r4.metric("Signoffs", len(review_board["role_signoffs"]))
    st.dataframe(review_board["action_board"], use_container_width=True, hide_index=True)
    st.subheader("Closure Gates")
    st.dataframe(review_board["closure_gates"], use_container_width=True, hide_index=True)
    st.subheader("Role Signoffs")
    st.dataframe(review_board["role_signoffs"], use_container_width=True, hide_index=True)
    st.subheader("Artifact Handoffs")
    st.dataframe(review_board["artifact_handoffs"], use_container_width=True, hide_index=True)

    pack = st.session_state.get("rca_pack")
    if pack:
        st.caption(f"Markdown: {pack['markdown_path']}")
        st.caption(f"JSON: {pack['json_path']}")
        st.download_button(
            "Download RCA Pack",
            data=pack["markdown"],
            file_name=f"{pack['pack_id']}.md",
            mime="text/markdown",
        )
        st.markdown(pack["markdown"])
        with st.expander("RCA Pack JSON"):
            st.json(pack["pack"])

    review_pack = st.session_state.get("postmortem_review_pack")
    if review_pack:
        st.caption(f"Review Markdown: {review_pack['markdown_path']}")
        st.caption(f"Review JSON: {review_pack['json_path']}")
        st.download_button(
            "Download Postmortem Review Pack",
            data=review_pack["markdown"],
            file_name=f"{review_pack['pack_id']}.md",
            mime="text/markdown",
        )
        st.markdown(review_pack["markdown"])
        with st.expander("Postmortem Review Pack JSON"):
            st.json(review_pack["pack"])

with tabs[36]:
    run_id = st.text_input("Finance run ID", value=st.session_state.get("run_id", ""))
    payload = {"run_id": run_id} if run_id else None
    left, right = st.columns(2)
    if left.button("Refresh Finance Impact", type="primary", use_container_width=True):
        summary = api("POST", "/finance/impact-summary", payload)
        st.session_state["finance_impact_summary"] = summary
        st.session_state["run_id"] = summary["run_id"]
    if right.button("Export Finance Impact Pack", use_container_width=True):
        pack = api("POST", "/finance/impact-pack", payload)
        st.session_state["finance_impact_pack"] = pack
        st.session_state["finance_impact_summary"] = pack["pack"]["impact_summary"]
        st.session_state["run_id"] = pack["run_id"]
        st.success(f"Finance Impact Pack exported: {pack['markdown_path']}")

    summary = st.session_state.get("finance_impact_summary") or api("POST", "/finance/impact-summary", payload)
    st.session_state["finance_impact_summary"] = summary
    metrics = summary["dashboard_metrics"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Exposure", f"${metrics['estimated_financial_exposure_usd']:,.0f}")
    c2.metric("Direct cost", f"${metrics['direct_cost_usd']:,.0f}")
    c3.metric("ARR at risk", f"${metrics['arr_at_risk_usd']:,.0f}")
    c4.metric("Finance status", metrics["readiness_status"])

    c5, c6 = st.columns(2)
    c5.metric("Support minutes", metrics["support_minutes"])
    c6.metric("Engineering hours", metrics["engineering_hours"])

    st.subheader("Executive Summary")
    st.write(summary["executive_summary"])

    st.subheader("Support Cost Components")
    st.dataframe(summary["support_cost"]["components"], use_container_width=True, hide_index=True)

    st.subheader("Engineering Effort Components")
    st.dataframe(summary["engineering_effort"]["components"], use_container_width=True, hide_index=True)

    st.subheader("ARR Risk Drivers")
    st.dataframe(summary["customer_arr_at_risk"]["drivers"], use_container_width=True, hide_index=True)

    st.subheader("Recommended Actions")
    st.dataframe(summary["recommended_actions"], use_container_width=True, hide_index=True)

    st.subheader("Assumptions and Limitations")
    st.json({"assumptions": summary["assumptions"], "limitations": summary["limitations"]})

    pack = st.session_state.get("finance_impact_pack")
    if pack:
        st.caption(f"Markdown: {pack['markdown_path']}")
        st.caption(f"JSON: {pack['json_path']}")
        st.download_button(
            "Download Finance Impact Pack",
            data=pack["markdown"],
            file_name=f"{pack['pack_id']}.md",
            mime="text/markdown",
        )
        st.subheader("Executive Decision Table")
        st.dataframe(pack["pack"]["executive_decision_table"], use_container_width=True, hide_index=True)
        st.markdown(pack["markdown"])
        with st.expander("Finance Impact JSON"):
            st.json(pack["pack"])

with tabs[37]:
    left, right = st.columns(2)
    if left.button("Refresh Runbook Coverage", type="primary", use_container_width=True):
        st.session_state["runbook_coverage_audit"] = api("GET", "/runbooks/coverage-audit")
    if right.button("Export Runbook Gap Pack", use_container_width=True):
        pack = api("POST", "/runbooks/gap-pack")
        st.session_state["runbook_gap_pack"] = pack
        st.session_state["runbook_coverage_audit"] = {
            "coverage_score": pack["coverage_score"],
            "readiness_status": pack["readiness_status"],
            "coverage_summary": pack["pack"]["coverage_summary"],
            "ticket_mappings": pack["pack"]["ticket_mappings"],
            "runbook_gaps": pack["pack"]["runbook_gaps"],
            "owner_assignments": pack["pack"]["owner_assignments"],
            "selected_process_mode": pack["pack"]["selected_process_mode"],
            "role_playbooks": pack["pack"]["role_playbooks"],
            "delegated_tasks": pack["pack"]["delegated_tasks"],
            "review_gates": pack["pack"]["review_gates"],
            "artifact_handoffs": pack["pack"]["artifact_handoffs"],
            "run_transparency": pack["pack"]["run_transparency"],
            "repo_radar_patterns": pack["pack"]["repo_radar_patterns"],
            "endpoint_list": pack["pack"]["endpoint_list"],
        }
        st.success(f"Runbook Gap Pack exported: {pack['markdown_path']}")

    audit = st.session_state.get("runbook_coverage_audit") or api("GET", "/runbooks/coverage-audit")
    st.session_state["runbook_coverage_audit"] = audit
    summary = audit["coverage_summary"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Coverage score", audit["coverage_score"])
    c2.metric("Status", audit["readiness_status"])
    c3.metric("Open gaps", summary["open_runbook_gap_count"])
    c4.metric("Tickets mapped", summary["ticket_count"])

    st.subheader("Ticket Coverage Map")
    st.dataframe(
        [
            {
                "ticket": item["ticket_id"],
                "type": item["ticket_type"],
                "status": item["coverage_status"],
                "runbook": item["runbook_coverage"]["top_runbook_id"],
                "confidence": item["runbook_coverage"]["confidence"],
                "kb_articles": ", ".join(item["kb_coverage"]["article_ids"]),
                "owner": item["owner"],
            }
            for item in audit["ticket_mappings"]
        ],
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("Runbook Gaps")
    st.dataframe(audit["runbook_gaps"], use_container_width=True, hide_index=True)

    st.subheader("Owner Assignments")
    st.dataframe(audit["owner_assignments"], use_container_width=True, hide_index=True)

    st.subheader("Process Mode")
    process_mode = audit["selected_process_mode"]
    p1, p2, p3, p4 = st.columns(4)
    p1.metric("Mode", process_mode["mode_id"])
    p2.metric("Cadence", process_mode["review_cadence"])
    p3.metric("Owner tasks", process_mode["max_parallel_owner_tasks"])
    p4.metric("Executive review", str(process_mode["requires_executive_review"]))

    st.subheader("Role Playbooks")
    st.dataframe(audit["role_playbooks"], use_container_width=True, hide_index=True)

    st.subheader("Delegated Coverage Tasks")
    st.dataframe(
        [
            {
                "task": task["task_id"],
                "owner": task["owner_role"],
                "priority": task["priority"],
                "status": task["status"],
                "ticket_type": task["ticket_type"],
                "evidence": ", ".join(task["evidence_refs"]),
            }
            for task in audit["delegated_tasks"]
        ],
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("Review Gates")
    st.dataframe(audit["review_gates"], use_container_width=True, hide_index=True)

    st.subheader("Artifact Handoffs")
    st.dataframe(audit["artifact_handoffs"], use_container_width=True, hide_index=True)

    st.subheader("Run Transparency")
    st.json(audit["run_transparency"])

    st.subheader("Endpoint Coverage")
    st.dataframe(
        [{"endpoint": endpoint} for endpoint in audit["endpoint_list"]],
        use_container_width=True,
        hide_index=True,
    )

    pack = st.session_state.get("runbook_gap_pack")
    if pack:
        st.caption(f"Markdown: {pack['markdown_path']}")
        st.caption(f"JSON: {pack['json_path']}")
        st.download_button(
            "Download Runbook Gap Pack",
            data=pack["markdown"],
            file_name=f"{pack['pack_id']}.md",
            mime="text/markdown",
        )
        st.subheader("Remediation Tasks")
        st.dataframe(pack["pack"]["remediation_tasks"], use_container_width=True, hide_index=True)
        st.markdown(pack["markdown"])
        with st.expander("Runbook Gap Pack JSON"):
            st.json(pack["pack"])

with tabs[38]:
    left, right = st.columns(2)
    if left.button("Refresh Evidence Retention", type="primary", use_container_width=True):
        st.session_state["evidence_retention_audit"] = api("GET", "/evidence/retention-audit")
    if right.button("Export Evidence Retention Pack", use_container_width=True):
        pack = api("POST", "/evidence/retention-pack")
        st.session_state["evidence_retention_pack"] = pack
        st.session_state["evidence_retention_audit"] = pack["pack"]["retention_audit"]
        st.success(f"Evidence Retention Pack exported: {pack['markdown_path']}")

    audit = st.session_state.get("evidence_retention_audit") or api("GET", "/evidence/retention-audit")
    st.session_state["evidence_retention_audit"] = audit
    counts = audit["state_counts"]
    artifacts = audit["artifact_summary"]
    hashes = audit["hash_manifest"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Evidence score", audit["readiness_score"])
    c2.metric("Status", audit["status"])
    c3.metric("Runs", counts["run_count"])
    c4.metric("Hashed files", hashes["file_count"])

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Trace events", counts["trace_event_count"])
    c6.metric("Approvals", counts["approval_count"])
    c7.metric("Outbox events", counts["outbox_event_count"])
    c8.metric("Audit events", counts["audit_event_count"])

    st.subheader("Recent Run Evidence")
    st.dataframe(audit["run_evidence_map"], use_container_width=True, hide_index=True)

    st.subheader("Artifact Custody")
    st.dataframe(artifacts["directories"], use_container_width=True, hide_index=True)

    st.subheader("Hash Manifest")
    st.dataframe(hashes["files"], use_container_width=True, hide_index=True)

    st.subheader("Findings")
    st.dataframe(audit["findings"], use_container_width=True, hide_index=True)

    st.subheader("Recommended Actions")
    st.dataframe(audit["recommended_actions"], use_container_width=True, hide_index=True)

    st.subheader("Controls and Limitations")
    st.json({"controls": audit["retention_controls"], "limitations": audit["limitations"]})

    pack = st.session_state.get("evidence_retention_pack")
    if pack:
        st.caption(f"Markdown: {pack['markdown_path']}")
        st.caption(f"JSON: {pack['json_path']}")
        st.download_button(
            "Download Evidence Retention Pack",
            data=pack["markdown"],
            file_name=f"{pack['pack_id']}.md",
            mime="text/markdown",
        )
        st.subheader("Custody Review Table")
        st.dataframe(pack["pack"]["custody_review_table"], use_container_width=True, hide_index=True)
        st.markdown(pack["markdown"])
        with st.expander("Evidence Retention JSON"):
            st.json(pack["pack"])

with tabs[39]:
    left, right = st.columns(2)
    if left.button("Refresh Capacity Forecast", type="primary", use_container_width=True):
        st.session_state["capacity_forecast"] = api("GET", "/capacity/forecast")
    if right.button("Export Staffing Plan", use_container_width=True):
        plan = api("POST", "/capacity/staffing-plan")
        st.session_state["capacity_plan"] = plan
        st.session_state["capacity_forecast"] = {
            "capacity_score": plan["capacity_score"],
            "readiness_status": plan["readiness_status"],
            "demand_summary": plan["plan"]["demand_summary"],
            "queue_forecast": plan["plan"]["queue_forecast"],
            "staffing_gaps": plan["plan"]["staffing_gaps"],
            "owner_assignments": plan["plan"]["owner_assignments"],
            "endpoint_list": plan["plan"]["endpoint_list"],
        }
        st.success(f"Capacity Staffing Plan exported: {plan['markdown_path']}")

    forecast = st.session_state.get("capacity_forecast") or api("GET", "/capacity/forecast")
    st.session_state["capacity_forecast"] = forecast
    summary = forecast["demand_summary"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Capacity score", forecast["capacity_score"])
    c2.metric("Status", forecast["readiness_status"])
    c3.metric("Projected tickets", summary["projected_weekly_tickets"])
    c4.metric("Gap queues", summary["capacity_gap_queue_count"])

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Effort hours", summary["projected_effort_hours"])
    c6.metric("Required FTE", summary["required_fte"])
    c7.metric("Available FTE", summary["available_fte"])
    c8.metric("Gap FTE", summary["capacity_gap_fte"])

    st.subheader("Queue Forecast")
    st.dataframe(forecast["queue_forecast"], use_container_width=True, hide_index=True)

    st.subheader("Staffing Gaps")
    st.dataframe(forecast["staffing_gaps"], use_container_width=True, hide_index=True)

    st.subheader("Owner Assignments")
    st.dataframe(forecast["owner_assignments"], use_container_width=True, hide_index=True)

    st.subheader("Endpoint Coverage")
    st.dataframe(
        [{"endpoint": endpoint} for endpoint in forecast["endpoint_list"]],
        use_container_width=True,
        hide_index=True,
    )

    plan = st.session_state.get("capacity_plan")
    if plan:
        st.caption(f"Markdown: {plan['markdown_path']}")
        st.caption(f"JSON: {plan['json_path']}")
        st.download_button(
            "Download Capacity Staffing Plan",
            data=plan["markdown"],
            file_name=f"{plan['plan_id']}.md",
            mime="text/markdown",
        )
        st.subheader("Staffing Actions")
        st.dataframe(plan["plan"]["staffing_actions"], use_container_width=True, hide_index=True)
        st.markdown(plan["markdown"])
        with st.expander("Capacity Staffing Plan JSON"):
            st.json(plan["plan"])

with tabs[40]:
    left, right = st.columns(2)
    if left.button("Refresh Data Residency Audit", type="primary", use_container_width=True):
        st.session_state["data_residency_audit"] = api("GET", "/compliance/data-residency-audit")
    if right.button("Export Data Residency Pack", use_container_width=True):
        pack = api("POST", "/compliance/data-residency-pack")
        st.session_state["data_residency_pack"] = pack
        st.session_state["data_residency_audit"] = pack["pack"]["audit"]
        st.success(f"Data Residency Pack exported: {pack['markdown_path']}")

    audit = st.session_state.get("data_residency_audit") or api("GET", "/compliance/data-residency-audit")
    st.session_state["data_residency_audit"] = audit
    summary = audit["summary"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Residency score", audit["residency_score"])
    c2.metric("Status", audit["readiness_status"])
    c3.metric("Critical", summary["critical_count"])
    c4.metric("High", summary["high_count"])

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("PII tickets", summary["pii_signal_ticket_count"])
    c6.metric("Restricted region", summary["restricted_region_ticket_count"])
    c7.metric("Regulated segment", summary["regulated_segment_ticket_count"])
    c8.metric("Outbox exposure", summary["outbox_exposure_ticket_count"])

    st.subheader("Account Exposure Queue")
    st.dataframe(audit["account_exposure"], use_container_width=True, hide_index=True)

    st.subheader("Data Flow Map")
    st.dataframe(audit["data_flow_map"], use_container_width=True, hide_index=True)

    st.subheader("Control Checks")
    st.dataframe(audit["control_checks"], use_container_width=True, hide_index=True)

    st.subheader("Owner Actions")
    st.dataframe(audit["owner_actions"], use_container_width=True, hide_index=True)

    st.subheader("Policy Rules and Limitations")
    st.json({"policy_rules": audit["policy_rules"], "limitations": audit["limitations"]})

    pack = st.session_state.get("data_residency_pack")
    if pack:
        st.caption(f"Markdown: {pack['markdown_path']}")
        st.caption(f"JSON: {pack['json_path']}")
        st.download_button(
            "Download Data Residency Pack",
            data=pack["markdown"],
            file_name=f"{pack['pack_id']}.md",
            mime="text/markdown",
        )
        st.subheader("Review Queue")
        st.dataframe(pack["pack"]["review_queue"], use_container_width=True, hide_index=True)
        st.markdown(pack["markdown"])
        with st.expander("Data Residency Pack JSON"):
            st.json(pack["pack"])

with tabs[41]:
    left, right = st.columns(2)
    if left.button("Refresh Access Matrix", type="primary", use_container_width=True):
        st.session_state["access_matrix"] = api("GET", "/security/access-matrix")
    if right.button("Export Access Review Pack", use_container_width=True):
        pack = api("POST", "/security/access-review-pack")
        st.session_state["access_review_pack"] = pack
        st.session_state["access_matrix"] = pack["pack"]["access_matrix"]
        st.success(f"Access Review Pack exported: {pack['markdown_path']}")

    matrix = st.session_state.get("access_matrix") or api("GET", "/security/access-matrix")
    st.session_state["access_matrix"] = matrix
    summary = matrix["summary"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Least-privilege score", summary["least_privilege_score"])
    c2.metric("Status", matrix["status"])
    c3.metric("Protected", summary["protected_endpoint_count"])
    c4.metric("Findings", summary["critical_finding_count"] + summary["high_finding_count"])

    st.subheader("Auth Model")
    st.json(matrix["auth_model"])

    st.subheader("Roles")
    st.dataframe(matrix["roles"], use_container_width=True, hide_index=True)

    st.subheader("Domain Ownership")
    st.dataframe(matrix["domain_ownership"], use_container_width=True, hide_index=True)

    st.subheader("Endpoint Access Matrix")
    st.dataframe(
        [
            {
                "endpoint": item["endpoint"],
                "sensitivity": item["sensitivity"],
                "owner_role": item["owner_role"],
                "allowed_roles": ", ".join(item["allowed_roles"]),
                "production_scope": item["production_scope"],
                "approval": item["requires_human_approval"],
            }
            for item in matrix["access_matrix"]
        ],
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("Findings")
    st.json(matrix["findings"])

    st.subheader("Limitations")
    for limitation in matrix["limitations"]:
        st.markdown(f"- {limitation}")

    pack = st.session_state.get("access_review_pack")
    if pack:
        st.caption(f"Markdown: {pack['markdown_path']}")
        st.caption(f"JSON: {pack['json_path']}")
        st.download_button(
            "Download Access Review Pack",
            data=pack["markdown"],
            file_name=f"{pack['pack_id']}.md",
            mime="text/markdown",
        )
        st.subheader("Production Authz Backlog")
        st.dataframe(pack["pack"]["production_authz_backlog"], use_container_width=True, hide_index=True)
        st.markdown(pack["markdown"])
        with st.expander("Access Review Pack JSON"):
            st.json(pack["pack"])

with tabs[42]:
    left, right = st.columns(2)
    if left.button("Refresh Risk Register", type="primary", use_container_width=True):
        st.session_state["risk_register"] = api("GET", "/risk/register")
    if right.button("Export Risk Register Pack", use_container_width=True):
        pack = api("POST", "/risk/register-pack")
        st.session_state["risk_register_pack"] = pack
        st.session_state["risk_register"] = pack["pack"]["risk_register"]
        st.success(f"Risk Register Pack exported: {pack['markdown_path']}")

    register = st.session_state.get("risk_register") or api("GET", "/risk/register")
    st.session_state["risk_register"] = register
    summary = register["summary"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Risk score", register["risk_score"])
    c2.metric("Status", register["readiness_status"])
    c3.metric("Open risks", summary["open_risk_count"])
    c4.metric("Critical / High", f"{summary['critical_count']} / {summary['high_count']}")

    st.subheader("Risk Register")
    st.dataframe(register["risk_register"], use_container_width=True, hide_index=True)

    st.subheader("Owner Action Plan")
    st.dataframe(register["owner_action_plan"], use_container_width=True, hide_index=True)

    st.subheader("Control Signal Summary")
    st.dataframe(register["control_signal_summary"], use_container_width=True, hide_index=True)

    st.subheader("Endpoint Coverage")
    st.dataframe(
        [{"endpoint": endpoint} for endpoint in register["endpoint_list"]],
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("Limitations")
    for limitation in register["limitations"]:
        st.markdown(f"- {limitation}")

    pack = st.session_state.get("risk_register_pack")
    if pack:
        st.caption(f"Markdown: {pack['markdown_path']}")
        st.caption(f"JSON: {pack['json_path']}")
        st.download_button(
            "Download Risk Register Pack",
            data=pack["markdown"],
            file_name=f"{pack['pack_id']}.md",
            mime="text/markdown",
        )
        st.subheader("Acceptance Criteria")
        st.markdown("\n".join(f"- {item}" for item in pack["pack"]["risk_acceptance_criteria"]))
        st.markdown(pack["markdown"])
        with st.expander("Risk Register Pack JSON"):
            st.json(pack["pack"])

with tabs[43]:
    left, mid_left, mid_right, right = st.columns(4)
    if left.button("Refresh Provider Readiness", type="primary", use_container_width=True):
        st.session_state["provider_readiness"] = api("GET", "/providers/readiness")
    if mid_left.button("Export Provider Readiness Pack", use_container_width=True):
        pack = api("POST", "/providers/readiness-pack")
        st.session_state["provider_readiness_pack"] = pack
        st.session_state["provider_readiness"] = pack["pack"]["provider_readiness"]
        st.success(f"Provider Readiness Pack exported: {pack['markdown_path']}")
    if mid_right.button("Run Failover Drill", use_container_width=True):
        st.session_state["provider_failover_drill"] = api("GET", "/providers/failover-drill")
    if right.button("Export Failover Pack", use_container_width=True):
        pack = api("POST", "/providers/failover-pack")
        st.session_state["provider_failover_pack"] = pack
        st.session_state["provider_failover_drill"] = pack["pack"]["failover_drill"]
        st.success(f"Provider Failover Pack exported: {pack['markdown_path']}")

    readiness = st.session_state.get("provider_readiness") or api("GET", "/providers/readiness")
    st.session_state["provider_readiness"] = readiness
    summary = readiness["summary"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Provider score", readiness["provider_score"])
    c2.metric("Status", readiness["readiness_status"])
    c3.metric("Provider", readiness["configured_provider"])
    c4.metric("Failures / Warnings", f"{summary['fail_count']} / {summary['warn_count']}")

    st.subheader("Provider Matrix")
    st.dataframe(readiness["provider_matrix"], use_container_width=True, hide_index=True)

    st.subheader("Provider Checks")
    st.dataframe(readiness["provider_checks"], use_container_width=True, hide_index=True)

    st.subheader("Environment Presence")
    st.dataframe(readiness["env_presence"]["variables"], use_container_width=True, hide_index=True)

    st.subheader("Fallback Policy")
    st.json(readiness["fallback_policy"])

    st.subheader("Production Backlog")
    st.dataframe(readiness["production_backlog"], use_container_width=True, hide_index=True)

    failover = st.session_state.get("provider_failover_drill") or api("GET", "/providers/failover-drill")
    st.session_state["provider_failover_drill"] = failover
    failover_summary = failover["summary"]
    st.subheader("Provider Failover Drill")
    f1, f2, f3, f4 = st.columns(4)
    f1.metric("Failover score", failover["failover_score"])
    f2.metric("Drill status", failover["readiness_status"])
    f3.metric("Fallbacks used", failover_summary["fallback_used_count"])
    f4.metric("External calls", failover_summary["external_call_count"])
    st.dataframe(
        [
            {
                "scenario": row["scenario_id"],
                "configured": row["configured_provider"],
                "status": row["status"],
                "provider": row["provider"],
                "fallback": row["fallback_used"],
                "fail_closed": row["fail_closed"],
                "external_call": row["external_call"],
            }
            for row in failover["provider_scenarios"]
        ],
        use_container_width=True,
        hide_index=True,
    )
    st.subheader("Failover Controls")
    st.dataframe(failover["control_checks"], use_container_width=True, hide_index=True)

    st.subheader("Limitations")
    for limitation in readiness["limitations"]:
        st.markdown(f"- {limitation}")

    pack = st.session_state.get("provider_readiness_pack")
    if pack:
        st.caption(f"Markdown: {pack['markdown_path']}")
        st.caption(f"JSON: {pack['json_path']}")
        st.download_button(
            "Download Provider Readiness Pack",
            data=pack["markdown"],
            file_name=f"{pack['pack_id']}.md",
            mime="text/markdown",
        )
        st.subheader("Activation Checklist")
        st.dataframe(pack["pack"]["activation_checklist"], use_container_width=True, hide_index=True)
        st.markdown(pack["markdown"])
        with st.expander("Provider Readiness Pack JSON"):
            st.json(pack["pack"])

    failover_pack = st.session_state.get("provider_failover_pack")
    if failover_pack:
        st.caption(f"Failover Markdown: {failover_pack['markdown_path']}")
        st.caption(f"Failover JSON: {failover_pack['json_path']}")
        st.download_button(
            "Download Provider Failover Pack",
            data=failover_pack["markdown"],
            file_name=f"{failover_pack['pack_id']}.md",
            mime="text/markdown",
        )
        st.subheader("Provider Activation Decision Table")
        st.dataframe(
            failover_pack["pack"]["failover_drill"]["activation_decision_table"],
            use_container_width=True,
            hide_index=True,
        )
        st.markdown(failover_pack["markdown"])
        with st.expander("Provider Failover Pack JSON"):
            st.json(failover_pack["pack"])

with tabs[44]:
    left, right = st.columns(2)
    if left.button("Refresh Daily Ops Brief", type="primary", use_container_width=True):
        st.session_state["daily_ops_brief"] = api("GET", "/ops/daily-brief")
    if right.button("Export Daily Ops Brief Pack", use_container_width=True):
        pack = api("POST", "/ops/daily-brief-pack")
        st.session_state["daily_ops_brief_pack"] = pack
        st.session_state["daily_ops_brief"] = pack["pack"]["daily_brief"]
        st.success(f"Daily Ops Brief Pack exported: {pack['markdown_path']}")

    brief = st.session_state.get("daily_ops_brief") or api("GET", "/ops/daily-brief")
    st.session_state["daily_ops_brief"] = brief
    sla = brief["sla_exposure"]
    load = brief["engineer_load"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Daily status", brief["status"])
    c2.metric("High SLA risk", sla["high_sla_risk_count"])
    c3.metric("Blocked approvals", len(brief["blocked_approvals"]))
    c4.metric("Capacity gap FTE", load["capacity_gap_fte"])

    st.subheader("Executive Summary")
    st.write(brief["executive_summary"])

    st.subheader("Recommended Actions")
    for action in brief["recommended_actions"]:
        st.markdown(f"- {action}")

    st.subheader("Blocked Approvals")
    st.dataframe(brief["blocked_approvals"], use_container_width=True, hide_index=True)

    st.subheader("Engineer Load")
    st.dataframe(load["queues"], use_container_width=True, hide_index=True)

    st.subheader("Critical Accounts")
    st.dataframe(brief["critical_accounts"], use_container_width=True, hide_index=True)

    st.subheader("Top Risky Tickets")
    st.dataframe(brief["top_risky_tickets"], use_container_width=True, hide_index=True)

    st.subheader("Control Signals")
    st.dataframe(brief["control_signals"], use_container_width=True, hide_index=True)

    pack = st.session_state.get("daily_ops_brief_pack")
    if pack:
        st.caption(f"Markdown: {pack['markdown_path']}")
        st.caption(f"JSON: {pack['json_path']}")
        st.download_button(
            "Download Daily Ops Brief Pack",
            data=pack["markdown"],
            file_name=f"{pack['brief_id']}.md",
            mime="text/markdown",
        )
        st.subheader("Decision Table")
        st.dataframe(pack["pack"]["decision_table"], use_container_width=True, hide_index=True)
        st.markdown(pack["markdown"])
        with st.expander("Daily Ops Brief Pack JSON"):
            st.json(pack["pack"])

with tabs[45]:
    left, right = st.columns(2)
    if left.button("Refresh Autonomy Governance", type="primary", use_container_width=True):
        st.session_state["autonomy_governance"] = api("GET", "/governance/autonomy-audit")
    if right.button("Export Autonomy Governance Pack", use_container_width=True):
        pack = api("POST", "/governance/autonomy-pack")
        st.session_state["autonomy_governance_pack"] = pack
        st.session_state["autonomy_governance"] = pack["pack"]["autonomy_audit"]
        st.success(f"Autonomy Governance Pack exported: {pack['markdown_path']}")

    audit = st.session_state.get("autonomy_governance") or api("GET", "/governance/autonomy-audit")
    st.session_state["autonomy_governance"] = audit
    summary = audit["summary"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Governance score", audit["governance_score"])
    c2.metric("Status", audit["readiness_status"])
    c3.metric("Runs audited", summary["run_count"])
    c4.metric("Findings", summary["finding_count"])

    st.subheader("Control Checks")
    st.dataframe(audit["control_checks"], use_container_width=True, hide_index=True)

    st.subheader("Run Governance")
    st.dataframe(audit["run_governance"], use_container_width=True, hide_index=True)

    st.subheader("Owner Action Plan")
    st.dataframe(audit["owner_action_plan"], use_container_width=True, hide_index=True)

    st.subheader("Policy Defaults")
    st.json(audit["policy_defaults"])

    st.subheader("Limitations")
    for limitation in audit["limitations"]:
        st.markdown(f"- {limitation}")

    pack = st.session_state.get("autonomy_governance_pack")
    if pack:
        st.caption(f"Markdown: {pack['markdown_path']}")
        st.caption(f"JSON: {pack['json_path']}")
        st.download_button(
            "Download Autonomy Governance Pack",
            data=pack["markdown"],
            file_name=f"{pack['pack_id']}.md",
            mime="text/markdown",
        )
        st.subheader("Decision Table")
        st.dataframe(pack["pack"]["decision_table"], use_container_width=True, hide_index=True)
        st.markdown(pack["markdown"])
        with st.expander("Autonomy Governance Pack JSON"):
            st.json(pack["pack"])

with tabs[46]:
    left, right = st.columns(2)
    if left.button("Refresh Durable Workflow Audit", type="primary", use_container_width=True):
        st.session_state["workflow_durability"] = api("GET", "/workflows/durability-audit")
    if right.button("Export Durable Workflow Pack", use_container_width=True):
        pack = api("POST", "/workflows/durability-pack")
        st.session_state["workflow_durability_pack"] = pack
        st.session_state["workflow_durability"] = pack["pack"]["durability_audit"]
        st.success(f"Durable Workflow Pack exported: {pack['markdown_path']}")

    audit = st.session_state.get("workflow_durability") or api("GET", "/workflows/durability-audit")
    st.session_state["workflow_durability"] = audit
    summary = audit["summary"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Durability score", audit["durability_score"])
    c2.metric("Status", audit["readiness_status"])
    c3.metric("Checkpoints", summary["checkpoint_count"])
    c4.metric("Resume-ready", summary["resume_ready_count"])

    st.subheader("Control Checks")
    st.dataframe(audit["control_checks"], use_container_width=True, hide_index=True)

    st.subheader("Run Recovery")
    st.dataframe(audit["run_recovery"], use_container_width=True, hide_index=True)

    st.subheader("Operator Recovery Queue")
    st.dataframe(audit["operator_recovery_queue"], use_container_width=True, hide_index=True)

    st.subheader("Resume Policy")
    st.json(audit["resume_policy"])

    st.subheader("Limitations")
    for limitation in audit["limitations"]:
        st.markdown(f"- {limitation}")

    pack = st.session_state.get("workflow_durability_pack")
    if pack:
        st.caption(f"Markdown: {pack['markdown_path']}")
        st.caption(f"JSON: {pack['json_path']}")
        st.download_button(
            "Download Durable Workflow Pack",
            data=pack["markdown"],
            file_name=f"{pack['pack_id']}.md",
            mime="text/markdown",
        )
        st.subheader("Recovery Decision Table")
        st.dataframe(pack["pack"]["recovery_decision_table"], use_container_width=True, hide_index=True)
        st.markdown(pack["markdown"])
        with st.expander("Durable Workflow Pack JSON"):
            st.json(pack["pack"])

with tabs[47]:
    run_id = st.text_input("Escalation quality run ID", value=st.session_state.get("run_id", ""))
    quality_path = f"/escalations/quality-audit?run_id={run_id}" if run_id else "/escalations/quality-audit"
    pack_path = f"/escalations/quality-pack?run_id={run_id}" if run_id else "/escalations/quality-pack"
    left, right = st.columns(2)
    if left.button("Refresh Escalation Quality", type="primary", use_container_width=True):
        audit = api("GET", quality_path)
        st.session_state["escalation_quality_audit"] = audit
        st.session_state["run_id"] = audit["run_id"]
    if right.button("Export Escalation Quality Pack", use_container_width=True):
        pack = api("POST", pack_path)
        st.session_state["escalation_quality_pack"] = pack
        st.session_state["escalation_quality_audit"] = pack["pack"]["quality_audit"]
        st.session_state["run_id"] = pack["pack"]["quality_audit"]["run_id"]
        st.success(f"Escalation Quality Pack exported: {pack['markdown_path']}")

    audit = st.session_state.get("escalation_quality_audit") or api("GET", quality_path)
    st.session_state["escalation_quality_audit"] = audit
    gate = audit["quality_gate"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Overall score", audit["overall_score"])
    c2.metric("Status", audit["status"])
    c3.metric("Internal dispatch", str(gate["approved_for_internal_dispatch"]))
    c4.metric("Required", str(audit["escalation_required"]))

    st.subheader("Score Dimensions")
    st.dataframe(
        [
            {
                "dimension": name,
                "score": item["score"],
                "status": item["status"],
                "gaps": "; ".join(item["gaps"]),
            }
            for name, item in audit["score_dimensions"].items()
        ],
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("Engineering Review Crew")
    st.dataframe(audit["role_playbook_handoffs"], use_container_width=True, hide_index=True)

    st.subheader("Reviewer Actions")
    st.dataframe(audit["required_revisions"], use_container_width=True, hide_index=True)

    st.subheader("Escalation Evidence")
    st.json(audit["escalation_evidence"])

    st.subheader("Run Transparency")
    st.json(audit["run_transparency"])

    st.subheader("Artifact Handoffs")
    st.dataframe(audit["artifact_handoffs"], use_container_width=True, hide_index=True)

    st.subheader("Scenario Coverage")
    st.dataframe(audit["scenario_coverage"]["scenarios"], use_container_width=True, hide_index=True)

    pack = st.session_state.get("escalation_quality_pack")
    if pack:
        st.caption(f"Markdown: {pack['markdown_path']}")
        st.caption(f"JSON: {pack['json_path']}")
        st.download_button(
            "Download Escalation Quality Pack",
            data=pack["markdown"],
            file_name=f"{pack['pack_id']}.md",
            mime="text/markdown",
        )
        st.markdown(pack["markdown"])
        with st.expander("Escalation Quality JSON"):
            st.json(pack["pack"])

with tabs[48]:
    run_id = st.text_input("Communication quality run ID", value=st.session_state.get("run_id", ""))
    quality_path = f"/communications/quality-audit?run_id={run_id}" if run_id else "/communications/quality-audit"
    pack_path = f"/communications/quality-pack?run_id={run_id}" if run_id else "/communications/quality-pack"
    left, right = st.columns(2)
    if left.button("Refresh Communication Quality", type="primary", use_container_width=True):
        audit = api("GET", quality_path)
        st.session_state["communication_quality_audit"] = audit
        st.session_state["run_id"] = audit["run_id"]
    if right.button("Export Communication Quality Pack", use_container_width=True):
        pack = api("POST", pack_path)
        st.session_state["communication_quality_pack"] = pack
        st.session_state["communication_quality_audit"] = pack["pack"]["quality_audit"]
        st.session_state["run_id"] = pack["pack"]["quality_audit"]["run_id"]
        st.success(f"Communication Quality Pack exported: {pack['markdown_path']}")

    audit = st.session_state.get("communication_quality_audit") or api("GET", quality_path)
    st.session_state["communication_quality_audit"] = audit
    gate = audit["quality_gate"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Overall score", audit["overall_score"])
    c2.metric("Status", audit["status"])
    c3.metric("Dispatch ready", str(gate["approved_for_dispatch"]))
    c4.metric("Scenarios", audit["scenario_coverage"]["scenario_count"])

    st.subheader("Score Dimensions")
    st.dataframe(
        [
            {
                "dimension": name,
                "score": item["score"],
                "status": item["status"],
                "gaps": "; ".join(item["gaps"]),
            }
            for name, item in audit["score_dimensions"].items()
        ],
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("Role Crew Review")
    st.dataframe(audit["role_playbook_handoffs"], use_container_width=True, hide_index=True)

    st.subheader("Reviewer Actions")
    st.dataframe(audit["required_revisions"], use_container_width=True, hide_index=True)

    st.subheader("Run Transparency")
    st.json(audit["run_transparency"])

    st.subheader("Artifact Handoffs")
    st.dataframe(audit["artifact_handoffs"], use_container_width=True, hide_index=True)

    st.subheader("Scenario Coverage")
    st.dataframe(audit["scenario_coverage"]["scenarios"], use_container_width=True, hide_index=True)

    pack = st.session_state.get("communication_quality_pack")
    if pack:
        st.caption(f"Markdown: {pack['markdown_path']}")
        st.caption(f"JSON: {pack['json_path']}")
        st.download_button(
            "Download Communication Quality Pack",
            data=pack["markdown"],
            file_name=f"{pack['pack_id']}.md",
            mime="text/markdown",
        )
        st.markdown(pack["markdown"])
        with st.expander("Communication Quality JSON"):
            st.json(pack["pack"])

with tabs[49]:
    run_id = st.text_input("Support ops run ID", value=st.session_state.get("run_id", ""))
    plan_path = f"/ops/crew-plan?run_id={run_id}" if run_id else "/ops/crew-plan"
    pack_path = f"/ops/crew-pack?run_id={run_id}" if run_id else "/ops/crew-pack"
    left, right = st.columns(2)
    if left.button("Refresh Support Ops Crews", type="primary", use_container_width=True):
        plan = api("GET", plan_path)
        st.session_state["support_ops_crew_plan"] = plan
        st.session_state["run_id"] = plan["run_id"]
    if right.button("Export Support Ops Pack", use_container_width=True):
        pack = api("POST", pack_path)
        st.session_state["support_ops_pack"] = pack
        st.session_state["support_ops_crew_plan"] = pack["pack"]["crew_plan"]
        st.session_state["run_id"] = pack["pack"]["crew_plan"]["run_id"]
        st.success(f"Support Ops Pack exported: {pack['markdown_path']}")

    plan = st.session_state.get("support_ops_crew_plan") or api("GET", plan_path)
    st.session_state["support_ops_crew_plan"] = plan
    mode = plan["selected_process_mode"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Operations score", plan["operations_score"])
    c2.metric("Status", plan["readiness_status"])
    c3.metric("Process mode", mode["mode_id"])
    c4.metric("Delegated tasks", len(plan["delegated_tasks"]))

    st.subheader("Role Crews")
    st.dataframe(plan["role_crews"], use_container_width=True, hide_index=True)

    st.subheader("Delegated Task Board")
    st.dataframe(
        [
            {
                "task": task["task_id"],
                "owner": task["owner_role"],
                "artifact": task["artifact_type"],
                "status": task["status"],
                "evidence": ", ".join(task["evidence_refs"]),
            }
            for task in plan["delegated_tasks"]
        ],
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("Review Gates")
    st.dataframe(plan["review_gates"], use_container_width=True, hide_index=True)

    st.subheader("Artifact Handoffs")
    st.dataframe(plan["artifact_handoffs"], use_container_width=True, hide_index=True)

    st.subheader("Run Transparency")
    st.json(plan["run_transparency"])

    st.subheader("Scenario Coverage")
    st.dataframe(plan["scenario_coverage"]["scenarios"], use_container_width=True, hide_index=True)

    pack = st.session_state.get("support_ops_pack")
    if pack:
        st.caption(f"Markdown: {pack['markdown_path']}")
        st.caption(f"JSON: {pack['json_path']}")
        st.download_button(
            "Download Support Ops Pack",
            data=pack["markdown"],
            file_name=f"{pack['pack_id']}.md",
            mime="text/markdown",
        )
        st.markdown(pack["markdown"])
        with st.expander("Support Ops Pack JSON"):
            st.json(pack["pack"])

with tabs[50]:
    run_id = st.text_input("Sandbox run ID", value=st.session_state.get("run_id", ""))
    sandbox_path = f"/ops/crew-sandbox?run_id={run_id}" if run_id else "/ops/crew-sandbox"
    pack_path = f"/ops/crew-sandbox-pack?run_id={run_id}" if run_id else "/ops/crew-sandbox-pack"
    left, right = st.columns(2)
    if left.button("Refresh Worker Sandbox", type="primary", use_container_width=True):
        sandbox = api("GET", sandbox_path)
        st.session_state["support_ops_sandbox"] = sandbox
        st.session_state["run_id"] = sandbox["run_id"]
    if right.button("Export Sandbox Pack", use_container_width=True):
        pack = api("POST", pack_path)
        st.session_state["support_ops_sandbox_pack"] = pack
        st.session_state["support_ops_sandbox"] = pack["pack"]["sandbox_run"]
        st.session_state["run_id"] = pack["pack"]["sandbox_run"]["run_id"]
        st.success(f"Support Ops Sandbox Pack exported: {pack['markdown_path']}")

    sandbox = st.session_state.get("support_ops_sandbox") or api("GET", sandbox_path)
    st.session_state["support_ops_sandbox"] = sandbox
    benchmark = sandbox["benchmark_discipline"]
    scale = sandbox["worker_scale_out"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Sandbox score", benchmark["score"])
    c2.metric("Status", benchmark["status"])
    c3.metric("Workers", scale["assigned_worker_count"])
    c4.metric("Transcript events", sum(len(run["transcript"]) for run in sandbox["task_runs"]))

    st.subheader("Worker Assignment Board")
    st.dataframe(
        [
            {
                "task": run["task_id"],
                "worker": run["worker_id"],
                "owner": run["owner_role"],
                "status": run["status"],
                "tools used": run["budget"]["tool_calls_used"],
                "tokens": run["budget"]["estimated_tokens_used"],
            }
            for run in sandbox["task_runs"]
        ],
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("Sandbox Policy")
    st.json(sandbox["sandbox_policy"])

    st.subheader("Verification Gates")
    st.dataframe(sandbox["verification_gates"], use_container_width=True, hide_index=True)

    st.subheader("Worker Scale-Out")
    st.json(sandbox["worker_scale_out"])

    st.subheader("Tool Transcripts")
    selected = st.selectbox("Task transcript", [run["task_id"] for run in sandbox["task_runs"]])
    selected_run = next(run for run in sandbox["task_runs"] if run["task_id"] == selected)
    st.json(selected_run["transcript"])

    st.subheader("Issue-to-Handoff Loop")
    st.dataframe(sandbox["issue_to_handoff_loop"], use_container_width=True, hide_index=True)

    pack = st.session_state.get("support_ops_sandbox_pack")
    if pack:
        st.caption(f"Markdown: {pack['markdown_path']}")
        st.caption(f"JSON: {pack['json_path']}")
        st.download_button(
            "Download Support Ops Sandbox Pack",
            data=pack["markdown"],
            file_name=f"{pack['pack_id']}.md",
            mime="text/markdown",
        )
        st.markdown(pack["markdown"])
        with st.expander("Support Ops Sandbox Pack JSON"):
            st.json(pack["pack"])

with tabs[51]:
    left, right = st.columns(2)
    if left.button("Refresh Crew Readiness", type="primary", use_container_width=True):
        drill = api("GET", "/ops/crew-readiness-drill")
        st.session_state["support_ops_readiness_drill"] = drill
    if right.button("Export Crew Readiness Pack", use_container_width=True):
        pack = api("POST", "/ops/crew-readiness-pack")
        st.session_state["support_ops_readiness_pack"] = pack
        st.session_state["support_ops_readiness_drill"] = pack["pack"]["readiness_drill"]
        st.success(f"Support Ops Readiness Pack exported: {pack['markdown_path']}")

    drill = st.session_state.get("support_ops_readiness_drill") or api("GET", "/ops/crew-readiness-drill")
    st.session_state["support_ops_readiness_drill"] = drill
    summary = drill["summary"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Readiness score", drill["readiness_score"])
    c2.metric("Status", drill["readiness_status"])
    c3.metric("Process modes", summary["process_mode_count"])
    c4.metric("External calls", summary["external_call_count"])

    st.subheader("Scenario Results")
    st.dataframe(
        [
            {
                "scenario": row["scenario_id"],
                "domain": row["domain"],
                "expected": row["expected_process_mode"],
                "actual": row["actual_process_mode"],
                "mode match": row["process_mode_match"],
                "sandbox": row["sandbox_status"],
                "missing roles": ", ".join(row["missing_roles"]),
            }
            for row in drill["scenario_results"]
        ],
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("Readiness Gates")
    st.dataframe(drill["readiness_gates"], use_container_width=True, hide_index=True)

    st.subheader("Role Coverage Matrix")
    st.dataframe(drill["role_coverage_matrix"], use_container_width=True, hide_index=True)

    st.subheader("Process-Mode Coverage")
    st.json(drill["process_mode_coverage"])

    st.subheader("Sandbox Transcript Audit")
    st.json(drill["sandbox_transcript_audit"])

    pack = st.session_state.get("support_ops_readiness_pack")
    if pack:
        st.caption(f"Markdown: {pack['markdown_path']}")
        st.caption(f"JSON: {pack['json_path']}")
        st.download_button(
            "Download Support Ops Readiness Pack",
            data=pack["markdown"],
            file_name=f"{pack['pack_id']}.md",
            mime="text/markdown",
        )
        st.markdown(pack["markdown"])
        with st.expander("Support Ops Readiness Pack JSON"):
            st.json(pack["pack"])

with tabs[52]:
    left, right = st.columns(2)
    if left.button("Refresh Tool Governance", type="primary", use_container_width=True):
        st.session_state["tool_governance_registry"] = api("GET", "/tools/registry")
    if right.button("Export Tool Governance Pack", use_container_width=True):
        pack = api("POST", "/tools/governance-pack")
        st.session_state["tool_governance_pack"] = pack
        st.session_state["tool_governance_registry"] = pack["pack"]["tool_registry"]
        st.success(f"Tool Governance Pack exported: {pack['markdown_path']}")

    registry = st.session_state.get("tool_governance_registry") or api("GET", "/tools/registry")
    st.session_state["tool_governance_registry"] = registry
    summary = registry["summary"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Tool governance score", registry["tool_governance_score"])
    c2.metric("Status", registry["readiness_status"])
    c3.metric("Registered tools", summary["registered_tool_count"])
    c4.metric("Observed calls", summary["observed_tool_call_count"])

    st.subheader("Tool Manifests")
    st.dataframe(
        [
            {
                "tool": item["tool_name"],
                "owner": item["owner"],
                "category": item["category"],
                "risk": item["risk_tier"],
                "calls": item["observed_call_count"],
                "errors": item["observed_error_count"],
                "controls": item["control_status"],
                "rollout": item["rollout_state"],
            }
            for item in registry["tool_manifests"]
        ],
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("Control Checks")
    st.dataframe(registry["control_checks"], use_container_width=True, hide_index=True)

    st.subheader("Unknown Tool References")
    st.dataframe(registry["unknown_tool_references"], use_container_width=True, hide_index=True)

    st.subheader("Marketplace Intake Policy")
    st.json(registry["marketplace_intake_policy"])

    st.subheader("Owner Action Plan")
    st.dataframe(registry["owner_action_plan"], use_container_width=True, hide_index=True)

    pack = st.session_state.get("tool_governance_pack")
    if pack:
        st.caption(f"Markdown: {pack['markdown_path']}")
        st.caption(f"JSON: {pack['json_path']}")
        st.download_button(
            "Download Tool Governance Pack",
            data=pack["markdown"],
            file_name=f"{pack['pack_id']}.md",
            mime="text/markdown",
        )
        st.dataframe(pack["pack"]["approval_matrix"], use_container_width=True, hide_index=True)
        st.markdown(pack["markdown"])
        with st.expander("Tool Governance Pack JSON"):
            st.json(pack["pack"])

with tabs[53]:
    left, right = st.columns(2)
    if left.button("Refresh Agent Bus", type="primary", use_container_width=True):
        st.session_state["agent_bus_audit"] = api("GET", "/ops/agent-bus-audit")
    if right.button("Export Agent Bus Pack", use_container_width=True):
        pack = api("POST", "/ops/agent-bus-pack")
        st.session_state["agent_bus_pack"] = pack
        st.session_state["agent_bus_audit"] = pack["pack"]["bus_audit"]
        st.success(f"Agent Bus Pack exported: {pack['markdown_path']}")

    audit = st.session_state.get("agent_bus_audit") or api("GET", "/ops/agent-bus-audit")
    st.session_state["agent_bus_audit"] = audit
    summary = audit["summary"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Coordination score", audit["coordination_score"])
    c2.metric("Status", audit["readiness_status"])
    c3.metric("Messages", summary["message_count"])
    c4.metric("Malformed", summary["malformed_message_count"])

    st.caption(f"Bus root: {audit['bus_root']}")

    st.subheader("Agent Registry")
    st.dataframe(audit["agent_registry"], use_container_width=True, hide_index=True)

    st.subheader("Message Files")
    st.dataframe(audit["message_files"], use_container_width=True, hide_index=True)

    st.subheader("Handoff Ledger")
    st.dataframe(audit["handoff_ledger"], use_container_width=True, hide_index=True)

    st.subheader("Review Gates")
    st.dataframe(audit["control_gates"], use_container_width=True, hide_index=True)

    st.subheader("Operator Queue")
    st.dataframe(audit["operator_queue"], use_container_width=True, hide_index=True)

    st.subheader("Recent Messages")
    st.dataframe(audit["recent_messages"], use_container_width=True, hide_index=True)

    pack = st.session_state.get("agent_bus_pack")
    if pack:
        st.caption(f"Markdown: {pack['markdown_path']}")
        st.caption(f"JSON: {pack['json_path']}")
        st.download_button(
            "Download Agent Bus Pack",
            data=pack["markdown"],
            file_name=f"{pack['pack_id']}.md",
            mime="text/markdown",
        )
        st.markdown(pack["markdown"])
        with st.expander("Agent Bus Pack JSON"):
            st.json(pack["pack"])

with tabs[54]:
    left, right = st.columns(2)
    if left.button("Refresh Trace Eval Lab", type="primary", use_container_width=True):
        st.session_state["trace_eval_lab"] = api("GET", "/observability/trace-eval-lab")
    if right.button("Export Trace Eval Lab Pack", use_container_width=True):
        pack = api("POST", "/observability/eval-pack")
        st.session_state["trace_eval_lab_pack"] = pack
        st.session_state["trace_eval_lab"] = pack["pack"]["trace_eval_lab"]
        st.success(f"Trace Eval Lab Pack exported: {pack['markdown_path']}")

    lab = st.session_state.get("trace_eval_lab") or api("GET", "/observability/trace-eval-lab")
    st.session_state["trace_eval_lab"] = lab
    summary = lab["summary"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Observability score", lab["observability_score"])
    c2.metric("Status", lab["readiness_status"])
    c3.metric("Trace events", summary["trace_event_count"])
    c4.metric("Eval scenarios", summary["eval_dataset_size"])

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Retrieval", summary["retrieval_status"])
    c6.metric("Winner", summary["experiment_winner"])
    c7.metric("Unsafe auto actions", summary["unsafe_auto_action_count"])
    c8.metric("External calls", summary["external_call_count"])

    st.subheader("Trace Diagnostics")
    st.dataframe(lab["trace_diagnostics"], use_container_width=True, hide_index=True)

    st.subheader("Retrieval Diagnostics")
    st.json(lab["retrieval_diagnostics"])

    st.subheader("Experiment Variants")
    variants = [
        {
            "variant": item["variant"],
            "routing_accuracy": item["routing_accuracy"],
            "approval_recall": item["approval_recall"],
            "approvals": item["approval_required_count"],
            "unsafe_auto_actions": item["unsafe_auto_action_count"],
            "external_calls": item["external_call_count"],
        }
        for item in lab["experiment_comparison"]["variants"]
    ]
    st.dataframe(variants, use_container_width=True, hide_index=True)

    st.subheader("Control Checks")
    st.dataframe(lab["control_checks"], use_container_width=True, hide_index=True)

    pack = st.session_state.get("trace_eval_lab_pack")
    if pack:
        st.caption(f"Markdown: {pack['markdown_path']}")
        st.caption(f"JSON: {pack['json_path']}")
        st.download_button(
            "Download Trace Eval Lab Pack",
            data=pack["markdown"],
            file_name=f"{pack['pack_id']}.md",
            mime="text/markdown",
        )
        st.markdown(pack["markdown"])
        with st.expander("Trace Eval Lab Pack JSON"):
            st.json(pack["pack"])
