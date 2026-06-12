from pathlib import Path


def test_provider_failover_drill_exercises_fallback_and_fail_closed_paths(client, auth_headers):
    response = client.get("/providers/failover-drill", headers=auth_headers)
    assert response.status_code == 200, response.text
    drill = response.json()

    assert drill["title"] == "Provider Failover Drill"
    assert drill["local_mock_only"] is True
    assert drill["readiness_status"] == "ready"
    assert drill["failover_score"] >= 95
    assert {"provider flexibility", "governance", "human-in-the-loop"} <= set(drill["repo_radar_patterns"])
    scenarios = {item["scenario_id"]: item for item in drill["provider_scenarios"]}
    assert scenarios["local_default"]["provider"] == "local"
    assert scenarios["openai_missing_credentials"]["fallback_used"] is True
    assert scenarios["azure_missing_credentials"]["fallback_used"] is True
    assert scenarios["primary_timeout"]["fallback_used"] is True
    assert scenarios["fallback_disabled_missing_credentials"]["fail_closed"] is True
    assert drill["summary"]["external_call_count"] == 0
    assert all(item["status"] == "pass" for item in drill["control_checks"])


def test_provider_failover_pack_exports_artifacts_and_audit_event(client, auth_headers):
    response = client.post("/providers/failover-pack", headers=auth_headers)
    assert response.status_code == 200, response.text
    exported = response.json()
    pack = exported["pack"]

    assert exported["status"] == "ready"
    assert "provider_failover_packs" in exported["markdown_path"]
    assert Path(exported["markdown_path"]).exists()
    assert Path(exported["json_path"]).exists()
    assert pack["title"] == "Provider Failover and Fallback Drill Pack"
    assert pack["deployment_gate"]["status"] == "approved_for_local_demo"
    assert "## Provider Scenarios" in exported["markdown"]
    assert "fallback" in Path(exported["json_path"]).read_text(encoding="utf-8").lower()

    events = client.get("/audit/events", headers=auth_headers).json()
    assert any(event["action"] == "providers.failover_pack_exported" for event in events)


def test_provider_failover_dashboard_contract_and_artifact_wiring(client, auth_headers):
    client.post("/providers/failover-pack", headers=auth_headers)

    smoke = client.get("/ui/dashboard-smoke", headers=auth_headers).json()
    assert smoke["status"] == "pass"
    assert any(
        item["endpoint"] == "GET /providers/failover-drill"
        and item["dashboard_reference_present"]
        and item["route_present"]
        for item in smoke["endpoint_references"]
    )
    assert any(
        item["producer_endpoint"] == "POST /providers/failover-pack"
        and item["tab_present"]
        and item["endpoint_reference_present"]
        for item in smoke["generated_artifact_tabs"]
    )

    contract = client.get("/api/contract-audit", headers=auth_headers).json()
    assert "GET /providers/failover-drill" in {item["endpoint"] for item in contract["endpoint_inventory"]}
    assert any(
        item["producer"] == "POST /providers/failover-pack"
        and item["artifact_directory"] == "data/provider_failover_packs"
        for item in contract["generated_artifact_endpoint_coverage"]
    )

    inventory = client.get("/artifacts/inventory", headers=auth_headers).json()
    assert any(item["directory"] == "data/provider_failover_packs" for item in inventory["artifacts"])
