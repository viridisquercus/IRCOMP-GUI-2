# ************************************************************************
# @file sqlite.py
# @brief Loading and saving of the studies in SQLite
# @author Lukas (Viridis) Dubsik
# @date 6-11-2026
# @version 0.1
#
# Detailed description:
#  The whole study is stored as one JSON document in one row. The other
#  columns only duplicate what the study selector needs, so the documents
#  don't have to be parsed to list them.
#  A database the application does not recognize is never changed.
# ************************************************************************

"""Load and save the studies using SQLite."""

from __future__ import annotations

import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError

from ircomp_gui.application.ports import ExchangePort, SavedStudy, StudySummary
from ircomp_gui.domain.catalogue import Catalogue
from ircomp_gui.domain.constants import MAX_DOCUMENT
from ircomp_gui.domain.errors import DomainError
from ircomp_gui.domain.models import Study
from ircomp_gui.domain.rules import validate_study
from ircomp_gui.domain.serialization import encode_json, parse_json

# Version of the database layout, stored in PRAGMA user_version
DATABASE_VERSION = 1
# Version of the stored JSON document
STORAGE_VERSION = 1
# Columns of the studies table, in order
COLUMNS = [
    "study_id",
    "request_id",
    "saved_version",
    "title",
    "updated_at",
    "document_json",
]

CREATE_TABLE = (
    "CREATE TABLE studies (study_id TEXT PRIMARY KEY, "
    "request_id TEXT NOT NULL UNIQUE, saved_version INTEGER "
    "NOT NULL CHECK(saved_version > 0), title TEXT NOT NULL, "
    "updated_at TEXT NOT NULL, document_json TEXT NOT NULL)"
)
LIST_TABLES = (
    "SELECT name FROM sqlite_master WHERE type = 'table' "
    "AND name NOT LIKE 'sqlite_%' ORDER BY name"
)
# Insert a new study or update the existing one with the same request
UPSERT = (
    "INSERT INTO studies VALUES (?, ?, 1, ?, ?, ?) "
    "ON CONFLICT(study_id) DO UPDATE SET "
    "saved_version = studies.saved_version + 1, "
    "title = excluded.title, updated_at = excluded.updated_at, "
    "document_json = excluded.document_json "
    "WHERE studies.request_id = excluded.request_id "
    "RETURNING saved_version"
)


class SQLiteRepository:
    """Store each complete study in one SQLite row.

    Attributes
    ----------
    path : Path
        Path to the database file
    catalogue : Catalogue
        Used to check the loaded studies
    exchange : ExchangePort
        Used to check the stored evidence bytes
    """

    def __init__(
        self, path: Path, catalogue: Catalogue, exchange: ExchangePort
    ) -> None:
        self.path = path
        self.catalogue = catalogue
        self.exchange = exchange

        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with self._connection() as connection:
                self._prepare_layout(connection)
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

    def _prepare_layout(self, connection: sqlite3.Connection) -> None:
        # Find out what the database contains
        version = connection.execute("PRAGMA user_version").fetchone()[0]
        if version not in {0, DATABASE_VERSION}:
            raise DomainError(
                "SCHEMA_INVALID",
                "Unsupported database layout; the file was not changed.",
            )
        tables = [row[0] for row in connection.execute(LIST_TABLES).fetchall()]

        # Version 0 means new database, create the table if it is really empty
        if version == 0:
            if tables:
                raise DomainError(
                    "SCHEMA_INVALID",
                    "Unversioned database contains data; it was not changed.",
                )
            connection.execute("BEGIN IMMEDIATE")
            try:
                connection.execute(CREATE_TABLE)
                connection.execute(f"PRAGMA user_version = {DATABASE_VERSION}")
                connection.execute("COMMIT")
            except Exception:
                connection.execute("ROLLBACK")
                raise
            return

        # Otherwise check the layout is exactly the one we created
        rows = connection.execute("PRAGMA table_info(studies)").fetchall()
        columns = [row[1] for row in rows]
        if tables != ["studies"] or columns != COLUMNS:
            raise DomainError(
                "SCHEMA_INVALID",
                "Database layout is invalid; the file was not changed.",
            )

    def list(self) -> list[StudySummary]:
        """Read the titles, save counters and dates of the saved studies.

        Returns
        -------
        list[StudySummary]
            Saved studies, the last modified first
        """
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
        """Find if the study ID or request ID is already saved.

        Parameters
        ----------
        study_id : str
            Study ID to look for
        request_id : str
            Request ID to look for

        Returns
        -------
        str | None
            ID of the saved study using one of them, None if there is none
        """
        try:
            with self._connection() as connection:
                row = connection.execute(
                    "SELECT study_id FROM studies WHERE study_id = ? OR request_id = ?",
                    (study_id, request_id),
                ).fetchone()
        except sqlite3.Error as error:
            raise DomainError(
                "PERSISTENCE_UNAVAILABLE", "Cannot check saved request identity."
            ) from error

        if row is None:
            return None
        return str(row["study_id"])

    def _read_study(self, row: sqlite3.Row) -> Study:
        # Parse the stored document and check its envelope
        document = parse_json(row["document_json"].encode("utf-8"), limit=MAX_DOCUMENT)
        if (
            set(document) != {"storage_version", "study"}
            or type(document["storage_version"]) is not int
            or document["storage_version"] != STORAGE_VERSION
        ):
            raise DomainError(
                "SCHEMA_INVALID", "Unsupported stored document; it was not changed."
            )

        # The columns have to say the same as the document
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
        return study

    def load(self, study_id: str) -> SavedStudy:
        """Read the study and check its format, metadata and evidence.

        Parameters
        ----------
        study_id : str
            ID of the study to load

        Returns
        -------
        SavedStudy
            The study together with its save counter and date
        """
        try:
            with self._connection() as connection:
                row = connection.execute(
                    "SELECT * FROM studies WHERE study_id = ?", (study_id,)
                ).fetchone()
            if row is None:
                raise DomainError("NOT_FOUND", "Saved study was not found.")

            study = self._read_study(row)
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
        """Save the complete study in one ordinary SQLite transaction.

        Parameters
        ----------
        study : Study
            Study to save

        Returns
        -------
        int
            New save counter of the study
        """
        # Never save something that could not be loaded again
        validate_study(study, self.catalogue)
        self.exchange.verify_sources(study)

        document = {
            "storage_version": STORAGE_VERSION,
            "study": study.model_dump(mode="json"),
        }
        raw = encode_json(document).decode("utf-8")
        updated_at = datetime.now(UTC).isoformat()

        try:
            with self._connection() as connection, connection:
                row = connection.execute(
                    UPSERT,
                    (study.study_id, study.request_id, study.title, updated_at, raw),
                ).fetchone()
                # No row means the WHERE refused it - different request ID
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
