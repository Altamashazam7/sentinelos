import logging
import re
from typing import Any, TypedDict

from models import Incident
from services.ollama_service import OllamaService

logger = logging.getLogger(__name__)
_MAX_GIT_DIFF_CHARS = 12_000
_DIFF_TRUNCATION_MARKER = "\n[git diff truncated]"
_LOCKFILE_PATH = re.compile(
    r"/(?:package-lock\.json|yarn\.lock|pnpm-lock\.yaml|poetry\.lock|Pipfile\.lock)"
    r'(?=$|[\s"])'
)


class RootCauseAgentResult(TypedDict):
    agent: str
    status: str
    root_cause: str
    confidence: float
    evidence: list[str]


def run(
    incident: Incident,
    log_result: dict[str, Any],
    git_result: dict[str, Any],
    test_result: dict[str, Any],
    dependency_result: dict[str, Any],
    ollama: OllamaService | None = None,
    prior_resolutions: list[dict[str, Any]] | None = None,
) -> RootCauseAgentResult:
    evidence = {
        "incident": incident.error,
        "logs": incident.logs or log_result.get("finding"),
        "stack_trace": incident.stack_trace,
        "failed_test": incident.failed_test or test_result.get("finding"),
        "git_diff": _root_cause_git_diff(incident.git_diff or git_result.get("diff")),
        "git": git_result.get("finding"),
        "commits": git_result.get("commits"),
        "tests": incident.failed_test or test_result.get("finding"),
        "dependencies": dependency_result.get("finding"),
        "prior_resolutions": prior_resolutions or [],
    }
    return analyze_evidence(evidence, ollama)


def _root_cause_git_diff(git_diff: str | None) -> str:
    if not git_diff:
        return ""

    sections = re.split(r"(?m)(?=^diff --git )", git_diff)
    relevant_sections = [
        section
        for section in sections
        if section and not _LOCKFILE_PATH.search(section.splitlines()[0])
    ]
    filtered_diff = "".join(relevant_sections)
    if len(filtered_diff) <= _MAX_GIT_DIFF_CHARS:
        return filtered_diff

    content_limit = _MAX_GIT_DIFF_CHARS - len(_DIFF_TRUNCATION_MARKER)
    return f"{filtered_diff[:content_limit]}{_DIFF_TRUNCATION_MARKER}"


def analyze_evidence(
    evidence: dict[str, Any],
    ollama: OllamaService | None = None,
) -> RootCauseAgentResult:
    model_result = (ollama or OllamaService()).generate_json(
        "Analyze the supplied production incident evidence. Use every present "
        "log excerpt, stack trace, failed test, and git diff. Identify the most "
        "likely root cause using only the evidence; distinguish observed facts "
        "from inference. Return JSON with root_cause (string), confidence "
        "(number 0 to 1), and evidence (list of short supporting facts). If evidence "
        "is insufficient, say so instead of inventing a cause. Evidence: "
        f"{evidence!r}"
    )
    logger.info(
        "root cause model response received: %s",
        model_result,
        extra={
            "event": "root_cause_model_response",
            "root_cause_model_result": model_result,
            "root_cause_value": (
                model_result.get("root_cause") if model_result is not None else None
            ),
            "confidence_value": (
                model_result.get("confidence") if model_result is not None else None
            ),
        },
    )
    cause = model_result.get("root_cause") if model_result else None
    confidence = model_result.get("confidence", 0.0) if model_result else 0.0
    if not isinstance(cause, str) or not cause.strip():
        cause = ""
    if not isinstance(confidence, (float, int)) or isinstance(confidence, bool):
        confidence = 0.0
    return {
        "agent": "RootCauseAgent",
        "status": "completed" if cause else "unavailable",
        "root_cause": cause.strip(),
        "confidence": max(0.0, min(float(confidence), 1.0)),
        "evidence": (
            [
                str(item)
                for item in model_result.get("evidence", [])
                if isinstance(item, (str, int, float))
            ][:20]
            if model_result and isinstance(model_result.get("evidence", []), list)
            else []
        ),
    }
