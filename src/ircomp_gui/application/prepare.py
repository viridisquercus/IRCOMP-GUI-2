# /************************************************************************
# Name: Lukas (Viridis) Dubsik
# ************************************************************************/

"""Edit request targets and their reference context."""

from __future__ import annotations

from collections.abc import Callable

from ircomp_gui.application.commands import (
    ApplyTarget,
    RemoveTarget,
    RenameStudy,
    RenameTarget,
    SetContext,
)
from ircomp_gui.domain.catalogue import Catalogue
from ircomp_gui.domain.errors import DomainError
from ircomp_gui.domain.models import Revision, Study
from ircomp_gui.domain.rules import (
    active_revision,
    parse_target,
    same_context,
    validate_revision,
)


class PrepareService:
    """Edit the request while keeping the previous study unchanged."""

    def __init__(self, catalogue: Catalogue, new_id: Callable[[], str]) -> None:
        self.catalogue = catalogue
        self.new_id = new_id

    def apply(
        self,
        study: Study,
        command: RenameStudy | ApplyTarget | RemoveTarget | RenameTarget | SetContext,
    ) -> Study:
        """Apply a request operation and return the resulting study."""
        if isinstance(command, RenameStudy):
            return study.model_copy(update={"title": command.title})
        revision = active_revision(study)
        if isinstance(command, RenameTarget):
            if command.target_id not in study.target_labels:
                raise DomainError("DANGLING_REFERENCE", "Target label does not exist.")
            return study.model_copy(
                update={
                    "target_labels": {
                        **study.target_labels,
                        command.target_id: command.label,
                    }
                }
            )
        if isinstance(command, ApplyTarget):
            target_id = command.draft.target_id or self.new_id()
            if command.draft.target_id and not any(
                target.target_id == target_id for target in revision.targets
            ):
                raise DomainError(
                    "DANGLING_REFERENCE", "Only an active target can be edited."
                )
            target = parse_target(command.draft, target_id)
            targets = [
                item for item in revision.targets if item.target_id != target_id
            ] + [target]
            proposed = revision.model_copy(update={"targets": targets})
            study = study.model_copy(
                update={
                    "target_labels": {
                        **study.target_labels,
                        target_id: command.draft.label,
                    },
                    "draft_buffers": study.draft_buffers.model_copy(
                        update={"target": None}
                    ),
                }
            )
        elif isinstance(command, RemoveTarget):
            if not any(
                target.target_id == command.target_id for target in revision.targets
            ):
                raise DomainError(
                    "DANGLING_REFERENCE", "Only an active target can be removed."
                )
            proposed = revision.model_copy(
                update={
                    "targets": [
                        target
                        for target in revision.targets
                        if target.target_id != command.target_id
                    ]
                }
            )
            if (
                study.draft_buffers.target
                and study.draft_buffers.target.target_id == command.target_id
            ):
                study = study.model_copy(
                    update={
                        "draft_buffers": study.draft_buffers.model_copy(
                            update={"target": None}
                        )
                    }
                )
        else:
            if {target.target_id for target in command.targets} != {
                target.target_id for target in revision.targets
            }:
                raise DomainError(
                    "DANGLING_REFERENCE",
                    (
                        "Context replacement must preserve exactly the active target "
                        "identities."
                    ),
                )
            proposed = revision.model_copy(
                update={
                    "reference_id": command.reference_id,
                    "profile_id": command.profile_id,
                    "targets": command.targets,
                }
            )
        if len(proposed.targets) > 50:
            raise DomainError(
                "LIMIT_EXCEEDED", "A request supports at most 50 targets."
            )
        proposed = Revision.model_validate(proposed.model_dump())
        validate_revision(proposed, self.catalogue)
        if same_context(proposed, revision):
            return study
        if len(study.revisions) >= 200:
            raise DomainError(
                "LIMIT_EXCEEDED",
                (
                    "The 200-revision limit is reached. Duplicate the active "
                    "request to start a new study."
                ),
            )
        proposed = proposed.model_copy(update={"revision_id": self.new_id()})
        return study.model_copy(
            update={
                "active_revision_id": proposed.revision_id,
                "revisions": [*study.revisions, proposed],
            }
        )
