# ************************************************************************
# @file imports.py
# @brief Inspection of the imported files before they are used
# @author Lukas (Viridis) Dubsik
# @date 6-11-2026
# @version 0.1
#
# Detailed description:
#  Import has two steps. Firstly the file is previewed - parsed, checked
#  and described to the user, while the study stays untouched. Only after
#  the user confirms, the request is opened or the evidence attached.
#  At most MAX_PREVIEWS previews are kept in memory at once.
# ************************************************************************

"""Check an imported file before it is added to the study."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from ircomp_gui.application.ports import ExchangePort
from ircomp_gui.application.workspace import Session, WorkspaceService
from ircomp_gui.domain.constants import MAX_PREVIEWS
from ircomp_gui.domain.errors import DomainError
from ircomp_gui.domain.models import (
    Collection,
    DraftBuffers,
    EvidenceBundle,
    EvidenceFile,
    RequestSnapshot,
    Revision,
    Study,
)
from ircomp_gui.domain.rules import revision_by_id, same_context, validate_study
from ircomp_gui.domain.serialization import decode_base64, parse_json


@dataclass(frozen=True)
class ImportPreview:
    """Keep the imported file and its inspection until it is confirmed.

    Attributes
    ----------
    preview_id : str
        ID of the preview
    kind : str
        request or evidence
    status : str
        ready, duplicate or blocked
    raw : bytes
        Original bytes of the file
    parsed : RequestSnapshot | EvidenceBundle | None
        Parsed file, None if parsing failed
    workspace_id : str | None
        Session the evidence is meant for, None for a request
    response : dict
        Description sent to the client
    """

    preview_id: str
    kind: str
    status: str
    raw: bytes
    parsed: RequestSnapshot | EvidenceBundle | None
    workspace_id: str | None
    response: dict[str, Any]


def _find_evidence(study: Study, bundle_id: str) -> EvidenceFile | None:
    # Find the already attached evidence with the given bundle ID
    for item in study.evidence:
        if item.bundle.bundle_id == bundle_id:
            return item
    return None


def _received_context(raw: bytes, kind: str) -> dict[str, Any] | None:
    # Try to read the context from the file even if it is invalid otherwise,
    # so the user can see what the file was produced for
    document = parse_json(raw)
    if kind == "evidence":
        context = document.get("context")
    else:
        context = document.get("revision")
    if context is None:
        return None
    try:
        return Revision.model_validate(context).model_dump()
    except ValidationError:
        return None


class ImportService:
    """Inspect the imported files and add them only after confirmation.

    Attributes
    ----------
    workspace : WorkspaceService
        Working sessions and their lock
    exchange : ExchangePort
        Reading of the exchange files
    previews : dict[str, ImportPreview]
        Previews waiting for confirmation
    """

    def __init__(self, workspace: WorkspaceService, exchange: ExchangePort) -> None:
        self.workspace = workspace
        self.exchange = exchange
        self.previews: dict[str, ImportPreview] = {}

    def _describe_request(self, request: RequestSnapshot) -> dict[str, Any]:
        # Say if the request is already saved, it can't be imported twice
        collision = self.workspace.repository.identity_exists(
            request.study_id, request.request_id
        )
        return {
            "study_id": request.study_id,
            "request_id": request.request_id,
            "revision_id": request.revision.revision_id,
            "reference_id": request.revision.reference_id,
            "target_count": len(request.revision.targets),
            "existing_study_id": collision,
        }

    def _describe_evidence(self, bundle: EvidenceBundle) -> dict[str, Any]:
        return {
            "bundle_id": bundle.bundle_id,
            "request_id": bundle.request_id,
            "revision_id": bundle.context.revision_id,
            "reference_id": bundle.context.reference_id,
            "profile_id": bundle.context.profile_id,
            "category": bundle.category,
            "candidate_count": len(bundle.candidates),
            "source": bundle.source.model_dump(),
        }

    def _check_evidence(
        self,
        bundle: EvidenceBundle,
        session: Session | None,
        expected: Revision | None,
        raw: bytes,
        content_base64: str,
    ) -> str:
        # The evidence has to be for exactly the selected revision
        if (
            session is None
            or expected is None
            or bundle.request_id != session.study.request_id
            or not same_context(bundle.context, expected)
        ):
            raise DomainError(
                "CONTEXT_MISMATCH",
                "Evidence does not match the selected request "
                "context. Obtain matching evidence or select its "
                "actual retained revision.",
            )

        # Same bundle again is fine, but only with the very same bytes
        existing = _find_evidence(session.study, bundle.bundle_id)
        if existing is None:
            return "ready"
        if (
            existing.sha256 != hashlib.sha256(raw).hexdigest()
            or existing.content_base64 != content_base64
        ):
            raise DomainError(
                "BUNDLE_ID_COLLISION",
                "Bundle identity already has different bytes. "
                "Use a new bundle identity for changed output.",
            )
        return "duplicate"

    def preview(
        self,
        kind: str,
        content_base64: str,
        workspace_id: str | None = None,
        revision_id: str | None = None,
    ) -> dict[str, Any]:
        """Inspect the exact bytes of the file and keep them for confirmation.

        A file with problems is still previewed (as blocked), so the user
        can see what is wrong with it.

        Parameters
        ----------
        kind : str
            request or evidence
        content_base64 : str
            The file, base64 encoded
        workspace_id : str | None
            Session the evidence is meant for
        revision_id : str | None
            Revision the evidence is meant for

        Returns
        -------
        dict
            Description of the preview for the client
        """
        raw = decode_base64(content_base64)
        with self.workspace.lock:
            if len(self.previews) >= MAX_PREVIEWS:
                raise DomainError(
                    "LIMIT_EXCEEDED",
                    "Cancel an existing import preview before adding another "
                    "(maximum five).",
                )

            # Find what the evidence is expected to match
            session = None
            if workspace_id:
                session = self.workspace.get(workspace_id)
            expected = None
            if session and revision_id:
                expected = revision_by_id(session.study, revision_id)

            parsed: RequestSnapshot | EvidenceBundle | None = None
            status = "ready"
            diagnostics: list[dict[str, Any]] = []
            summary: dict[str, Any] = {
                "expected_context": expected.model_dump() if expected else None,
                "received_context": None,
            }

            # Any problem only blocks the preview, it is not an error
            try:
                summary["received_context"] = _received_context(raw, kind)
                parsed = self.exchange.decode(raw, kind)
                if isinstance(parsed, RequestSnapshot):
                    summary.update(self._describe_request(parsed))
                else:
                    summary.update(self._describe_evidence(parsed))
                    status = self._check_evidence(
                        parsed, session, expected, raw, content_base64
                    )
            except DomainError as error:
                status = "blocked"
                diagnostics = [item.model_dump() for item in error.diagnostics]

            # Store the preview until it is accepted or cancelled
            preview_id = self.workspace.new_id()
            response = {
                "preview_id": preview_id,
                "kind": kind,
                "status": status,
                "diagnostics": diagnostics,
                "summary": summary,
            }
            self.previews[preview_id] = ImportPreview(
                preview_id, kind, status, raw, parsed, workspace_id, response
            )
            return response

    def _get(self, preview_id: str) -> ImportPreview:
        preview = self.previews.get(preview_id)
        if preview is None:
            raise DomainError(
                "PREVIEW_EXPIRED", "This preview is unavailable. Choose the file again."
            )
        return preview

    def accept_request(self, preview_id: str) -> Session:
        """Create an unsaved study from a ready request preview.

        Parameters
        ----------
        preview_id : str
            ID of the request preview

        Returns
        -------
        Session
            Session of the new study
        """
        with self.workspace.lock:
            preview = self._get(preview_id)
            if preview.status != "ready" or not isinstance(
                preview.parsed, RequestSnapshot
            ):
                raise DomainError(
                    "SCHEMA_INVALID",
                    "This request preview is not ready for acceptance.",
                )

            session = self.workspace.import_request(preview.parsed)
            del self.previews[preview_id]
            return session

    def attach(
        self, workspace_id: str, buffers: DraftBuffers, preview_id: str
    ) -> Session:
        """Check the bundle again and attach it with its original bytes.

        Parameters
        ----------
        workspace_id : str
            Session to attach to
        buffers : DraftBuffers
            Current editor text from the client
        preview_id : str
            ID of the evidence preview

        Returns
        -------
        Session
            The updated session
        """
        with self.workspace.lock:
            session = self.workspace.get(workspace_id)
            preview = self._get(preview_id)

            # The preview has to be evidence made for this very session
            if preview.workspace_id != workspace_id or preview.kind != "evidence":
                raise DomainError(
                    "CONTEXT_MISMATCH",
                    "The evidence preview belongs to another workspace.",
                )
            if preview.status == "blocked" or not isinstance(
                preview.parsed, EvidenceBundle
            ):
                raise DomainError(
                    "CONTEXT_MISMATCH", "Resolve the preview problems before attaching."
                )
            bundle = preview.parsed

            # A duplicate is only acknowledged, nothing is added
            existing = _find_evidence(session.study, bundle.bundle_id)
            if existing is not None:
                if existing.sha256 != hashlib.sha256(preview.raw).hexdigest():
                    raise DomainError(
                        "BUNDLE_ID_COLLISION",
                        "Bundle identity already has different bytes.",
                    )
                del self.previews[preview_id]
                return session

            # The study could have changed since the preview, check again
            revision = revision_by_id(session.study, bundle.context.revision_id)
            if bundle.request_id != session.study.request_id or not same_context(
                revision, bundle.context
            ):
                raise DomainError(
                    "CONTEXT_MISMATCH", "Evidence context changed; preview again."
                )

            previous = session.study.model_copy(update={"draft_buffers": buffers})
            validate_study(previous, self.workspace.catalogue)

            # Give the revision a collection, if it has none yet
            collections = list(previous.collections)
            has_collection = False
            for item in collections:
                if item.revision_id == revision.revision_id:
                    has_collection = True
                    break
            if not has_collection:
                collections.append(
                    Collection(
                        collection_id=self.workspace.new_id(),
                        revision_id=revision.revision_id,
                        name="Review collection",
                        memberships=[],
                    )
                )

            evidence = self.exchange.evidence_file(preview.raw, bundle)
            changed = previous.model_copy(
                update={
                    "evidence": [*previous.evidence, evidence],
                    "collections": collections,
                }
            )
            result = self.workspace.accept(session, changed, previous)
            del self.previews[preview_id]
            return result

    def cancel(self, preview_id: str) -> None:
        """Remove the preview, if it is still there.

        Parameters
        ----------
        preview_id : str
            ID of the preview
        """
        with self.workspace.lock:
            self.previews.pop(preview_id, None)

    def close_workspace(self, workspace_id: str) -> None:
        """Close the working copy and remove its previews, saved data stay.

        Parameters
        ----------
        workspace_id : str
            Session to close
        """
        with self.workspace.lock:
            # Raises if there is no such session
            self.workspace.get(workspace_id)

            remaining: dict[str, ImportPreview] = {}
            for key, preview in self.previews.items():
                if preview.workspace_id != workspace_id:
                    remaining[key] = preview
            self.previews = remaining
            del self.workspace.sessions[workspace_id]
