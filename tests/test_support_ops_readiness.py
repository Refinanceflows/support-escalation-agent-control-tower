from pathlib import Path


def test_support_ops_readiness_drill_scores_scenario_crews(client, auth_headers):
    response = client.get("/ops/crew-readiness-drill", headers=auth_headers)
    assert response.status_code == 200, response.text
    drill = response.json()

    assert drill["title"] == "Support Ops Crew Readiness Drill"
    assert drill["mode"] == "local-deterministic-crew-readiness-drill"
    assert drill["local_mock_only"] is True
    assert drill["readiness_status"] in {"ready", "ready_with_review_items"}
    assert drill["readiness_score"] >= 90
    assert drill["summary"]["scenario_count"] >= 5
    assert drill["summary"]["external_call_count"] == 0
    assert drill["process_mode_coverage"]["coverage_status"] == "pass"
    assert len(drill["process_mode_coverage"]["actual_modes"]) >= 3
    assert {"role crews", "process modes", "task sandbox"} <= set(drill["repo_radar_patterns"])
    assert all(row["process_mode_match"] for row in drill["scenario_results"])
    assert all(not row["missing_roles"] for row in drill["scenario_results"])
    assert all(gate["status"] == "pass" for gate in drill["readiness_gates"])


def test_support_ops_readiness_pack_exports_markdown_json_and_audit_event(client, auth_headers):
    response = client.post("/ops/crew-readiness-pack", headers=auth_headers)
    assert response.status_code == 200, response.text
    exported = response.json()
    pack = exported["pack"]

    assert exported["status"] in {"ready", "ready_with_review_items"}
    assert exported["readiness_score"] >= 90
    assert "support_ops_readiness" in exported["markdown_path"]
    assert Path(exported["markdown_path"]).exists()
    assert Path(exported["json_path"]).exists()
    assert pack["title"] == "Support Ops Crew Readiness Pack"
    assert pack["readiness_gate_summary"]["review_count"] == 0
    assert "## Scenario Results" in exported["markdown"]
    assert "## Role Coverage Matrix" in exported["markdown"]
    saved = Path(exported["json_path"]).read_text(encoding="utf-8")
    assert "process modes" in saved.lower()
    assert "task sandbox" in saved.lower()

    events = client.get("/audit/events", headers=auth_headers).json()
    assert any(event["action"] == "ops.crew_readiness_pack_exported" for event in events)


def test_support_ops_readiness_dashboard_contract_and_artifact_wiring(client, auth_headers):
    client.post("/ops/crew-readiness-pack", headers=auth_headers)

    smoke = client.get("/ui/dashboard-smoke", headers=auth_headers).json()
    assert smoke["status"] == "pass"
    assert any(item["label"] == "Support Ops Readiness" and item["present"] for item in smoke["expected_views"])
    assert any(
        item["endpoint"] == "GET /ops/crew-readiness-drill"
        and item["dashboard_reference_present"]
        and item["route_present"]
        for item in smoke["endpoint_references"]
    )
    assert any(
        item["producer_endpoint"] == "POST /ops/crew-readiness-pack"
        and item["tab_present"]
        and item["endpoint_reference_present"]
        for item in smoke["generated_artifact_tabs"]
    )

    contract = client.get("/api/contract-audit", headers=auth_headers).json()
    assert "GET /ops/crew-readiness-drill" in {item["endpoint"] for item in contract["endpoint_inventory"]}
    assert any(
        item["producer"] == "POST /ops/crew-readiness-pack"
        and item["artifact_directory"] == "data/support_ops_readiness"
        for item in contract["generated_artifact_endpoint_coverage"]
    )

    inventory = client.get("/artifacts/inventory", headers=auth_headers).json()
    assert any(item["directory"] == "data/support_ops_readiness" for item in inventory["artifacts"])
