from pathlib import Path
from typing import Any

from commander import IncidentCommander
from core.config import Settings
from models import (
    Incident,
    IncidentStatus,
    PatchProposal,
    RegressionTestReport,
    ValidationReport,
)
from services.docker_sandbox_service import DockerSandboxService
from services.github_service import GitHubService
from services.ollama_service import OllamaService
from services.patch_application_service import (
    PatchApplicationResult,
    PatchApplicationService,
)
from services.patch_generation_service import PatchGenerationService
from services.test_generation_service import RegressionTestGenerator


class FakeGitHub(GitHubService):
    def __init__(self) -> None:
        super().__init__()

    def recent_commits(self, repo: str, branch: str) -> list[dict[str, str]]:
        return [{"sha": "abc123", "message": "Handle incident"}]


class FakeOllama(OllamaService):
    def __init__(self) -> None:
        super().__init__()

    def generate_json(self, prompt: str) -> dict[str, Any]:
        if "root_cause and confidence" in prompt:
            return {"root_cause": "Input is not checked.", "confidence": 0.8}
        if "proposed unified diff" in prompt:
            return {
                "file_name": "src/handler.py",
                "proposed_diff": (
                    "--- a/src/handler.py\n+++ b/src/handler.py\n"
                    "@@ -1 +1 @@\n-old\n+new\n"
                ),
                "explanation": "Validate the input.",
            }
        return {
            "generated_test_code": "def test_missing_value():\n    assert True\n",
            "expected_result": "The missing value is handled.",
        }


class FakeSandbox(DockerSandboxService):
    def __init__(self) -> None:
        super().__init__()

    def run_tests(
        self,
        repository: Path,
        command: list[str],
        generated_test_code: str,
    ) -> tuple[bool, str]:
        return True, "1 passed"


def test_langgraph_workflow_returns_all_agent_results() -> None:
    config = Settings(
        github_token=None,
        github_api_url="https://api.github.com",
        ollama_base_url="http://localhost:11434",
        ollama_model="test",
        repository_root=None,
        docker_image="python:3.13-slim",
        test_command=None,
        request_timeout_seconds=1,
    )
    ollama = FakeOllama()
    commander = IncidentCommander(
        config=config,
        github=FakeGitHub(),
        ollama=ollama,
        sandbox=FakeSandbox(),
        patch_generator=PatchGenerationService(ollama),
        test_generator=RegressionTestGenerator(ollama),
    )

    activity: list[dict[str, Any]] = []
    report = commander.investigate(
        Incident(repo="owner/repo", branch="main", error="Request failed."),
        activity.append,
    )

    assert report.status is IncidentStatus.BLOCKED
    assert [agent.agent for agent in report.agents] == [
        "LogAgent",
        "GitAgent",
        "TestAgent",
        "DependencyAgent",
        "RootCauseAgent",
        "PatchAgent",
        "RegressionTestAgent",
        "ValidationAgent",
        "PullRequestAgent",
    ]
    assert report.patch.proposed_diff.startswith("---")
    assert report.regression_test.generated_test_code
    assert report.pull_request.status == "blocked"
    assert len(activity) == 22
    assert activity[0]["agent"] == "RepositoryService"
    assert activity[1]["status"] == "unavailable"
    assert [event["status"] for event in activity[2:4]] == [
        "running",
        "completed",
    ]
    assert activity[-2]["agent"] == "IncidentReport"


def test_commander_applies_pushed_fix_through_pull_request_agent() -> None:
    class SuccessfulApplication(PatchApplicationService):
        def __init__(self) -> None:
            pass

        def apply(
            self,
            incident: Incident,
            patch: PatchProposal,
            regression_test: RegressionTestReport,
        ) -> PatchApplicationResult:
            return PatchApplicationResult(
                branch="sentinelos/fix-1234",
                validation=ValidationReport(
                    status="passed",
                    passed=True,
                    report="Validation passed.",
                ),
                pushed=True,
                changed_files=["src/handler.py"],
            )

    class PullRequestGitHub(FakeGitHub):
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

    config = Settings(
        github_token=None,
        github_api_url="https://api.github.com",
        ollama_base_url="http://localhost:11434",
        ollama_model="test",
        repository_root=None,
        docker_image="python:3.13-slim",
        test_command=None,
        request_timeout_seconds=1,
    )
    github = PullRequestGitHub()
    commander = IncidentCommander(
        config=config,
        github=github,
        patch_application=SuccessfulApplication(),
    )
    patch = PatchProposal(
        status="proposed",
        file_name="src/handler.py",
        proposed_diff=(
            "--- a/src/handler.py\n+++ b/src/handler.py\n"
            "@@ -1 +1 @@\n-old\n+new\n"
        ),
        explanation="Fix the handler.",
    )
    regression = RegressionTestReport(
        status="generated",
        generated_test_code="def test_fix():\n    assert True\n",
        expected_result="The handler is fixed.",
    )
    result = commander.apply_fix(
        Incident(
            repo="owner/repo",
            branch="main",
            error="Handler fails",
            local_path="C:/repos/repo",
        ),
        patch,
        regression,
        approved=True,
    )

    assert github.head == "sentinelos/fix-1234"
    assert result.ready_for_pr is True
    assert result.validation == "passed"
    assert result.validation_report is not None
    assert result.validation_report.passed
