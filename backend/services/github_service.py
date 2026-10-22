import re
from typing import Any
from urllib.parse import quote

import httpx

from core.config import Settings, settings


class GitHubService:
    """Authenticated GitHub REST client for repository and PR operations."""

    def __init__(self, config: Settings = settings) -> None:
        self._config = config

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self._config.github_token:
            headers["Authorization"] = "Bearer " + self._config.github_token
        return headers

    def repository_summary(self, repo: str) -> dict[str, Any]:
        payload = self._request("GET", f"/repos/{quote(repo, safe='/')}").json()
        if not isinstance(payload, dict):
            raise TypeError("GitHub returned an invalid repository response.")
        return {
            "full_name": payload.get("full_name", repo),
            "default_branch": payload.get("default_branch"),
            "html_url": payload.get("html_url"),
            "private": payload.get("private"),
        }

    def recent_commits(self, repo: str, branch: str) -> list[dict[str, str]]:
        payload = self._request(
            "GET",
            f"/repos/{quote(repo, safe='/')}/commits",
            params={"sha": branch, "per_page": 5},
        ).json()
        if not isinstance(payload, list):
            raise TypeError("GitHub returned an invalid commit list.")
        commits: list[dict[str, str]] = []
        for item in payload:
            if isinstance(item, dict):
                commit = item.get("commit")
                message = commit.get("message", "") if isinstance(commit, dict) else ""
                commits.append(
                    {"sha": str(item.get("sha", "")), "message": str(message)}
                )
        return commits

    def create_branch(
        self,
        repo: str,
        branch: str,
        from_branch: str,
    ) -> dict[str, Any]:
        self._require_token()
        _validate_branch(branch)
        _validate_branch(from_branch)
        repository = quote(repo, safe="/")
        source = self._request(
            "GET",
            f"/repos/{repository}/git/ref/heads/{quote(from_branch, safe='')}",
        ).json()
        source_object = source.get("object") if isinstance(source, dict) else None
        source_sha = (
            source_object.get("sha") if isinstance(source_object, dict) else None
        )
        if not isinstance(source_sha, str):
            raise TypeError("GitHub returned an invalid source branch reference.")
        return _response_object(
            self._request(
                "POST",
                f"/repos/{repository}/git/refs",
                json={"ref": f"refs/heads/{branch}", "sha": source_sha},
            ),
            "branch creation",
        )

    def create_commit(
        self,
        repo: str,
        branch: str,
        files: dict[str, str],
        message: str,
    ) -> dict[str, Any]:
        self._require_token()
        _validate_branch(branch)
        if not files:
            raise ValueError("At least one file is required to create a commit.")
        repository = quote(repo, safe="/")
        reference = self._request(
            "GET",
            f"/repos/{repository}/git/ref/heads/{quote(branch, safe='')}",
        ).json()
        reference_object = (
            reference.get("object") if isinstance(reference, dict) else None
        )
        parent_sha = (
            reference_object.get("sha") if isinstance(reference_object, dict) else None
        )
        if not isinstance(parent_sha, str):
            raise TypeError("GitHub returned an invalid branch reference.")
        parent_commit = self._request(
            "GET",
            f"/repos/{repository}/git/commits/{quote(parent_sha, safe='')}",
        ).json()
        parent_tree = (
            parent_commit.get("tree") if isinstance(parent_commit, dict) else None
        )
        parent_tree_sha = (
            parent_tree.get("sha") if isinstance(parent_tree, dict) else None
        )
        if not isinstance(parent_tree_sha, str):
            raise TypeError("GitHub returned an invalid base commit tree.")

        tree_entries: list[dict[str, str]] = []
        for path, content in sorted(files.items()):
            if (
                not path
                or path.startswith("/")
                or "\\" in path
                or any(part in {"", ".", "..", ".git"} for part in path.split("/"))
            ):
                raise ValueError(
                    "Commit file paths must be safe repository-relative paths."
                )
            blob = self._request(
                "POST",
                f"/repos/{repository}/git/blobs",
                json={"content": content, "encoding": "utf-8"},
            ).json()
            blob_sha = blob.get("sha") if isinstance(blob, dict) else None
            if not isinstance(blob_sha, str):
                raise TypeError("GitHub returned an invalid file blob.")
            tree_entries.append(
                {
                    "path": path,
                    "mode": "100644",
                    "type": "blob",
                    "sha": blob_sha,
                }
            )
        tree = self._request(
            "POST",
            f"/repos/{repository}/git/trees",
            json={"base_tree": parent_tree_sha, "tree": tree_entries},
        ).json()
        tree_sha = tree.get("sha") if isinstance(tree, dict) else None
        if not isinstance(tree_sha, str):
            raise TypeError("GitHub returned an invalid commit tree.")
        return _response_object(
            self._request(
                "POST",
                f"/repos/{repository}/git/commits",
                json={"message": message, "tree": tree_sha, "parents": [parent_sha]},
            ),
            "commit creation",
        )

    def push_branch(
        self,
        repo: str,
        branch: str,
        commit_sha: str,
    ) -> dict[str, Any]:
        self._require_token()
        _validate_branch(branch)
        if not commit_sha:
            raise ValueError("A commit SHA is required to update a branch.")
        return _response_object(
            self._request(
                "PATCH",
                f"/repos/{quote(repo, safe='/')}/git/refs/heads/{quote(branch, safe='')}",
                json={"sha": commit_sha, "force": False},
            ),
            "branch update",
        )

    def create_pull_request(
        self,
        repo: str,
        title: str,
        body: str,
        head: str,
        base: str,
    ) -> dict[str, Any]:
        self._require_token()
        return _response_object(
            self._request(
                "POST",
                f"/repos/{quote(repo, safe='/')}/pulls",
                json={"title": title, "body": body, "head": head, "base": base},
            ),
            "pull request creation",
        )

    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        response = httpx.request(
            method,
            f"{self._config.github_api_url}{path}",
            headers=self._headers(),
            timeout=self._config.request_timeout_seconds,
            **kwargs,
        )
        response.raise_for_status()
        return response

    def _require_token(self) -> None:
        if not self._config.github_token:
            raise RuntimeError("GITHUB_TOKEN is required for GitHub write operations.")


def _response_object(response: httpx.Response, operation: str) -> dict[str, Any]:
    payload = response.json()
    if not isinstance(payload, dict):
        raise TypeError(f"GitHub returned an invalid response for {operation}.")
    return payload


def _validate_branch(branch: str) -> None:
    if (
        not branch
        or branch.startswith("-")
        or branch.endswith("/")
        or "//" in branch
        or ".." in branch
        or not re.fullmatch(r"[A-Za-z0-9_.\-/]+", branch)
    ):
        raise ValueError("Branch name is invalid.")
