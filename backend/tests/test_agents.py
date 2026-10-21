import subprocess
from pathlib import Path
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


def test_patch_agent_generates_diff_from_model_snippets() -> None:
    generator = patch_agent.PatchGenerationService(
        FakeOllama(
            {
                "file_name": "src/fix.py",
                "explanation": "Reject a missing input.",
                "old_code": "return value\n",
                "new_code": "if value is None:\n    raise ValueError()\nreturn value\n",
            }
        )
    )
    result = patch_agent.run(
        "request failed",
        "input is not checked",
        {"files": ["src/fix.py"]},
        generator,
        repository_files={"src/fix.py": "return value\n"},
    )
    assert result.file_name == "src/fix.py"
    assert result.proposed_diff.startswith("---")
    assert "+if value is None:" in result.proposed_diff
    assert patch_is_consistent(result)
    assert result.applied is False


def test_patch_generation_prompt_requests_snippets_and_matching_source() -> None:
    class PromptCapturingOllama(FakeOllama):
        def __init__(self) -> None:
            super().__init__(
                {
                    "file_name": "app.py",
                    "explanation": "Reject missing email before lower().",
                    "old_code": 'return {"email": email.lower()}',
                    "new_code": (
                        "if email is None:\n"
                        "    raise HTTPException(\n"
                        "        status_code=422,\n"
                        '        detail="email is required",\n'
                        "    )\n"
                        'return {"email": email.lower()}'
                    ),
                }
            )
            self.prompt = ""

        def generate_json(self, prompt: str) -> dict[str, Any]:
            self.prompt = prompt
            return super().generate_json(prompt)

    ollama = PromptCapturingOllama()
    generator = patch_agent.PatchGenerationService(ollama)

    result = generator.generate(
        "AttributeError: 'NoneType' object has no attribute 'lower'",
        "email is None before lower() is called",
        {"files": ["app.py"]},
        evidence={
            "stack_trace": "AttributeError: 'NoneType' object has no attribute 'lower'",
            "failed_test": "test_missing_email",
        },
        repository_files={"app.py": 'return {"email": email.lower()}'},
    )

    assert result.file_name == "app.py"
    assert result.proposed_diff
    assert "Select exactly one target file" in ollama.prompt
    assert "exact old_code snippet" in ollama.prompt
    assert "new_code replacement" in ollama.prompt
    assert "do not produce a diff" in ollama.prompt
    assert "AttributeError: 'NoneType' object has no attribute 'lower'" in ollama.prompt
    assert "File: app.py\nreturn {\"email\": email.lower()}" in ollama.prompt


def test_patch_generation_builds_consistent_app_py_diff_from_snippets() -> None:
    demo_app = Path(__file__).resolve().parents[2] / "demo-repo" / "app.py"
    original = demo_app.read_text(encoding="utf-8")
    old_code = '    return {"user_id": user_id, "email": email.lower()}'
    new_code = (
        "    if email is None:\n"
        "        raise HTTPException(\n"
        "            status_code=422,\n"
        '            detail="email is required",\n'
        "        )\n"
        '    return {"user_id": user_id, "email": email.lower()}'
    )
    generator = patch_agent.PatchGenerationService(
        FakeOllama(
            {
                "file_name": "app.py",
                "explanation": "Reject missing email before calling lower().",
                "old_code": old_code,
                "new_code": new_code,
            }
        )
    )

    result = generator.generate(
        "email may be missing",
        "email.lower() fails for None",
        {},
        repository_files={"app.py": original},
    )

    assert result.file_name == "app.py"
    assert result.status == "proposed"
    diff_lines = result.proposed_diff.splitlines()
    assert diff_lines[:2] == ["--- a/app.py", "+++ b/app.py"]
    assert result.proposed_diff == (
        "--- a/app.py\n"
        "+++ b/app.py\n"
        "@@ -5,4 +5,9 @@\n"
        " \n"
        " @app.get(\"/profile/{user_id}\")\n"
        " def get_profile(user_id: str, email: str | None = None) -> dict[str, str]:\n"
        "+    if email is None:\n"
        "+        raise HTTPException(\n"
        "+            status_code=422,\n"
        '+            detail="email is required",\n'
        "+        )\n"
        '     return {"user_id": user_id, "email": email.lower()}\n'
    )
    assert "+    if email is None:" in result.proposed_diff
    assert '+            detail="email is required",' in result.proposed_diff
    assert " " + old_code in result.proposed_diff
    assert patch_is_consistent(result)


def test_patch_generation_rejects_ambiguous_old_snippet() -> None:
    generator = patch_agent.PatchGenerationService(
        FakeOllama(
            {
                "file_name": "app.py",
                "explanation": "Update the value.",
                "old_code": "return value\n",
                "new_code": "return fixed_value\n",
            }
        )
    )

    result = generator.generate(
        "failure",
        "wrong value is returned",
        {},
        repository_files={"app.py": "return value\nreturn value\n"},
    )

    assert result.status == "unavailable"
    assert result.proposed_diff == ""
    assert not patch_is_consistent(result)


def test_patch_generation_rejects_overlapping_old_snippet_matches() -> None:
    generator = patch_agent.PatchGenerationService(
        FakeOllama(
            {
                "file_name": "app.py",
                "explanation": "Replace the ambiguous snippet.",
                "old_code": "aba",
                "new_code": "changed",
            }
        )
    )

    result = generator.generate(
        "failure",
        "ambiguous source snippet",
        {},
        repository_files={"app.py": "ababa"},
    )

    assert result.status == "unavailable"
    assert result.proposed_diff == ""


def test_patch_agent_rejects_path_traversal() -> None:
    generator = patch_agent.PatchGenerationService(
        FakeOllama(
            {
                "file_name": "../secrets.txt",
                "explanation": "Do not edit files outside the repository.",
                "old_code": "old",
                "new_code": "changed",
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
            "--- a/src/fix.py\n+++ b/src/fix.py\n" "@@ -1,2 +1 @@\n-old\n+new\n"
        ),
        explanation="Invalid hunk count.",
    )

    assert patch_is_consistent(patch) is False


def test_patch_consistency_rejects_path_mismatch() -> None:
    patch = PatchProposal(
        status="proposed",
        file_name="src/expected.py",
        proposed_diff=(
            "--- a/src/actual.py\n+++ b/src/actual.py\n" "@@ -1 +1 @@\n-old\n+new\n"
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
        proposed_diff=("--- a/src/fix.py\n+++ b/src/fix.py\n@@ -1 +1 @@\n-old\n+new\n"),
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
