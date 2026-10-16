from typing import Any

from models import ArchitectureEvolutionResponse
from services.ollama_service import OllamaService


class ArchitectureAnalysisUnavailable(RuntimeError):
    """Raised when Ollama cannot return a structured architecture review."""


def run(
    repository_analysis: dict[str, Any],
    git_history: list[dict[str, str]],
    incident_memory: list[dict[str, Any]],
    focus: str,
    ollama: OllamaService,
) -> ArchitectureEvolutionResponse:
    prompt = (
        "Act as a principal software architect. Ground every finding in the "
        "repository inventory, git history, recurring incident memory, or "
        "request focus supplied below. Identify concrete risks, high-value "
        "refactoring RFCs, and cost optimisations. Do not claim measurements "
        "or facts that are not present. Return JSON with three arrays of concise "
        "strings: architecture_risks, refactoring_suggestions, "
        "cost_optimisations. Write refactoring_suggestions as actionable mini-RFCs "
        "with title, rationale, proposed change, and validation/rollout notes. "
        f"\nFocus:\n{focus}\nRepository:\n{repository_analysis}"
        f"\nRecent Git history:\n{git_history}\nRelated incidents and fixes:\n{incident_memory}"
    )
    response = ollama.generate_json(prompt)
    if response is None:
        raise ArchitectureAnalysisUnavailable(
            "The configured Ollama model did not return architecture recommendations."
        )
    keys = (
        "architecture_risks",
        "refactoring_suggestions",
        "cost_optimisations",
    )
    if any(
        not isinstance(response.get(key), list)
        or any(not isinstance(item, str) for item in response[key])
        for key in keys
    ):
        raise ArchitectureAnalysisUnavailable(
            "Ollama returned an incomplete architecture recommendation document."
        )
    return ArchitectureEvolutionResponse(
        architecture_risks=_string_list(response.get("architecture_risks")),
        refactoring_suggestions=_string_list(
            response.get("refactoring_suggestions")
        ),
        cost_optimisations=_string_list(response.get("cost_optimisations")),
    )


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [
        item.strip()
        for item in value
        if isinstance(item, str) and item.strip()
    ][:20]
