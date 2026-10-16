from typing import Any

from models import RegressionTestReport
from services.ollama_service import OllamaService


class RegressionTestGenerator:
    def __init__(self, ollama: OllamaService | None = None) -> None:
        self._ollama = ollama or OllamaService()

    def generate(
        self,
        test_finding: str,
        root_cause: str,
        repository_analysis: dict[str, Any],
        evidence: dict[str, str] | None = None,
    ) -> RegressionTestReport:
        result = self._ollama.generate_json(
            "Generate an executable pytest regression suite as Python code, "
            "including a focused regression test and meaningful edge cases. Return "
            "JSON keys generated_test_code, expected_result, and edge_cases (a list "
            "of strings). Do not claim that the tests have been run. The tests must "
            "exercise the actual failure rather than contain unconditional asserts. "
            "Failure: "
            f"{test_finding}\nRoot cause: {root_cause}\n"
            f"Repository analysis: {repository_analysis}\n"
            f"Additional supplied logs, stack, tests and git diff: {evidence or {}}"
        )
        if result is None:
            return RegressionTestReport(
                status="unavailable",
                expected_result=(
                    "Ollama did not return a regression suite; no tests were generated."
                ),
            )
        code = result.get("generated_test_code")
        expected = result.get("expected_result")
        edge_cases = result.get("edge_cases", [])
        valid_code = _strip_code_fence(code) if isinstance(code, str) else ""
        return RegressionTestReport(
            status="generated" if valid_code.strip() else "unavailable",
            generated_test_code=valid_code,
            expected_result=(
                expected.strip()
                if isinstance(expected, str) and expected.strip()
                else "No expected result was returned by the model."
            ),
            edge_cases=[
                case.strip()
                for case in edge_cases
                if isinstance(case, str) and case.strip()
            ]
            if isinstance(edge_cases, list)
            else [],
        )


def _strip_code_fence(value: str) -> str:
    stripped = value.strip()
    if stripped.startswith("```python"):
        stripped = stripped[len("```python") :].lstrip()
    elif stripped.startswith("```"):
        stripped = stripped[3:].lstrip()
    if stripped.endswith("```"):
        stripped = stripped[:-3].rstrip()
    return stripped
