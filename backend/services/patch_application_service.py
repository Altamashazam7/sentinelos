import base64
import logging
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory

from agents import validation_agent
from core.config import Settings, settings
from models import (
    Incident,
    PatchProposal,
    RegressionTestReport,
    ValidationReport,
)
from services.docker_sandbox_service import DockerSandboxService
from services.git_utils import git_command
from services.repository_service import RepositoryService

logger = logging.getLogger(__name__)


class PatchApplicationError(RuntimeError):
    """Raised when a Git operation cannot safely complete."""


@dataclass(slots=True)
class PatchApplicationResult:
    branch: str | None
    validation: ValidationReport
    pushed: bool
    changed_files: list[str]
    message: str | None = None


class PatchApplicationService:
    """Apply and validate a proposed patch in a disposable Git worktree."""

    def __init__(
        self,
        config: Settings = settings,
        repository: RepositoryService | None = None,
        sandbox: DockerSandboxService | None = None,
    ) -> None:
        self._config = config
        self._repository = repository or RepositoryService(config)
        self._sandbox = sandbox or DockerSandboxService(config)

    def apply(
        self,
        incident: Incident,
        patch: PatchProposal,
        regression_test: RegressionTestReport,
    ) -> PatchApplicationResult:
        repository = self._repository.resolve_repository(incident.local_path)
        if repository is None:
            raise ValueError("local_path is required to apply a patch.")
        if not validation_agent.patch_is_consistent(patch):
            return self._blocked(
                "Patch is missing or is not a consistent unified diff."
            )
        changed_files = _changed_files(patch.proposed_diff)
        if not changed_files:
            return self._blocked("The patch does not identify any changed files.")

        branch = _branch_name(incident.id)
        branch_created = False
        commit_created = False
        worktree: Path | None = None
        temp_dir: TemporaryDirectory[str] | None = None
        try:
            self._require_clean_repository(repository)
            self._require_origin(repository)
            self._validate_ref(repository, incident.base_branch)
            self._run_git(
                repository,
                ["fetch", "--no-tags", "origin", incident.base_branch],
                "fetch the requested base branch",
            )
            existing_branch = self._run_git(
                repository,
                ["show-ref", "--verify", "--quiet", f"refs/heads/{branch}"],
                "check the generated branch name",
                check=False,
            )
            if existing_branch.returncode == 0:
                raise PatchApplicationError(
                    "The generated patch branch already exists."
                )
            if existing_branch.returncode != 1:
                raise PatchApplicationError(
                    "Could not check whether the patch branch exists."
                )

            temp_dir = TemporaryDirectory(prefix="sentinelos-worktree-")
            worktree = Path(temp_dir.name) / "checkout"
            self._run_git(
                repository,
                ["worktree", "add", "-b", branch, str(worktree), "FETCH_HEAD"],
                "create an isolated worktree",
            )
            branch_created = True
            _ensure_safe_targets(worktree, changed_files)

            self._run_git(
                worktree,
                ["apply", "--check", "-"],
                "check patch applicability",
                input_text=patch.proposed_diff,
            )
            self._run_git(
                worktree,
                ["apply", "--whitespace=error", "-"],
                "apply the proposed patch",
                input_text=patch.proposed_diff,
            )
            actual_files = self._actual_changed_files(worktree)
            if actual_files != sorted(changed_files):
                raise PatchApplicationError(
                    "The applied changes do not match the files in the proposed patch."
                )

            applied_patch = patch.model_copy(
                update={"status": "applied", "applied": True}
            )
            validation = validation_agent.run(
                applied_patch,
                regression_test,
                worktree,
                self._config,
                self._sandbox,
                verify_worktree=True,
                expected_files=changed_files,
            )
            if not validation.passed:
                return PatchApplicationResult(
                    branch=None,
                    validation=validation,
                    pushed=False,
                    changed_files=changed_files,
                    message=validation.report,
                )

            self._run_git(worktree, ["add", "--", *changed_files], "stage patch files")
            staged_files = self._git_file_list(
                worktree, ["diff", "--cached", "--name-only"]
            )
            if staged_files != sorted(changed_files):
                raise PatchApplicationError(
                    "Staged changes do not match the validated patch."
                )
            message = f"fix: resolve incident {incident.id[:12]}"
            self._run_git(
                worktree,
                [
                    "-c",
                    "user.name=SentinelOS",
                    "-c",
                    "user.email=sentinel-os[bot]@users.noreply.github.com",
                    "commit",
                    "--no-gpg-sign",
                    "-m",
                    message,
                ],
                "commit the validated patch",
            )
            commit_created = True
            try:
                self._run_git(
                    worktree,
                    ["push", "--set-upstream", "origin", branch],
                    "push the validated branch",
                    env=_push_environment(self._config.github_token),
                )
            except PatchApplicationError:
                logger.warning(
                    "Validated patch commit could not be pushed",
                    extra={"incident_id": incident.id, "branch": branch},
                )
                return PatchApplicationResult(
                    branch=branch,
                    validation=validation,
                    pushed=False,
                    changed_files=changed_files,
                    message="Validation passed and the local commit was created, but pushing the branch failed.",
                )
            return PatchApplicationResult(
                branch=branch,
                validation=validation,
                pushed=True,
                changed_files=changed_files,
            )
        except PatchApplicationError as exc:
            logger.warning(
                "Patch application stopped",
                extra={"incident_id": incident.id, "branch": branch},
            )
            return PatchApplicationResult(
                branch=branch if commit_created else None,
                validation=_failed_validation(str(exc)),
                pushed=False,
                changed_files=changed_files,
                message=str(exc),
            )
        finally:
            if worktree is not None:
                try:
                    self._run_git(
                        repository,
                        ["worktree", "remove", "--force", str(worktree)],
                        "remove the temporary worktree",
                        check=False,
                    )
                except PatchApplicationError:
                    logger.warning(
                        "Temporary worktree cleanup failed",
                        extra={"incident_id": incident.id, "branch": branch},
                    )
            if temp_dir is not None:
                temp_dir.cleanup()
            if branch_created and not commit_created:
                try:
                    self._run_git(
                        repository,
                        ["branch", "-D", branch],
                        "remove the unvalidated branch",
                        check=False,
                    )
                    self._run_git(
                        repository,
                        ["worktree", "prune"],
                        "prune removed worktree metadata",
                        check=False,
                    )
                except PatchApplicationError:
                    logger.warning(
                        "Unvalidated branch cleanup failed",
                        extra={"incident_id": incident.id, "branch": branch},
                    )

    def _require_clean_repository(self, repository: Path) -> None:
        self._run_git(
            repository, ["rev-parse", "--show-toplevel"], "locate Git repository"
        )
        status = self._run_git(
            repository,
            ["status", "--porcelain", "--untracked-files=all"],
            "check source repository state",
        )
        if status.stdout.strip():
            raise PatchApplicationError(
                "The configured repository has local changes; commit or remove them before applying a fix."
            )

    def _require_origin(self, repository: Path) -> None:
        self._run_git(
            repository, ["remote", "get-url", "origin"], "check origin remote"
        )

    def _validate_ref(self, repository: Path, ref: str) -> None:
        if (
            not ref
            or self._run_git(
                repository,
                ["check-ref-format", "--branch", ref],
                "validate the requested base branch",
                check=False,
            ).returncode
            != 0
        ):
            raise PatchApplicationError("The requested base branch name is invalid.")

    def _git_file_list(self, repository: Path, args: list[str]) -> list[str]:
        output = self._run_git(repository, args, "inspect changed files").stdout
        return sorted(
            line.replace("\\", "/") for line in output.splitlines() if line.strip()
        )

    def _actual_changed_files(self, repository: Path) -> list[str]:
        tracked = self._git_file_list(repository, ["diff", "--name-only"])
        untracked = self._git_file_list(
            repository,
            ["ls-files", "--others", "--exclude-standard"],
        )
        return sorted(set(tracked).union(untracked))

    @staticmethod
    def _run_git(
        repository: Path,
        args: list[str],
        operation: str,
        *,
        input_text: str | None = None,
        env: dict[str, str] | None = None,
        check: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        try:
            result = subprocess.run(
                git_command(repository, args),
                cwd=repository,
                input=input_text,
                capture_output=True,
                text=True,
                timeout=180,
                check=False,
                env=env,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise PatchApplicationError(
                f"Could not {operation}; verify Git is installed and the operation can complete."
            ) from exc
        if check and result.returncode != 0:
            raise PatchApplicationError(
                f"Could not {operation} (git exit {result.returncode})."
            )
        return result

    @staticmethod
    def _blocked(message: str) -> PatchApplicationResult:
        return PatchApplicationResult(
            branch=None,
            validation=ValidationReport(
                status="blocked",
                passed=False,
                report=message,
                checks={"patch_consistent": False},
            ),
            pushed=False,
            changed_files=[],
            message=message,
        )


def _branch_name(incident_id: str) -> str:
    suffix = re.sub(r"[^A-Za-z0-9]", "", incident_id)[:12].lower()
    if not suffix:
        raise ValueError("Incident ID cannot be used to name a patch branch.")
    return f"sentinelos/fix-{suffix}"


def _changed_files(diff: str) -> list[str]:
    files: set[str] = set()
    lines = diff.splitlines()
    for index, line in enumerate(lines[:-1]):
        if not line.startswith("--- ") or not lines[index + 1].startswith("+++ "):
            continue
        old_path = line[4:].split("\t", maxsplit=1)[0]
        new_path = lines[index + 1][4:].split("\t", maxsplit=1)[0]
        selected = new_path if new_path != "/dev/null" else old_path
        if selected in {"/dev/null", "a/", "b/"}:
            continue
        if selected.startswith(("a/", "b/")):
            selected = selected[2:]
        files.add(selected)
    return sorted(files)


def _ensure_safe_targets(worktree: Path, files: list[str]) -> None:
    root = worktree.resolve()
    for filename in files:
        path = PurePosixPath(filename)
        if (
            path.is_absolute()
            or not path.parts
            or any(
                part in {"", ".", ".."} or part.casefold() == ".git"
                for part in path.parts
            )
            or ":" in path.parts[0]
        ):
            raise PatchApplicationError("The patch contains an unsafe target path.")
        target = root.joinpath(*path.parts)
        try:
            target.resolve(strict=False).relative_to(root)
        except ValueError as exc:
            raise PatchApplicationError(
                "The patch target resolves outside the temporary worktree."
            ) from exc
        current = root
        for part in path.parts:
            current = current / part
            if current.is_symlink():
                raise PatchApplicationError(
                    "The patch cannot target a symbolic link in the repository."
                )


def _failed_validation(message: str) -> ValidationReport:
    return ValidationReport(
        status="failed",
        passed=False,
        report=message,
        checks={"patch_application": False},
    )


def _push_environment(token: str | None) -> dict[str, str] | None:
    if not token:
        return None
    environment = os.environ.copy()
    credential = base64.b64encode(f"x-access-token:{token}".encode()).decode("ascii")
    environment["GIT_CONFIG_COUNT"] = "1"
    environment["GIT_CONFIG_KEY_0"] = "http.extraheader"
    environment["GIT_CONFIG_VALUE_0"] = f"AUTHORIZATION: basic {credential}"
    return environment
