# ************************************************************************
# @file responses.py
# @brief Data returned by the services and sent to the web client
# @author Lukas (Viridis) Dubsik
# @version 0.1
#
# Detailed description:
#  The routes return these models instead of plain dictionaries. FastAPI
#  checks every response against them and /docs shows their fields. The
#  TypeScript types of the client are generated from them too
#  (scripts/generate_contracts.py), so both sides always agree.
# ************************************************************************

"""Define the data returned by the application services."""

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
    """Describe attached evidence, without its original bytes.

    The client never needs the bytes and they can be big, so only the
    parsed bundle and its checksum are sent.
    """

    bundle: EvidenceBundle
    sha256: str


class CollectionView(Collection):
    """Add the count of unfinished decisions to a collection.

    The count is done by unresolved() in domain/rules.py, so the client
    does not have to repeat the rule.
    """

    unresolved_count: int


class StudyView(StudyData):
    """Describe the study as the client sees it (no evidence bytes)."""

    evidence: Annotated[list[EvidenceSummary], Field(max_length=MAX_BUNDLES)]
    collections: Annotated[list[CollectionView], Field(max_length=MAX_COLLECTIONS)]


class WorkspaceView(Value):
    """Hold the open study and its save state.

    Attributes
    ----------
    workspace_id : str
        ID of the session
    base_saved_version : int
        Save counter the study is based on, 0 if never saved
    dirty : bool
        True if there are changes not saved yet
    can_undo : bool
        True if the last change can be undone
    study : StudyView
        The study itself
    diagnostics : list[Diagnostic]
        Problems which stop the request from being exported
    """

    workspace_id: Id
    base_saved_version: int
    dirty: bool
    can_undo: bool
    study: StudyView
    diagnostics: list[Diagnostic]


class StudyList(Value):
    """List the saved studies which can be opened."""

    studies: list[StudySummary]


class Limits(Value):
    """Publish the limits, taken from domain/constants.py."""

    import_bytes: int = MAX_FILE
    targets: int = MAX_TARGETS
    bundles: int = MAX_BUNDLES
    collections: int = MAX_COLLECTIONS
    memberships: int = MAX_MEMBERSHIPS
    revisions: int = MAX_REVISIONS


class CatalogueView(Catalogue):
    """Add the supported file versions and limits to the catalogue."""

    format_versions: list[str] = Field(default_factory=lambda: ["1.0"])
    limits: Limits = Field(default_factory=Limits)


class CheckResult(Value):
    """Describe the result of one check of the request."""

    name: str
    status: Literal["passed", "failed", "not_performed"]
    message: str


class ValidationView(Value):
    """Hold the result of Check request.

    The problems of the unapplied target text are kept apart, as they
    are not a part of the request yet.
    """

    revision_id: Id
    export_ready: bool
    checks: list[CheckResult]
    diagnostics: list[Diagnostic]
    draft_diagnostics: list[Diagnostic]


class ImportSummary(Value):
    """Describe an inspected file, a field is None if it is not known.

    A blocked file is described as far as it could be read, so the user
    can see what it was made for.
    """

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
    """Describe an import preview, kept until accepted or cancelled."""

    preview_id: Id
    kind: Literal["request", "evidence"]
    status: Literal["ready", "blocked", "duplicate"]
    diagnostics: list[Diagnostic]
    summary: ImportSummary


class ExportPreviewView(Value):
    """Describe the file prepared for download (exactly what it contains)."""

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
    """Describe an error with its code, message and the fields involved."""

    code: str
    message: str
    diagnostics: list[Diagnostic]


class ErrorResponse(Value):
    """Wrap the error, the same body is used by all the routes."""

    error: ErrorDetail
