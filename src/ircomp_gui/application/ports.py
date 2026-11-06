# ************************************************************************
# @file ports.py
# @brief Interfaces of the storage and exchange used by the services
# @author Lukas (Viridis) Dubsik
# @date 6-11-2026
# @version 0.1
#
# Detailed description:
#  The services only know these protocols, the implementations are in
#  adapters/. This way the services don't depend on SQLite or jsonschema.
# ************************************************************************

"""Define the storage and JSON functions used by the application."""

from collections.abc import Mapping
from typing import Protocol

from ircomp_gui.domain.models import (
    EvidenceBundle,
    EvidenceFile,
    RequestSnapshot,
    Study,
    Value,
)


class SavedStudy(Value):
    """Hold one checked saved study with its save counter and date."""

    study: Study
    saved_version: int
    updated_at: str


class StudySummary(Value):
    """Hold the title, counter and date shown in the study selector."""

    study_id: str
    title: str
    saved_version: int
    updated_at: str


class Repository(Protocol):
    """Storage functions needed by the services."""

    def list(self) -> list[StudySummary]:
        """Return the summaries of the saved studies."""
        ...

    def load(self, study_id: str) -> SavedStudy:
        """Load a complete saved study and check its contents."""
        ...

    def save(self, study: Study) -> int:
        """Save the study atomically and return its save counter."""
        ...

    def identity_exists(self, study_id: str, request_id: str) -> str | None:
        """Find a saved study by its study ID or request ID."""
        ...


class ExchangePort(Protocol):
    """JSON functions needed by the imports, exports and storage."""

    def decode(self, raw: bytes, kind: str) -> RequestSnapshot | EvidenceBundle:
        """Read and check a request or evidence file."""
        ...

    def verify_sources(self, study: Study) -> None:
        """Check the stored bytes against their checksum and parsed data."""
        ...

    def evidence_file(self, raw: bytes, bundle: EvidenceBundle) -> EvidenceFile:
        """Store the original evidence bytes with their checksum."""
        ...

    def validate_document(self, document: Mapping[str, object]) -> None:
        """Check a generated JSON document against the schema."""
        ...
