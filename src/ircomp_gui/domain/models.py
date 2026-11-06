# /************************************************************************
# Name: Lukas (Viridis) Dubsik
# ************************************************************************/

"""Define the study, request and review data."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue

Id = Annotated[
    str,
    Field(pattern=r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"),
]
Label = Annotated[str, Field(min_length=1, max_length=200, pattern=r"\S")]
Text = Annotated[str, Field(max_length=200)]
Coordinate = Annotated[int, Field(ge=0, le=9007199254740991)]
Disposition = Literal[
    "undecided", "include_for_review", "exclude", "needs_clarification"
]


class Value(BaseModel):
    """Keep model values typed and reject unknown fields."""

    model_config = ConfigDict(
        strict=True, extra="forbid", frozen=True, allow_inf_nan=False
    )


class Diagnostic(Value):
    """Describe a problem and the field to which it belongs."""

    code: str
    severity: Literal["error", "warning", "info"] = "error"
    location: str | None = None
    message: str


class Target(Value):
    """Store one target interval using an exact contig accession."""

    target_id: Id
    contig: Label
    start: Coordinate
    end: Coordinate
    strand: Literal["+", "-", "."]


class Revision(Value):
    """Keep the reference and targets for one request revision."""

    revision_id: Id
    reference_id: Label
    profile_id: Label
    coordinate_system: Literal["0-based-half-open"] = "0-based-half-open"
    targets: Annotated[list[Target], Field(max_length=50)]


class RequestSnapshot(Value):
    """Store one request revision in the local exchange format."""

    kind: Literal["request"] = "request"
    format_version: Literal["1.0"] = "1.0"
    study_id: Id
    request_id: Id
    title: Label
    revision: Revision
    target_labels: dict[Id, Label]


class Metric(Value):
    """Store a score together with its meaning and availability."""

    name: Label
    model: Text | None
    unit: Text | None
    scale: Text | None
    direction: Literal["higher", "lower", "not_ordered"] | None
    availability: Literal["present", "not_supplied", "unsupported", "failed", "unknown"]
    value: float | int | None


class CandidateKey(Value):
    """Identify a candidate by its bundle ID and candidate ID."""

    bundle_id: Id
    candidate_id: Annotated[
        str,
        Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]*$"),
    ]


class Candidate(Value):
    """Describe a candidate and retain the original producer record."""

    candidate_id: Annotated[
        str,
        Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:-]*$"),
    ]
    target_id: Id
    label: Label
    metrics: Annotated[list[Metric], Field(max_length=20)]
    raw_record: dict[str, JsonValue]


class Source(Value):
    """Describe the producer declared by an evidence file."""

    name: Label
    version: Label
    uri: Annotated[str, Field(max_length=2000)] | None


class Dependency(Value):
    """Record an external file or resource without downloading it."""

    uri: Annotated[str, Field(min_length=1, max_length=2000)]
    description: Annotated[str, Field(min_length=1, max_length=1000)]


class EvidenceBundle(Value):
    """Group candidates with the request context used by their producer."""

    kind: Literal["evidence"] = "evidence"
    format_version: Literal["1.0"] = "1.0"
    bundle_id: Id
    request_id: Id
    context: Revision
    category: Literal["synthetic", "computational_prediction"]
    source: Source
    candidates: Annotated[list[Candidate], Field(max_length=200)]
    dependencies: Annotated[list[Dependency], Field(max_length=100)]


class EvidenceFile(Value):
    """Keep the original evidence file together with its checksum."""

    bundle: EvidenceBundle
    sha256: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    content_base64: str


class Membership(Value):
    """Store the decision about a candidate in one collection."""

    candidate: CandidateKey
    disposition: Disposition
    rationale: Annotated[str, Field(max_length=4000)]
    evidence_refs: Annotated[list[CandidateKey], Field(max_length=100)]


class Collection(Value):
    """Group candidate decisions belonging to one request revision."""

    collection_id: Id
    revision_id: Id
    name: Label
    memberships: Annotated[list[Membership], Field(max_length=1000)]


class TargetDraft(Value):
    """Keep target input as text before it is accepted."""

    target_id: Id | None
    label: Text
    contig: Text
    start: Text
    end: Text
    strand: Text


class DecisionDraft(Value):
    """Keep an unfinished decision separate from an accepted one."""

    collection_id: Id
    candidate: CandidateKey
    disposition: Disposition
    rationale: Annotated[str, Field(max_length=4000)]
    evidence_refs: Annotated[list[CandidateKey], Field(max_length=100)]


class DraftBuffers(Value):
    """Keep the current target and decision text before it is applied."""

    target: TargetDraft | None = None
    decision: DecisionDraft | None = None


class Study(Value):
    """Keep all data that belongs to one study."""

    study_id: Id
    request_id: Id
    title: Label
    active_revision_id: Id
    revisions: Annotated[list[Revision], Field(min_length=1, max_length=200)]
    target_labels: dict[Id, Label]
    evidence: Annotated[list[EvidenceFile], Field(max_length=10)]
    collections: Annotated[list[Collection], Field(max_length=20)]
    draft_buffers: DraftBuffers
