# ************************************************************************
# @file models.py
# @brief Data of the study, request and review
# @author Lukas (Viridis) Dubsik
# @version 0.1
#
# Detailed description:
#  Every class here is a frozen pydantic model. Unknown fields are refused,
#  so a file from a newer version cannot silently lose data.
# ************************************************************************

"""Define the data of the study, request and review."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from ircomp_gui.domain.constants import (
    MAX_BASE64,
    MAX_BUNDLES,
    MAX_CANDIDATES,
    MAX_COLLECTIONS,
    MAX_DEPENDENCIES,
    MAX_LABEL,
    MAX_MEMBERSHIPS,
    MAX_METRICS,
    MAX_RATIONALE,
    MAX_REFERENCES,
    MAX_REVISIONS,
    MAX_SAFE_INTEGER,
    MAX_TARGETS,
)

# Basic types
UUID_PATTERN = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
CANDIDATE_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_.:-]*$"

Id = Annotated[str, Field(pattern=UUID_PATTERN)]
Label = Annotated[str, Field(min_length=1, max_length=MAX_LABEL, pattern=r"\S")]
Text = Annotated[str, Field(max_length=MAX_LABEL)]
Coordinate = Annotated[int, Field(ge=0, le=MAX_SAFE_INTEGER)]
CandidateId = Annotated[
    str, Field(min_length=1, max_length=100, pattern=CANDIDATE_PATTERN)
]
Rationale = Annotated[str, Field(max_length=MAX_RATIONALE)]
Strand = Literal["+", "-", "."]
Disposition = Literal[
    "undecided", "include_for_review", "exclude", "needs_clarification"
]


class Value(BaseModel):
    """Base of all models, keeps the values typed and refuses unknown fields."""

    model_config = ConfigDict(
        strict=True,
        extra="forbid",
        frozen=True,
        allow_inf_nan=False,
        json_schema_serialization_defaults_required=True,
    )


class Diagnostic(Value):
    """Describe one problem and the field it belongs to.

    Attributes
    ----------
    code : str
        Machine readable error code, such as INTERVAL_INVALID
    severity : str
        How serious the problem is (error, warning, info)
    location : str | None
        JSON pointer to the field, None if not tied to one
    message : str
        Text shown to the user
    """

    code: str
    severity: Literal["error", "warning", "info"] = "error"
    location: str | None = None
    message: str


class Target(Value):
    """Store one target interval on an exact contig accession.

    Attributes
    ----------
    target_id : str
        UUID of the target, stays the same through revisions
    contig : str
        Accession of the contig (for example NC_000001.11)
    start : int
        First base of the interval, 0-based
    end : int
        End of the interval, exclusive
    strand : str
        +, - or . when not specified
    """

    target_id: Id
    contig: Label
    start: Coordinate
    end: Coordinate
    strand: Strand


class Revision(Value):
    """Keep the reference and targets of one request revision.

    Attributes
    ----------
    revision_id : str
        UUID of the revision
    reference_id : str
        Catalogue ID of the reference
    profile_id : str
        Catalogue ID of the analysis profile
    coordinate_system : str
        Always 0-based-half-open
    targets : list[Target]
        Accepted targets of this revision
    """

    revision_id: Id
    reference_id: Label
    profile_id: Label
    coordinate_system: Literal["0-based-half-open"] = "0-based-half-open"
    targets: Annotated[list[Target], Field(max_length=MAX_TARGETS)]


class RequestSnapshot(Value):
    """Store one request revision in the local exchange format.

    Attributes
    ----------
    study_id, request_id : str
        Identity of the study the request comes from
    title : str
        Title of the study
    revision : Revision
        The exported revision
    target_labels : dict[str, str]
        Labels of the targets of the revision, keyed by target ID
    """

    kind: Literal["request"] = "request"
    format_version: Literal["1.0"] = "1.0"
    study_id: Id
    request_id: Id
    title: Label
    revision: Revision
    target_labels: dict[Id, Label]


class Metric(Value):
    """Store one score together with its meaning and availability.

    Zero and a missing value are different things here, the availability
    says which one it is.
    """

    name: Label
    model: Text | None
    unit: Text | None
    scale: Text | None
    direction: Literal["higher", "lower", "not_ordered"] | None
    availability: Literal["present", "not_supplied", "unsupported", "failed", "unknown"]
    value: float | int | None


class CandidateKey(Value):
    """Identify a candidate by the bundle ID and candidate ID."""

    bundle_id: Id
    candidate_id: CandidateId


class Candidate(Value):
    """Describe a candidate and keep the original record of its producer.

    Attributes
    ----------
    candidate_id : str
        ID of the candidate, unique inside its bundle
    target_id : str
        Target the candidate belongs to
    label : str
        Name shown in the candidate list
    metrics : list[Metric]
        Scores supplied by the producer
    raw_record : dict
        Untouched record as the producer wrote it
    """

    candidate_id: CandidateId
    target_id: Id
    label: Label
    metrics: Annotated[list[Metric], Field(max_length=MAX_METRICS)]
    raw_record: dict[str, JsonValue]


class Source(Value):
    """Describe the producer declared in the evidence file."""

    name: Label
    version: Label
    uri: Annotated[str, Field(max_length=2000)] | None


class Dependency(Value):
    """Record an external file or resource, it is never downloaded."""

    uri: Annotated[str, Field(min_length=1, max_length=2000)]
    description: Annotated[str, Field(min_length=1, max_length=1000)]


class EvidenceBundle(Value):
    """Group candidates with the request context their producer used.

    Attributes
    ----------
    bundle_id : str
        UUID of the bundle
    request_id : str
        Request the bundle was produced for
    context : Revision
        Exact revision the producer received
    category : str
        synthetic or computational_prediction
    source : Source
        Who produced the bundle
    candidates : list[Candidate]
        Candidates of the bundle
    dependencies : list[Dependency]
        External resources the producer refers to
    """

    kind: Literal["evidence"] = "evidence"
    format_version: Literal["1.0"] = "1.0"
    bundle_id: Id
    request_id: Id
    context: Revision
    category: Literal["synthetic", "computational_prediction"]
    source: Source
    candidates: Annotated[list[Candidate], Field(max_length=MAX_CANDIDATES)]
    dependencies: Annotated[list[Dependency], Field(max_length=MAX_DEPENDENCIES)]


class EvidenceFile(Value):
    """Keep the original evidence file together with its checksum.

    Attributes
    ----------
    bundle : EvidenceBundle
        Parsed contents of the file
    sha256 : str
        Checksum of the original bytes
    content_base64 : str
        Original bytes, base64 encoded
    """

    bundle: EvidenceBundle
    sha256: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    content_base64: str


class Membership(Value):
    """Store the decision about one candidate in one collection.

    Attributes
    ----------
    candidate : CandidateKey
        The candidate the decision is about
    disposition : str
        The decision itself
    rationale : str
        Why the decision was made
    evidence_refs : list[CandidateKey]
        Other candidates supporting the decision
    """

    candidate: CandidateKey
    disposition: Disposition
    rationale: Rationale
    evidence_refs: Annotated[list[CandidateKey], Field(max_length=MAX_REFERENCES)]


class Collection(Value):
    """Group the decisions belonging to one request revision."""

    collection_id: Id
    revision_id: Id
    name: Label
    memberships: Annotated[list[Membership], Field(max_length=MAX_MEMBERSHIPS)]


class TargetDraft(Value):
    """Keep the target editor input as text before it is accepted.

    The values stay text so an unfinished input (empty end for example)
    can be saved and restored without being applied.
    """

    target_id: Id | None
    label: Text
    contig: Text
    start: Text
    end: Text
    strand: Text


class DecisionDraft(Membership):
    """Keep an unfinished decision separate from the accepted one."""

    collection_id: Id


class DraftBuffers(Value):
    """Keep the current target and decision text before it is applied."""

    target: TargetDraft | None = None
    decision: DecisionDraft | None = None


class StudyData(Value):
    """Study fields shared by the database and browser responses."""

    study_id: Id
    request_id: Id
    title: Label
    active_revision_id: Id
    revisions: Annotated[list[Revision], Field(min_length=1, max_length=MAX_REVISIONS)]
    target_labels: dict[Id, Label]
    draft_buffers: DraftBuffers


class Study(StudyData):
    """Keep all the data belonging to one study.

    Attributes
    ----------
    study_id, request_id : str
        Identity of the study and of its request
    title : str
        Title of the study
    active_revision_id : str
        Revision that is currently edited
    revisions : list[Revision]
        All retained revisions, the old ones are read-only
    target_labels : dict[str, str]
        Labels of all targets from all revisions
    evidence : list[EvidenceFile]
        Attached evidence with original bytes
    collections : list[Collection]
        Review collections and their decisions
    draft_buffers : DraftBuffers
        Unapplied editor text saved for recovery
    """

    evidence: Annotated[list[EvidenceFile], Field(max_length=MAX_BUNDLES)]
    collections: Annotated[list[Collection], Field(max_length=MAX_COLLECTIONS)]


class ReviewSourceFile(Value):
    """Original evidence bytes included in a review download."""

    bundle_id: Id
    sha256: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    content_base64: Annotated[
        str,
        Field(
            min_length=4,
            max_length=MAX_BASE64,
            pattern=r"^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$",
        ),
    ]


class ReviewPackage(Value):
    """Saved request, review decisions and the original evidence files."""

    kind: Literal["review"] = "review"
    format_version: Literal["1.0"] = "1.0"
    request: RequestSnapshot
    source_saved_version: Annotated[int, Field(ge=1)]
    collections: Annotated[
        list[Collection], Field(min_length=1, max_length=MAX_COLLECTIONS)
    ]
    evidence_files: Annotated[
        list[ReviewSourceFile], Field(min_length=1, max_length=MAX_BUNDLES)
    ]
    review_status: Literal["draft", "reviewed"]
    unresolved_count: Annotated[int, Field(ge=0, le=MAX_MEMBERSHIPS + MAX_COLLECTIONS)]
