# ************************************************************************
# @file prepare.py
# @brief Editing of the request targets and their reference context
# @author Lukas (Viridis) Dubsik
# @date 6-11-2026
# @version 0.1
#
# Detailed description:
#  The study is never changed in place, every operation returns a new one.
#  A change of the coordinates, contig, reference or profile creates a new
#  revision, the old one is kept so its evidence stays valid.
#  A change of the label only does not create a revision.
# ************************************************************************

"""Edit the request targets and their reference context."""

from __future__ import annotations

from collections.abc import Callable

from ircomp_gui.application.commands import (
    ApplyTarget,
    PrepareCommand,
    RemoveTarget,
    RenameStudy,
    RenameTarget,
    SetContext,
)
from ircomp_gui.domain.catalogue import Catalogue
from ircomp_gui.domain.constants import MAX_REVISIONS, MAX_TARGETS
from ircomp_gui.domain.errors import DomainError
from ircomp_gui.domain.models import Revision, Study, Target
from ircomp_gui.domain.rules import (
    active_revision,
    parse_target,
    same_context,
    validate_revision,
)


def _has_target(revision: Revision, target_id: str) -> bool:
    # Check if the revision contains the target
    for target in revision.targets:
        if target.target_id == target_id:
            return True
    return False


def _without_target(revision: Revision, target_id: str) -> list[Target]:
    # Copy the targets apart from the given one
    targets: list[Target] = []
    for target in revision.targets:
        if target.target_id != target_id:
            targets.append(target)
    return targets


def _clear_target_draft(study: Study) -> Study:
    buffers = study.draft_buffers.model_copy(update={"target": None})
    return study.model_copy(update={"draft_buffers": buffers})


class PrepareService:
    """Edit the request, the previous study always stays unchanged.

    Attributes
    ----------
    catalogue : Catalogue
        Supported references and profiles
    new_id : Callable
        Generator of new IDs
    """

    def __init__(self, catalogue: Catalogue, new_id: Callable[[], str]) -> None:
        self.catalogue = catalogue
        self.new_id = new_id

    def apply(self, study: Study, command: PrepareCommand) -> Study:
        """Apply the request operation and return the resulting study.

        Parameters
        ----------
        study : Study
            Study to change
        command : PrepareCommand
            Operation to apply

        Returns
        -------
        Study
            The changed study (or the same one if nothing changed)
        """
        # Operations not touching the revision
        if isinstance(command, RenameStudy):
            return study.model_copy(update={"title": command.title})
        if isinstance(command, RenameTarget):
            return self._rename_target(study, command)

        # Operations proposing a new revision
        revision = active_revision(study)
        if isinstance(command, ApplyTarget):
            study, proposed = self._apply_target(study, revision, command)
        elif isinstance(command, RemoveTarget):
            study, proposed = self._remove_target(study, revision, command)
        else:
            proposed = self._set_context(revision, command)

        return self._add_revision(study, revision, proposed)

    def _rename_target(self, study: Study, command: RenameTarget) -> Study:
        if command.target_id not in study.target_labels:
            raise DomainError("DANGLING_REFERENCE", "Target label does not exist.")

        labels = dict(study.target_labels)
        labels[command.target_id] = command.label
        return study.model_copy(update={"target_labels": labels})

    def _apply_target(
        self, study: Study, revision: Revision, command: ApplyTarget
    ) -> tuple[Study, Revision]:
        # A draft without ID adds a new target, with ID it edits that one
        target_id = command.draft.target_id or self.new_id()
        if command.draft.target_id and not _has_target(revision, target_id):
            raise DomainError(
                "DANGLING_REFERENCE", "Only an active target can be edited."
            )

        # Replace the old version of the target (if there was any)
        target = parse_target(command.draft, target_id)
        targets = [*_without_target(revision, target_id), target]
        proposed = revision.model_copy(update={"targets": targets})

        # Store the label and clear the applied draft
        labels = dict(study.target_labels)
        labels[target_id] = command.draft.label
        study = _clear_target_draft(study).model_copy(update={"target_labels": labels})
        return study, proposed

    def _remove_target(
        self, study: Study, revision: Revision, command: RemoveTarget
    ) -> tuple[Study, Revision]:
        if not _has_target(revision, command.target_id):
            raise DomainError(
                "DANGLING_REFERENCE", "Only an active target can be removed."
            )
        targets = _without_target(revision, command.target_id)
        proposed = revision.model_copy(update={"targets": targets})

        # The label stays (old revisions still use it), only the draft goes
        draft = study.draft_buffers.target
        if draft and draft.target_id == command.target_id:
            study = _clear_target_draft(study)
        return study, proposed

    def _set_context(self, revision: Revision, command: SetContext) -> Revision:
        # Exactly the same targets have to stay, only their values can change
        new_ids = {target.target_id for target in command.targets}
        old_ids = {target.target_id for target in revision.targets}
        if new_ids != old_ids:
            raise DomainError(
                "DANGLING_REFERENCE",
                "Context replacement must preserve exactly the active target "
                "identities.",
            )
        return revision.model_copy(
            update={
                "reference_id": command.reference_id,
                "profile_id": command.profile_id,
                "targets": command.targets,
            }
        )

    def _add_revision(
        self, study: Study, revision: Revision, proposed: Revision
    ) -> Study:
        if len(proposed.targets) > MAX_TARGETS:
            raise DomainError(
                "LIMIT_EXCEEDED", "A request supports at most 50 targets."
            )

        # model_copy does not validate, so validate the proposal again
        proposed = Revision.model_validate(proposed.model_dump())
        validate_revision(proposed, self.catalogue)

        # Nothing changed, no new revision needed
        if same_context(proposed, revision):
            return study

        if len(study.revisions) >= MAX_REVISIONS:
            raise DomainError(
                "LIMIT_EXCEEDED",
                "The 200-revision limit is reached. Duplicate the active "
                "request to start a new study.",
            )

        # Add the proposal as a new active revision
        proposed = proposed.model_copy(update={"revision_id": self.new_id()})
        return study.model_copy(
            update={
                "active_revision_id": proposed.revision_id,
                "revisions": [*study.revisions, proposed],
            }
        )
