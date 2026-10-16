import logging
import re
from typing import TypedDict
from urllib.parse import quote

import httpx

from models import Incident
from services.github_service import GitHubService

logger = logging.getLogger(__name__)
_REPOSITORY_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


class GitAgentResult(TypedDict):
    agent: str
    status: str
    finding: str
    commits: list[dict[str, str]]


def run(incident: Incident, github: GitHubService | None = None) -> GitAgentResult:
    if not _REPOSITORY_PATTERN.fullmatch(incident.repo):
        return {
            "agent": "GitAgent",
            "status": "unavailable",
            "finding": "Repository must be provided as owner/repository.",
            "commits": [],
        }
    service = github or GitHubService()
    encoded_repo = quote(incident.repo, safe="/")
    try:
        commits = service.recent_commits(encoded_repo, incident.branch)
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning(
            "GitHub commit lookup failed",
            extra={"repo": incident.repo, "agent": "GitAgent"},
        )
        return {
            "agent": "GitAgent",
            "status": "unavailable",
            "finding": f"GitHub commit history could not be retrieved: {exc}",
            "commits": [],
        }
    finding = (
        f"Retrieved {len(commits)} recent commits for {incident.repo}@{incident.branch}."
        if commits
        else f"No commits were returned for {incident.repo}@{incident.branch}."
    )
    return {
        "agent": "GitAgent",
        "status": "completed",
        "finding": finding,
        "commits": commits,
    }
