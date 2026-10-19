from pathlib import PurePath
from typing import Any

from models import PatchProposal
from services.ollama_service import OllamaService


class PatchGenerationService:
    def __init__(self, ollama: OllamaService | None = None) -> None:
        self._ollama = ollama or OllamaService()

    def generate(
        self,
        incident_error: str,
        root_cause: str,
        repository_analysis: dict[str, Any],
        evidence: dict[str, str] | None = None,
        repository_files: dict[str, str] | None = None,
    ) -> PatchProposal:
        source_context = "\n".join(
            f"File: {file_name}\n{contents}"
            for file_name, contents in (repository_files or {}).items()
        )
        prompt = (
            "Generate a safe, minimal proposed unified diff for the incident below. "
            "Treat the supplied git diff as source-code context. Do not emit an empty "
            "diff merely because no checkout was provided when the supplied evidence "
            "identifies a target file and relevant code. If there is not enough "
            "evidence to safely identify code to change, use an empty diff and explain "
            "what is missing. Do not claim to apply the patch. Return JSON with keys "
            "file_name, proposed_diff, explanation. Use exact unified-diff file "
            "headers and accurate hunk line counts. The diff must be syntactically "
            "valid and must not modify unrelated files. Incident: "
            f"{incident_error}\nRoot cause: {root_cause}\n"
            f"Repository analysis: {repository_analysis}\n"
            f"Repository source files:\n{source_context}\n"
            f"Additional supplied logs, stack, tests and git diff: {evidence or {}}"
        )
        result = self._ollama.generate_patch(prompt)
        if result is None:
            return PatchProposal(
                status="unavailable",
                explanation=(
                    "No patch was generated because the configured Ollama service "
                    "did not return a valid JSON response."
                ),
            )
        name = result.get("file_name")
        diff = result.get("proposed_diff")
        explanation = result.get("explanation")
        safe_name = (
            name
            if isinstance(name, str) and name.strip() and not _unsafe_model_path(name)
            else None
        )
        valid_diff = _strip_code_fence(diff, "diff") if isinstance(diff, str) else ""
        return PatchProposal(
            status="proposed" if valid_diff.strip() else "unavailable",
            file_name=safe_name,
            proposed_diff=valid_diff,
            explanation=(
                explanation.strip()
                if isinstance(explanation, str) and explanation.strip()
                else "The model did not provide an explanation."
            ),
        )


def _unsafe_model_path(name: str) -> bool:
    path = PurePath(name)
    return path.is_absolute() or ".." in path.parts or "\\" in name


def _strip_code_fence(value: str, language: str) -> str:
    stripped = value.strip()
    if stripped.startswith(f"```{language}"):
        stripped = stripped[len(language) + 3 :].lstrip()
    elif stripped.startswith("```"):
        stripped = stripped[3:].lstrip()
    if stripped.endswith("```"):
        stripped = stripped[:-3].rstrip()
    return stripped
