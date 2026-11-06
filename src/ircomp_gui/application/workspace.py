# /************************************************************************
# Name: Lukas (Viridis) Dubsik
# ************************************************************************/

"""Keep the working study and handle Save and Undo."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from threading import RLock
from typing import Any
from uuid import uuid4

from ircomp_gui.application.commands import (
    ApplyTarget,
    AttachEvidence,
    Command,
    RemoveTarget,
    RenameStudy,
    RenameTarget,
    SetContext,
)
from ircomp_gui.application.ports import Repository
from ircomp_gui.application.prepare import PrepareService
from ircomp_gui.application.review import ReviewService
from ircomp_gui.domain.catalogue import Catalogue
from ircomp_gui.domain.errors import DomainError
from ircomp_gui.domain.models import (
    Diagnostic,
    DraftBuffers,
    RequestSnapshot,
    Revision,
    Study,
    TargetDraft,
)
from ircomp_gui.domain.rules import (
    active_revision,
    parse_target,
    request_diagnostics,
    revision_by_id,
    validate_revision,
    validate_study,
)


@dataclass
class Session:
    """Keep the working study, its saved copy and the last Undo copy."""

    workspace_id: str
    study: Study
    base_saved_version: int = 0
    saved: Study | None = None
    previous: Study | None = None


def new_uuid() -> str:
    """Create a UUID for a new study object."""
    return str(uuid4())


class WorkspaceService:
    """Keep working studies and handle their changes, saves and Undo.

    Attributes:
        repository: Storage used to load and save complete studies.
        catalogue: Supported references and profiles used for input checks.
        sessions: Working copies that exist while the service is running.
        lock: Local lock used to order changes from HTTP handlers.
        prepare: Functions for changing request targets and context.
        review: Functions for changing collections and decisions.
    """

    def __init__(
        self,
        repository: Repository,
        catalogue: Catalogue,
        new_id: Callable[[], str] = new_uuid,
    ) -> None:
        self.repository = repository
        self.catalogue = catalogue
        self.new_id = new_id
        self.sessions: dict[str, Session] = {}
        self.lock = RLock()
        self.prepare = PrepareService(catalogue, new_id)
        self.review = ReviewService(new_id)

    def get(self, workspace_id: str) -> Session:
        """Resolve a local working session."""
        session = self.sessions.get(workspace_id)
        if session is None:
            raise DomainError(
                "SESSION_EXPIRED",
                (
                    "This working session is unavailable. Reopen the saved study;"
                    " unsaved changes may be lost."
                ),
            )
        return session

    def view(self, session: Session) -> dict[str, Any]:
        """Prepare the workspace data sent back to the web client."""
        return {
            "workspace_id": session.workspace_id,
            "base_saved_version": session.base_saved_version,
            "dirty": session.study != session.saved,
            "can_undo": session.previous is not None,
            "study": session.study.model_dump(
                mode="json", exclude={"evidence": {"__all__": {"content_base64"}}}
            ),
            "diagnostics": [
                item.model_dump()
                for item in request_diagnostics(
                    session.study, active_revision(session.study), self.catalogue
                )
            ],
        }

    def _register(self, study: Study, saved_version: int = 0) -> Session:
        validate_study(study, self.catalogue)
        session = Session(
            workspace_id=self.new_id(),
            study=study,
            base_saved_version=saved_version,
            saved=study if saved_version else None,
        )
        self.sessions[session.workspace_id] = session
        return session

    def create(self, title: str) -> Session:
        """Create an empty study using the demonstration reference and profile."""
        with self.lock:
            revision = Revision(
                revision_id=self.new_id(),
                reference_id="demo-reference-v1",
                profile_id="demo-spcas9-ngg-v1",
                targets=[],
            )
            study = Study(
                study_id=self.new_id(),
                request_id=self.new_id(),
                title=title,
                active_revision_id=revision.revision_id,
                revisions=[revision],
                target_labels={},
                evidence=[],
                collections=[],
                draft_buffers=DraftBuffers(),
            )
            return self._register(study)

    def open(self, study_id: str) -> Session:
        """Load a saved study into a working copy, including its editor text."""
        with self.lock:
            saved = self.repository.load(study_id)
            return self._register(saved.study, saved.saved_version)

    def import_request(self, request: RequestSnapshot) -> Session:
        """Open an imported request while keeping its IDs."""
        with self.lock:
            collision = self.repository.identity_exists(
                request.study_id, request.request_id
            )
            if collision:
                code = (
                    "IDENTITY_EXISTS"
                    if collision == request.study_id
                    else "IDENTITY_CONFLICT"
                )
                raise DomainError(
                    code,
                    f"Identity already belongs to study {collision}. "
                    "Open it or duplicate its request.",
                )
            study = Study(
                study_id=request.study_id,
                request_id=request.request_id,
                title=request.title,
                active_revision_id=request.revision.revision_id,
                revisions=[request.revision],
                target_labels=request.target_labels,
                evidence=[],
                collections=[],
                draft_buffers=DraftBuffers(),
            )
            return self._register(study)

    def duplicate(self, workspace_id: str, title: str) -> Session:
        """Copy the active request into a new study with new IDs."""
        with self.lock:
            source = self.get(workspace_id).study
            revision = active_revision(source)
            replacements = {
                target.target_id: self.new_id() for target in revision.targets
            }
            copied = revision.model_copy(
                update={
                    "revision_id": self.new_id(),
                    "targets": [
                        target.model_copy(
                            update={"target_id": replacements[target.target_id]}
                        )
                        for target in revision.targets
                    ],
                }
            )
            study = Study(
                study_id=self.new_id(),
                request_id=self.new_id(),
                title=title,
                active_revision_id=copied.revision_id,
                revisions=[copied],
                target_labels={
                    replacements[target.target_id]: source.target_labels[
                        target.target_id
                    ]
                    for target in revision.targets
                },
                evidence=[],
                collections=[],
                draft_buffers=DraftBuffers(),
            )
            return self._register(study)

    def accept(self, session: Session, changed: Study, previous: Study) -> Session:
        """Check the changed study, then keep the previous one for Undo."""
        if (
            len(changed.collections) > 20
            or len(changed.evidence) > 10
            or len(changed.revisions) > 200
        ):
            raise DomainError(
                "LIMIT_EXCEEDED", "The proposed change exceeds a study limit."
            )
        changed = Study.model_validate(changed.model_dump())
        validate_study(changed, self.catalogue)
        if changed != session.study:
            session.previous = previous
            session.study = changed
        return session

    def command(
        self,
        workspace_id: str,
        buffers: DraftBuffers,
        command: Command,
    ) -> Session:
        """Pass the command to Prepare or Review and accept the result."""
        with self.lock:
            session = self.get(workspace_id)
            previous = session.study.model_copy(update={"draft_buffers": buffers})
            validate_study(previous, self.catalogue)
            if isinstance(command, AttachEvidence):
                raise DomainError(
                    "SCHEMA_INVALID", "Attachment requires an owned evidence preview."
                )
            if isinstance(
                command,
                (RenameStudy, ApplyTarget, RemoveTarget, RenameTarget, SetContext),
            ):
                changed = self.prepare.apply(previous, command)
            else:
                changed = self.review.apply(previous, command)
            return self.accept(session, changed, previous)

    def save(
        self,
        workspace_id: str,
        buffers: DraftBuffers,
    ) -> Session:
        """Save the study and update the saved copy after the database succeeds."""
        with self.lock:
            session = self.get(workspace_id)
            proposed = session.study.model_copy(update={"draft_buffers": buffers})
            version = self.repository.save(proposed)
            session.study = proposed
            session.saved = proposed
            session.base_saved_version = version
            session.previous = None
            return session

    def undo(self, workspace_id: str) -> Session:
        """Restore the study from before the last accepted unsaved change."""
        with self.lock:
            session = self.get(workspace_id)
            if session.previous is None:
                raise DomainError(
                    "UNDO_UNAVAILABLE", "There is no unsaved accepted action to undo."
                )
            session.study = session.previous
            session.previous = None
            return session

    def validate(
        self,
        workspace_id: str,
        revision_id: str,
        target_draft: TargetDraft | None = None,
    ) -> dict[str, Any]:
        """Check the local request and list the scientific checks not performed."""
        with self.lock:
            session = self.get(workspace_id)
            revision = revision_by_id(session.study, revision_id)
            diagnostics = request_diagnostics(session.study, revision, self.catalogue)
            draft_diagnostics: list[Diagnostic] = []
            if target_draft is not None:
                try:
                    target = parse_target(
                        target_draft, target_draft.target_id or self.new_id()
                    )
                    validate_revision(
                        revision.model_copy(update={"targets": [target]}),
                        self.catalogue,
                    )
                except DomainError as error:
                    draft_diagnostics = error.diagnostics
            checks = [
                {
                    "name": "Local request structure and catalogue bounds",
                    "status": "failed" if diagnostics else "passed",
                    "message": (
                        "Local checks only; no biological or compiler acceptance is "
                        "implied."
                    ),
                }
            ]
            for name in [
                "Reference sequence availability/checksum",
                "Sequence extraction",
                "PAM inspection",
                "Off-target search",
                "Biological suitability",
                "IRCOMP specification and controller validation",
            ]:
                checks.append(
                    {
                        "name": name,
                        "status": "not_performed",
                        "message": "Not performed by this local workspace.",
                    }
                )
            return {
                "revision_id": revision_id,
                "export_ready": not diagnostics,
                "checks": checks,
                "diagnostics": [item.model_dump() for item in diagnostics],
                "draft_diagnostics": [item.model_dump() for item in draft_diagnostics],
            }
