import logging
import os
import subprocess
from pathlib import Path
from typing import Any

from core.config import Settings, settings
from services.git_utils import git_command

logger = logging.getLogger(__name__)


class RepositoryService:
    def __init__(self, config: Settings = settings) -> None:
        self._config = config

    def resolve_repository(self, requested_path: str | None) -> Path | None:
        if not requested_path:
            return None
        if not self._config.repository_root:
            raise ValueError(
                "Set SENTINELOS_REPOSITORY_ROOT before providing local_path."
            )
        root = Path(self._config.repository_root).expanduser().resolve()
        candidate = Path(requested_path).expanduser().resolve()
        logger.info(
            "repository path resolved: requested_path=%s requested_path_repr=%r "
            "root=%s candidate=%s candidate_exists=%s candidate_is_dir=%s",
            requested_path,
            requested_path,
            root,
            candidate,
            candidate.exists(),
            candidate.is_dir(),
            extra={"event": "repository_path_resolution_checked"},
        )
        if not candidate.is_relative_to(root):
            raise ValueError(
                "Repository path must be inside SENTINELOS_REPOSITORY_ROOT."
            )
        if not candidate.is_dir():
            raise ValueError("Repository path does not exist or is not a directory.")
        return candidate

    def analyze(self, path: Path | None) -> dict[str, Any]:
        if path is None:
            return {
                "available": False,
                "files": [],
                "languages": [],
                "test_files": [],
                "summary": "No permitted local repository path was provided.",
            }
        ignored = {".git", ".venv", "venv", "node_modules", "__pycache__"}
        files: list[Path] = []
        for directory, subdirectories, filenames in os.walk(path, followlinks=False):
            subdirectories[:] = [
                name
                for name in subdirectories
                if name not in ignored and not (Path(directory) / name).is_symlink()
            ]
            for filename in filenames:
                candidate = Path(directory) / filename
                if not candidate.is_symlink():
                    files.append(candidate)
                    if len(files) >= 500:
                        break
            if len(files) >= 500:
                break
        suffixes = sorted({item.suffix for item in files if item.suffix})
        tests = [
            item.relative_to(path).as_posix()
            for item in files
            if "test" in item.name.lower() or item.name.lower().startswith("spec")
        ][:100]
        return {
            "available": True,
            "files": [item.relative_to(path).as_posix() for item in files],
            "languages": suffixes,
            "test_files": tests,
            "summary": f"Indexed {len(files)} repository files.",
        }

    def read_files(
        self,
        repository: Path,
        files: list[str],
        *,
        max_bytes_per_file: int = 100_000,
    ) -> dict[str, str]:
        if max_bytes_per_file < 1:
            raise ValueError("max_bytes_per_file must be positive.")
        root = repository.resolve()
        content: dict[str, str] = {}
        for relative_path in files:
            relative = Path(relative_path)
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError("Requested file is outside the repository.")
            unresolved = root / relative
            current = root
            for part in Path(relative_path).parts:
                current = current / part
                if current.is_symlink():
                    raise ValueError(
                        "Symbolic links cannot be read as repository files."
                    )
            try:
                candidate = unresolved.resolve(strict=True)
            except FileNotFoundError as exc:
                raise ValueError("Requested repository file does not exist.") from exc
            try:
                candidate.relative_to(root)
            except ValueError as exc:
                raise ValueError("Requested file is outside the repository.") from exc
            if candidate.is_symlink() or not candidate.is_file():
                raise ValueError("Requested path is not a regular repository file.")
            if candidate.stat().st_size > max_bytes_per_file:
                raise ValueError(f"Requested file exceeds {max_bytes_per_file} bytes.")
            content[Path(relative_path).as_posix()] = candidate.read_text(
                encoding="utf-8"
            )
        return content

    def git_diff(
        self,
        repository: Path,
        base: str = "HEAD",
        target: str | None = None,
    ) -> str:
        self._validate_ref(base)
        args = ["diff", "--no-ext-diff", base]
        if target is not None:
            self._validate_ref(target)
            args.append(target)
        return self._git(repository, args)

    def git_history(self, repository: Path, limit: int = 20) -> list[dict[str, str]]:
        if not 1 <= limit <= 100:
            raise ValueError("Git history limit must be between 1 and 100.")
        output = self._git(
            repository,
            [
                "log",
                f"-{limit}",
                "--format=%H%x1f%an%x1f%aI%x1f%s",
            ],
        )
        history: list[dict[str, str]] = []
        for line in output.splitlines():
            parts = line.split("\x1f", maxsplit=3)
            if len(parts) == 4:
                history.append(
                    {
                        "sha": parts[0],
                        "author": parts[1],
                        "date": parts[2],
                        "message": parts[3],
                    }
                )
        return history

    def recent_commits(
        self,
        repository: Path,
        limit: int = 5,
    ) -> list[dict[str, str]]:
        return self.git_history(repository, limit)

    def find_changed_files(
        self,
        repository: Path,
        base: str = "HEAD",
    ) -> list[str]:
        self._validate_ref(base)
        tracked = self._git(
            repository,
            ["diff", "--name-only", "--no-renames", base],
        ).splitlines()
        untracked = self._git(
            repository,
            ["ls-files", "--others", "--exclude-standard"],
        ).splitlines()
        return sorted(
            {
                Path(filename).as_posix()
                for filename in (*tracked, *untracked)
                if filename.strip()
            }
        )

    @staticmethod
    def _validate_ref(ref: str) -> None:
        if (
            not ref
            or ref.startswith("-")
            or "\x00" in ref
            or any(character.isspace() for character in ref)
        ):
            raise ValueError("Git ref is invalid.")

    @staticmethod
    def _git(repository: Path, args: list[str]) -> str:
        try:
            result = subprocess.run(
                git_command(repository, args),
                cwd=repository,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise RuntimeError("Git repository operation failed.") from exc
        if result.returncode != 0:
            raise RuntimeError("Git repository operation failed.")
        return result.stdout
