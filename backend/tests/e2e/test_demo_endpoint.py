from fastapi.testclient import TestClient

from api.routes import get_demo_service
from main import app
from models import DemoRunResponse


def test_demo_run_endpoint_returns_complete_status_contract() -> None:
    class FakeDemoService:
        def run(self) -> DemoRunResponse:
            return DemoRunResponse(
                incident_detected=True,
                root_cause_found=True,
                patch_generated=True,
                tests_generated=True,
                validation_passed=True,
                pr_created=True,
                incident_report_path="docs/incident_report.json",
            )

    app.dependency_overrides[get_demo_service] = lambda: FakeDemoService()
    try:
        response = TestClient(app).post("/demo/run")
    finally:
        app.dependency_overrides.pop(get_demo_service, None)

    assert response.status_code == 200
    assert response.json()["incident_detected"] is True
    assert response.json()["root_cause_found"] is True
    assert response.json()["patch_generated"] is True
    assert response.json()["tests_generated"] is True
    assert response.json()["validation_passed"] is True
    assert response.json()["pr_created"] is True


def test_demo_run_endpoint_is_disabled_by_default() -> None:
    response = TestClient(app).post("/demo/run")

    assert response.status_code == 403
    assert "SENTINELOS_DEMO_ENABLED=true" in response.json()["detail"]
