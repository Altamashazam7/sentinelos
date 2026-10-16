from pathlib import Path


def git_command(repository: Path, arguments: list[str]) -> list[str]:
    """Trust only the explicitly selected checkout for this Git invocation."""
    path = repository.resolve().as_posix()
    safe_directory = (
        f"%(prefix)///{path.lstrip('/')}" if path.startswith("//") else path
    )
    return [
        "git",
        "-c",
        f"safe.directory={safe_directory}",
        *arguments,
    ]
