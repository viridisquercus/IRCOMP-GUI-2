# /************************************************************************
# Name: Lukas (Viridis) Dubsik
# ************************************************************************/

"""Check an imported file before adding it to the study."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from ircomp_gui.application.ports import ExchangePort
from ircomp_gui.application.workspace import Session, WorkspaceService
from ircomp_gui.domain.errors import DomainError
from ircomp_gui.domain.models import (
    Collection,
    DraftBuffers,
    EvidenceBundle,
    RequestSnapshot,
    Revision,
)
from ircomp_gui.domain.rules import revision_by_id, same_context, validate_study
from ircomp_gui.domain.serialization import decode_base64, parse_json


@dataclass(frozen=True)
class ImportPreview:
    """Keep an imported file and its inspection result until confirmation."""

    preview_id: str
    kind: str
    status: str
    raw: bytes
    parsed: RequestSnapshot | EvidenceBundle | None
    workspace_id: str | None
    response: dict[str, Any]


class ImportService:
    """Inspect imported files and add them only after confirmation."""

    def __init__(self, workspace: WorkspaceService, exchange: ExchangePort) -> None:
        self.workspace = workspace
        self.exchange = exchange
        self.previews: dict[str, ImportPreview] = {}

    def preview(
        self,
        kind: str,
        content_base64: str,
        workspace_id: str | None = None,
        revision_id: str | None = None,
    ) -> dict[str, Any]:
        """Inspect exact bytes, report incompatibility and retain at most five files."""
        raw = decode_base64(content_base64)
        with self.workspace.lock:
            if len(self.previews) >= 5:
                raise DomainError(
                    "LIMIT_EXCEEDED",
                    (
                        "Cancel an existing import preview before adding another "
                        "(maximum five)."
                    ),
                )
            session = self.workspace.get(workspace_id) if workspace_id else None
            expected = (
                revision_by_id(session.study, revision_id)
                if session and revision_id
                else None
            )
            parsed: RequestSnapshot | EvidenceBundle | None = None
            status = "ready"
            diagnostics: list[dict[str, Any]] = []
            summary: dict[str, Any] = {
                "expected_context": expected.model_dump() if expected else None,
                "received_context": None,
            }
            try:
                document = parse_json(raw)
                context = (
                    document.get("context")
                    if kind == "evidence"
                    else document.get("revision")
                )
                if context is not None:
                    try:
                        summary["received_context"] = Revision.model_validate(
                            context
                        ).model_dump()
                    except ValidationError:
                        pass
                parsed = self.exchange.decode(raw, kind)
                if isinstance(parsed, RequestSnapshot):
                    collision = self.workspace.repository.identity_exists(
                        parsed.study_id, parsed.request_id
                    )
                    summary.update(
                        {
                            "study_id": parsed.study_id,
                            "request_id": parsed.request_id,
                            "revision_id": parsed.revision.revision_id,
                            "reference_id": parsed.revision.reference_id,
                            "target_count": len(parsed.revision.targets),
                            "existing_study_id": collision,
                        }
                    )
                else:
                    summary.update(
                        {
                            "bundle_id": parsed.bundle_id,
                            "request_id": parsed.request_id,
                            "revision_id": parsed.context.revision_id,
                            "reference_id": parsed.context.reference_id,
                            "profile_id": parsed.context.profile_id,
                            "category": parsed.category,
                            "candidate_count": len(parsed.candidates),
                            "source": parsed.source.model_dump(),
                        }
                    )
                    if (
                        session is None
                        or expected is None
                        or parsed.request_id != session.study.request_id
                        or not same_context(parsed.context, expected)
                    ):
                        raise DomainError(
                            "CONTEXT_MISMATCH",
                            "Evidence does not match the selected request "
                            "context. Obtain matching evidence or select its "
                            "actual retained revision.",
                        )
                    existing = next(
                        (
                            item
                            for item in session.study.evidence
                            if item.bundle.bundle_id == parsed.bundle_id
                        ),
                        None,
                    )
                    if existing:
                        if (
                            existing.sha256 != hashlib.sha256(raw).hexdigest()
                            or existing.content_base64 != content_base64
                        ):
                            raise DomainError(
                                "BUNDLE_ID_COLLISION",
                                "Bundle identity already has different bytes. "
                                "Use a new bundle identity for changed output.",
                            )
                        status = "duplicate"
            except DomainError as error:
                status = "blocked"
                diagnostics = [item.model_dump() for item in error.diagnostics]
            preview_id = self.workspace.new_id()
            response = {
                "preview_id": preview_id,
                "kind": kind,
                "status": status,
                "diagnostics": diagnostics,
                "summary": summary,
            }
            self.previews[preview_id] = ImportPreview(
                preview_id,
                kind,
                status,
                raw,
                parsed,
                workspace_id,
                response,
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
        """Create an unsaved study only from a ready local request preview."""
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
        self,
        workspace_id: str,
        buffers: DraftBuffers,
        preview_id: str,
    ) -> Session:
        """Check the bundle again and add it together with its original bytes."""
        with self.workspace.lock:
            session = self.workspace.get(workspace_id)
            preview = self._get(preview_id)
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
            existing = next(
                (
                    item
                    for item in session.study.evidence
                    if item.bundle.bundle_id == bundle.bundle_id
                ),
                None,
            )
            if existing is not None:
                if existing.sha256 != hashlib.sha256(preview.raw).hexdigest():
                    raise DomainError(
                        "BUNDLE_ID_COLLISION",
                        "Bundle identity already has different bytes.",
                    )
                del self.previews[preview_id]
                return session
            revision = revision_by_id(session.study, bundle.context.revision_id)
            if bundle.request_id != session.study.request_id or not same_context(
                revision, bundle.context
            ):
                raise DomainError(
                    "CONTEXT_MISMATCH", "Evidence context changed; preview again."
                )
            previous = session.study.model_copy(update={"draft_buffers": buffers})
            validate_study(previous, self.workspace.catalogue)
            collections = list(previous.collections)
            if not any(
                item.revision_id == revision.revision_id for item in collections
            ):
                collections.append(
                    Collection(
                        collection_id=self.workspace.new_id(),
                        revision_id=revision.revision_id,
                        name="Review collection",
                        memberships=[],
                    )
                )
            changed = previous.model_copy(
                update={
                    "evidence": [
                        *previous.evidence,
                        self.exchange.evidence_file(preview.raw, bundle),
                    ],
                    "collections": collections,
                }
            )
            result = self.workspace.accept(session, changed, previous)
            del self.previews[preview_id]
            return result

    def cancel(self, preview_id: str) -> None:
        """Remove the preview if it is still present."""
        with self.workspace.lock:
            _ = self.previews.pop(preview_id, None)

    def close_workspace(self, workspace_id: str) -> None:
        """Close the working copy and remove its previews; keep saved data."""
        with self.workspace.lock:
            _ = self.workspace.get(workspace_id)
            self.previews = {
                key: preview
                for key, preview in self.previews.items()
                if preview.workspace_id != workspace_id
            }
            del self.workspace.sessions[workspace_id]
