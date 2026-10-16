from typing import Any, TypedDict

from models import Incident


class AgentTestResult(TypedDict):
    agent: str
    status: str
    finding: str
    test_files: list[str]


def run(
    incident: Incident,
    repository_analysis: dict[str, Any],
) -> AgentTestResult:
    test_files = repository_analysis["test_files"]
    finding = (
        f"Found {len(test_files)} repository test files."
        if test_files
        else f"Test failure reported: {incident.error}"
    )
    return {
        "agent": "TestAgent",
        "status": "completed",
        "finding": finding,
        "test_files": test_files,
    }
