from pathlib import Path
import sys

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import Settings  # noqa: E402
from app.main import create_app  # noqa: E402


def main() -> int:
    state_file = ROOT / "data" / "capacity_plan_state.db"
    app = create_app(Settings(state_file=state_file))
    with TestClient(app) as client:
        token = client.post("/auth/demo-token").json()["token"]
        headers = {"x-api-key": token}
        forecast_response = client.get("/capacity/forecast", headers=headers)
        forecast_response.raise_for_status()
        plan_response = client.post("/capacity/staffing-plan", headers=headers)
        plan_response.raise_for_status()

    forecast = forecast_response.json()
    plan = plan_response.json()
    summary = forecast["demand_summary"]
    print("Capacity Forecast:", forecast["readiness_status"])
    print("Capacity score:", forecast["capacity_score"])
    print("Projected weekly tickets:", summary["projected_weekly_tickets"])
    print("Projected effort hours:", summary["projected_effort_hours"])
    print("Capacity gap queues:", summary["capacity_gap_queue_count"])
    print("Staffing Plan:", plan["markdown_path"])
    print("Staffing Plan JSON:", plan["json_path"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
