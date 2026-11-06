# /************************************************************************
# Name: Lukas (Viridis) Dubsik
# ************************************************************************/

"""Load and save the study using SQLite."""

from __future__ import annotations

import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError

from ircomp_gui.application.ports import ExchangePort, SavedStudy, StudySummary
from ircomp_gui.domain.catalogue import Catalogue
from ircomp_gui.domain.errors import DomainError
from ircomp_gui.domain.models import Study
from ircomp_gui.domain.rules import validate_study
from ircomp_gui.domain.serialization import MAX_DOCUMENT, encode_json, parse_json


class SQLiteRepository:
    """Store a complete study in one SQLite row."""

    def __init__(
        self, path: Path, catalogue: Catalogue, exchange: ExchangePort
    ) -> None:
        self.path = path
        self.catalogue = catalogue
        self.exchange = exchange
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with self._connection() as connection:
                version = connection.execute("PRAGMA user_version").fetchone()[0]
                if version not in {0, 1}:
                    raise DomainError(
                        "SCHEMA_INVALID",
                        "Unsupported database layout; the file was not changed.",
                    )
                tables = [
                    row[0]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master WHERE type = 'table' "
                        "AND name NOT LIKE 'sqlite_%' ORDER BY name"
                    ).fetchall()
                ]
                if version == 0:
                    if tables:
                        raise DomainError(
                            "SCHEMA_INVALID",
                            "Unversioned database contains data; it was not changed.",
                        )
                    _ = connection.execute("BEGIN IMMEDIATE")
                    try:
                        _ = connection.execute(
                            "CREATE TABLE studies (study_id TEXT PRIMARY KEY, "
                            "request_id TEXT NOT NULL UNIQUE, saved_version INTEGER "
                            "NOT NULL CHECK(saved_version > 0), title TEXT NOT NULL, "
                            "updated_at TEXT NOT NULL, document_json TEXT NOT NULL)"
                        )
                        _ = connection.execute("PRAGMA user_version = 1")
                        _ = connection.execute("COMMIT")
                    except Exception:
                        _ = connection.execute("ROLLBACK")
                        raise
                else:
                    columns = [
                        row[1]
                        for row in connection.execute(
                            "PRAGMA table_info(studies)"
                        ).fetchall()
                    ]
                    if tables != ["studies"] or columns != [
                        "study_id",
                        "request_id",
                        "saved_version",
                        "title",
                        "updated_at",
                        "document_json",
                    ]:
                        raise DomainError(
                            "SCHEMA_INVALID",
                            "Database layout is invalid; the file was not changed.",
                        )
        except (sqlite3.Error, OSError) as error:
            raise DomainError(
                "PERSISTENCE_UNAVAILABLE", "Cannot open the local study database."
            ) from error

    @contextmanager
    def _connection(self) -> Generator[sqlite3.Connection, None, None]:
        connection = sqlite3.connect(self.path, timeout=5)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
        finally:
            connection.close()

    def list(self) -> list[StudySummary]:
        """Read the saved study titles, counters and modification dates."""
        try:
            with self._connection() as connection:
                rows = connection.execute(
                    "SELECT study_id, title, saved_version, updated_at FROM "
                    "studies ORDER BY updated_at DESC, study_id"
                ).fetchall()
                return [StudySummary.model_validate(dict(row)) for row in rows]
        except sqlite3.Error as error:
            raise DomainError(
                "PERSISTENCE_UNAVAILABLE", "Cannot list saved studies."
            ) from error

    def identity_exists(self, study_id: str, request_id: str) -> str | None:
        """Find whether the study ID or request ID is already saved."""
        try:
            with self._connection() as connection:
                row = connection.execute(
                    "SELECT study_id FROM studies WHERE study_id = ? OR request_id = ?",
                    (study_id, request_id),
                ).fetchone()
                return str(row["study_id"]) if row else None
        except sqlite3.Error as error:
            raise DomainError(
                "PERSISTENCE_UNAVAILABLE", "Cannot check saved request identity."
            ) from error

    def load(self, study_id: str) -> SavedStudy:
        """Read the study and check its format, metadata and evidence."""
        try:
            with self._connection() as connection:
                row = connection.execute(
                    "SELECT * FROM studies WHERE study_id = ?", (study_id,)
                ).fetchone()
            if row is None:
                raise DomainError("NOT_FOUND", "Saved study was not found.")
            document = parse_json(
                row["document_json"].encode("utf-8"), limit=MAX_DOCUMENT
            )
            if (
                set(document) != {"storage_version", "study"}
                or type(document["storage_version"]) is not int
                or document["storage_version"] != 1
            ):
                raise DomainError(
                    "SCHEMA_INVALID", "Unsupported stored document; it was not changed."
                )
            study = Study.model_validate(document["study"])
            if (
                study.study_id != row["study_id"]
                or study.request_id != row["request_id"]
                or study.title != row["title"]
            ):
                raise DomainError(
                    "SCHEMA_INVALID",
                    "Stored study metadata disagrees with its document.",
                )
            validate_study(study, self.catalogue)
            self.exchange.verify_sources(study)
            return SavedStudy(
                study=study,
                saved_version=row["saved_version"],
                updated_at=row["updated_at"],
            )
        except (ValidationError, ValueError, TypeError) as error:
            raise DomainError(
                "SCHEMA_INVALID", "Stored study is invalid; it was not changed."
            ) from error
        except sqlite3.Error as error:
            raise DomainError(
                "PERSISTENCE_UNAVAILABLE", "Cannot read the saved study."
            ) from error

    def save(self, study: Study) -> int:
        """Save a complete snapshot with an ordinary SQLite transaction."""
        validate_study(study, self.catalogue)
        self.exchange.verify_sources(study)
        raw = encode_json(
            {"storage_version": 1, "study": study.model_dump(mode="json")}
        ).decode("utf-8")
        updated_at = datetime.now(UTC).isoformat()
        try:
            with self._connection() as connection, connection:
                row = connection.execute(
                    "INSERT INTO studies VALUES (?, ?, 1, ?, ?, ?) "
                    "ON CONFLICT(study_id) DO UPDATE SET "
                    "saved_version = studies.saved_version + 1, "
                    "title = excluded.title, updated_at = excluded.updated_at, "
                    "document_json = excluded.document_json "
                    "WHERE studies.request_id = excluded.request_id "
                    "RETURNING saved_version",
                    (study.study_id, study.request_id, study.title, updated_at, raw),
                ).fetchone()
                if row is None:
                    raise DomainError(
                        "IDENTITY_CONFLICT",
                        "The saved study has a different request ID.",
                    )
                return int(row["saved_version"])
        except sqlite3.IntegrityError as error:
            raise DomainError(
                "IDENTITY_CONFLICT",
                "This request identity belongs to another saved study.",
            ) from error
        except sqlite3.Error as error:
            raise DomainError(
                "PERSISTENCE_UNAVAILABLE",
                "Save failed. Working changes remain available; "
                "retry when storage is writable.",
            ) from error
