# ************************************************************************
# @file workspace.py
# @brief Working copies of the studies, Save and Undo
# @author Lukas (Viridis) Dubsik
# @date 6-11-2026
# @version 0.1
#
# Detailed description:
#  Each opened study gets a session with its working copy. The copy only
#  reaches the database on an explicit Save. Undo keeps just one step -
#  the study as it was before the last accepted change.
#  All changes go through one lock, as the HTTP handlers run in threads.
# ************************************************************************

"""Keep the working studies and handle their Save and Undo."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from threading import RLock
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
from ircomp_gui.application.responses import (
    CheckResult,
    CollectionView,
    EvidenceSummary,
    StudyView,
    ValidationView,
    WorkspaceView,
)
from ircomp_gui.application.review import ReviewService
from ircomp_gui.domain.catalogue import Catalogue
from ircomp_gui.domain.constants import (
    DEMO_PROFILE,
    DEMO_REFERENCE,
    MAX_BUNDLES,
    MAX_COLLECTIONS,
    MAX_REVISIONS,
)
from ircomp_gui.domain.errors import DomainError
from ircomp_gui.domain.models import (
    Diagnostic,
    DraftBuffers,
    RequestSnapshot,
    Revision,
    Study,
    Target,
    TargetDraft,
)
from ircomp_gui.domain.rules import (
    active_revision,
    parse_target,
    request_diagnostics,
    revision_by_id,
    unresolved,
    validate_revision,
    validate_study,
)

# Checks listed by Check request which this application does not do
NOT_PERFORMED = [
    "Reference sequence (file and checksum)",
    "Sequence extraction",
    "PAM inspection",
    "Off-target search",
    "Biological suitability",
    "IRCOMP specification check",
]


@dataclass
class Session:
    """Keep the working study, its saved copy and the last Undo copy.

    Attributes
    ----------
    workspace_id : str
        ID of the session, the client sends it with every request
    study : Study
        Current working copy
    base_saved_version : int
        Save counter the copy is based on, 0 if never saved
    saved : Study | None
        Study as it was last saved, used to know if there are changes
    previous : Study | None
        Study before the last accepted change, used for Undo
    """

    workspace_id: str
    study: Study
    base_saved_version: int = 0
    saved: Study | None = None
    previous: Study | None = None


def new_uuid() -> str:
    """Create a new random UUID.

    Returns
    -------
    str
        The UUID as a string
    """
    return str(uuid4())


def new_study(study_id: str, request_id: str, title: str, revision: Revision) -> Study:
    """Create a study with one revision and nothing else.

    Parameters
    ----------
    study_id, request_id : str
        Identity of the study
    title : str
        Title of the study
    revision : Revision
        The first and active revision

    Returns
    -------
    Study
        The created study, without labels, evidence or collections
    """
    return Study(
        study_id=study_id,
        request_id=request_id,
        title=title,
        active_revision_id=revision.revision_id,
        revisions=[revision],
        target_labels={},
        evidence=[],
        collections=[],
        draft_buffers=DraftBuffers(),
    )


class WorkspaceService:
    """Keep the working studies and handle their changes, Save and Undo.

    Attributes
    ----------
    repository : Repository
        Storage used to load and save the complete studies
    catalogue : Catalogue
        Supported references and profiles used in the checks
    sessions : dict[str, Session]
        Working copies, they exist only while the service runs
    lock : RLock
        Orders the changes coming from the HTTP handlers
    prepare : PrepareService
        Changes of the request targets and context
    review : ReviewService
        Changes of the collections and decisions
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

    # -----------------------------------------------------------------------
    # Sessions
    # -----------------------------------------------------------------------
    def get(self, workspace_id: str) -> Session:
        """Find the working session.

        Parameters
        ----------
        workspace_id : str
            ID of the session

        Returns
        -------
        Session
            The found session

        Raises
        ------
        DomainError
            SESSION_EXPIRED if there is no such session (service restarted)
        """
        session = self.sessions.get(workspace_id)
        if session is None:
            raise DomainError(
                "SESSION_EXPIRED",
                "This session doesn't exist anymore (was the service restarted?). "
                "Open the saved study again, unsaved changes are lost.",
            )
        return session

    def view(self, session: Session) -> WorkspaceView:
        """Return study data without sending the original evidence files."""
        study = session.study
        return WorkspaceView(
            workspace_id=session.workspace_id,
            base_saved_version=session.base_saved_version,
            dirty=study != session.saved,
            can_undo=session.previous is not None,
            study=StudyView(
                study_id=study.study_id,
                request_id=study.request_id,
                title=study.title,
                active_revision_id=study.active_revision_id,
                revisions=study.revisions,
                target_labels=study.target_labels,
                evidence=[
                    EvidenceSummary(bundle=item.bundle, sha256=item.sha256)
                    for item in study.evidence
                ],
                collections=[
                    CollectionView(
                        **item.model_dump(), unresolved_count=unresolved([item])
                    )
                    for item in study.collections
                ],
                draft_buffers=study.draft_buffers,
            ),
            diagnostics=request_diagnostics(
                study, active_revision(study), self.catalogue
            ),
        )

    def _register(self, study: Study, saved_version: int = 0) -> Session:
        validate_study(study, self.catalogue)

        # A study loaded from the database starts as saved
        saved = study if saved_version else None
        session = Session(
            workspace_id=self.new_id(),
            study=study,
            base_saved_version=saved_version,
            saved=saved,
        )
        self.sessions[session.workspace_id] = session
        return session

    def create(self, title: str) -> Session:
        """Create an empty study with the demonstration reference and profile.

        Parameters
        ----------
        title : str
            Title of the new study

        Returns
        -------
        Session
            Session of the new, unsaved study
        """
        with self.lock:
            revision = Revision(
                revision_id=self.new_id(),
                reference_id=DEMO_REFERENCE,
                profile_id=DEMO_PROFILE,
                targets=[],
            )
            study = new_study(self.new_id(), self.new_id(), title, revision)
            return self._register(study)

    def open(self, study_id: str) -> Session:
        """Load a saved study into a working copy, with its editor text.

        Parameters
        ----------
        study_id : str
            ID of the saved study

        Returns
        -------
        Session
            Session of the loaded study
        """
        with self.lock:
            saved = self.repository.load(study_id)
            return self._register(saved.study, saved.saved_version)

    def import_request(self, request: RequestSnapshot) -> Session:
        """Open an imported request, its IDs are kept.

        Parameters
        ----------
        request : RequestSnapshot
            Checked request file

        Returns
        -------
        Session
            Session of the new, unsaved study

        Raises
        ------
        DomainError
            If a saved study already uses the study ID or request ID
        """
        with self.lock:
            collision = self.repository.identity_exists(
                request.study_id, request.request_id
            )
            if collision:
                # Same study is "exists", only the request matching is "conflict"
                if collision == request.study_id:
                    code = "IDENTITY_EXISTS"
                else:
                    code = "IDENTITY_CONFLICT"
                raise DomainError(
                    code,
                    f"This request is already saved as study {collision}. "
                    "Open that one, or duplicate it.",
                )

            study = new_study(
                request.study_id, request.request_id, request.title, request.revision
            )
            study = study.model_copy(update={"target_labels": request.target_labels})
            return self._register(study)

    def duplicate(self, workspace_id: str, title: str) -> Session:
        """Copy the active request into a new study with new IDs.

        Only the request is copied - no evidence, decisions or drafts.

        Parameters
        ----------
        workspace_id : str
            Session of the source study
        title : str
            Title of the copy

        Returns
        -------
        Session
            Session of the new, unsaved study
        """
        with self.lock:
            source = self.get(workspace_id).study
            revision = active_revision(source)

            # Give every target a new ID and move its label over
            targets: list[Target] = []
            labels: dict[str, str] = {}
            for target in revision.targets:
                target_id = self.new_id()
                targets.append(target.model_copy(update={"target_id": target_id}))
                labels[target_id] = source.target_labels[target.target_id]

            copied = revision.model_copy(
                update={"revision_id": self.new_id(), "targets": targets}
            )
            study = new_study(self.new_id(), self.new_id(), title, copied)
            study = study.model_copy(update={"target_labels": labels})
            return self._register(study)

    # -----------------------------------------------------------------------
    # Changes
    # -----------------------------------------------------------------------
    def accept(self, session: Session, changed: Study, previous: Study) -> Session:
        """Check the changed study, then keep the previous one for Undo.

        Parameters
        ----------
        session : Session
            Session to update
        changed : Study
            Proposed new study
        previous : Study
            Study before the change, with the current editor text

        Returns
        -------
        Session
            The updated session
        """
        if (
            len(changed.collections) > MAX_COLLECTIONS
            or len(changed.evidence) > MAX_BUNDLES
            or len(changed.revisions) > MAX_REVISIONS
        ):
            raise DomainError(
                "LIMIT_EXCEEDED", "The proposed change exceeds a study limit."
            )

        # model_copy does not validate, so run the whole validation again
        changed = Study.model_validate(changed.model_dump())
        validate_study(changed, self.catalogue)

        # Only a real change can be undone
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
        """Pass the command to Prepare or Review and accept the result.

        Parameters
        ----------
        workspace_id : str
            Session to change
        buffers : DraftBuffers
            Current editor text from the client
        command : Command
            Operation to apply

        Returns
        -------
        Session
            The updated session
        """
        with self.lock:
            session = self.get(workspace_id)

            # The editor text is a part of what Undo restores
            previous = session.study.model_copy(update={"draft_buffers": buffers})
            validate_study(previous, self.catalogue)

            if isinstance(command, AttachEvidence):
                raise DomainError(
                    "SCHEMA_INVALID",
                    "Evidence can only be attached from an import preview.",
                )
            if isinstance(
                command,
                (RenameStudy, ApplyTarget, RemoveTarget, RenameTarget, SetContext),
            ):
                changed = self.prepare.apply(previous, command)
            else:
                changed = self.review.apply(previous, command)
            return self.accept(session, changed, previous)

    def save(self, workspace_id: str, buffers: DraftBuffers) -> Session:
        """Save the study, the session changes only if the database succeeds.

        Parameters
        ----------
        workspace_id : str
            Session to save
        buffers : DraftBuffers
            Current editor text, saved along for recovery

        Returns
        -------
        Session
            The saved session
        """
        with self.lock:
            session = self.get(workspace_id)
            proposed = session.study.model_copy(update={"draft_buffers": buffers})
            version = self.repository.save(proposed)

            # Saved now, so there is nothing to undo
            session.study = proposed
            session.saved = proposed
            session.base_saved_version = version
            session.previous = None
            return session

    def undo(self, workspace_id: str) -> Session:
        """Restore the study from before the last accepted unsaved change.

        Parameters
        ----------
        workspace_id : str
            Session to undo in

        Returns
        -------
        Session
            The restored session
        """
        with self.lock:
            session = self.get(workspace_id)
            if session.previous is None:
                raise DomainError("UNDO_UNAVAILABLE", "Nothing to undo.")
            session.study = session.previous
            session.previous = None
            return session

    # -----------------------------------------------------------------------
    # Check request
    # -----------------------------------------------------------------------
    def _check_draft(
        self, revision: Revision, target_draft: TargetDraft
    ) -> list[Diagnostic]:
        # Check the draft alone, as if it was the only target of the revision
        try:
            target_id = target_draft.target_id or self.new_id()
            target = parse_target(target_draft, target_id)
            validate_revision(
                revision.model_copy(update={"targets": [target]}), self.catalogue
            )
        except DomainError as error:
            return error.diagnostics
        return []

    def validate(
        self,
        workspace_id: str,
        revision_id: str,
        target_draft: TargetDraft | None = None,
    ) -> ValidationView:
        """Check the request locally and list the checks that are not done.

        Parameters
        ----------
        workspace_id : str
            Session to check
        revision_id : str
            Revision to check
        target_draft : TargetDraft | None
            Unapplied target editor text, checked separately

        Returns
        -------
        ValidationView
            Result of the checks for the client
        """
        with self.lock:
            session = self.get(workspace_id)
            revision = revision_by_id(session.study, revision_id)
            diagnostics = request_diagnostics(session.study, revision, self.catalogue)

            draft_diagnostics: list[Diagnostic] = []
            if target_draft is not None:
                draft_diagnostics = self._check_draft(revision, target_draft)

            # The one check done here, then the ones which are not
            checks = [
                CheckResult(
                    name="Request structure and contig lengths",
                    status="failed" if diagnostics else "passed",
                    message="Only checked locally, IRCOMP may still refuse it.",
                )
            ]
            for name in NOT_PERFORMED:
                checks.append(
                    CheckResult(
                        name=name, status="not_performed", message="Not done here."
                    )
                )

            return ValidationView(
                revision_id=revision_id,
                export_ready=not diagnostics,
                checks=checks,
                diagnostics=diagnostics,
                draft_diagnostics=draft_diagnostics,
            )
