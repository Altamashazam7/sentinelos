from typing import Any

from models import RegressionTestReport
from services.test_generation_service import RegressionTestGenerator


def run(
    test_finding: str,
    root_cause: str,
    repository_analysis: dict[str, Any],
    generator: RegressionTestGenerator | None = None,
    evidence: dict[str, str] | None = None,
) -> RegressionTestReport:
    return (generator or RegressionTestGenerator()).generate(
        test_finding,
        root_cause,
        repository_analysis,
        evidence,
    )
