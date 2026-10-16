import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

from core.config import Settings, settings


class DockerSandboxService:
    def __init__(self, config: Settings = settings) -> None:
        self._config = config

    def run_tests(
        self,
        repository: Path,
        command: list[str],
        generated_test_code: str,
    ) -> tuple[bool, str]:
        if not command or any("\x00" in part for part in command):
            raise ValueError("A valid test command is required.")
        with TemporaryDirectory(prefix="sentinelos-tests-") as tests_directory:
            test_file = Path(tests_directory) / "test_sentinelos_regression.py"
            test_file.write_text(generated_test_code, encoding="utf-8")
            Path(tests_directory).chmod(0o755)
            args = [
                "docker",
                "run",
                "--rm",
                "--network",
                "none",
                "--read-only",
                "--user",
                "65534:65534",
                "--cap-drop",
                "ALL",
                "--security-opt",
                "no-new-privileges",
                "--pids-limit",
                "128",
                "--tmpfs",
                "/tmp:rw,noexec,nosuid,size=256m,mode=1777",
                "--env",
                "PYTHONDONTWRITEBYTECODE=1",
                "--env",
                "PYTEST_ADDOPTS=-p no:cacheprovider",
                "--memory",
                "1g",
                "--cpus",
                "1",
                "--volume",
                f"{repository.resolve()}:/workspace:ro",
                "--volume",
                f"{tests_directory}:/sentinel-tests:ro",
                "--workdir",
                "/workspace",
                self._config.docker_image,
                *command,
                "/sentinel-tests/test_sentinelos_regression.py",
            ]
            try:
                result = subprocess.run(
                    args,
                    capture_output=True,
                    text=True,
                    timeout=300,
                    check=False,
                )
            except FileNotFoundError:
                return False, "Docker executable is unavailable."
            except subprocess.TimeoutExpired:
                return False, "Sandbox test execution timed out after 300 seconds."
            output = (result.stdout + result.stderr)[-20_000:]
            return result.returncode == 0, output
