"""Data returned by the application services."""

from typing import Annotated, Literal

from pydantic import Field

from ircomp_gui.application.ports import StudySummary
from ircomp_gui.domain.catalogue import Catalogue
from ircomp_gui.domain.constants import (
    MAX_BUNDLES,
    MAX_COLLECTIONS,
    MAX_FILE,
    MAX_MEMBERSHIPS,
    MAX_REVISIONS,
    MAX_TARGETS,
)
from ircomp_gui.domain.models import (
    Collection,
    Diagnostic,
    EvidenceBundle,
    Id,
    Revision,
    Source,
    StudyData,
    Value,
)


class EvidenceSummary(Value):
    """Evidence metadata sent to the browser without its original file bytes."""

    bundle: EvidenceBundle
    sha256: str


class CollectionView(Collection):
    """A collection with its unresolved count calculated by the review rules."""

    unresolved_count: int


class StudyView(StudyData):
    """Browser view of a study; source file contents stay on the server."""

    evidence: Annotated[list[EvidenceSummary], Field(max_length=MAX_BUNDLES)]
    collections: Annotated[list[CollectionView], Field(max_length=MAX_COLLECTIONS)]


class WorkspaceView(Value):
    """The working study and its save status."""

    workspace_id: Id
    base_saved_version: int
    dirty: bool
    can_undo: bool
    study: StudyView
    diagnostics: list[Diagnostic]


class StudyList(Value):
    """Saved studies available to open."""

    studies: list[StudySummary]


class Limits(Value):
    """Published limits, taken from the same constants as the domain models."""

    import_bytes: int = MAX_FILE
    targets: int = MAX_TARGETS
    bundles: int = MAX_BUNDLES
    collections: int = MAX_COLLECTIONS
    memberships: int = MAX_MEMBERSHIPS
    revisions: int = MAX_REVISIONS


class CatalogueView(Catalogue):
    """Supported metadata and file versions."""

    format_versions: list[str] = Field(default_factory=lambda: ["1.0"])
    limits: Limits = Field(default_factory=Limits)


class CheckResult(Value):
    """Result of one local check."""

    name: str
    status: Literal["passed", "failed", "not_performed"]
    message: str


class ValidationView(Value):
    """Request checks and separate diagnostics for unapplied input."""

    revision_id: Id
    export_ready: bool
    checks: list[CheckResult]
    diagnostics: list[Diagnostic]
    draft_diagnostics: list[Diagnostic]


class ImportSummary(Value):
    """Details available after inspecting a request or evidence file."""

    expected_context: Revision | None = None
    received_context: Revision | None = None
    study_id: Id | None = None
    request_id: Id | None = None
    revision_id: Id | None = None
    reference_id: str | None = None
    profile_id: str | None = None
    target_count: int | None = None
    existing_study_id: Id | None = None
    bundle_id: Id | None = None
    category: Literal["synthetic", "computational_prediction"] | None = None
    candidate_count: int | None = None
    source: Source | None = None


class ImportPreviewView(Value):
    """Inspection result kept until the file is accepted or cancelled."""

    preview_id: Id
    kind: Literal["request", "evidence"]
    status: Literal["ready", "blocked", "duplicate"]
    diagnostics: list[Diagnostic]
    summary: ImportSummary


class ExportPreviewView(Value):
    """Description of the exact file prepared for download."""

    export_id: Id
    filename: str
    sha256: str
    byte_length: int
    study_id: Id
    saved_version: int
    revision_id: Id
    kind: Literal["request", "review"]
    review_status: Literal["draft", "reviewed"] | None
    target_count: int
    candidate_count: int
    collection_count: int
    unresolved_count: int
    dependency_count: int


class ErrorDetail(Value):
    """An application error and the inputs involved."""

    code: str
    message: str
    diagnostics: list[Diagnostic]


class ErrorResponse(Value):
    """Error body shared by the HTTP handlers."""

    error: ErrorDetail
