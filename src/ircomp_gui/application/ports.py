# /************************************************************************
# Name: Lukas (Viridis) Dubsik
# ************************************************************************/

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
    """One verified saved snapshot."""

    study: Study
    saved_version: int
    updated_at: str


class StudySummary(Value):
    """Hold the saved title, counter and date shown in the study selector."""

    study_id: str
    title: str
    saved_version: int
    updated_at: str


class Repository(Protocol):
    """Describe the storage functions required by the application services."""

    def list(self) -> list[StudySummary]:
        """Return saved study summaries."""
        ...

    def load(self, study_id: str) -> SavedStudy:
        """Load a complete saved study and check its contents."""
        ...

    def save(self, study: Study) -> int:
        """Save one snapshot atomically and return its save counter."""
        ...

    def identity_exists(self, study_id: str, request_id: str) -> str | None:
        """Find a saved study using the study ID or request ID."""
        ...


class ExchangePort(Protocol):
    """Describe the JSON functions required by imports, exports and storage."""

    def decode(self, raw: bytes, kind: str) -> RequestSnapshot | EvidenceBundle:
        """Read and check a request or evidence file."""
        ...

    def verify_sources(self, study: Study) -> None:
        """Check that the stored source bytes match their checksum and parsed data."""
        ...

    def evidence_file(self, raw: bytes, bundle: EvidenceBundle) -> EvidenceFile:
        """Store the original evidence bytes with their checksum."""
        ...

    def validate_document(self, document: Mapping[str, object]) -> None:
        """Check a generated JSON document against the schema."""
        ...
