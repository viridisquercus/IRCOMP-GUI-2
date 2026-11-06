# ************************************************************************
# @file review.py
# @brief Review collections and the decisions in them
# @author Lukas (Viridis) Dubsik
# @date 6-11-2026
# @version 0.1
#
# Detailed description:
#  A collection belongs to one revision and holds decisions about the
#  candidates of that revision. The same candidate can be in more
#  collections with a different decision in each of them.
#  The imported evidence itself is never changed here.
# ************************************************************************

"""Manage the review collections and the decisions in them."""

from __future__ import annotations

from collections.abc import Callable

from ircomp_gui.application.commands import (
    AddMember,
    CreateCollection,
    RemoveCollection,
    RemoveMember,
    RenameCollection,
    ReviewCommand,
    SetDecision,
)
from ircomp_gui.domain.errors import DomainError
from ircomp_gui.domain.models import (
    CandidateKey,
    Collection,
    DraftBuffers,
    Membership,
    Study,
)
from ircomp_gui.domain.rules import find_collection, resolve_candidate, revision_by_id


def _find_member(collection: Collection, candidate: CandidateKey) -> Membership | None:
    # Find the membership of the candidate in the collection
    for member in collection.memberships:
        if member.candidate == candidate:
            return member
    return None


def _draft_in(buffers: DraftBuffers, collection: Collection) -> bool:
    # Check if the decision draft belongs to the collection
    draft = buffers.decision
    return draft is not None and draft.collection_id == collection.collection_id


class ReviewService:
    """Manage the collections and decisions, the evidence stays unchanged.

    Attributes
    ----------
    new_id : Callable
        Generator of new IDs
    """

    def __init__(self, new_id: Callable[[], str]) -> None:
        self.new_id = new_id

    def apply(self, study: Study, command: ReviewCommand) -> Study:
        """Apply the collection operation and return the resulting study.

        Parameters
        ----------
        study : Study
            Study to change
        command : ReviewCommand
            Operation to apply

        Returns
        -------
        Study
            The changed study (or the same one if nothing changed)
        """
        if isinstance(command, CreateCollection):
            return self._create(study, command)

        # Every other command works on an existing collection
        collection = find_collection(study, command.collection_id)
        if collection is None:
            raise DomainError("DANGLING_REFERENCE", "Review collection was not found.")

        if isinstance(command, RemoveCollection):
            return self._remove(study, collection)

        buffers = study.draft_buffers
        if isinstance(command, RenameCollection):
            changed = collection.model_copy(update={"name": command.name})
        else:
            # Commands about a candidate - it has to be in this revision
            resolve_candidate(study, command.candidate, collection.revision_id)
            member = _find_member(collection, command.candidate)

            if isinstance(command, AddMember):
                # Adding it twice does nothing
                if member:
                    return study
                changed = self._add_member(collection, command)
            elif isinstance(command, RemoveMember):
                changed = self._remove_member(collection, command)
                # Drop the draft if it was about the removed candidate
                draft = buffers.decision
                if (
                    _draft_in(buffers, collection)
                    and draft is not None
                    and draft.candidate == command.candidate
                ):
                    buffers = buffers.model_copy(update={"decision": None})
            else:
                changed = self._set_decision(collection, member, command)
                buffers = buffers.model_copy(update={"decision": None})

        return self._replace(study, changed, buffers)

    def _create(self, study: Study, command: CreateCollection) -> Study:
        # The revision has to exist
        revision_by_id(study, command.revision_id)

        collection = Collection(
            collection_id=self.new_id(),
            revision_id=command.revision_id,
            name=command.name,
            memberships=[],
        )
        return study.model_copy(
            update={"collections": [*study.collections, collection]}
        )

    def _remove(self, study: Study, collection: Collection) -> Study:
        buffers = study.draft_buffers
        if _draft_in(buffers, collection):
            buffers = buffers.model_copy(update={"decision": None})

        # Keep all the other collections
        collections: list[Collection] = []
        for item in study.collections:
            if item.collection_id != collection.collection_id:
                collections.append(item)

        return study.model_copy(
            update={"collections": collections, "draft_buffers": buffers}
        )

    def _add_member(self, collection: Collection, command: AddMember) -> Collection:
        member = Membership(
            candidate=command.candidate,
            disposition="undecided",
            rationale="",
            evidence_refs=[],
        )
        return collection.model_copy(
            update={"memberships": [*collection.memberships, member]}
        )

    def _remove_member(
        self, collection: Collection, command: RemoveMember
    ) -> Collection:
        memberships: list[Membership] = []
        for item in collection.memberships:
            if item.candidate != command.candidate:
                memberships.append(item)
        return collection.model_copy(update={"memberships": memberships})

    def _set_decision(
        self,
        collection: Collection,
        member: Membership | None,
        command: SetDecision,
    ) -> Collection:
        if member is None:
            raise DomainError(
                "DANGLING_REFERENCE",
                "Add the candidate to this collection before recording a decision.",
            )

        replacement = Membership(
            candidate=command.candidate,
            disposition=command.disposition,
            rationale=command.rationale,
            evidence_refs=command.evidence_refs,
        )

        # Replace the decision in this collection only
        memberships: list[Membership] = []
        for item in collection.memberships:
            if item.candidate == command.candidate:
                memberships.append(replacement)
            else:
                memberships.append(item)
        return collection.model_copy(update={"memberships": memberships})

    def _replace(
        self, study: Study, changed: Collection, buffers: DraftBuffers
    ) -> Study:
        # Put the changed collection back, the other ones stay as they are
        collections: list[Collection] = []
        for item in study.collections:
            if item.collection_id == changed.collection_id:
                collections.append(changed)
            else:
                collections.append(item)

        return study.model_copy(
            update={"collections": collections, "draft_buffers": buffers}
        )
