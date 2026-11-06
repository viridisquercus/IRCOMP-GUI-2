# /************************************************************************
# Name: Lukas (Viridis) Dubsik
# ************************************************************************/

"""Manage review collections and the decisions in them."""

from __future__ import annotations

from collections.abc import Callable

from ircomp_gui.application.commands import (
    AddMember,
    CreateCollection,
    RemoveCollection,
    RemoveMember,
    RenameCollection,
    SetDecision,
)
from ircomp_gui.domain.errors import DomainError
from ircomp_gui.domain.models import Collection, Membership, Study
from ircomp_gui.domain.rules import resolve_candidate, revision_by_id


class ReviewService:
    """Manage collections and decisions without changing imported evidence."""

    def __init__(self, new_id: Callable[[], str]) -> None:
        self.new_id = new_id

    def apply(
        self,
        study: Study,
        command: CreateCollection
        | RenameCollection
        | RemoveCollection
        | AddMember
        | RemoveMember
        | SetDecision,
    ) -> Study:
        """Apply a collection operation and return the resulting study."""
        if isinstance(command, CreateCollection):
            _ = revision_by_id(study, command.revision_id)
            collection = Collection(
                collection_id=self.new_id(),
                revision_id=command.revision_id,
                name=command.name,
                memberships=[],
            )
            return study.model_copy(
                update={"collections": [*study.collections, collection]}
            )
        # Find the collection before changing any of its members.
        collection: Collection | None = None
        for item in study.collections:
            if item.collection_id == command.collection_id:
                collection = item
                break
        if collection is None:
            raise DomainError("DANGLING_REFERENCE", "Review collection was not found.")
        buffers = study.draft_buffers
        if isinstance(command, RemoveCollection):
            if (
                buffers.decision
                and buffers.decision.collection_id == collection.collection_id
            ):
                buffers = buffers.model_copy(update={"decision": None})
            return study.model_copy(
                update={
                    "collections": [
                        item
                        for item in study.collections
                        if item.collection_id != collection.collection_id
                    ],
                    "draft_buffers": buffers,
                }
            )
        if isinstance(command, RenameCollection):
            changed = collection.model_copy(update={"name": command.name})
        else:
            resolve_candidate(study, command.candidate, collection.revision_id)
            member: Membership | None = None
            for item in collection.memberships:
                if item.candidate == command.candidate:
                    member = item
                    break
            if isinstance(command, AddMember):
                if member:
                    return study
                changed = collection.model_copy(
                    update={
                        "memberships": [
                            *collection.memberships,
                            Membership(
                                candidate=command.candidate,
                                disposition="undecided",
                                rationale="",
                                evidence_refs=[],
                            ),
                        ]
                    }
                )
            elif isinstance(command, RemoveMember):
                changed = collection.model_copy(
                    update={
                        "memberships": [
                            item
                            for item in collection.memberships
                            if item.candidate != command.candidate
                        ]
                    }
                )
                if (
                    buffers.decision
                    and buffers.decision.collection_id == collection.collection_id
                    and buffers.decision.candidate == command.candidate
                ):
                    buffers = buffers.model_copy(update={"decision": None})
            else:
                if member is None:
                    raise DomainError(
                        "DANGLING_REFERENCE",
                        (
                            "Add the candidate to this collection before recording a "
                            "decision."
                        ),
                    )
                replacement = Membership(
                    candidate=command.candidate,
                    disposition=command.disposition,
                    rationale=command.rationale,
                    evidence_refs=command.evidence_refs,
                )
                # Replace the decision in this collection only.
                memberships: list[Membership] = []
                for item in collection.memberships:
                    if item.candidate == command.candidate:
                        memberships.append(replacement)
                    else:
                        memberships.append(item)
                changed = collection.model_copy(update={"memberships": memberships})
                buffers = buffers.model_copy(update={"decision": None})
        # Put the changed collection back without changing the other ones.
        collections: list[Collection] = []
        for item in study.collections:
            if item.collection_id == changed.collection_id:
                collections.append(changed)
            else:
                collections.append(item)
        return study.model_copy(
            update={"collections": collections, "draft_buffers": buffers}
        )
