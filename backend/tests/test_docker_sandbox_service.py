import subprocess
from pathlib import Path

import pytest

from core.config import Settings
from services.docker_sandbox_service import DockerSandboxService


def test_generated_tests_are_readable_by_sandbox_user(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = Settings(
        github_token=None,
        github_api_url="https://api.github.test",
        ollama_base_url="http://localhost:11434",
        ollama_model="qwen2.5-coder:7b",
        repository_root=str(tmp_path),
        docker_image="sentinel-test",
        test_command="python -m pytest",
        request_timeout_seconds=1,
    )

    def fake_run(
        args: list[str],
        **kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        volume_args = [
            args[index + 1]
            for index, argument in enumerate(args[:-1])
            if argument == "--volume"
        ]
        tests_directory = Path(volume_args[-1].split(":", maxsplit=1)[0])
        test_file = tests_directory / "test_sentinelos_regression.py"

        assert args[args.index("--user") + 1] == "65534:65534"
        assert tests_directory.stat().st_mode & 0o005 == 0o005
        assert test_file.stat().st_mode & 0o004
        return subprocess.CompletedProcess(args, 0, "1 passed\n", "")

    monkeypatch.setattr("services.docker_sandbox_service.subprocess.run", fake_run)

    passed, output = DockerSandboxService(config).run_tests(
        tmp_path,
        ["python", "-m", "pytest"],
        "def test_regression(): assert True\n",
    )

    assert passed
    assert output == "1 passed\n"
