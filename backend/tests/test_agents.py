from pathlib import Path
import subprocess
from typing import Any

import pytest

from agents import patch_agent, validation_agent
from agents.dependency_agent import run as run_dependency_agent
from agents.pull_request_agent import run as run_pull_request_agent
from agents.validation_agent import patch_is_consistent
from core.config import Settings
from models import (
    Incident,
    PatchProposal,
    RegressionTestReport,
    ValidationReport,
)
from services.docker_sandbox_service import DockerSandboxService
from services.github_service import GitHubService
from services.ollama_service import OllamaService


class FakeOllama(OllamaService):
    def __init__(self, response: dict[str, Any] | None) -> None:
        super().__init__()
        self.response = response

    def generate_json(self, prompt: str) -> dict[str, Any] | None:
        return self.response


class FakeSandbox(DockerSandboxService):
    def __init__(self, passed: bool) -> None:
        super().__init__()
        self.passed = passed

    def run_tests(
        self,
        repository: Path,
        command: list[str],
        generated_test_code: str,
    ) -> tuple[bool, str]:
        assert repository.is_dir()
        assert command == ["python", "-m", "pytest"]
        assert "assert" in generated_test_code
        return self.passed, "1 passed" if self.passed else "1 failed"


def test_patch_agent_returns_model_diff() -> None:
    generator = patch_agent.PatchGenerationService(
        FakeOllama(
            {
                "file_name": "src/fix.py",
                "proposed_diff": (
                    "--- a/src/fix.py\n+++ b/src/fix.py\n"
                    "@@ -1 +1 @@\n-old\n+new\n"
                ),
                "explanation": "Guard missing input.",
            }
        )
    )
    result = patch_agent.run(
        "request failed",
        "input is not checked",
        {"files": ["src/fix.py"]},
        generator,
    )
    assert result.file_name == "src/fix.py"
    assert result.proposed_diff.startswith("---")
    assert result.applied is False


def test_patch_agent_rejects_path_traversal() -> None:
    generator = patch_agent.PatchGenerationService(
        FakeOllama(
            {
                "file_name": "../secrets.txt",
                "proposed_diff": "diff",
                "explanation": "Invalid path.",
            }
        )
    )
    result = patch_agent.run("failure", "cause", {}, generator)
    assert result.file_name is None


def test_pull_request_agent_uses_the_pushed_fix_branch() -> None:
    class FakePullRequestGitHub(GitHubService):
        def __init__(self) -> None:
            super().__init__()
            self.head: str | None = None

        def create_pull_request(
            self,
            repo: str,
            title: str,
            body: str,
            head: str,
            base: str,
        ) -> dict[str, str]:
            self.head = head
            return {"html_url": "https://github.com/owner/repo/pull/1"}

    github = FakePullRequestGitHub()
    incident = Incident(
        repo="owner/repo",
        branch="main",
        error="Checkout failure",
    )
    patch = PatchProposal(
        status="applied",
        file_name="src/handler.py",
        proposed_diff="--- a/src/handler.py\n+++ b/src/handler.py\n",
        explanation="Fix checkout.",
        applied=True,
    )
    validation = ValidationReport(
        status="passed",
        passed=True,
        report="Validation passed.",
    )

    report = run_pull_request_agent(
        incident,
        patch,
        validation,
        github,
        head_branch="sentinelos/fix-1234",
        changed_files=["src/handler.py", "tests/test_handler.py"],
    )

    assert github.head == "sentinelos/fix-1234"
    assert report.status == "created"
    assert report.changed_files == ["src/handler.py", "tests/test_handler.py"]


def test_patch_consistency_rejects_incorrect_hunk_counts() -> None:
    patch = PatchProposal(
        status="proposed",
        file_name="src/fix.py",
        proposed_diff=(
            "--- a/src/fix.py\n+++ b/src/fix.py\n"
            "@@ -1,2 +1 @@\n-old\n+new\n"
        ),
        explanation="Invalid hunk count.",
    )

    assert patch_is_consistent(patch) is False


def test_patch_consistency_rejects_path_mismatch() -> None:
    patch = PatchProposal(
        status="proposed",
        file_name="src/expected.py",
        proposed_diff=(
            "--- a/src/actual.py\n+++ b/src/actual.py\n"
            "@@ -1 +1 @@\n-old\n+new\n"
        ),
        explanation="The filename does not match the diff.",
    )

    assert patch_is_consistent(patch) is False


def test_dependency_agent_reads_manifests(tmp_path: Path) -> None:
    (tmp_path / "requirements.txt").write_text(
        "fastapi>=0.1\nhttpx==1.0\n", encoding="utf-8"
    )

    result = run_dependency_agent(tmp_path)

    assert result["status"] == "completed"
    assert result["dependencies"]["requirements.txt"] == ["fastapi", "httpx"]


def test_validation_executes_generated_test_and_reports_patch_gate(
    tmp_path: Path,
) -> None:
    patch = PatchProposal(
        status="applied",
        file_name="src/fix.py",
        proposed_diff="--- a/src/fix.py\n+++ b/src/fix.py\n@@ -1 +1 @@\n-old\n+new\n",
        explanation="Proposed change.",
        applied=True,
    )
    regression = RegressionTestReport(
        status="generated",
        generated_test_code="def test_fix():\n    assert True\n",
        expected_result="The test passes.",
    )
    config = Settings(
        github_token=None,
        github_api_url="https://api.github.com",
        ollama_base_url="http://localhost:11434",
        ollama_model="test",
        repository_root=str(tmp_path),
        docker_image="python:3.13-slim",
        test_command="python -m pytest",
        request_timeout_seconds=1,
    )
    result = validation_agent.run(
        patch,
        regression,
        tmp_path,
        config,
        FakeSandbox(passed=True),
    )
    assert result.passed is True
    assert result.checks["tests_passed"] is True
    assert regression.executed is True
    assert regression.status == "passed"


def test_validation_does_not_run_unapplied_patch(
    tmp_path: Path,
) -> None:
    patch = PatchProposal(
        status="proposed",
        proposed_diff="--- a/src/fix.py\n+++ b/src/fix.py\n@@ -1 +1 @@\n-old\n+new\n",
        explanation="Not applied.",
        applied=False,
    )
    regression = RegressionTestReport(
        status="generated",
        generated_test_code="def test_fix():\n    assert True\n",
        expected_result="The test passes.",
    )
    config = Settings(
        github_token=None,
        github_api_url="https://api.github.com",
        ollama_base_url="http://localhost:11434",
        ollama_model="test",
        repository_root=str(tmp_path),
        docker_image="python:3.13-slim",
        test_command="python -m pytest",
        request_timeout_seconds=1,
    )
    result = validation_agent.run(
        patch,
        regression,
        tmp_path,
        config,
        FakeSandbox(passed=True),
    )
    assert result.passed is False
    assert result.checks["patch_applied"] is False
    assert regression.executed is False


def test_validation_reports_failed_sandbox_run(tmp_path: Path) -> None:
    patch = PatchProposal(
        status="applied",
        file_name="src/fix.py",
        proposed_diff=(
            "--- a/src/fix.py\n+++ b/src/fix.py\n@@ -1 +1 @@\n-old\n+new\n"
        ),
        explanation="Applied change.",
        applied=True,
    )
    regression = RegressionTestReport(
        status="generated",
        generated_test_code="def test_fix():\n    assert True\n",
        expected_result="The test passes.",
    )
    config = Settings(
        github_token=None,
        github_api_url="https://api.github.com",
        ollama_base_url="http://localhost:11434",
        ollama_model="test",
        repository_root=str(tmp_path),
        docker_image="python:3.13-slim",
        test_command="python -m pytest",
        request_timeout_seconds=1,
    )
    result = validation_agent.run(
        patch,
        regression,
        tmp_path,
        config,
        FakeSandbox(passed=False),
    )
    assert result.status == "failed"
    assert result.passed is False
    assert regression.status == "failed"


def test_docker_sandbox_invokes_locked_down_container(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: list[str] = []

    def fake_run(
        args: list[str],
        capture_output: bool,
        text: bool,
        timeout: int,
        check: bool,
    ) -> subprocess.CompletedProcess[str]:
        captured.extend(args)
        return subprocess.CompletedProcess(args, 0, "1 passed", "")

    monkeypatch.setattr("services.docker_sandbox_service.subprocess.run", fake_run)
    service = DockerSandboxService()

    passed, output = service.run_tests(
        tmp_path,
        ["python", "-m", "pytest"],
        "def test_regression():\n    assert True\n",
    )

    assert passed is True
    assert output == "1 passed"
    assert captured[captured.index("--network") + 1] == "none"
    assert "--read-only" in captured
    assert "--cap-drop" in captured
