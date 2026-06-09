from pathlib import Path


def _enterprise_run(client, auth_headers):
    ticket = client.post(
        "/tickets/ingest",
        headers=auth_headers,
        json={
            "subject": "Northstar SSO outage with renewal sponsor risk",
            "body": (
                "SAML SSO is down for all production support agents. "
                "The renewal sponsor asked for executive visibility and SLA breach risk is high."
            ),
            "customer": "Northstar Health",
            "customer_email": "ops@northstar.example",
            "priority": "urgent",
            "customer_tier": "enterprise",
            "tags": ["auth", "sso", "outage", "renewal"],
        },
    ).json()
    run = client.post(f"/tickets/{ticket['ticket_id']}/analyze", headers=auth_headers).json()
    approved = client.post(
        f"/runs/{run['run_id']}/approve",
        headers=auth_headers,
        json={"decided_by": "finance-test", "note": "approved for finance impact"},
    ).json()
    return ticket, approved


def test_finance_impact_summary_estimates_cost_penalty_effort_and_arr(client, auth_headers):
    _, run = _enterprise_run(client, auth_headers)

    response = client.post(
        "/finance/impact-summary",
        headers=auth_headers,
        json={"run_id": run["run_id"]},
    )
    assert response.status_code == 200, response.text
    summary = response.json()

    assert summary["mode"] == "local-deterministic-finance-impact"
    assert summary["local_mock_only"] is True
    assert summary["run_id"] == run["run_id"]
    assert summary["fallback_used"] == "supplied_run"
    assert summary["customer_context"]["account"] == "Northstar Health"
    assert summary["customer_context"]["arr_usd"] == 420000
    assert summary["support_cost"]["estimated_cost_usd"] > 0
    assert summary["sla_penalty_exposure"]["estimated_penalty_exposure_usd"] > 0
    assert summary["engineering_effort"]["estimated_hours"] >= 20
    assert summary["customer_arr_at_risk"]["arr_at_risk_usd"] >= 200000
    assert summary["finance_rollup"]["estimated_financial_exposure_usd"] > summary["finance_rollup"]["estimated_direct_cost_usd"]
    assert summary["finance_rollup"]["readiness_status"] == "finance_review_required"
    assert "material_arr_at_risk" in summary["risk_flags"]
    assert "ARR at risk" in summary["executive_summary"]
    assert summary["limitations"]


def test_finance_impact_pack_exports_markdown_and_json(client, auth_headers):
    _, run = _enterprise_run(client, auth_headers)

    response = client.post(
        "/finance/impact-pack",
        headers=auth_headers,
        json={"run_id": run["run_id"]},
    )
    assert response.status_code == 200, response.text
    exported = response.json()
    pack = exported["pack"]
    markdown = exported["markdown"]

    assert exported["readiness_status"] == "finance_review_required"
    assert exported["estimated_financial_exposure_usd"] > 0
    assert "finance_impact_packs" in exported["markdown_path"]
    assert Path(exported["markdown_path"]).exists()
    assert Path(exported["json_path"]).exists()
    assert pack["title"] == "Escalation Finance Impact Pack"
    assert pack["executive_decision_table"]
    assert pack["finance_controls"]
    assert "finance_impact_markdown" in pack["artifact_paths"]
    assert "# Escalation Finance Impact Pack" in markdown
    assert "## SLA Penalty Exposure" in markdown
    assert "## Customer ARR At Risk" in markdown
    saved = Path(exported["json_path"]).read_text(encoding="utf-8")
    assert "finance_impact_json" in saved


def test_finance_impact_fallback_and_missing_run(client, auth_headers):
    fallback = client.post("/finance/impact-summary", headers=auth_headers)
    assert fallback.status_code == 200, fallback.text
    summary = fallback.json()
    assert summary["fallback_used"] == "sample_bootstrap"
    assert summary["run_id"].startswith("run_")
    assert summary["finance_rollup"]["estimated_financial_exposure_usd"] > 0

    missing = client.post(
        "/finance/impact-pack",
        headers=auth_headers,
        json={"run_id": "run_missing"},
    )
    assert missing.status_code == 404
