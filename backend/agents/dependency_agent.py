import json
import os
from pathlib import Path
import re
import tomllib
from typing import TypedDict
import xml.etree.ElementTree as ElementTree


class DependencyAgentResult(TypedDict):
    agent: str
    status: str
    finding: str
    manifests: list[str]
    dependencies: dict[str, list[str]]
    errors: list[str]


def run(repository_path: Path | None) -> DependencyAgentResult:
    if repository_path is None:
        return {
            "agent": "DependencyAgent",
            "status": "unavailable",
            "finding": "Local repository analysis is not configured.",
            "manifests": [],
            "dependencies": {},
            "errors": [],
        }
    manifest_names = {
        "requirements.txt",
        "pyproject.toml",
        "Pipfile",
        "poetry.lock",
        "package.json",
        "package-lock.json",
        "Cargo.toml",
        "go.mod",
        "pom.xml",
        "build.gradle",
    }
    ignored = {".git", ".venv", "venv", "node_modules", "__pycache__"}
    manifests: list[str] = []
    for directory, subdirectories, filenames in os.walk(
        repository_path,
        followlinks=False,
    ):
        subdirectories[:] = [
            name
            for name in subdirectories
            if name not in ignored and not (Path(directory) / name).is_symlink()
        ]
        for filename in filenames:
            candidate = Path(directory) / filename
            if filename in manifest_names and not candidate.is_symlink():
                manifests.append(candidate.relative_to(repository_path).as_posix())
                if len(manifests) >= 100:
                    break
        if len(manifests) >= 100:
            break
    manifests.sort()
    dependencies: dict[str, list[str]] = {}
    errors: list[str] = []
    for relative_name in manifests:
        path = repository_path / relative_name
        try:
            parsed = _read_dependency_names(path)
        except (
            OSError,
            UnicodeError,
            json.JSONDecodeError,
            tomllib.TOMLDecodeError,
            ElementTree.ParseError,
        ) as exc:
            errors.append(f"{relative_name}: {type(exc).__name__}")
            continue
        if parsed:
            dependencies[relative_name] = parsed
    dependency_count = sum(map(len, dependencies.values()))
    return {
        "agent": "DependencyAgent",
        "status": "partial" if errors else "completed",
        "finding": (
            f"Found {len(manifests)} dependency manifest(s) and "
            f"{dependency_count} declared dependencies."
            if manifests
            else "No supported dependency manifests were found."
        ),
        "manifests": manifests,
        "dependencies": dependencies,
        "errors": errors,
    }


def _read_dependency_names(path: Path) -> list[str]:
    if path.name in {"requirements.txt", "Pipfile", "go.mod"}:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        if path.name == "requirements.txt":
            names = [
                re.split(r"[<>=!~;\[]", line.strip(), maxsplit=1)[0]
                for line in lines
                if line.strip() and not line.lstrip().startswith("#")
            ]
        elif path.name == "Pipfile":
            names = [
                line.split("=", maxsplit=1)[0].strip().strip('"\'')
                for line in lines
                if "=" in line and not line.lstrip().startswith("#")
            ]
        else:
            names = [
                line.strip().split()[0]
                for line in lines
                if line[:1].isspace()
                and line.strip()
                and not line.strip().startswith("//")
            ]
        return sorted(set(name for name in names if name))
    if path.suffix == ".toml":
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        project = data.get("project", {})
        dependencies = (
            project.get("dependencies", []) if isinstance(project, dict) else []
        )
        if not isinstance(dependencies, list):
            dependencies = []
        if path.name == "Cargo.toml":
            cargo_dependencies = data.get("dependencies", {})
            if isinstance(cargo_dependencies, dict):
                dependencies = list(cargo_dependencies)
        elif not dependencies:
            poetry = data.get("tool", {}).get("poetry", {})
            poetry_dependencies = poetry.get("dependencies", {})
            if isinstance(poetry_dependencies, dict):
                dependencies = list(poetry_dependencies)
        return sorted(
            {
                re.split(r"[<>=!~;\[]", item, maxsplit=1)[0]
                for item in dependencies
                if isinstance(item, str)
            }
        )
    if path.name == "package.json":
        data = json.loads(path.read_text(encoding="utf-8"))
        names: set[str] = set()
        if isinstance(data, dict):
            for section in ("dependencies", "devDependencies", "peerDependencies"):
                values = data.get(section, {})
                if isinstance(values, dict):
                    names.update(str(name) for name in values)
        return sorted(names)
    if path.name == "pom.xml":
        tree = ElementTree.parse(path)
        namespace = {"m": "http://maven.apache.org/POM/4.0.0"}
        return sorted(
            {
                element.text.strip()
                for element in tree.findall(".//m:dependency/m:artifactId", namespace)
                if element.text and element.text.strip()
            }
        )
    if path.name == "build.gradle":
        text = path.read_text(encoding="utf-8", errors="replace")
        return sorted(set(re.findall(r"""['"]([\w.-]+:[\w.-]+(?::[\w.+-]+)?)['"]""", text)))
    return []
