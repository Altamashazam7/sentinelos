import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")


@dataclass(frozen=True, slots=True)
class Settings:
    """Environment-backed settings; external integrations remain optional."""

    github_token: str | None
    github_api_url: str
    ollama_base_url: str
    ollama_model: str
    repository_root: str | None
    docker_image: str
    test_command: str | None
    request_timeout_seconds: float
    memory_database_path: str | None = None
    ollama_retries: int = 2
    demo_enabled: bool = False
    demo_repository_slug: str | None = None
    demo_repository_path: str | None = None

    @classmethod
    def from_environment(cls) -> "Settings":
        timeout = float(os.getenv("SENTINELOS_REQUEST_TIMEOUT", "120"))
        if timeout <= 0:
            raise ValueError("SENTINELOS_REQUEST_TIMEOUT must be positive.")
        retries = int(os.getenv("SENTINELOS_OLLAMA_RETRIES", "2"))
        if retries < 0 or retries > 10:
            raise ValueError("SENTINELOS_OLLAMA_RETRIES must be between 0 and 10.")
        test_command = os.getenv("SENTINELOS_TEST_COMMAND", "").strip() or None
        return cls(
            github_token=os.getenv("GITHUB_TOKEN") or None,
            github_api_url=os.getenv("GITHUB_API_URL", "https://api.github.com").rstrip(
                "/"
            ),
            ollama_base_url=os.getenv(
                "OLLAMA_BASE_URL", "http://localhost:11434"
            ).rstrip("/"),
            ollama_model=os.getenv("OLLAMA_MODEL", "qwen2.5-coder:7b"),
            repository_root=os.getenv("SENTINELOS_REPOSITORY_ROOT") or None,
            docker_image=os.getenv(
                "SENTINELOS_DOCKER_IMAGE", "sentinel-os-sandbox:latest"
            ),
            test_command=test_command,
            request_timeout_seconds=timeout,
            memory_database_path=os.getenv("SENTINELOS_MEMORY_DB")
            or str(Path.home() / ".sentinel-os" / "incidents.sqlite3"),
            ollama_retries=retries,
            demo_enabled=os.getenv("SENTINELOS_DEMO_ENABLED", "").casefold()
            in {"1", "true", "yes"},
            demo_repository_slug=os.getenv("SENTINELOS_DEMO_REPOSITORY") or None,
            demo_repository_path=os.getenv("SENTINELOS_DEMO_PATH") or None,
        )


settings = Settings.from_environment()
