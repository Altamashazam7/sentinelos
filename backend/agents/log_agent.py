from typing import TypedDict

from models import Incident


class LogAgentResult(TypedDict):
    agent: str
    status: str
    finding: str


def run(incident: Incident) -> LogAgentResult:
    log_text = incident.logs or incident.error
    lines = [line.strip() for line in log_text.splitlines() if line.strip()]
    finding = lines[-1] if lines else "Incident has no log or error details."
    return {
        "agent": "LogAgent",
        "status": "completed" if lines else "unavailable",
        "finding": finding[:2_000],
    }
