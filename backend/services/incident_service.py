import logging
from collections.abc import Callable
from threading import RLock

from agents import patch_agent, regression_test_agent, root_cause_agent
from agents.validation_agent import run as validate_patch
from commander import investigate
from core.config import Settings, settings
from models import (
    Incident,
    IncidentAnalysisRequest,
    IncidentAnalysisResponse,
    IncidentReport,
)
from services.memory_service import MemoryService
from services.ollama_service import OllamaService
from services.patch_generation_service import PatchGenerationService
from services.repository_service import RepositoryService
from services.test_generation_service import RegressionTestGenerator

logger = logging.getLogger(__name__)


class IncidentService:
    def __init__(
        self,
        workflow: Callable[[Incident], IncidentReport] = investigate,
        memory: MemoryService | None = None,
    ) -> None:
        self._workflow = workflow
        self._memory = memory or MemoryService()
        self._incidents: dict[str, IncidentReport] = {}
        self._lock = RLock()

    def handle(self, incident: Incident) -> IncidentReport:
        logger.info(
            "incident investigation started",
            extra={"incident_id": incident.id, "repo": incident.repo},
        )
        report = self._workflow(incident)
        self._memory.record(incident, report)
        with self._lock:
            self._incidents[incident.id] = report
        logger.info(
            "incident investigation finished",
            extra={
                "incident_id": incident.id,
                "repo": incident.repo,
                "event": report.status.value,
            },
        )
        return report

    def get(self, incident_id: str) -> IncidentReport | None:
        with self._lock:
            return self._incidents.get(incident_id)

    def list(self) -> list[IncidentReport]:
        with self._lock:
            return list(self._incidents.values())


class IncidentAnalysisService:
    """Analyze caller-supplied evidence with injected local model/services."""

    def __init__(
        self,
        config: Settings = settings,
        ollama: OllamaService | None = None,
        repository: RepositoryService | None = None,
        patch_generator: PatchGenerationService | None = None,
        test_generator: RegressionTestGenerator | None = None,
    ) -> None:
        self._config = config
        self._ollama = ollama or OllamaService(config)
        self._repository = repository or RepositoryService(config)
        self._patch_generator = patch_generator or PatchGenerationService(self._ollama)
        self._test_generator = test_generator or RegressionTestGenerator(self._ollama)

    def analyze(
        self,
        request: IncidentAnalysisRequest,
    ) -> IncidentAnalysisResponse:
        evidence = {
            "logs": request.logs,
            "stack_trace": request.stack_trace,
            "failed_test": request.failed_test,
            "git_diff": request.git_diff,
        }
        evidence = {key: value for key, value in evidence.items() if value}
        logger.info(
            "incident evidence analysis started",
            extra={
                "event": "incident_analysis_started",
                "evidence_fields": sorted(evidence),
            },
        )
        root_result = root_cause_agent.analyze_evidence(evidence, self._ollama)
        root_cause = root_result["root_cause"]
        if not root_cause:
            raise OllamaUnavailableError(
                "Ollama did not return a root-cause analysis. Verify that Ollama is "
                f"running and model {self._ollama.model_name!r} is installed."
            )

        repository_analysis = self._repository.analyze(None)
        incident_summary = "\n".join(
            f"{key}:\n{value}" for key, value in evidence.items()
        )
        patch = patch_agent.run(
            incident_summary,
            root_cause,
            repository_analysis,
            self._patch_generator,
            evidence,
        )
        regression = regression_test_agent.run(
            evidence.get("failed_test", "")
            or evidence.get("stack_trace", "")
            or evidence.get("logs", ""),
            root_cause,
            repository_analysis,
            self._test_generator,
            evidence,
        )
        validation = validate_patch(
            patch,
            regression,
            repository_path=None,
            config=self._config,
        )
        patch_consistent = validation.checks["patch_consistent"]
        if not validation.checks["regression_test_syntax_valid"]:
            regression.status = "invalid"
            regression.generated_test_code = ""
        if not patch_consistent:
            patch.status = "invalid"
            patch.explanation = (
                f"{patch.explanation} Validation rejected the model response because "
                "it was not a consistent unified diff."
            )

        logger.info(
            "incident evidence analysis finished",
            extra={
                "event": "incident_analysis_finished",
                "root_cause_status": root_result["status"],
                "patch_status": patch.status,
                "regression_status": regression.status,
                "patch_consistent": patch_consistent,
                "validation_status": validation.status,
            },
        )
        return IncidentAnalysisResponse(
            root_cause=root_cause,
            patch=patch.proposed_diff if patch_consistent else "",
            generated_tests=regression.generated_test_code,
            edge_cases=regression.edge_cases,
        )


class OllamaUnavailableError(RuntimeError):
    """Raised when local model inference cannot produce required analysis."""


incident_service = IncidentService()
incident_analysis_service = IncidentAnalysisService()
