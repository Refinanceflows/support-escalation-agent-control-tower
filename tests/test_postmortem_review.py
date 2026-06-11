from pathlib import Path


def _analyze(client, headers, payload):
    ticket = client.post("/tickets/ingest", headers=headers, json=payload).json()
    run = client.post(f"/tickets/{ticket['ticket_id']}/analyze", headers=headers).json()
    return ticket, run


def test_postmortem_review_board_builds_owner_closure_gates(client, auth_headers):
    _ticket, run = _analyze(
        client,
        auth_headers,
        {
            "subject": "Production login outage for enterprise users",
            "body": "Users cannot log in and the SLA deadline is at risk after a production deploy.",
            "customer": "Northstar Health",
            "priority": "urgent",
            "customer_tier": "enterprise",
            "tags": ["incident", "outage", "sla", "login"],
        },
    )

    response = client.get(
        f"/incidents/postmortem-review-board?run_id={run['run_id']}",
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    board = response.json()

    assert board["title"] == "Postmortem Review Board"
    assert board["local_mock_only"] is True
    assert board["run_id"] == run["run_id"]
    assert board["trace_id"] == run["trace_id"]
    assert board["action_board"]
    assert {"role crews", "task delegation", "review gates", "artifact handoffs"} <= set(
        board["repo_radar_patterns"]
    )
    assert any(action["owner_role"] == "Customer Success" for action in board["action_board"])
    assert any(action["required_artifact"] == "POST /handoff/customer-comms-pack" for action in board["action_board"])
    assert {gate["gate_id"] for gate in board["closure_gates"]} >= {
        "owner_assignment_gate",
        "evidence_linkage_gate",
        "role_signoff_gate",
        "recurrence_guard_gate",
    }
    assert board["run_transparency"]["trace_event_count"] > 0
    assert board["process_mode"]["mode_id"] in {
        "incident_review_war_room",
        "customer_followup_review",
        "standard_closure",
    }


def test_postmortem_review_pack_exports_artifacts_and_audit_event(client, auth_headers):
    _ticket, run = _analyze(
        client,
        auth_headers,
        {
            "subject": "Webhook API regression after release",
            "body": "Webhook calls return 500s and customer jobs are blocked.",
            "customer": "Atlas Logistics",
            "priority": "high",
            "customer_tier": "enterprise",
            "tags": ["webhook", "api", "regression"],
        },
    )

    response = client.post(
        "/incidents/postmortem-review-pack",
        headers=auth_headers,
        json={"run_id": run["run_id"]},
    )
    assert response.status_code == 200, response.text
    exported = response.json()
    pack = exported["pack"]

    assert "postmortem_review_packs" in exported["markdown_path"]
    assert Path(exported["markdown_path"]).exists()
    assert Path(exported["json_path"]).exists()
    assert pack["title"] == "Postmortem Corrective Action Review Pack"
    assert pack["review_board"]["run_id"] == run["run_id"]
    assert pack["closure_owner_summary"]
    assert pack["review_gate_summary"]["pass_count"] >= 1
    assert "## Corrective Action Board" in exported["markdown"]
    assert "closure gate" in Path(exported["json_path"]).read_text(encoding="utf-8").lower()

    events = client.get("/audit/events", headers=auth_headers).json()
    assert any(event["action"] == "incident.postmortem_review_pack_exported" for event in events)


def test_postmortem_review_dashboard_contract_and_artifact_wiring(client, auth_headers):
    client.post("/incidents/postmortem-review-pack", headers=auth_headers)

    smoke = client.get("/ui/dashboard-smoke", headers=auth_headers).json()
    assert smoke["status"] == "pass"
    assert any(
        item["endpoint"] == "GET /incidents/postmortem-review-board"
        and item["dashboard_reference_present"]
        and item["route_present"]
        for item in smoke["endpoint_references"]
    )
    assert any(
        item["producer_endpoint"] == "POST /incidents/postmortem-review-pack"
        and item["tab_present"]
        and item["endpoint_reference_present"]
        for item in smoke["generated_artifact_tabs"]
    )

    contract = client.get("/api/contract-audit", headers=auth_headers).json()
    assert "GET /incidents/postmortem-review-board" in {
        item["endpoint"] for item in contract["endpoint_inventory"]
    }
    assert any(
        item["producer"] == "POST /incidents/postmortem-review-pack"
        and item["artifact_directory"] == "data/postmortem_review_packs"
        for item in contract["generated_artifact_endpoint_coverage"]
    )

    inventory = client.get("/artifacts/inventory", headers=auth_headers).json()
    assert any(item["directory"] == "data/postmortem_review_packs" for item in inventory["artifacts"])
