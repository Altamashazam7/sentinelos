import subprocess
from pathlib import Path

from core.config import Settings
from models import Incident, PatchProposal, RegressionTestReport
from services.docker_sandbox_service import DockerSandboxService
from services.patch_application_service import PatchApplicationService
from services.repository_service import RepositoryService


class PassingSandbox(DockerSandboxService):
    def __init__(self, passed: bool) -> None:
        super().__init__()
        self.passed = passed

    def run_tests(
        self,
        repository: Path,
        command: list[str],
        generated_test_code: str,
    ) -> tuple[bool, str]:
        assert repository.joinpath("src", "handler.py").read_text() == "new\n"
        assert command == ["python", "-m", "pytest"]
        assert "def test_fix" in generated_test_code
        return self.passed, "tests passed" if self.passed else "test failed"


def _git(repository: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=repository,
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stdout.strip()


def _repository(tmp_path: Path) -> tuple[Path, Path]:
    source = tmp_path / "source"
    remote = tmp_path / "remote.git"
    source.mkdir()
    _git(tmp_path, "init", "--bare", str(remote))
    _git(source, "init", "-b", "main")
    _git(source, "config", "user.name", "SentinelOS test")
    _git(source, "config", "user.email", "test@example.invalid")
    source.joinpath("src").mkdir()
    source.joinpath("src", "handler.py").write_text("old\n", encoding="utf-8")
    _git(source, "add", "src/handler.py")
    _git(source, "commit", "-m", "initial")
    _git(source, "remote", "add", "origin", str(remote))
    _git(source, "push", "-u", "origin", "main")
    return source, remote


def _config(root: Path) -> Settings:
    return Settings(
        github_token=None,
        github_api_url="https://api.github.com",
        ollama_base_url="http://localhost:11434",
        ollama_model="test",
        repository_root=str(root),
        docker_image="test-image",
        test_command="python -m pytest",
        request_timeout_seconds=1,
    )


def _incident(repository: Path) -> Incident:
    return Incident(
        repo="owner/repo",
        branch="main",
        base_branch="main",
        error="Handler returned the old value.",
        local_path=str(repository),
        id="12345678-1234-5678-1234-567812345678",
    )


def _patch() -> PatchProposal:
    return PatchProposal(
        status="proposed",
        file_name="src/handler.py",
        proposed_diff=(
            "--- a/src/handler.py\n"
            "+++ b/src/handler.py\n"
            "@@ -1 +1 @@\n"
            "-old\n"
            "+new\n"
        ),
        explanation="Return the corrected value.",
    )


def _regression_test() -> RegressionTestReport:
    return RegressionTestReport(
        status="generated",
        generated_test_code="def test_fix():\n    assert True\n",
        expected_result="The handler returns the corrected value.",
    )


def test_patch_application_validates_commits_and_pushes_isolated_branch(
    tmp_path: Path,
) -> None:
    source, remote = _repository(tmp_path)
    config = _config(tmp_path)
    service = PatchApplicationService(
        config,
        RepositoryService(config),
        PassingSandbox(passed=True),
    )

    result = service.apply(_incident(source), _patch(), _regression_test())

    assert result.validation.status == "passed"
    assert result.validation.passed
    assert result.pushed
    assert result.branch == "sentinelos/fix-123456781234"
    assert source.joinpath("src", "handler.py").read_text() == "old\n"
    assert (
        subprocess.run(
            [
                "git",
                "--git-dir",
                str(remote),
                "show",
                f"{result.branch}:src/handler.py",
            ],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        == "new\n"
    )
    worktrees = _git(source, "worktree", "list", "--porcelain")
    assert worktrees.count("worktree ") == 1


def test_patch_application_does_not_commit_or_push_when_tests_fail(
    tmp_path: Path,
) -> None:
    source, remote = _repository(tmp_path)
    config = _config(tmp_path)
    service = PatchApplicationService(
        config,
        RepositoryService(config),
        PassingSandbox(passed=False),
    )

    result = service.apply(_incident(source), _patch(), _regression_test())

    assert result.validation.status == "failed"
    assert result.validation.passed is False
    assert result.pushed is False
    assert result.branch is None
    remote_branch = subprocess.run(
        [
            "git",
            "--git-dir",
            str(remote),
            "show-ref",
            "--verify",
            "refs/heads/sentinelos/fix-123456781234",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert remote_branch.returncode != 0
    assert source.joinpath("src", "handler.py").read_text() == "old\n"
