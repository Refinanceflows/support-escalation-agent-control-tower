from pathlib import Path


def _token_headers(client):
    token = client.post("/auth/demo-token").json()["token"]
    return {"X-API-Key": token}


def _analyze_urgent_enterprise_ticket(client, headers):
    ticket_response = client.post(
        "/tickets/ingest",
        headers=headers,
        json={
            "subject": "Enterprise webhook outage with SLA breach risk",
            "body": "Webhook 500 errors are blocking production order sync for all agents.",
            "priority": "urgent",
            "customer_tier": "enterprise",
            "tags": ["webhook", "incident"],
        },
    )
    assert ticket_response.status_code == 200, ticket_response.text
    ticket = ticket_response.json()
    run_response = client.post(
        f"/tickets/{ticket['ticket_id']}/analyze",
        headers=headers,
    )
    assert run_response.status_code == 200, run_response.text
    return run_response.json()


def test_policy_drift_audit_flags_current_policy_changes(client):
    headers = _token_headers(client)
    run = _analyze_urgent_enterprise_ticket(client, headers)

    response = client.post(
        "/policies/drift-audit",
        headers=headers,
        json={
            "baseline": {
                "confidence_cutoff": 0.1,
                "sla_high_risk_threshold": 0.95,
                "auto_approval_max_blast_radius": 100,
            },
            "current": {
                "confidence_cutoff": 0.8,
                "sla_high_risk_threshold": 0.5,
                "auto_approval_max_blast_radius": 20,
            },
            "max_runs": 5,
        },
    )
    assert response.status_code == 200, response.text
    audit = response.json()

    assert audit["mode"] == "local-deterministic-policy-drift-monitor"
    assert audit["local_mock_only"] is True
    assert audit["run_count"] == 1
    assert audit["summary"]["drifted_run_count"] == 1
    assert audit["status"] in {"review_required", "watch"}
    assert audit["drift_rows"][0]["run_id"] == run["run_id"]
    assert audit["drift_rows"][0]["changed_fields"]
    assert "shared state" in audit["repo_radar_patterns"]
    assert any("policies/drift-audit" in command for command in audit["local_commands"])


def test_policy_drift_pack_exports_reviewer_artifacts(client):
    headers = _token_headers(client)
    _analyze_urgent_enterprise_ticket(client, headers)

    response = client.post(
        "/policies/drift-pack",
        headers=headers,
        json={
            "baseline": {
                "confidence_cutoff": 0.1,
                "sla_high_risk_threshold": 0.95,
                "auto_approval_max_blast_radius": 100,
            },
            "current": {
                "confidence_cutoff": 0.8,
                "sla_high_risk_threshold": 0.5,
                "auto_approval_max_blast_radius": 20,
            },
        },
    )
    assert response.status_code == 200, response.text
    exported = response.json()

    assert "policy_drift_packs" in exported["markdown_path"]
    assert Path(exported["markdown_path"]).exists()
    assert Path(exported["json_path"]).exists()
    assert "# Policy Drift Reviewer Pack" in exported["markdown"]
    assert exported["pack"]["drift_audit"]["summary"]["evaluated_run_count"] >= 1

    events = client.get("/audit/events", headers=headers).json()
    assert any(event["action"] == "policy.drift_pack_exported" for event in events)


def test_policy_drift_pack_is_listed_in_artifact_inventory(client):
    headers = _token_headers(client)
    _analyze_urgent_enterprise_ticket(client, headers)
    client.post("/policies/drift-pack", headers=headers, json={})

    response = client.get("/artifacts/inventory", headers=headers)
    assert response.status_code == 200, response.text
    inventory = response.json()

    row = next(
        item for item in inventory["artifacts"] if item["directory"] == "data/policy_drift_packs"
    )
    assert row["producer"] == "POST /policies/drift-pack"
    assert row["file_count"] >= 2
    assert "drift" in row["reviewer_purpose"].lower()
