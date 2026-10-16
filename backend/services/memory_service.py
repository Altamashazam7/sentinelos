from pathlib import Path
import re
import sqlite3
from contextlib import contextmanager
from collections.abc import Generator
from typing import Any

from core.config import Settings, settings
from models import Incident, IncidentReport


class MemoryService:
    """Persistent SQLite memory for incidents and successful engineering fixes."""

    def __init__(self, config: Settings = settings) -> None:
        configured_path = config.memory_database_path
        self._path = (
            Path(configured_path).expanduser()
            if configured_path
            else Path.home() / ".sentinel-os" / "incidents.sqlite3"
        )
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def record(self, incident: Incident, report: IncidentReport) -> None:
        root_cause = next(
            (
                agent.finding or ""
                for agent in report.agents
                if agent.agent == "RootCauseAgent"
            ),
            "",
        )
        self.record_resolution(
            incident,
            root_cause,
            report.patch.proposed_diff,
            report.regression_test.generated_test_code,
            report.validation.status,
        )

    def record_resolution(
        self,
        incident: Incident,
        root_cause: str,
        fix_diff: str,
        generated_tests: str,
        validation: str,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO incidents (
                    incident_id, repository, description, root_cause,
                    fix_diff, generated_tests, validation, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(incident_id) DO UPDATE SET
                    root_cause = excluded.root_cause,
                    fix_diff = excluded.fix_diff,
                    generated_tests = excluded.generated_tests,
                    validation = excluded.validation
                """,
                (
                    incident.id,
                    incident.repo,
                    incident.error,
                    root_cause,
                    fix_diff,
                    generated_tests,
                    validation,
                    incident.created_at.isoformat(),
                ),
            )

    def find_similar(
        self,
        repository: str,
        description: str,
        limit: int = 3,
    ) -> list[dict[str, Any]]:
        if not 1 <= limit <= 20:
            raise ValueError("Memory result limit must be between 1 and 20.")
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT incident_id, description, root_cause, fix_diff,
                       generated_tests, validation, created_at
                FROM incidents
                WHERE repository = ?
                ORDER BY created_at DESC
                LIMIT 100
                """,
                (repository,),
            ).fetchall()
        query_tokens = _tokens(description)
        ranked: list[tuple[float, dict[str, Any]]] = []
        for row in rows:
            record = dict(row)
            record_tokens = _tokens(
                " ".join(
                    (
                        record["description"],
                        record["root_cause"],
                    )
                )
            )
            union = query_tokens | record_tokens
            similarity = len(query_tokens & record_tokens) / len(union) if union else 0
            if similarity:
                record["fix_diff"] = _clip(record["fix_diff"], 8_000)
                record["generated_tests"] = _clip(
                    record["generated_tests"], 5_000
                )
                record["description"] = _clip(record["description"], 2_000)
                record["root_cause"] = _clip(record["root_cause"], 1_000)
                record["similarity"] = round(similarity, 3)
                ranked.append((similarity, record))
        ranked.sort(key=lambda item: item[0], reverse=True)
        return [record for _, record in ranked[:limit]]

    def recent_incidents(
        self,
        repository: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        if not 1 <= limit <= 100:
            raise ValueError("Memory result limit must be between 1 and 100.")
        with self._connect() as connection:
            if repository:
                rows = connection.execute(
                    """
                    SELECT incident_id, repository, description, root_cause,
                           fix_diff, generated_tests, validation, created_at
                    FROM incidents WHERE repository = ?
                    ORDER BY created_at DESC LIMIT ?
                    """,
                    (repository, limit),
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT incident_id, repository, description, root_cause,
                           fix_diff, generated_tests, validation, created_at
                    FROM incidents ORDER BY created_at DESC LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
        results = [dict(row) for row in rows]
        for record in results:
            record["description"] = _clip(record["description"], 500)
            record["root_cause"] = _clip(record["root_cause"], 500)
            record["fix_diff"] = _clip(record["fix_diff"], 1_000)
            record["generated_tests"] = _clip(record["generated_tests"], 1_000)
        return results

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS incidents (
                    incident_id TEXT PRIMARY KEY,
                    repository TEXT NOT NULL,
                    description TEXT NOT NULL,
                    root_cause TEXT NOT NULL,
                    fix_diff TEXT NOT NULL,
                    generated_tests TEXT NOT NULL,
                    validation TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS incidents_repo_date "
                "ON incidents(repository, created_at DESC)"
            )

    @contextmanager
    def _connect(self) -> Generator[sqlite3.Connection, None, None]:
        connection = sqlite3.connect(self._path, timeout=10)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()


def _tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9_]{3,}", value.casefold())
        if token not in {"the", "and", "for", "with", "from", "this", "that"}
    }


def _clip(value: str, maximum: int) -> str:
    return value if len(value) <= maximum else f"{value[:maximum]}…"
