import difflib
import logging
from pathlib import PurePath
from typing import Any

from models import PatchProposal
from services.ollama_service import OllamaService

logger = logging.getLogger(__name__)


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
        logger.info(
            "patch source context prepared: file_count=%d file_names=%s "
            "source_context_length=%d source_context_preview=%r",
            len(repository_files or {}),
            list((repository_files or {}).keys()),
            len(source_context),
            source_context[:500],
            extra={"event": "patch_source_context_prepared"},
        )
        prompt = (
            "Determine the smallest safe code change for the incident below. "
            "Select exactly one target file from the supplied repository source "
            "files. Return the exact old_code snippet to replace and its new_code "
            "replacement. Copy old_code exactly from the source and preserve "
            "indentation in both snippets; do not produce a diff or return the "
            "full file. The old_code snippet must occur exactly once in the target "
            "file. "
            "Also return a concise explanation of the root cause and intended "
            "change. Return JSON with string keys file_name, explanation, old_code, "
            "and new_code. The file_name must exactly match a supplied source file. "
            "If no source file supports a justified change, return empty strings "
            "for all fields. Incident: "
            f"{incident_error}\nRoot cause context: {root_cause}\n"
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
        explanation = result.get("explanation")
        old_code = result.get("old_code")
        new_code = result.get("new_code")
        safe_name = (
            name.strip()
            if isinstance(name, str) and name.strip() and not _unsafe_model_path(name)
            else None
        )
        source = (repository_files or {}).get(safe_name) if safe_name else None
        valid_explanation = (
            explanation.strip()
            if isinstance(explanation, str) and explanation.strip()
            else ""
        )
        valid_diff = (
            _generate_unified_diff(safe_name, source, old_code, new_code)
            if safe_name
            and isinstance(source, str)
            and isinstance(old_code, str)
            and old_code
            and _snippet_occurs_once(source, old_code)
            and isinstance(new_code, str)
            and new_code != old_code
            and valid_explanation
            else ""
        )
        return PatchProposal(
            status="proposed" if valid_diff.strip() else "unavailable",
            file_name=safe_name,
            proposed_diff=valid_diff,
            explanation=(
                valid_explanation or "The model did not provide a valid file change."
            ),
        )


def _unsafe_model_path(name: str) -> bool:
    path = PurePath(name)
    return path.is_absolute() or ".." in path.parts or "\\" in name


def _snippet_occurs_once(source: str, snippet: str) -> bool:
    first_match = source.find(snippet)
    return first_match >= 0 and source.find(snippet, first_match + 1) == -1


def _generate_unified_diff(
    file_name: str,
    original: str,
    old_code: str,
    new_code: str,
) -> str:
    updated = original.replace(old_code, new_code, 1)
    diff = difflib.unified_diff(
        original.splitlines(keepends=True),
        updated.splitlines(keepends=True),
        fromfile=f"a/{file_name}",
        tofile=f"b/{file_name}",
        lineterm="\n",
    )
    output: list[str] = []
    for line in diff:
        output.append(line)
        if line.startswith((" ", "+", "-")) and not line.endswith(("\n", "\r")):
            output.append("\n\\ No newline at end of file\n")
    return "".join(output)
