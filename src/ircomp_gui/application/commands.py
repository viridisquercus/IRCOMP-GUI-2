# ************************************************************************
# @file commands.py
# @brief Operations which can change a study
# @author Lukas (Viridis) Dubsik
# @version 0.1
#
# Detailed description:
#  Each command is one class with a fixed "type" field. The web client
#  sends the type and pydantic picks the right class from it.
#  Request commands are handled in prepare.py, review ones in review.py.
# ************************************************************************

"""Define the operations which can change a study."""

from typing import Annotated, Literal

from pydantic import Field

from ircomp_gui.domain.constants import MAX_REFERENCES, MAX_TARGETS
from ircomp_gui.domain.models import (
    CandidateKey,
    Disposition,
    Id,
    Label,
    Rationale,
    Target,
    TargetDraft,
    Value,
)

# ---------------------------------------------------------------------------
# Request commands
# ---------------------------------------------------------------------------


class RenameStudy(Value):
    """Change only the title of the study."""

    type: Literal["rename_study"]
    title: Label


class ApplyTarget(Value):
    """Accept the text from the target editor."""

    type: Literal["apply_target"]
    draft: TargetDraft


class RemoveTarget(Value):
    """Remove one active target, the old revisions keep it."""

    type: Literal["remove_target"]
    target_id: Id


class RenameTarget(Value):
    """Change only the label of a target, its identity stays."""

    type: Literal["rename_target"]
    target_id: Id
    label: Label


class SetContext(Value):
    """Replace the reference, profile and intervals in one step."""

    type: Literal["set_context"]
    reference_id: Label
    profile_id: Label
    targets: Annotated[list[Target], Field(max_length=MAX_TARGETS)]


# ---------------------------------------------------------------------------
# Review commands
# ---------------------------------------------------------------------------


class AttachEvidence(Value):
    """Attach the evidence file shown in the import preview."""

    type: Literal["attach_evidence"]
    preview_id: Id


class CreateCollection(Value):
    """Create an empty collection for the chosen revision."""

    type: Literal["create_collection"]
    revision_id: Id
    name: Label


class RenameCollection(Value):
    """Rename a collection, its members stay."""

    type: Literal["rename_collection"]
    collection_id: Id
    name: Label


class RemoveCollection(Value):
    """Remove a collection and its decisions, the evidence stays."""

    type: Literal["remove_collection"]
    collection_id: Id


class AddMember(Value):
    """Add a candidate to a collection as undecided."""

    type: Literal["add_member"]
    collection_id: Id
    candidate: CandidateKey


class RemoveMember(Value):
    """Remove a candidate from a collection, the evidence stays."""

    type: Literal["remove_member"]
    collection_id: Id
    candidate: CandidateKey


class SetDecision(Value):
    """Set the disposition, reason and references of one membership."""

    type: Literal["set_decision"]
    collection_id: Id
    candidate: CandidateKey
    disposition: Disposition
    rationale: Rationale
    evidence_refs: Annotated[list[CandidateKey], Field(max_length=MAX_REFERENCES)]


# Groups used by the services
PrepareCommand = RenameStudy | ApplyTarget | RemoveTarget | RenameTarget | SetContext
ReviewCommand = (
    CreateCollection
    | RenameCollection
    | RemoveCollection
    | AddMember
    | RemoveMember
    | SetDecision
)

# Any command, picked by its type field
Command = Annotated[
    PrepareCommand | AttachEvidence | ReviewCommand,
    Field(discriminator="type"),
]
