from pathlib import Path


def _run_incident(client, auth_headers):
    ticket = client.post(
        "/tickets/ingest",
        headers=auth_headers,
        json={
            "subject": "Enterprise SSO outage needs decision gate",
            "body": (
                "SAML SSO is down for all production support agents. "
                "SLA breach risk is high and the renewal sponsor wants executive visibility."
            ),
            "customer": "Northstar Health",
            "customer_email": "ops@northstar.example",
            "priority": "urgent",
            "customer_tier": "enterprise",
            "tags": ["auth", "sso", "outage", "renewal"],
        },
    ).json()
    run = client.post(f"/tickets/{ticket['ticket_id']}/analyze", headers=auth_headers).json()
    return ticket, run


def test_escalation_decision_board_aggregates_finance_quality_ops_and_signoffs(client, auth_headers):
    _ticket, run = _run_incident(client, auth_headers)

    response = client.get(
        "/escalations/decision-board",
        headers=auth_headers,
        params={"run_id": run["run_id"]},
    )
    assert response.status_code == 200, response.text
    board = response.json()

    assert board["title"] == "Escalation Decision Board"
    assert board["mode"] == "local-deterministic-escalation-decision-board"
    assert board["local_mock_only"] is True
    assert board["run_id"] == run["run_id"]
    assert board["decision_status"] in {
        "ready_for_human_approval",
        "executive_review_required",
        "blocked",
    }
    assert board["signal_rollup"]["finance_exposure_usd"] > 0
    assert board["signal_rollup"]["arr_at_risk_usd"] > 0
    assert board["signal_rollup"]["delegated_task_count"] >= 1
    assert {"role crews", "review gates", "artifact handoffs", "run transparency"} <= set(
        board["repo_radar_patterns"]
    )
    assert any(item["role"] == "Finance Partner" for item in board["role_signoffs"])
    assert any(item["gate_id"] == "finance_exposure_review" for item in board["review_gates"])
    assert "POST /escalations/decision-pack" in board["endpoint_list"]
    assert board["limitations"]


def test_escalation_decision_pack_exports_markdown_and_json(client, auth_headers):
    _ticket, run = _run_incident(client, auth_headers)

    response = client.post(
        "/escalations/decision-pack",
        headers=auth_headers,
        params={"run_id": run["run_id"]},
    )
    assert response.status_code == 200, response.text
    exported = response.json()
    pack = exported["pack"]

    assert exported["format"] == "markdown+json"
    assert exported["status"] == pack["decision_board"]["decision_status"]
    assert "escalation_decision_packs" in exported["markdown_path"]
    assert Path(exported["markdown_path"]).exists()
    assert Path(exported["json_path"]).exists()
    assert pack["title"] == "Escalation Decision Pack"
    assert pack["executive_decision_table"]
    assert pack["handoff_acceptance_criteria"]
    assert "# Escalation Decision Pack" in exported["markdown"]
    assert "## Review Gates" in exported["markdown"]
    saved = Path(exported["json_path"]).read_text(encoding="utf-8")
    assert "escalation_decision_json" in saved


def test_escalation_decision_dashboard_contract_and_artifact_wiring(client, auth_headers):
    client.post("/escalations/decision-pack", headers=auth_headers)

    smoke = client.get("/ui/dashboard-smoke", headers=auth_headers).json()
    assert smoke["status"] == "pass"
    assert any(item["label"] == "Escalation Decision Board" and item["present"] for item in smoke["expected_views"])
    assert any(
        item["endpoint"] == "GET /escalations/decision-board"
        and item["dashboard_reference_present"]
        and item["route_present"]
        for item in smoke["endpoint_references"]
    )
    assert any(
        item["producer_endpoint"] == "POST /escalations/decision-pack"
        and item["tab_present"]
        and item["endpoint_reference_present"]
        for item in smoke["generated_artifact_tabs"]
    )

    contract = client.get("/api/contract-audit", headers=auth_headers).json()
    assert "GET /escalations/decision-board" in {item["endpoint"] for item in contract["endpoint_inventory"]}

    inventory = client.get("/artifacts/inventory", headers=auth_headers).json()
    assert any(item["directory"] == "data/escalation_decision_packs" for item in inventory["artifacts"])
