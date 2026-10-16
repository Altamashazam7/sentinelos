from fastapi.testclient import TestClient
import pytest

from main import app
from api.routes import (
    get_architecture_evolution_service,
    get_incident_analysis_service,
    get_incident_commander,
)
from models import (
    Incident,
    IncidentAnalysisResponse,
    ApplyFixResponse,
    ArchitectureEvolutionResponse,
    IncidentReport,
    IncidentStatus,
    PatchProposal,
    PullRequestReport,
    RegressionTestReport,
    ValidationReport,
)

client = TestClient(app)


def test_health_and_agents_endpoints() -> None:
    health_response = client.get("/health")
    agents_response = client.get("/agents")

    assert health_response.status_code == 200
    assert health_response.json()["service"] == "SentinelOS"
    assert agents_response.status_code == 200
    assert agents_response.json()[0]["name"] == "LogAgent"
    names = [agent["name"] for agent in agents_response.json()]
    assert "PullRequestAgent" in names
    assert names[-1] == "ArchitectureAgent"


def test_incident_request_schema_rejects_empty_error() -> None:
    response = client.post(
        "/incidents",
        json={"repo": "owner/repo", "branch": "main", "error": "   "},
    )

    assert response.status_code == 422


def test_post_incidents_returns_workflow_report(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report = IncidentReport(
        incident=Incident(repo="owner/repo", branch="main", error="failure"),
        status=IncidentStatus.BLOCKED,
        agents=[],
        patch=PatchProposal(status="unavailable", explanation="Model unavailable."),
        regression_test=RegressionTestReport(
            status="unavailable",
            expected_result="The failure should be resolved.",
        ),
        validation=ValidationReport(
            status="blocked",
            passed=False,
            report="Patch proposal unavailable.",
            checks={},
        ),
        pull_request=PullRequestReport(
            status="blocked",
            title="Fix incident",
            description="PR unavailable.",
            reason="Validation blocked.",
        ),
    )
    monkeypatch.setattr(
        "api.routes.incident_service.handle",
        lambda incident: report,
    )

    response = client.post(
        "/incidents",
        json={"repo": "owner/repo", "branch": "main", "error": "failure"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "blocked"
    assert response.json()["pull_request"]["status"] == "blocked"


def test_incident_replay_websocket_streams_agent_events_and_report() -> None:
    class ReplayCommander:
        def investigate(self, incident, activity_callback=None):
            assert incident.repo == "owner/repo"
            assert activity_callback is not None
            activity_callback(
                {
                    "type": "agent_activity",
                    "agent": "RootCauseAgent",
                    "stage": "root_cause_agent",
                    "status": "running",
                    "message": "RootCauseAgent started.",
                }
            )
            activity_callback(
                {
                    "type": "agent_activity",
                    "agent": "RootCauseAgent",
                    "stage": "root_cause_agent",
                    "status": "completed",
                    "message": "Missing input guard.",
                    "data": {
                        "root_cause": "Missing input guard.",
                        "confidence": 0.9,
                        "evidence": ["The stack trace points to the failing call."],
                    },
                }
            )
            return IncidentReport(
                incident=incident,
                status=IncidentStatus.BLOCKED,
                agents=[],
                patch=PatchProposal(
                    status="unavailable",
                    explanation="Patch generation is disabled in this test.",
                ),
                regression_test=RegressionTestReport(
                    status="unavailable",
                    expected_result="A regression test should cover the failure.",
                ),
                validation=ValidationReport(
                    status="blocked",
                    passed=False,
                    report="No patch was generated.",
                ),
                pull_request=PullRequestReport(
                    status="blocked",
                    title="Fix incident",
                    description="Validation is required.",
                ),
            )

    app.dependency_overrides[get_incident_commander] = lambda: ReplayCommander()
    try:
        with TestClient(app).websocket_connect(
            "/ws/incidents/replay"
        ) as websocket:
            websocket.send_json(
                {
                    "repo": "owner/repo",
                    "branch": "main",
                    "error": "A missing input crashes the endpoint.",
                }
            )
            events = [websocket.receive_json() for _ in range(3)]
    finally:
        app.dependency_overrides.pop(get_incident_commander, None)

    assert [event["type"] for event in events] == [
        "agent_activity",
        "agent_activity",
        "complete",
    ]
    assert events[0]["status"] == "running"
    assert events[1]["data"]["confidence"] == 0.9
    assert events[2]["report"]["status"] == "blocked"


def test_analyze_incident_endpoint_returns_analysis(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeAnalysisService:
        def analyze(self, request):
            assert request.logs == "ValueError: bad input"
            return IncidentAnalysisResponse(
                root_cause="Input validation is missing.",
                patch="--- a/app.py\n+++ b/app.py",
                generated_tests="def test_bad_input():\n    assert True\n",
                edge_cases=["empty input"],
            )

    app.dependency_overrides[get_incident_analysis_service] = (
        lambda: FakeAnalysisService()
    )
    try:
        response = client.post(
            "/incident/analyze",
            json={"logs": "ValueError: bad input"},
        )
    finally:
        app.dependency_overrides.pop(get_incident_analysis_service, None)

    assert response.status_code == 200
    assert response.json()["root_cause"] == "Input validation is missing."
    assert response.json()["edge_cases"] == ["empty input"]


def test_analyze_incident_requires_at_least_one_evidence_field() -> None:
    response = client.post("/incident/analyze", json={})

    assert response.status_code == 422


def test_apply_fix_endpoint_returns_review_gate_result() -> None:
    class FakeCommander:
        def apply_fix(
            self,
            incident,
            patch,
            regression_test,
            *,
            approved,
            root_cause,
        ):
            assert incident.local_path == "C:/repos/demo"
            assert patch.proposed_diff.startswith("---")
            assert regression_test.generated_test_code.startswith("def test_")
            assert approved is True
            assert root_cause == "Input validation is missing."
            return ApplyFixResponse(
                branch="sentinelos/fix-123",
                validation="passed",
                ready_for_pr=True,
            )

    app.dependency_overrides[get_incident_commander] = lambda: FakeCommander()
    try:
        response = client.post(
            "/incident/apply-fix",
            json={
                "incident": {
                    "repo": "owner/repo",
                    "branch": "main",
                    "base_branch": "main",
                    "error": "failure",
                    "local_path": "C:/repos/demo",
                },
                "patch": {
                    "status": "proposed",
                    "file_name": "src/handler.py",
                    "proposed_diff": (
                        "--- a/src/handler.py\n+++ b/src/handler.py\n"
                        "@@ -1 +1 @@\n-old\n+new\n"
                    ),
                    "explanation": "Fix the handler.",
                },
                "regression_test": {
                    "status": "generated",
                    "generated_test_code": "def test_fix():\n    assert True\n",
                    "expected_result": "The handler returns the fixed result.",
                },
                "root_cause": "Input validation is missing.",
                "approved": True,
            },
        )
    finally:
        app.dependency_overrides.pop(get_incident_commander, None)

    assert response.status_code == 200
    assert response.json() == {
        "branch": "sentinelos/fix-123",
        "validation": "passed",
        "ready_for_pr": True,
        "pull_request_url": None,
        "message": None,
        "validation_report": None,
        "pull_request_report": None,
    }


def test_apply_fix_requires_explicit_review_approval() -> None:
    response = client.post(
        "/incident/apply-fix",
        json={
            "incident": {
                "repo": "owner/repo",
                "branch": "main",
                "error": "failure",
                "local_path": "C:/repos/demo",
            },
            "patch": {
                "status": "proposed",
                "explanation": "A proposed fix.",
            },
            "regression_test": {
                "status": "generated",
                "expected_result": "The test passes.",
            },
            "approved": False,
        },
    )

    assert response.status_code == 422


def test_architecture_evolution_endpoint_returns_recommendations() -> None:
    class FakeArchitectureService:
        def evolve(self, request):
            assert request.repo == "owner/repo"
            return ArchitectureEvolutionResponse(
                architecture_risks=["Repeated checkout failures."],
                refactoring_suggestions=["RFC: isolate checkout validation."],
                cost_optimisations=["Cache repository metadata."],
            )

    app.dependency_overrides[get_architecture_evolution_service] = (
        lambda: FakeArchitectureService()
    )
    try:
        response = client.post(
            "/incident/evolve",
            json={"repo": "owner/repo", "focus": "checkout reliability"},
        )
    finally:
        app.dependency_overrides.pop(get_architecture_evolution_service, None)

    assert response.status_code == 200
    assert response.json() == {
        "architecture_risks": ["Repeated checkout failures."],
        "refactoring_suggestions": ["RFC: isolate checkout validation."],
        "cost_optimisations": ["Cache repository metadata."],
    }


def test_architecture_evolution_requires_repository_context() -> None:
    response = client.post("/incident/evolve", json={})

    assert response.status_code == 422
