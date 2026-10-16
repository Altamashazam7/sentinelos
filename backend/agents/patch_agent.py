from typing import Any

from models import PatchProposal
from services.patch_generation_service import PatchGenerationService


def run(
    incident_error: str,
    root_cause: str,
    repository_analysis: dict[str, Any],
    generator: PatchGenerationService | None = None,
    evidence: dict[str, str] | None = None,
) -> PatchProposal:
    return (generator or PatchGenerationService()).generate(
        incident_error,
        root_cause,
        repository_analysis,
        evidence,
    )
