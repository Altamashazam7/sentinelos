import logging
import re
from typing import Any
from urllib.parse import quote

import httpx

from models import Incident, PatchProposal, PullRequestReport, ValidationReport
from services.github_service import GitHubService

logger = logging.getLogger(__name__)
_SAFE_BRANCH = re.compile(r"^[A-Za-z0-9_.\-/]+$")
_REPOSITORY_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


def run(
    incident: Incident,
    patch: PatchProposal,
    validation: ValidationReport,
    github: GitHubService | None = None,
    *,
    head_branch: str | None = None,
    changed_files: list[str] | None = None,
) -> PullRequestReport:
    pull_request_branch = head_branch or incident.branch
    title = f"Fix incident: {incident.error[:100]}"
    changed_files = (
        sorted(set(changed_files))
        if changed_files is not None
        else [patch.file_name] if patch.file_name else []
    )
    description = (
        f"## Incident\n{incident.error}\n\n"
        f"## Proposed change\n{patch.explanation}\n\n"
        f"```diff\n{patch.proposed_diff}\n```\n"
        f"\nValidation: {validation.status}."
    )
    if not validation.passed or not patch.applied:
        return PullRequestReport(
            status="blocked",
            title=title,
            description=description,
            changed_files=changed_files,
            reason="A pull request requires an applied patch and passing validation.",
        )
    if not _REPOSITORY_PATTERN.fullmatch(incident.repo):
        return PullRequestReport(
            status="blocked",
            title=title,
            description=description,
            changed_files=changed_files,
            reason="Repository must be provided as owner/repository.",
        )
    if not _SAFE_BRANCH.fullmatch(pull_request_branch):
        return PullRequestReport(
            status="blocked",
            title=title,
            description=description,
            changed_files=changed_files,
            reason="The source branch name contains unsupported characters.",
        )
    service = github or GitHubService()
    try:
        result: dict[str, Any] = service.create_pull_request(
            quote(incident.repo, safe="/"),
            title,
            description,
            pull_request_branch,
            incident.base_branch,
        )
    except (httpx.HTTPError, RuntimeError, ValueError) as exc:
        logger.warning(
            "Pull request creation failed",
            extra={"repo": incident.repo, "agent": "PullRequestAgent"},
        )
        return PullRequestReport(
            status="unavailable",
            title=title,
            description=description,
            changed_files=changed_files,
            reason=f"GitHub could not create the pull request: {exc}",
        )
    return PullRequestReport(
        status="created",
        title=title,
        description=description,
        changed_files=changed_files,
        url=result.get("html_url"),
    )
