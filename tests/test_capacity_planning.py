from pathlib import Path


def _headers(client):
    token = client.post("/auth/demo-token").json()["token"]
    return {"X-API-Key": token}


def test_capacity_forecast_maps_ticket_load_to_staffing_gaps(client):
    headers = _headers(client)

    response = client.get("/capacity/forecast", headers=headers)
    assert response.status_code == 200, response.text
    forecast = response.json()

    assert forecast["mode"] == "local-deterministic-capacity-planner"
    assert forecast["local_mock_only"] is True
    assert 0 <= forecast["capacity_score"] <= 100
    assert forecast["demand_summary"]["ticket_count"] >= 10
    assert forecast["queue_forecast"]
    assert forecast["owner_assignments"]
    assert "GET /capacity/forecast" in forecast["endpoint_list"]
    assert "POST /capacity/staffing-plan" in forecast["endpoint_list"]

    incident = next(item for item in forecast["queue_forecast"] if item["queue"] == "incident")
    assert incident["owner"] == "Incident Commander"
    assert incident["projected_effort_hours"] > 0
    assert incident["sample_ticket_ids"]

    statuses = {item["status"] for item in forecast["queue_forecast"]}
    assert statuses <= {"covered", "near_capacity", "capacity_gap"}


def test_capacity_staffing_plan_exports_markdown_and_json(client):
    headers = _headers(client)

    response = client.post("/capacity/staffing-plan", headers=headers)
    assert response.status_code == 200, response.text
    exported = response.json()
    plan = exported["plan"]
    markdown = exported["markdown"]

    assert exported["readiness_status"] in {
        "staffing_gaps_require_owner_action",
        "review_ready_with_capacity_watchlist",
        "ready_for_current_fixture_load",
    }
    assert "capacity_plans" in exported["markdown_path"]
    assert Path(exported["markdown_path"]).exists()
    assert Path(exported["json_path"]).exists()
    assert plan["queue_forecast"]
    assert plan["staffing_actions"]
    assert plan["owner_assignments"]
    assert "POST /capacity/staffing-plan" in plan["endpoint_list"]
    assert "capacity_plan_markdown" in plan["artifact_paths"]
    assert "# Support Capacity Forecast and Staffing Plan" in markdown
    assert "## Queue Forecast" in markdown
    assert "## Staffing Actions" in markdown
