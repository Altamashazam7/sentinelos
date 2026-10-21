import logging
from collections.abc import Callable
from itertools import pairwise
from pathlib import Path
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from agents import (
    dependency_agent,
    git_agent,
    log_agent,
    patch_agent,
    pull_request_agent,
    regression_test_agent,
    root_cause_agent,
    test_agent,
    validation_agent,
)
from core.config import Settings, settings
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
from services.docker_sandbox_service import DockerSandboxService
from services.github_service import GitHubService
from services.memory_service import MemoryService
from services.ollama_service import OllamaService
from services.patch_application_service import PatchApplicationService
from services.patch_generation_service import PatchGenerationService
from services.repository_service import RepositoryService
from services.test_generation_service import RegressionTestGenerator

logger = logging.getLogger(__name__)


_SOURCE_FILE_SUFFIXES = frozenset(
    {
        ".c",
        ".cc",
        ".cpp",
        ".cs",
        ".go",
        ".h",
        ".hpp",
        ".java",
        ".js",
        ".jsx",
        ".kt",
        ".php",
        ".py",
        ".pyi",
        ".rb",
        ".rs",
        ".scala",
        ".sh",
        ".sql",
        ".swift",
        ".ts",
        ".tsx",
        ".vue",
    }
)


class SwarmState(TypedDict, total=False):
    incident: Incident
    activity_callback: Callable[[dict[str, Any]], None] | None
    repository_path: Path | None
    repository_analysis: dict[str, Any]
    repository_files: dict[str, str]
    log_result: dict[str, Any]
    git_result: dict[str, Any]
    test_result: dict[str, Any]
    dependency_result: dict[str, Any]
    root_result: dict[str, Any]
    patch_result: PatchProposal
    regression_result: RegressionTestReport
    validation_result: ValidationReport
    pull_request_result: PullRequestReport
    report: IncidentReport


class IncidentCommander:
    """Build and execute the LangGraph incident response pipeline."""

    def __init__(
        self,
        config: Settings = settings,
        repository: RepositoryService | None = None,
        github: GitHubService | None = None,
        ollama: OllamaService | None = None,
        sandbox: DockerSandboxService | None = None,
        patch_generator: PatchGenerationService | None = None,
        test_generator: RegressionTestGenerator | None = None,
        patch_application: PatchApplicationService | None = None,
        memory: MemoryService | None = None,
    ) -> None:
        self._config = config
        self._repository = repository or RepositoryService(config)
        self._github = github or GitHubService(config)
        self._ollama = ollama or OllamaService(config)
        self._sandbox = sandbox or DockerSandboxService(config)
        self._patch_generator = patch_generator or PatchGenerationService(self._ollama)
        self._test_generator = test_generator or RegressionTestGenerator(self._ollama)
        self._patch_application = patch_application or PatchApplicationService(
            config,
            self._repository,
            self._sandbox,
        )
        self._memory = memory or MemoryService(config)
        self._workflow = self._build_workflow()

    def _build_workflow(self) -> Any:
        graph = StateGraph(SwarmState)
        nodes: dict[str, Callable[[SwarmState], dict[str, Any]]] = {
            "repository_analysis": self._repository_analysis,
            "log_agent": self._log_agent,
            "git_agent": self._git_agent,
            "test_agent": self._test_agent,
            "dependency_agent": self._dependency_agent,
            "root_cause_agent": self._root_cause_agent,
            "patch_agent": self._patch_agent,
            "regression_test_agent": self._regression_test_agent,
            "validation_agent": self._validation_agent,
            "pull_request_agent": self._pull_request_agent,
            "incident_report": self._incident_report,
        }
        for name, function in nodes.items():
            graph.add_node(
                name,
                lambda state, stage=name, handler=function: self._run_stage(
                    stage,
                    handler,
                    state,
                ),
            )
        graph.add_edge(START, "repository_analysis")
        stages = list(nodes)
        for current, following in pairwise(stages):
            graph.add_edge(current, following)
        graph.add_edge(stages[-1], END)
        return graph.compile()

    @staticmethod
    def _run_stage(
        stage: str,
        function: Callable[[SwarmState], dict[str, Any]],
        state: SwarmState,
    ) -> dict[str, Any]:
        callback = state.get("activity_callback")
        agent = _STAGE_LABELS[stage]
        if callback is not None:
            callback(
                {
                    "type": "agent_activity",
                    "stage": stage,
                    "agent": agent,
                    "status": "running",
                    "message": f"{agent} started.",
                }
            )
        try:
            result = function(state)
        except Exception as exc:
            if callback is not None:
                callback(
                    {
                        "type": "agent_activity",
                        "stage": stage,
                        "agent": agent,
                        "status": "failed",
                        "message": f"{agent} failed: {type(exc).__name__}.",
                    }
                )
            raise
        if callback is not None:
            callback(
                {
                    "type": "agent_activity",
                    "stage": stage,
                    "agent": agent,
                    "status": _stage_outcome(agent, result),
                    "message": _stage_message(agent, result),
                    "data": _stage_data(agent, result),
                }
            )
        return result

    def _repository_analysis(self, state: SwarmState) -> dict[str, Any]:
        local_path = state["incident"].local_path
        logger.info(
            "resolving incident repository path: local_path=%s local_path_repr=%r "
            "repository_root=%s",
            local_path,
            local_path,
            self._config.repository_root,
            extra={"event": "repository_path_resolution_requested"},
        )
        path = self._repository.resolve_repository(local_path)
        analysis = self._repository.analyze(path)
        test_files = set(analysis["test_files"])
        source_files = sorted(
            file_name
            for file_name in analysis["files"]
            if Path(file_name).suffix.lower() in _SOURCE_FILE_SUFFIXES
            and file_name not in test_files
        )[:10]
        repository_files = (
            self._repository.read_files(path, source_files)
            if path is not None
            else {}
        )
        return {
            "repository_path": path,
            "repository_analysis": analysis,
            "repository_files": repository_files,
        }

    @staticmethod
    def _log_agent(state: SwarmState) -> dict[str, Any]:
        return {"log_result": log_agent.run(state["incident"])}

    def _git_agent(self, state: SwarmState) -> dict[str, Any]:
        return {"git_result": git_agent.run(state["incident"], self._github)}

    def _test_agent(self, state: SwarmState) -> dict[str, Any]:
        return {
            "test_result": test_agent.run(
                state["incident"],
                state["repository_analysis"],
            )
        }

    @staticmethod
    def _dependency_agent(state: SwarmState) -> dict[str, Any]:
        return {"dependency_result": dependency_agent.run(state["repository_path"])}

    def _root_cause_agent(self, state: SwarmState) -> dict[str, Any]:
        return {
            "root_result": root_cause_agent.run(
                state["incident"],
                state["log_result"],
                state["git_result"],
                state["test_result"],
                state["dependency_result"],
                self._ollama,
                self._memory.find_similar(
                    state["incident"].repo,
                    state["incident"].error,
                ),
            )
        }

    def _patch_agent(self, state: SwarmState) -> dict[str, Any]:
        return {
            "patch_result": patch_agent.run(
                state["incident"].error,
                state["root_result"]["root_cause"],
                state["repository_analysis"],
                self._patch_generator,
                evidence={
                    "logs": state["incident"].logs or "",
                    "stack_trace": state["incident"].stack_trace or "",
                    "failed_test": state["incident"].failed_test or "",
                    "git_diff": state["incident"].git_diff or "",
                },
                repository_files=state["repository_files"],
            )
        }

    def _regression_test_agent(self, state: SwarmState) -> dict[str, Any]:
        return {
            "regression_result": regression_test_agent.run(
                state["test_result"]["finding"],
                state["root_result"]["root_cause"],
                state["repository_analysis"],
                self._test_generator,
                {
                    "logs": state["incident"].logs or "",
                    "stack_trace": state["incident"].stack_trace or "",
                    "failed_test": state["incident"].failed_test or "",
                    "git_diff": state["incident"].git_diff or "",
                },
            )
        }

    def _validation_agent(self, state: SwarmState) -> dict[str, Any]:
        return {
            "validation_result": validation_agent.run(
                state["patch_result"],
                state["regression_result"],
                state["repository_path"],
                self._config,
                self._sandbox,
            )
        }

    def _pull_request_agent(self, state: SwarmState) -> dict[str, Any]:
        return {
            "pull_request_result": pull_request_agent.run(
                state["incident"],
                state["patch_result"],
                state["validation_result"],
                self._github,
            )
        }

    @staticmethod
    def _incident_report(state: SwarmState) -> dict[str, IncidentReport]:
        incident = state["incident"]
        validation = state["validation_result"]
        pull_request = state["pull_request_result"]
        status = (
            IncidentStatus.PULL_REQUEST_CREATED
            if pull_request.status == "created"
            else (
                IncidentStatus.VALIDATED
                if validation.passed
                else (
                    IncidentStatus.FAILED
                    if validation.status == "failed"
                    else IncidentStatus.BLOCKED
                )
            )
        )
        updated_incident = incident.model_copy(update={"status": status})
        agent_results = [
            state["log_result"],
            state["git_result"],
            state["test_result"],
            state["dependency_result"],
            state["root_result"],
        ]
        agents = [
            AgentResult(
                agent=str(result["agent"]),
                status=str(result["status"]),
                finding=str(result.get("finding", result.get("root_cause", ""))),
                details={
                    key: value
                    for key, value in result.items()
                    if key not in {"agent", "status", "finding", "root_cause"}
                },
            )
            for result in agent_results
        ]
        agents.extend(
            [
                AgentResult(
                    agent="PatchAgent",
                    status=state["patch_result"].status,
                    finding=state["patch_result"].explanation,
                    details=state["patch_result"].model_dump(),
                ),
                AgentResult(
                    agent="RegressionTestAgent",
                    status=state["regression_result"].status,
                    finding=state["regression_result"].expected_result,
                    details=state["regression_result"].model_dump(),
                ),
                AgentResult(
                    agent="ValidationAgent",
                    status=validation.status,
                    finding=validation.report,
                    details=validation.model_dump(),
                ),
                AgentResult(
                    agent="PullRequestAgent",
                    status=pull_request.status,
                    finding=pull_request.reason or pull_request.description,
                    details=pull_request.model_dump(mode="json"),
                ),
            ]
        )
        return {
            "report": IncidentReport(
                incident=updated_incident,
                status=status,
                agents=agents,
                patch=state["patch_result"],
                regression_test=state["regression_result"],
                validation=validation,
                pull_request=pull_request,
            )
        }

    def investigate(
        self,
        incident: Incident,
        activity_callback: Callable[[dict[str, Any]], None] | None = None,
    ) -> IncidentReport:
        state = self._workflow.invoke(
            {
                "incident": incident,
                "activity_callback": activity_callback,
            }
        )
        report = state.get("report")
        if not isinstance(report, IncidentReport):
            raise TypeError("Incident workflow ended without an incident report.")
        return report

    def apply_fix(
        self,
        incident: Incident,
        patch: PatchProposal,
        regression_test: RegressionTestReport,
        *,
        approved: bool,
        root_cause: str = "",
    ) -> ApplyFixResponse:
        if not approved:
            raise ValueError("Review and explicitly approve the proposed patch first.")
        if not incident.local_path:
            raise ValueError("local_path is required to apply a fix.")
        application = self._patch_application.apply(
            incident,
            patch,
            regression_test,
        )
        if not application.validation.passed or not application.pushed:
            return ApplyFixResponse(
                branch=application.branch,
                validation=application.validation.status,
                ready_for_pr=False,
                message=application.message or application.validation.report,
                validation_report=application.validation,
            )

        self._memory.record_resolution(
            incident,
            root_cause,
            patch.proposed_diff,
            regression_test.generated_test_code,
            application.validation.status,
        )
        applied_patch = patch.model_copy(update={"status": "applied", "applied": True})
        pull_request = pull_request_agent.run(
            incident,
            applied_patch,
            application.validation,
            self._github,
            head_branch=application.branch,
            changed_files=application.changed_files,
        )
        return ApplyFixResponse(
            branch=application.branch,
            validation=application.validation.status,
            ready_for_pr=True,
            pull_request_url=pull_request.url,
            message=(None if pull_request.status == "created" else pull_request.reason),
            validation_report=application.validation,
            pull_request_report=pull_request,
        )


_commander = IncidentCommander()


_STAGE_LABELS = {
    "repository_analysis": "RepositoryService",
    "log_agent": "LogAgent",
    "git_agent": "GitAgent",
    "test_agent": "TestAgent",
    "dependency_agent": "DependencyAgent",
    "root_cause_agent": "RootCauseAgent",
    "patch_agent": "PatchAgent",
    "regression_test_agent": "RegressionTestAgent",
    "validation_agent": "ValidationAgent",
    "pull_request_agent": "PullRequestAgent",
    "incident_report": "IncidentReport",
}


def _stage_message(agent: str, result: dict[str, Any]) -> str:
    value: Any = result
    if agent == "RootCauseAgent":
        value = result.get("root_result", {}).get("root_cause")
    elif agent == "PatchAgent":
        value = result.get("patch_result")
        value = value.explanation if isinstance(value, PatchProposal) else value
    elif agent == "RegressionTestAgent":
        value = result.get("regression_result")
        value = (
            value.expected_result if isinstance(value, RegressionTestReport) else value
        )
    elif agent == "ValidationAgent":
        value = result.get("validation_result")
        value = value.report if isinstance(value, ValidationReport) else value
    elif agent == "PullRequestAgent":
        value = result.get("pull_request_result")
        value = (
            value.reason or value.title
            if isinstance(value, PullRequestReport)
            else value
        )
    elif agent == "IncidentReport":
        value = result.get("report")
        value = value.status.value if isinstance(value, IncidentReport) else value
    elif result:
        value = next(iter(result.values()))
        if isinstance(value, dict):
            value = value.get("finding", value.get("summary", ""))
    return str(value or f"{agent} {_stage_outcome(agent, result)}.")[:1_000]


def _stage_outcome(agent: str, result: dict[str, Any]) -> str:
    if agent == "RepositoryService":
        return (
            "completed"
            if result.get("repository_analysis", {}).get("available")
            else "unavailable"
        )
    result_key = {
        "LogAgent": "log_result",
        "GitAgent": "git_result",
        "TestAgent": "test_result",
        "DependencyAgent": "dependency_result",
        "RootCauseAgent": "root_result",
    }.get(agent)
    if result_key is not None:
        status = result.get(result_key, {}).get("status")
    elif agent == "PatchAgent":
        value = result.get("patch_result")
        status = value.status if isinstance(value, PatchProposal) else None
    elif agent == "RegressionTestAgent":
        value = result.get("regression_result")
        status = value.status if isinstance(value, RegressionTestReport) else None
    elif agent == "ValidationAgent":
        value = result.get("validation_result")
        status = value.status if isinstance(value, ValidationReport) else None
    elif agent == "PullRequestAgent":
        value = result.get("pull_request_result")
        status = value.status if isinstance(value, PullRequestReport) else None
    else:
        status = "completed"
    return str(status or "completed")


def _stage_data(agent: str, result: dict[str, Any]) -> dict[str, Any]:
    if agent == "RootCauseAgent":
        return result.get("root_result", {})
    if agent == "PatchAgent":
        proposal = result.get("patch_result")
        return (
            proposal.model_dump(mode="json")
            if isinstance(proposal, PatchProposal)
            else {}
        )
    if agent == "RegressionTestAgent":
        report = result.get("regression_result")
        return (
            report.model_dump(mode="json")
            if isinstance(report, RegressionTestReport)
            else {}
        )
    if agent == "ValidationAgent":
        report = result.get("validation_result")
        return (
            report.model_dump(mode="json")
            if isinstance(report, ValidationReport)
            else {}
        )
    if agent == "PullRequestAgent":
        report = result.get("pull_request_result")
        return (
            report.model_dump(mode="json")
            if isinstance(report, PullRequestReport)
            else {}
        )
    if agent == "IncidentReport":
        report = result.get("report")
        return (
            report.model_dump(mode="json") if isinstance(report, IncidentReport) else {}
        )
    return {}


def investigate(incident: Incident) -> IncidentReport:
    return _commander.investigate(incident)


def get_commander() -> IncidentCommander:
    return _commander
