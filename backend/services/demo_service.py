import json
import logging
import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol

from commander import get_commander
from core.config import Settings, settings
from models import (
    ApplyFixResponse,
    DemoRunResponse,
    Incident,
    IncidentReport,
    PatchProposal,
    RegressionTestReport,
)
from services.repository_service import RepositoryService

logger = logging.getLogger(__name__)
_EXPECTED_FAILURE = ("attributeerror", "nonetype", "lower")
_MAX_TEST_OUTPUT = 20_000
_MAX_INCIDENT_LOGS = 2_000
_MAX_STACK_TRACE = 5_000
_MAX_FAILED_TEST = 2_000


class DemoCommander(Protocol):
    def investigate(self, incident: Incident) -> IncidentReport: ...

    def apply_fix(
        self,
        incident: Incident,
        patch: PatchProposal,
        regression_test: RegressionTestReport,
        *,
        approved: bool,
        root_cause: str = "",
    ) -> ApplyFixResponse: ...


class DemoRepository(Protocol):
    def resolve_repository(self, requested_path: str | None) -> Path | None: ...

    def git_diff(
        self,
        repository: Path,
        base: str = "HEAD",
        target: str | None = None,
    ) -> str: ...


class DemoDisabledError(RuntimeError):
    """Raised when the explicitly opt-in demo endpoint is disabled."""


class DemoService:
    """Run the disposable repository through investigation, validation, and PR."""

    def __init__(
        self,
        config: Settings = settings,
        commander: DemoCommander | None = None,
        repository: DemoRepository | None = None,
        incident_handler: Callable[[Incident], IncidentReport] | None = None,
        report_path: Path | None = None,
    ) -> None:
        self._config = config
        self._commander = commander or get_commander()
        self._repository = repository or RepositoryService(config)
        self._incident_handler = incident_handler or self._commander.investigate
        project_root = Path(__file__).resolve().parents[2]
        self._repository_path = config.demo_repository_path or str(
            project_root / "demo-repo"
        )
        self._report_path = report_path or project_root / "docs" / "incident_report.json"

    def run(self) -> DemoRunResponse:
        if not self._config.demo_enabled:
            raise DemoDisabledError(
                "Demo mode is disabled. Set SENTINELOS_DEMO_ENABLED=true "
                "for a dedicated disposable demo checkout."
            )
        if not self._config.demo_repository_slug:
            raise ValueError(
                "Set SENTINELOS_DEMO_REPOSITORY to the disposable GitHub "
                "repository owner/name."
            )

        repository = self._repository.resolve_repository(self._repository_path)
        if repository is None:
            raise ValueError("The configured demo checkout is unavailable.")

        baseline_exit, baseline = self._run_baseline_tests(repository)
        if baseline_exit == 0 or not _is_expected_failure(baseline):
            report = _reproduction_failure(
                self._config.demo_repository_slug,
                repository,
                baseline,
            )
            self._write_report(report)
            return DemoRunResponse(
                incident_detected=False,
                root_cause_found=False,
                patch_generated=False,
                tests_generated=False,
                validation_passed=False,
                pr_created=False,
                incident_report_path=self._report_path.as_posix(),
                message=(
                    "The demo's expected missing-email failure was not reproduced. "
                    "See incident_report.json for the test output."
                ),
            )

        try:
            git_diff = self._repository.git_diff(repository, "HEAD~1", "HEAD")
        except RuntimeError:
            git_diff = self._repository.git_diff(repository)
        test_output = _clip(baseline, _MAX_TEST_OUTPUT)
        logs, stack_trace, failed_test = _incident_failure_evidence(test_output)
        incident = Incident(
            repo=self._config.demo_repository_slug,
            branch="main",
            base_branch="main",
            error="GET /profile/{user_id} crashes when email is missing.",
            logs=logs,
            stack_trace=stack_trace,
            failed_test=failed_test,
            git_diff=git_diff,
            local_path=str(repository),
        )
        report = self._incident_handler(incident)
        root_cause = next(
            (
                result.finding or ""
                for result in report.agents
                if result.agent == "RootCauseAgent"
            ),
            "",
        )

        application = None
        if (
            root_cause
            and report.patch.proposed_diff
            and report.regression_test.generated_test_code
        ):
            application = self._commander.apply_fix(
                incident,
                report.patch,
                report.regression_test,
                approved=True,
                root_cause=root_cause,
            )

        validation = (
            application.validation_report.model_dump(mode="json")
            if application and application.validation_report
            else report.validation.model_dump(mode="json")
        )
        pull_request_report = (
            application.pull_request_report
            if application and application.pull_request_report
            else report.pull_request
        )
        pull_request = pull_request_report.model_dump(mode="json")
        pull_request["branch"] = application.branch if application else None
        if application and application.message:
            pull_request["message"] = application.message
        incident_report: dict[str, Any] = {
            "incident": incident.model_dump(mode="json"),
            "root_cause": {
                "status": "found" if root_cause else "unavailable",
                "cause": root_cause,
                "confidence": _root_cause_confidence(report),
                "evidence": _root_cause_evidence(report),
            },
            "patch": report.patch.model_dump(mode="json"),
            "tests": report.regression_test.model_dump(mode="json"),
            "validation": validation,
            "pr": pull_request,
        }
        self._write_report(incident_report)
        validation_passed = bool(
            application
            and application.validation_report
            and application.validation_report.passed
        )
        pr_created = bool(application and application.pull_request_url)
        message = application.message if application else (
            None if root_cause else "RootCauseAgent did not produce a usable cause."
        )

        logger.info(
            "demo run finished",
            extra={
                "event": "demo_run_finished",
                "incident_detected": True,
                "root_cause_found": bool(root_cause),
                "validation_passed": validation_passed,
                "pr_created": pr_created,
            },
        )
        return DemoRunResponse(
            incident_detected=True,
            root_cause_found=bool(root_cause),
            patch_generated=bool(report.patch.proposed_diff),
            tests_generated=bool(report.regression_test.generated_test_code),
            validation_passed=validation_passed,
            pr_created=pr_created,
            incident_report_path=self._report_path.as_posix(),
            message=message,
        )

    @staticmethod
    def _run_baseline_tests(repository: Path) -> tuple[int, str]:
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pytest", "-q"],
                cwd=repository,
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise RuntimeError("Could not run the demo repository's baseline tests.") from exc
        return (
            result.returncode,
            _clip(f"{result.stdout}\n{result.stderr}", _MAX_TEST_OUTPUT),
        )

    def _write_report(self, report: dict[str, Any]) -> None:
        self._report_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self._report_path.with_suffix(".json.tmp")
        temporary_path.write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary_path, self._report_path)


def _is_expected_failure(output: str) -> bool:
    lowered = output.casefold()
    return all(fragment in lowered for fragment in _EXPECTED_FAILURE)


def _reproduction_failure(
    repository: str,
    repository_path: Path,
    output: str,
) -> dict[str, Any]:
    return {
        "incident": {
            "repo": repository,
            "local_path": str(repository_path),
            "error": "GET /profile/{user_id} crashes when email is missing.",
            "baseline_test_output": _clip(output, _MAX_TEST_OUTPUT),
        },
        "root_cause": {
            "status": "not_run",
            "cause": "",
            "confidence": 0.0,
            "evidence": [],
        },
        "patch": {"status": "not_run", "proposed_diff": ""},
        "tests": {"status": "not_run", "generated_test_code": ""},
        "validation": {"status": "not_run", "passed": False},
        "pr": {"status": "not_created", "url": None},
    }


def _root_cause_confidence(report: IncidentReport) -> float:
    for result in report.agents:
        if result.agent == "RootCauseAgent":
            value = result.details.get("confidence", 0.0)
            if isinstance(value, (float, int)) and not isinstance(value, bool):
                return max(0.0, min(float(value), 1.0))
    return 0.0


def _root_cause_evidence(report: IncidentReport) -> list[str]:
    for result in report.agents:
        if result.agent == "RootCauseAgent":
            evidence = result.details.get("evidence", [])
            if isinstance(evidence, list):
                return [str(item) for item in evidence[:20]]
    return []


def _clip(value: str, maximum: int) -> str:
    return value if len(value) <= maximum else value[:maximum]


def _incident_failure_evidence(output: str) -> tuple[str, str, str]:
    lines = output.splitlines()
    stack_start = next(
        (
            index
            for index, line in enumerate(lines)
            if "Traceback (most recent call last)" in line
            or line.lstrip().startswith((">", "E   "))
        ),
        None,
    )
    logs = "\n".join(lines[:stack_start]) if stack_start is not None else output
    stack_trace = (
        "\n".join(lines[stack_start:]) if stack_start is not None else output
    )
    failure_summary = "\n".join(
        line for line in lines if line.startswith(("FAILED ", "ERROR "))
    )
    return (
        _clip(logs, _MAX_INCIDENT_LOGS),
        _clip_tail(stack_trace, _MAX_STACK_TRACE),
        _clip(failure_summary or output, _MAX_FAILED_TEST),
    )


def _clip_tail(value: str, maximum: int) -> str:
    return value if len(value) <= maximum else value[-maximum:]
