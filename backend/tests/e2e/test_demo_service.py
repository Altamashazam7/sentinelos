import json
import subprocess
import sys
from pathlib import Path

import pytest

from agents.validation_agent import patch_is_consistent
from core.config import Settings
from models import (
    AgentResult,
    ApplyFixResponse,
    Incident,
    IncidentReport,
    IncidentStatus,
    PatchProposal,
    PullRequestReport,
    RegressionTestReport,
    ValidationReport,
)
from services.demo_service import DemoService, _incident_failure_evidence
from services.repository_service import RepositoryService


def test_broken_demo_endpoint_reproduces_the_incident() -> None:
    project_root = Path(__file__).resolve().parents[3]
    demo_repository = project_root / "demo-repo"

    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=demo_repository,
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )

    output = f"{result.stdout}\n{result.stderr}"
    assert result.returncode != 0
    assert "AttributeError" in output
    assert "NoneType" in output
    assert "lower" in output


def test_checked_in_incident_report_contains_valid_patch() -> None:
    project_root = Path(__file__).resolve().parents[3]
    report = json.loads(
        (project_root / "docs" / "incident_report.json").read_text(encoding="utf-8")
    )
    assert set(report) == {
        "incident",
        "root_cause",
        "patch",
        "tests",
        "validation",
        "pr",
    }
    assert patch_is_consistent(PatchProposal(**report["patch"]))


def test_demo_fixture_can_build_a_recent_regression_diff(tmp_path: Path) -> None:
    project_root = Path(__file__).resolve().parents[3]
    demo_fixture = project_root / "demo-repo"
    demo_repository = tmp_path / "demo-repo"
    demo_repository.mkdir()
    broken_source = (demo_fixture / "app.py").read_text(encoding="utf-8")
    healthy_source = broken_source.replace(
        '    return {"user_id": user_id, "email": email.lower()}',
        "    if email is None:\n"
        '        raise HTTPException(status_code=422, detail="email is required")\n'
        '    return {"user_id": user_id, "email": email.lower()}',
    )
    assert healthy_source != broken_source
    app_file = demo_repository / "app.py"
    app_file.write_text(healthy_source, encoding="utf-8")
    for arguments in (
        ["init", "-b", "main"],
        ["config", "user.name", "SentinelOS Test"],
        ["config", "user.email", "test@example.invalid"],
        ["add", "app.py"],
        ["commit", "-m", "healthy baseline"],
    ):
        subprocess.run(
            ["git", *arguments],
            cwd=demo_repository,
            capture_output=True,
            check=True,
        )
    app_file.write_text(broken_source, encoding="utf-8")
    for arguments in (["add", "app.py"], ["commit", "-m", "introduce regression"]):
        subprocess.run(
            ["git", *arguments],
            cwd=demo_repository,
            capture_output=True,
            check=True,
        )

    diff = RepositoryService().git_diff(demo_repository, "HEAD~1", "HEAD")

    assert "email.lower()" in diff
    assert "if email is None" in diff


def test_demo_incident_uses_compact_failure_evidence() -> None:
    output = (
        "captured test logs\n"
        "_________________________ test_profile_requires_email _________________________\n"
        '>       response = client.get("/profile/demo-user")\n'
        "E       AttributeError: 'NoneType' object has no attribute 'lower'\n"
        "app.py:8: AttributeError: 'NoneType' object has no attribute 'lower'\n"
        "=========================== short test summary info ===========================\n"
        "FAILED tests/test_app.py::test_missing_email - AttributeError\n"
    )

    logs, stack_trace, failed_test = _incident_failure_evidence(output)

    assert logs.startswith("captured test logs")
    assert "captured test logs" not in stack_trace
    assert "AttributeError" in stack_trace
    assert failed_test == (
        "FAILED tests/test_app.py::test_missing_email - AttributeError"
    )


def test_demo_service_runs_the_gated_workflow_and_writes_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository_path = tmp_path / "demo-repo"
    repository_path.mkdir()
    report_path = tmp_path / "incident_report.json"
    config = Settings(
        github_token="test-token",
        github_api_url="https://api.github.test",
        ollama_base_url="http://localhost:11434",
        ollama_model="qwen2.5-coder:7b",
        repository_root=str(tmp_path),
        docker_image="sentinel-test",
        test_command="python -m pytest",
        request_timeout_seconds=1,
        demo_enabled=True,
        demo_repository_slug="owner/demo",
        demo_repository_path=str(repository_path),
    )
    report = IncidentReport(
        incident=Incident(
            repo="owner/demo",
            branch="main",
            error="Missing email causes an endpoint crash.",
        ),
        status=IncidentStatus.BLOCKED,
        agents=[
            AgentResult(
                agent="RootCauseAgent",
                status="completed",
                finding="The optional email is dereferenced without a None guard.",
                details={
                    "confidence": 0.95,
                    "evidence": ["The stack trace fails at email.lower()."],
                },
            )
        ],
        patch=PatchProposal(
            status="proposed",
            file_name="app.py",
            proposed_diff="--- a/app.py\n+++ b/app.py\n@@ -1 +1,2 @@\n-old\n+if email is None: raise HTTPException(422)\n+new\n",
            explanation="Reject missing email before normalizing it.",
        ),
        regression_test=RegressionTestReport(
            status="generated",
            generated_test_code=(
                "def test_missing_email():\n"
                "    assert client.get('/profile/demo').status_code == 422\n"
            ),
            expected_result="A missing email returns HTTP 422.",
        ),
        validation=ValidationReport(
            status="blocked",
            passed=False,
            report="Awaiting patch application.",
        ),
        pull_request=PullRequestReport(
            status="blocked",
            title="Fix missing email",
            description="Awaiting patch application.",
        ),
    )

    class FakeRepository:
        def resolve_repository(self, requested_path: str | None) -> Path:
            assert requested_path == str(repository_path)
            return repository_path

        def git_diff(
            self,
            path: Path,
            base: str = "HEAD",
            target: str | None = None,
        ) -> str:
            assert path == repository_path
            assert (base, target) == ("HEAD~1", "HEAD")
            return "diff --git a/app.py b/app.py"

    class FakeCommander:
        def investigate(self, incident: Incident) -> IncidentReport:
            assert "NoneType" in (incident.stack_trace or "")
            assert "diff --git" in (incident.git_diff or "")
            return report

        def apply_fix(
            self,
            incident: Incident,
            patch: PatchProposal,
            regression_test: RegressionTestReport,
            *,
            approved: bool,
            root_cause: str,
        ) -> ApplyFixResponse:
            assert approved is True
            assert root_cause.startswith("The optional email")
            assert patch.proposed_diff
            assert regression_test.generated_test_code
            return ApplyFixResponse(
                branch="sentinelos/demo-fix",
                validation="passed",
                ready_for_pr=True,
                pull_request_url="https://github.com/owner/demo/pull/1",
                validation_report=ValidationReport(
                    status="passed",
                    passed=True,
                    report="Sandbox checks passed.",
                    checks={"tests_passed": True},
                ),
                pull_request_report=PullRequestReport(
                    status="created",
                    title="Fix missing email",
                    description="Validate email before normalizing it.",
                    changed_files=["app.py"],
                    url="https://github.com/owner/demo/pull/1",
                ),
            )

    monkeypatch.setattr(
        "services.demo_service.subprocess.run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0],
            1,
            stdout="AttributeError: 'NoneType' object has no attribute 'lower'",
            stderr="",
        ),
    )
    service = DemoService(
        config,
        commander=FakeCommander(),
        repository=FakeRepository(),
        report_path=report_path,
    )

    result = service.run()

    assert result.incident_detected is True
    assert result.root_cause_found is True
    assert result.patch_generated is True
    assert result.tests_generated is True
    assert result.validation_passed is True
    assert result.pr_created is True
    saved = json.loads(report_path.read_text(encoding="utf-8"))
    assert set(saved) == {
        "incident",
        "root_cause",
        "patch",
        "tests",
        "validation",
        "pr",
    }
    assert saved["pr"]["url"] == "https://github.com/owner/demo/pull/1"
    assert saved["pr"]["title"] == "Fix missing email"
