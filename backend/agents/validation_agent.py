import ast
import re
import subprocess
from pathlib import Path
from shlex import split

from core.config import Settings, settings
from models import PatchProposal, RegressionTestReport, ValidationReport
from services.docker_sandbox_service import DockerSandboxService


def run(
    patch: PatchProposal,
    regression_test: RegressionTestReport,
    repository_path: Path | None,
    config: Settings = settings,
    sandbox: DockerSandboxService | None = None,
    *,
    verify_worktree: bool = False,
    expected_files: list[str] | None = None,
) -> ValidationReport:
    checks = {
        "patch_generated": bool(patch.proposed_diff.strip()),
        "patch_consistent": patch_is_consistent(patch),
        "regression_test_generated": bool(regression_test.generated_test_code.strip()),
        "regression_test_syntax_valid": _test_code_is_valid(
            regression_test.generated_test_code
        ),
        "patch_applied": patch.applied and patch.status == "applied",
        "repository_available": repository_path is not None,
        "test_runner_configured": bool(config.test_command),
        "worktree_changes_valid": (
            _worktree_changes_are_valid(repository_path, expected_files)
            if verify_worktree and repository_path is not None
            else not verify_worktree
        ),
    }
    output: str | None = None
    if all(checks.values()):
        assert repository_path is not None
        test_command = split(config.test_command) if config.test_command else []
        passed, output = (sandbox or DockerSandboxService(config)).run_tests(
            repository_path,
            test_command,
            regression_test.generated_test_code,
        )
        checks["tests_passed"] = passed
        regression_test.executed = True
        regression_test.output = output
        regression_test.status = "passed" if passed else "failed"
    else:
        checks["tests_passed"] = False
        regression_test.executed = False

    passed_validation = all(checks.values())
    if passed_validation:
        status = "passed"
        report = "Patch and generated regression test passed in the configured Docker sandbox."
    elif regression_test.executed:
        status = "failed"
        report = "Validation failed: " + ", ".join(
            name for name, check in checks.items() if not check
        )
    else:
        status = "blocked"
        report = "Validation blocked: " + ", ".join(
            name for name, check in checks.items() if not check
        )
    return ValidationReport(
        status=status,
        passed=passed_validation,
        report=report,
        checks=checks,
    )


def _worktree_changes_are_valid(
    repository_path: Path,
    expected_files: list[str] | None,
) -> bool:
    if not expected_files:
        return False
    try:
        changed = subprocess.run(
            ["git", "diff", "--name-only"],
            cwd=repository_path,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        untracked = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard"],
            cwd=repository_path,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        whitespace = subprocess.run(
            ["git", "diff", "--check"],
            cwd=repository_path,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    actual_files = sorted(
        {
            line.replace("\\", "/")
            for line in (*changed.stdout.splitlines(), *untracked.stdout.splitlines())
            if line.strip()
        }
    )
    return (
        changed.returncode == 0
        and untracked.returncode == 0
        and whitespace.returncode == 0
        and actual_files == sorted(expected_files)
    )


def patch_is_consistent(patch: PatchProposal) -> bool:
    """Check unified-diff headers, paths, and hunk line counts."""
    lines = patch.proposed_diff.splitlines()
    if not lines or not any(line.startswith("--- ") for line in lines):
        return False
    files: list[tuple[str, str]] = []
    hunk_index = 0
    while hunk_index < len(lines):
        if not lines[hunk_index].startswith("--- "):
            hunk_index += 1
            continue
        if hunk_index + 1 >= len(lines) or not lines[hunk_index + 1].startswith("+++ "):
            return False
        old_path = lines[hunk_index][4:].split("\t", maxsplit=1)[0]
        new_path = lines[hunk_index + 1][4:].split("\t", maxsplit=1)[0]
        for path in (old_path, new_path):
            if path != "/dev/null" and (
                path.startswith("/") or "\\" in path or ".." in Path(path).parts
            ):
                return False
        files.append((old_path, new_path))
        hunk_index += 2
        hunks_in_file = 0
        while hunk_index < len(lines) and not lines[hunk_index].startswith("--- "):
            if not lines[hunk_index].startswith("@@ "):
                hunk_index += 1
                continue
            match = re.match(
                r"^@@ -\d+(?:,(\d+))? \+\d+(?:,(\d+))? @@",
                lines[hunk_index],
            )
            if match is None:
                return False
            old_expected = int(match.group(1) or "1")
            new_expected = int(match.group(2) or "1")
            old_seen = 0
            new_seen = 0
            hunk_index += 1
            while hunk_index < len(lines):
                line = lines[hunk_index]
                if line.startswith(("@@ ", "--- ")):
                    break
                if line.startswith(" "):
                    old_seen += 1
                    new_seen += 1
                elif line.startswith("-") and not line.startswith("--- "):
                    old_seen += 1
                elif line.startswith("+") and not line.startswith("+++ "):
                    new_seen += 1
                elif line.startswith("\\"):
                    pass
                else:
                    return False
                hunk_index += 1
            if (old_seen, new_seen) != (old_expected, new_expected):
                return False
            hunks_in_file += 1
        if hunks_in_file == 0:
            return False
    if not files:
        return False
    return all(
        old_path == "/dev/null"
        or new_path == "/dev/null"
        or old_path.removeprefix("a/") == new_path.removeprefix("b/")
        for old_path, new_path in files
    ) and (
        patch.file_name is None
        or len(files) == 1
        and patch.file_name.replace("\\", "/")
        == (files[0][1] if files[0][1] != "/dev/null" else files[0][0])
        .removeprefix("a/")
        .removeprefix("b/")
    )


def _test_code_is_valid(code: str) -> bool:
    if not code.strip():
        return False
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return False
    return any(
        isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("test_")
        for node in ast.walk(tree)
    )
