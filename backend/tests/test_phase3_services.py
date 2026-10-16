from pathlib import Path
import subprocess
from typing import Any

import httpx
import pytest

from agents.architecture_agent import run as run_architecture_agent
from core.config import Settings
from models import (
    AgentResult,
    Incident,
    IncidentReport,
    IncidentStatus,
    PatchProposal,
    PullRequestReport,
    RegressionTestReport,
    ValidationReport,
)
from services.github_service import GitHubService
from services.memory_service import MemoryService
from services.ollama_service import OllamaService
from services.repository_service import RepositoryService


def _config(
    tmp_path: Path,
    *,
    token: str | None = None,
    model: str = "qwen2.5-coder:7b",
) -> Settings:
    return Settings(
        github_token=token,
        github_api_url="https://api.github.test",
        ollama_base_url="http://localhost:11434",
        ollama_model=model,
        repository_root=str(tmp_path),
        docker_image="sentinel-test",
        test_command="python -m pytest",
        request_timeout_seconds=1,
        memory_database_path=str(tmp_path / "memory.sqlite3"),
    )


def _git(repository: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repository,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def test_repository_service_reads_files_and_inspects_git(tmp_path: Path) -> None:
    repository = tmp_path / "repo"
    repository.mkdir()
    _git(repository, "init", "-b", "main")
    _git(repository, "config", "user.name", "Test")
    _git(repository, "config", "user.email", "test@example.invalid")
    source = repository / "module.py"
    source.write_text("value = 1\n", encoding="utf-8")
    _git(repository, "add", "module.py")
    _git(repository, "commit", "-m", "initial")
    source.write_text("value = 2\n", encoding="utf-8")
    (repository / "untracked.py").write_text("pass\n", encoding="utf-8")

    service = RepositoryService(_config(tmp_path))

    assert service.read_files(repository, ["module.py"]) == {
        "module.py": "value = 2\n"
    }
    assert "value = 2" in service.git_diff(repository)
    assert service.git_history(repository)[0]["message"] == "initial"
    assert service.recent_commits(repository, limit=1)[0]["sha"]
    assert service.find_changed_files(repository) == ["module.py", "untracked.py"]
    with pytest.raises(ValueError):
        service.read_files(repository, ["../outside.txt"])


def test_github_service_uses_rest_git_data_operations(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _config(tmp_path, token="test-token")
    service = GitHubService(config)
    responses = [
        {"object": {"sha": "base-sha"}},
        {"ref": "refs/heads/feature"},
        {"object": {"sha": "base-sha"}},
        {"tree": {"sha": "base-tree"}},
        {"sha": "blob-sha"},
        {"sha": "tree-sha"},
        {"sha": "commit-sha"},
        {"object": {"sha": "commit-sha"}},
        {"html_url": "https://github.com/owner/repo/pull/1"},
    ]
    requests: list[tuple[str, str, dict[str, Any]]] = []

    def fake_request(
        method: str,
        url: str,
        *,
        headers: dict[str, str],
        timeout: float,
        **kwargs: Any,
    ) -> httpx.Response:
        requests.append((method, url, kwargs))
        assert headers["Authorization"] == "Bearer test-token"
        return httpx.Response(
            200,
            json=responses.pop(0),
            request=httpx.Request(method, url),
        )

    monkeypatch.setattr("services.github_service.httpx.request", fake_request)

    assert service.create_branch("owner/repo", "feature", "main")["ref"]
    commit = service.create_commit(
        "owner/repo",
        "feature",
        {"src/module.py": "value = 2\n"},
        "Update module",
    )
    assert commit["sha"] == "commit-sha"
    assert service.push_branch("owner/repo", "feature", "commit-sha")[
        "object"
    ]["sha"] == "commit-sha"
    pull_request = service.create_pull_request(
        "owner/repo",
        "Fix issue",
        "Validated change.",
        "feature",
        "main",
    )
    assert pull_request["html_url"].endswith("/pull/1")
    assert [request[0] for request in requests] == [
        "GET",
        "POST",
        "GET",
        "GET",
        "POST",
        "POST",
        "POST",
        "PATCH",
        "POST",
    ]


def test_github_write_operations_require_credentials(tmp_path: Path) -> None:
    service = GitHubService(_config(tmp_path))

    with pytest.raises(RuntimeError, match="GITHUB_TOKEN"):
        service.create_branch("owner/repo", "feature", "main")


def test_memory_service_records_and_finds_prior_incident(tmp_path: Path) -> None:
    service = MemoryService(_config(tmp_path))
    incident = Incident(
        repo="owner/repo",
        branch="main",
        error="Checkout crashes when customer email is missing",
        id="incident-1",
    )
    report = IncidentReport(
        incident=incident,
        status=IncidentStatus.BLOCKED,
        agents=[
            AgentResult(
                agent="RootCauseAgent",
                status="completed",
                finding="Checkout dereferences a missing email.",
            )
        ],
        patch=PatchProposal(
            status="proposed",
            file_name="checkout.py",
            proposed_diff="diff",
            explanation="Guard missing email.",
        ),
        regression_test=RegressionTestReport(
            status="generated",
            generated_test_code="def test_missing_email(): pass",
            expected_result="Missing email is handled.",
        ),
        validation=ValidationReport(
            status="blocked",
            passed=False,
            report="Needs application.",
        ),
        pull_request=PullRequestReport(
            status="blocked",
            title="Fix checkout",
            description="Not applied.",
        ),
    )

    service.record(incident, report)

    matches = service.find_similar(
        "owner/repo",
        "Checkout crashes when customer email is missing",
    )
    assert matches
    assert matches[0]["root_cause"] == "Checkout dereferences a missing email."
    assert matches[0]["generated_tests"] == "def test_missing_email(): pass"
    assert len(service.recent_incidents("owner/repo")) == 1


def test_ollama_reports_supported_model_families(tmp_path: Path) -> None:
    assert OllamaService(_config(tmp_path, model="qwen2.5-coder:7b")).model_supported
    assert OllamaService(_config(tmp_path, model="deepseek-r1:8b")).model_supported
    assert OllamaService(_config(tmp_path, model="llama3.1:8b")).model_supported
    assert not OllamaService(_config(tmp_path, model="unknown:latest")).model_supported


def test_ollama_retries_transient_server_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def fake_post(url: str, **kwargs: Any) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(
                503,
                request=httpx.Request("POST", url),
            )
        return httpx.Response(
            200,
            json={"response": "Root cause identified."},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr("services.ollama_service.httpx.post", fake_post)
    monkeypatch.setattr("services.ollama_service.time.sleep", lambda _: None)

    assert OllamaService(_config(tmp_path)).generate("Analyze this incident.") == (
        "Root cause identified."
    )
    assert calls == 2


def test_architecture_agent_returns_typed_recommendations() -> None:
    class FakeOllama(OllamaService):
        def __init__(self) -> None:
            pass

        def generate_json(self, prompt: str) -> dict[str, Any]:
            assert "recurring incident memory" in prompt
            return {
                "architecture_risks": ["Incidents repeat in checkout."],
                "refactoring_suggestions": ["RFC: isolate checkout validation."],
                "cost_optimisations": ["Cache unchanged repository metadata."],
            }

    result = run_architecture_agent(
        {"available": True, "files": ["checkout.py"]},
        [{"message": "Fix checkout crash"}],
        [{"root_cause": "Missing email check"}],
        "review checkout",
        FakeOllama(),
    )

    assert result.architecture_risks == ["Incidents repeat in checkout."]
    assert result.refactoring_suggestions == ["RFC: isolate checkout validation."]
    assert result.cost_optimisations == ["Cache unchanged repository metadata."]
