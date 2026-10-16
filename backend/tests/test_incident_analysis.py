from typing import Any

from core.config import Settings
from models import IncidentAnalysisRequest
from services.incident_service import (
    IncidentAnalysisService,
    OllamaUnavailableError,
)
from services.ollama_service import OllamaService


class EvidenceOllama(OllamaService):
    def __init__(self, fail_root_cause: bool = False) -> None:
        super().__init__()
        self.prompts: list[str] = []
        self.fail_root_cause = fail_root_cause

    def generate_json(self, prompt: str) -> dict[str, Any] | None:
        self.prompts.append(prompt)
        if "root_cause (string), confidence" in prompt:
            if self.fail_root_cause:
                return None
            return {
                "root_cause": "The changed handler dereferences a missing value.",
                "confidence": 0.92,
                "evidence": ["The stack trace points to handler.py:18."],
            }
        if "proposed unified diff" in prompt:
            return {
                "file_name": "app/handler.py",
                "proposed_diff": (
                    "--- a/app/handler.py\n+++ b/app/handler.py\n"
                    "@@ -1 +1 @@\n-old\n+new\n"
                ),
                "explanation": "Guard the missing value.",
            }
        return {
            "generated_test_code": (
                "def test_missing_value():\n"
                "    assert handle(None) == 'invalid'\n"
            ),
            "expected_result": "Missing values return a validation error.",
            "edge_cases": ["None", "empty string", "whitespace-only string"],
        }


def _settings() -> Settings:
    return Settings(
        github_token=None,
        github_api_url="https://api.github.com",
        ollama_base_url="http://localhost:11434",
        ollama_model="test",
        repository_root=None,
        docker_image="sentinel-os-sandbox:latest",
        test_command=None,
        request_timeout_seconds=1,
    )


def test_incident_analysis_forwards_all_evidence_and_returns_model_content() -> None:
    ollama = EvidenceOllama()
    service = IncidentAnalysisService(config=_settings(), ollama=ollama)
    request = IncidentAnalysisRequest(
        logs="request failed",
        stack_trace="File app/handler.py, line 18",
        failed_test="test_checkout raised TypeError",
        git_diff="--- a/app/handler.py\n+++ b/app/handler.py",
    )

    result = service.analyze(request)

    assert result.root_cause == "The changed handler dereferences a missing value."
    assert result.patch.startswith("--- a/app/handler.py")
    assert "def test_missing_value" in result.generated_tests
    assert result.edge_cases == ["None", "empty string", "whitespace-only string"]
    assert len(ollama.prompts) == 3
    assert (
        "Do not emit an empty diff merely because no checkout was provided"
        in ollama.prompts[1]
    )
    assert all("request failed" in prompt for prompt in ollama.prompts)
    assert all("File app/handler.py, line 18" in prompt for prompt in ollama.prompts)
    assert all("test_checkout raised TypeError" in prompt for prompt in ollama.prompts)
    assert all("+++ b/app/handler.py" in prompt for prompt in ollama.prompts)


def test_analysis_does_not_fabricate_root_cause_when_ollama_is_unavailable() -> None:
    service = IncidentAnalysisService(
        config=_settings(),
        ollama=EvidenceOllama(fail_root_cause=True),
    )

    try:
        service.analyze(IncidentAnalysisRequest(logs="connection reset"))
    except OllamaUnavailableError as exc:
        assert "Ollama" in str(exc)
    else:
        raise AssertionError("Unavailable Ollama must not produce a fabricated analysis.")
