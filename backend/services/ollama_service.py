import json
import logging
import time
from typing import Any

import httpx

from core.config import Settings, settings

logger = logging.getLogger(__name__)
SUPPORTED_MODELS = ("qwen2.5-coder", "deepseek-r1", "llama3.1")


class OllamaService:
    """Local Ollama HTTP client with text and structured-generation helpers."""

    def __init__(self, config: Settings = settings) -> None:
        self._config = config

    @property
    def model_name(self) -> str:
        return self._config.ollama_model

    @property
    def model_supported(self) -> bool:
        return any(
            self.model_name == name or self.model_name.startswith(f"{name}:")
            for name in SUPPORTED_MODELS
        )

    def generate(self, prompt: str) -> str | None:
        generated = self._request_generation(prompt)
        if generated is None:
            return None
        return generated

    def generate_json(self, prompt: str) -> dict[str, Any] | None:
        generated = self._request_generation(prompt, json_output=True)
        if generated is None:
            return None
        logger.info(
            "Ollama JSON generation response received: "
            f"length={len(generated)} preview={generated[:1000]}",
            extra={
                "event": "ollama_json_response",
                "model": self.model_name,
            },
        )
        try:
            parsed = json.loads(generated)
            if not isinstance(parsed, dict):
                raise TypeError("Ollama response JSON must be an object.")
            return parsed
        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning(
                "Ollama JSON generation failed",
                extra={
                    "event": "ollama_generation_failed",
                    "error_type": type(exc).__name__,
                    "model": self.model_name,
                },
            )
            return None

    def _request_generation(
        self,
        prompt: str,
        *,
        json_output: bool = False,
    ) -> str | None:
        payload: dict[str, object] = {
            "model": self.model_name,
            "prompt": prompt,
            "stream": False,
        }
        if json_output:
            payload["format"] = "json"

        for attempt in range(self._config.ollama_retries + 1):
            try:
                response = httpx.post(
                    f"{self._config.ollama_base_url}/api/generate",
                    json=payload,
                    timeout=self._config.request_timeout_seconds,
                    trust_env=False,
                )
                response.raise_for_status()
                body = response.json()
                generated = body.get("response") if isinstance(body, dict) else None
                if not isinstance(generated, str):
                    raise TypeError("Ollama returned no generated response.")
                return generated
            except httpx.HTTPError as exc:
                retryable = not isinstance(exc, httpx.HTTPStatusError) or (
                    exc.response.status_code in {408, 429}
                    or exc.response.status_code >= 500
                )
                if retryable and attempt < self._config.ollama_retries:
                    time.sleep(min(0.25 * 2**attempt, 2.0))
                    continue
                self._log_generation_failure(exc)
                return None
            except ValueError as exc:
                self._log_generation_failure(exc)
                return None
        return None

    def _log_generation_failure(self, error: Exception) -> None:
        logger.warning(
            "Ollama generation failed",
            extra={
                "event": "ollama_generation_failed",
                "error_type": type(error).__name__,
                "model": self.model_name,
            },
        )

    def analyse_logs(
        self,
        logs: str,
        stack_trace: str = "",
        failed_test: str = "",
    ) -> str | None:
        return self.generate(
            "Analyze this incident evidence. Distinguish observations from "
            "hypotheses, identify likely cause and evidence, and do not invent "
            "missing facts.\n"
            f"Logs:\n{logs}\nStack trace:\n{stack_trace}\n"
            f"Failed test:\n{failed_test}"
        )

    def analyse_code(self, code: str, context: str = "") -> str | None:
        return self.generate(
            "Analyze the supplied source code and context. Identify relevant "
            "behavior, risks, and the smallest justified improvement.\n"
            f"Context:\n{context}\nSource:\n{code}"
        )

    def generate_patch(self, prompt: str) -> dict[str, Any] | None:
        return self.generate_json(prompt)

    def health(self) -> str:
        return (
            "configured_unverified"
            if self._config.ollama_base_url and self.model_name
            else "not_configured"
        )
