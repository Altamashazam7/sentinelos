from typing import Any

from agents.root_cause_agent import (
    _MAX_GIT_DIFF_CHARS,
    _root_cause_git_diff,
)
from agents.root_cause_agent import (
    run as run_root_cause_agent,
)
from models import Incident
from services.ollama_service import OllamaService


class PromptCapturingOllama(OllamaService):
    def __init__(self) -> None:
        self.prompt = ""

    def generate_json(self, prompt: str) -> dict[str, Any]:
        self.prompt = prompt
        return {
            "root_cause": "The handler calls lower() on a missing email.",
            "confidence": 0.95,
            "evidence": ["The stack trace shows email is None."],
        }


def test_root_cause_excludes_lockfile_diffs_and_keeps_incident_evidence() -> None:
    lockfiles = (
        "package-lock.json",
        "yarn.lock",
        "pnpm-lock.yaml",
        "poetry.lock",
        "Pipfile.lock",
    )
    lockfile_diffs = "\n".join(
        (
            f"diff --git a/frontend/{name} b/frontend/{name}\n"
            f"--- a/frontend/{name}\n"
            f"+++ b/frontend/{name}\n"
            '+  "resolved": "https://registry.example/package.tgz",\n'
            '+  "integrity": "sha512-package-metadata",\n'
            '+  "license": "ISC"\n'
        )
        for name in lockfiles
    )
    incident_diff = (
        "diff --git a/app.py b/app.py\n"
        "--- a/app.py\n"
        "+++ b/app.py\n"
        "@@ -1 +1 @@\n"
        "-email.lower()\n"
        '+(email or "").lower()\n'
    )
    ollama = PromptCapturingOllama()

    run_root_cause_agent(
        Incident(
            repo="owner/repo",
            branch="main",
            error="Profile request crashes when email is missing.",
            logs="AttributeError: 'NoneType' object has no attribute 'lower'",
            stack_trace="app.py:8 in get_profile; email is None",
            failed_test="test_profile_requires_email failed",
            git_diff=lockfile_diffs + incident_diff,
        ),
        log_result={},
        git_result={},
        test_result={},
        dependency_result={},
        ollama=ollama,
    )

    assert "resolved" not in ollama.prompt
    assert "integrity" not in ollama.prompt
    assert "license" not in ollama.prompt
    assert "package-lock.json" not in ollama.prompt
    assert "yarn.lock" not in ollama.prompt
    assert "pnpm-lock.yaml" not in ollama.prompt
    assert "poetry.lock" not in ollama.prompt
    assert "Pipfile.lock" not in ollama.prompt
    assert "diff --git a/app.py b/app.py" in ollama.prompt
    assert '+(email or "").lower()' in ollama.prompt
    assert "AttributeError: 'NoneType' object has no attribute 'lower'" in ollama.prompt
    assert "app.py:8 in get_profile; email is None" in ollama.prompt
    assert "test_profile_requires_email failed" in ollama.prompt


def test_root_cause_caps_git_diff_without_truncating_incident_evidence() -> None:
    oversized_diff = "diff --git a/app.py b/app.py\n" + ("x" * 20_000)
    capped_diff = _root_cause_git_diff(oversized_diff)
    ollama = PromptCapturingOllama()

    run_root_cause_agent(
        Incident(
            repo="owner/repo",
            branch="main",
            error="Profile request crashes when email is missing.",
            logs="critical log evidence",
            stack_trace="critical stack trace evidence",
            failed_test="critical failed-test evidence",
            git_diff=oversized_diff,
        ),
        log_result={},
        git_result={},
        test_result={},
        dependency_result={},
        ollama=ollama,
    )

    assert len(capped_diff) == _MAX_GIT_DIFF_CHARS
    assert capped_diff.endswith("[git diff truncated]")
    assert len(ollama.prompt.split("Evidence: ", maxsplit=1)[1]) < 13_000
    assert "critical log evidence" in ollama.prompt
    assert "critical stack trace evidence" in ollama.prompt
    assert "critical failed-test evidence" in ollama.prompt
