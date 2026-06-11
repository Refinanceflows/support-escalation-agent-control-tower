from pathlib import Path


def test_escalation_quality_audit_scores_latest_engineering_handoff(client):
    token = client.post("/auth/demo-token").json()["token"]
    headers = {"X-API-Key": token}

    response = client.get("/escalations/quality-audit", headers=headers)
    assert response.status_code == 200, response.text
    audit = response.json()

    assert audit["title"] == "Engineering Escalation Quality Audit"
    assert audit["mode"] == "local-deterministic-escalation-quality"
    assert audit["run_id"].startswith("run_")
    assert audit["trace_id"].startswith("trc_")
    assert audit["overall_score"] >= 60
    assert set(audit["score_dimensions"]) == {
        "actionability",
        "reproduction_evidence",
        "customer_impact",
        "routing_governance",
        "noise_control",
    }
    assert audit["quality_gate"]["gate"] == "engineering_escalation_pre_dispatch_review"
    assert audit["quality_gate"]["review_gate_pattern"] == "human_in_the_loop"
    assert audit["quality_gate"]["governance_pattern"] == "pre_dispatch_policy_gate"
    assert audit["quality_gate"]["observability_pattern"] == "trace_backed_handoff"
    assert {item["role"] for item in audit["review_crew"]} == {
        "engineering_triage_reviewer",
        "support_evidence_reviewer",
        "customer_impact_reviewer",
        "escalation_governance_reviewer",
        "noise_control_reviewer",
    }
    assert audit["role_playbook_handoffs"]
    assert audit["artifact_handoffs"]
    assert audit["run_transparency"]["node_history"]
    assert audit["escalation_evidence"]["engineering_preview"]
    assert audit["scenario_coverage"]["coverage_status"] == "pass"
    assert any("escalation_quality_packs" in command for command in audit["local_proof_commands"])


def test_escalation_quality_pack_writes_reviewer_artifacts(client):
    token = client.post("/auth/demo-token").json()["token"]
    headers = {"X-API-Key": token}

    response = client.post("/escalations/quality-pack", headers=headers)
    assert response.status_code == 200, response.text
    exported = response.json()
    pack = exported["pack"]

    assert "escalation_quality_packs" in exported["markdown_path"]
    assert Path(exported["markdown_path"]).exists()
    assert Path(exported["json_path"]).exists()
    assert "# Engineering Escalation Quality Pack" in exported["markdown"]
    assert "## Role Crew Review" in exported["markdown"]
    assert "## Scenario Coverage" in exported["markdown"]
    assert exported["overall_score"] == pack["quality_audit"]["overall_score"]
    assert pack["review_gate_summary"]["review_gate_pattern"] == "human_in_the_loop"
    assert pack["handoff_packet"]["run_transparency"]["approval_id"].startswith("apr_")


def test_escalation_quality_marks_low_risk_ticket_not_required(client):
    token = client.post("/auth/demo-token").json()["token"]
    headers = {"X-API-Key": token}
    ticket = client.post(
        "/tickets/ingest",
        headers=headers,
        json={
            "subject": "Question about workspace display name",
            "body": "Can we rename a workspace label for one team?",
            "customer": "Greyline Media",
            "priority": "low",
            "customer_tier": "standard",
            "tags": ["how-to"],
        },
    ).json()
    run = client.post(f"/tickets/{ticket['ticket_id']}/analyze", headers=headers).json()

    response = client.get(f"/escalations/quality-audit?run_id={run['run_id']}", headers=headers)
    assert response.status_code == 200, response.text
    audit = response.json()

    assert audit["run_id"] == run["run_id"]
    assert audit["escalation_required"] is False
    assert audit["status"] == "not_required"
    assert audit["quality_gate"]["approved_for_internal_dispatch"] is False
    assert any(item["dimension"] == "noise_control" for item in audit["required_revisions"])


def test_dashboard_smoke_includes_escalation_quality(client):
    token = client.post("/auth/demo-token").json()["token"]
    headers = {"X-API-Key": token}

    response = client.get("/ui/dashboard-smoke", headers=headers)
    assert response.status_code == 200, response.text
    smoke = response.json()

    views = {item["label"]: item for item in smoke["expected_views"]}
    endpoints = {item["endpoint"]: item for item in smoke["endpoint_references"]}
    artifacts = {item["artifact_directory"]: item for item in smoke["generated_artifact_tabs"]}

    assert smoke["status"] == "pass"
    assert views["Escalation Quality"]["present"] is True
    assert endpoints["GET /escalations/quality-audit"]["dashboard_reference_present"] is True
    assert endpoints["GET /escalations/quality-audit"]["route_present"] is True
    assert endpoints["POST /escalations/quality-pack"]["dashboard_reference_present"] is True
    assert endpoints["POST /escalations/quality-pack"]["route_present"] is True
    assert artifacts["data/escalation_quality_packs"]["tab_present"] is True
