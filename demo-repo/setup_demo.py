import subprocess
from pathlib import Path


def _safe_directory(path: Path) -> str:
    resolved = path.resolve().as_posix()
    if resolved.startswith("//"):
        return f"%(prefix)///{resolved.lstrip('/')}"
    return resolved


def _git(repository: Path, *arguments: str) -> None:
    command = [
        "git",
        "-c",
        f"safe.directory={_safe_directory(repository)}",
        "-c",
        "user.name=SentinelOS Demo",
        "-c",
        "user.email=sentinel-demo@example.invalid",
        *arguments,
    ]
    subprocess.run(command, cwd=repository, check=True)


def main() -> None:
    repository = Path(__file__).resolve().parent
    if (repository / ".git").exists():
        raise SystemExit("This demo checkout is already a Git repository.")

    broken_source = (repository / "app.py").read_text(encoding="utf-8")
    broken_function = (
        "def get_profile(user_id: str, email: str | None = None) "
        "-> dict[str, str]:\n"
        "    return {\"user_id\": user_id, \"email\": email.lower()}"
    )
    healthy_function = (
        "def get_profile(user_id: str, email: str | None = None) "
        "-> dict[str, str]:\n"
        "    if email is None:\n"
        "        raise HTTPException(status_code=422, detail=\"email is required\")\n"
        "    return {\"user_id\": user_id, \"email\": email.lower()}"
    )
    if broken_function not in broken_source:
        raise SystemExit("The demo endpoint is not in its expected broken state.")

    healthy_source = broken_source.replace(broken_function, healthy_function, 1)
    if healthy_source == broken_source:
        raise SystemExit("Could not construct the healthy demo baseline.")

    _git(repository, "init", "-b", "main")
    (repository / "app.py").write_text(healthy_source, encoding="utf-8")
    _git(repository, "add", ".")
    _git(repository, "commit", "--no-gpg-sign", "-m", "chore: add healthy demo")

    (repository / "app.py").write_text(broken_source, encoding="utf-8")
    _git(repository, "add", "app.py")
    _git(
        repository,
        "commit",
        "--no-gpg-sign",
        "-m",
        "bug: dereference optional email without a guard",
    )
    print("Demo Git history created; main contains the intentional regression.")


if __name__ == "__main__":
    main()
