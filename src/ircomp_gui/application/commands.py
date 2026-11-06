# /************************************************************************
# Name: Lukas (Viridis) Dubsik
# ************************************************************************/

"""Define the operations that can change a study."""

from typing import Annotated, Literal

from pydantic import Field

from ircomp_gui.domain.models import (
    CandidateKey,
    Disposition,
    Id,
    Label,
    Target,
    TargetDraft,
    Value,
)


class RenameStudy(Value):
    """Change only a study title."""

    type: Literal["rename_study"]
    title: Label


class ApplyTarget(Value):
    """Accept one target editor buffer."""

    type: Literal["apply_target"]
    draft: TargetDraft


class RemoveTarget(Value):
    """Remove one active target, retaining historical revisions."""

    type: Literal["remove_target"]
    target_id: Id


class RenameTarget(Value):
    """Change a cosmetic label without changing scientific identity."""

    type: Literal["rename_target"]
    target_id: Id
    label: Label


class SetContext(Value):
    """Replace the reference, profile and intervals in one operation."""

    type: Literal["set_context"]
    reference_id: Label
    profile_id: Label
    targets: Annotated[list[Target], Field(max_length=50)]


class AttachEvidence(Value):
    """Attach the evidence file selected in an import preview."""

    type: Literal["attach_evidence"]
    preview_id: Id


class CreateCollection(Value):
    """Create an empty collection for the selected request revision."""

    type: Literal["create_collection"]
    revision_id: Id
    name: Label


class RenameCollection(Value):
    """Rename a review collection without changing membership."""

    type: Literal["rename_collection"]
    collection_id: Id
    name: Label


class RemoveCollection(Value):
    """Remove a collection and decisions, preserving source evidence."""

    type: Literal["remove_collection"]
    collection_id: Id


class AddMember(Value):
    """Add a candidate to a collection with an undecided disposition."""

    type: Literal["add_member"]
    collection_id: Id
    candidate: CandidateKey


class RemoveMember(Value):
    """Remove a membership without deleting evidence."""

    type: Literal["remove_member"]
    collection_id: Id
    candidate: CandidateKey


class SetDecision(Value):
    """Apply a disposition, reason and supporting references to one membership."""

    type: Literal["set_decision"]
    collection_id: Id
    candidate: CandidateKey
    disposition: Disposition
    rationale: Annotated[str, Field(max_length=4000)]
    evidence_refs: Annotated[list[CandidateKey], Field(max_length=100)]


Command = Annotated[
    RenameStudy
    | ApplyTarget
    | RemoveTarget
    | RenameTarget
    | SetContext
    | AttachEvidence
    | CreateCollection
    | RenameCollection
    | RemoveCollection
    | AddMember
    | RemoveMember
    | SetDecision,
    Field(discriminator="type"),
]
