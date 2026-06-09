from pathlib import Path


def _token_headers(client):
    token = client.post("/auth/demo-token").json()["token"]
    return {"X-API-Key": token}


def test_policy_change_simulation_compares_thresholds_and_blast_radius(client):
    headers = _token_headers(client)
    response = client.post(
        "/policies/change-simulation",
        headers=headers,
        json={
            "baseline": {
                "confidence_cutoff": 0.62,
                "sla_high_risk_threshold": 0.70,
                "auto_approval_max_blast_radius": 35,
            },
            "proposed": {
                "confidence_cutoff": 0.80,
                "sla_high_risk_threshold": 0.60,
                "auto_approval_max_blast_radius": 20,
            },
            "scenario_limit": 5,
        },
    )
    assert response.status_code == 200, response.text
    simulation = response.json()

    assert simulation["mode"] == "local-deterministic-policy-change-workbench"
    assert simulation["local_mock_only"] is True
    assert simulation["scenario_count"] == 5
    assert simulation["summary"]["baseline"]["auto_allowed_count"] >= 0
    assert simulation["summary"]["proposed"]["blocked_for_review_count"] >= simulation[
        "summary"
    ]["baseline"]["blocked_for_review_count"]
    assert "overall_change_risk_score" in simulation["blast_radius"]
    assert "changed_route_count" in simulation["sla_routing"]
    assert simulation["scenario_results"]
    assert {
        "decision",
        "approval_type",
        "sla_route",
        "blast_radius_score",
    } <= set(simulation["scenario_results"][0]["proposed"])
    assert any("blast radius" in command for command in simulation["local_verification_commands"])


def test_policy_change_pack_exports_markdown_and_json(client):
    headers = _token_headers(client)
    response = client.post(
        "/policies/change-pack",
        headers=headers,
        json={
            "proposed": {
                "confidence_cutoff": 0.74,
                "sla_high_risk_threshold": 0.64,
                "auto_approval_max_blast_radius": 24,
            },
            "scenario_limit": 4,
        },
    )
    assert response.status_code == 200, response.text
    exported = response.json()
    markdown = exported["markdown"]
    pack = exported["pack"]

    assert "policy_change_packs" in exported["markdown_path"]
    assert Path(exported["markdown_path"]).exists()
    assert Path(exported["json_path"]).exists()
    assert pack["approval_thresholds"]["proposed"] == 24
    assert pack["confidence_cutoffs"]["proposed"] == 0.74
    assert pack["sla_thresholds"]["proposed"] == 0.64
    assert len(pack["interviewer_talking_points"]) == 5
    assert "# Agent Policy Simulation Pack" in markdown
    assert "## Blast Radius" in markdown
    assert "policy_change_pack_markdown" in Path(exported["json_path"]).read_text(
        encoding="utf-8"
    )


def test_policy_change_pack_is_listed_in_artifact_inventory(client):
    headers = _token_headers(client)
    client.post("/policies/change-pack", headers=headers, json={"scenario_limit": 3})

    response = client.get("/artifacts/inventory", headers=headers)
    assert response.status_code == 200, response.text
    inventory = response.json()

    row = next(
        item for item in inventory["artifacts"] if item["directory"] == "data/policy_change_packs"
    )
    assert row["producer"] == "POST /policies/change-pack"
    assert row["file_count"] >= 2
    assert "approval thresholds" in row["reviewer_purpose"]
