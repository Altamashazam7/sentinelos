import os
import re
from urllib.parse import quote
from uuid import uuid4

import httpx
import pytest

from core.config import settings
from services.github_service import GitHubService


def test_live_github_branch_commit_and_pull_request() -> None:
    if os.getenv("SENTINELOS_LIVE_GITHUB", "").casefold() not in {
        "1",
        "true",
        "yes",
    }:
        pytest.skip("Set SENTINELOS_LIVE_GITHUB=1 to enable live GitHub writes.")
    repository = os.getenv("SENTINELOS_E2E_REPO", "")
    if not settings.github_token or not repository:
        pytest.fail("Live GitHub mode requires GITHUB_TOKEN and SENTINELOS_E2E_REPO.")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        pytest.fail("SENTINELOS_E2E_REPO must be an owner/repository slug.")

    service = GitHubService(settings)
    repository_info = service.repository_summary(repository)
    base = repository_info.get("default_branch")
    if not isinstance(base, str) or not base:
        pytest.fail("The live test repository has no default branch.")

    branch = f"sentinel-e2e-{uuid4().hex[:12]}"
    pull_number: int | None = None
    service.create_branch(repository, branch, base)
    try:
        commit = service.create_commit(
            repository,
            branch,
            {
                f"sentinel-e2e/{branch}.md": (
                    f"Temporary integration-test commit: {branch}\n"
                )
            },
            f"test: SentinelOS live integration {branch}",
        )
        assert commit.get("sha")
        pull_request = service.create_pull_request(
            repository,
            f"SentinelOS live integration {branch}",
            "Temporary PR created by the opt-in SentinelOS GitHub integration test.",
            branch,
            base,
        )
        assert isinstance(pull_request.get("number"), int)
        assert isinstance(pull_request.get("html_url"), str)
        pull_number = pull_request["number"]
    finally:
        _cleanup_live_resources(repository, branch, pull_number)


def _cleanup_live_resources(
    repository: str,
    branch: str,
    pull_number: int | None,
) -> None:
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {settings.github_token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    base_url = f"{settings.github_api_url}/repos/{quote(repository, safe='/')}"
    try:
        if pull_number is not None:
            response = httpx.patch(
                f"{base_url}/pulls/{pull_number}",
                headers=headers,
                json={"state": "closed"},
                timeout=settings.request_timeout_seconds,
                trust_env=False,
            )
            response.raise_for_status()
    finally:
        response = httpx.delete(
            f"{base_url}/git/refs/heads/{branch}",
            headers=headers,
            timeout=settings.request_timeout_seconds,
            trust_env=False,
        )
        response.raise_for_status()
