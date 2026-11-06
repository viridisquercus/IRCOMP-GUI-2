# /************************************************************************
# Name: Lukas (Viridis) Dubsik
# ************************************************************************/

"""Prepare request and review files from a saved study."""

from __future__ import annotations

import hashlib
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any

from ircomp_gui.application.ports import ExchangePort
from ircomp_gui.application.workspace import WorkspaceService
from ircomp_gui.domain.errors import DomainError
from ircomp_gui.domain.models import RequestSnapshot, Study
from ircomp_gui.domain.rules import (
    request_diagnostics,
    revision_by_id,
    unique,
    unresolved,
)
from ircomp_gui.domain.serialization import encode_json


@dataclass(frozen=True)
class ExportFile:
    """Keep the bytes prepared for one download."""

    raw: bytes
    filename: str
    summary: dict[str, Any]


def request_snapshot(study: Study, revision_id: str) -> RequestSnapshot:
    """Build a request file using the selected revision and its labels."""
    revision = revision_by_id(study, revision_id)
    return RequestSnapshot(
        study_id=study.study_id,
        request_id=study.request_id,
        title=study.title,
        revision=revision,
        target_labels={
            target.target_id: study.target_labels[target.target_id]
            for target in revision.targets
        },
    )


class ExportService:
    """Prepare downloads from saved study data."""

    def __init__(self, workspace: WorkspaceService, exchange: ExchangePort) -> None:
        self.workspace = workspace
        self.exchange = exchange
        self.files: OrderedDict[str, ExportFile] = OrderedDict()

    def prepare(
        self,
        study_id: str,
        revision_id: str,
        kind: str,
        collection_ids: list[str],
    ) -> dict[str, Any]:
        """Prepare the selected saved data and describe the resulting download."""
        with self.workspace.lock:
            saved = self.workspace.repository.load(study_id)
            study = saved.study
            revision = revision_by_id(study, revision_id)
            diagnostics = request_diagnostics(study, revision, self.workspace.catalogue)
            if diagnostics:
                raise DomainError(
                    "EXPORT_NOT_READY",
                    "The saved request is not ready to export.",
                    diagnostics=diagnostics,
                )
            request = request_snapshot(study, revision_id)
            unique(collection_ids, "selected collection")
            selected = [
                item
                for item in study.collections
                if item.collection_id in collection_ids
            ]
            evidence = []
            count = 0
            status: str | None = None
            document: dict[str, Any] = request.model_dump(mode="json")
            if kind == "request":
                if collection_ids:
                    raise DomainError(
                        "SCHEMA_INVALID",
                        "Request exports cannot select review collections.",
                    )
            elif kind == "review":
                if (
                    not collection_ids
                    or len(selected) != len(collection_ids)
                    or any(item.revision_id != revision_id for item in selected)
                ):
                    raise DomainError(
                        "DANGLING_REFERENCE",
                        (
                            "Select existing collections belonging to the"
                            " selected revision."
                        ),
                    )
                available = [
                    item
                    for item in study.evidence
                    if item.bundle.context.revision_id == revision_id
                ]
                if not available:
                    raise DomainError(
                        "EXPORT_NOT_READY",
                        "Attach evidence before exporting a review package.",
                    )
                # Include the main candidate's source and every supporting source.
                bundle_ids: set[str] = set()
                for collection in selected:
                    for member in collection.memberships:
                        bundle_ids.add(member.candidate.bundle_id)
                        for reference in member.evidence_refs:
                            bundle_ids.add(reference.bundle_id)
                evidence = [
                    item
                    for item in available
                    if not bundle_ids or item.bundle.bundle_id in bundle_ids
                ]
                count = unresolved(selected)
                status = "draft" if count else "reviewed"
                document = {
                    "kind": "review",
                    "format_version": "1.0",
                    "request": request.model_dump(mode="json"),
                    "source_saved_version": saved.saved_version,
                    "collections": [item.model_dump(mode="json") for item in selected],
                    "evidence_files": [
                        {
                            "bundle_id": item.bundle.bundle_id,
                            "sha256": item.sha256,
                            "content_base64": item.content_base64,
                        }
                        for item in evidence
                    ],
                    "review_status": status,
                    "unresolved_count": count,
                }
            else:
                raise DomainError("SCHEMA_INVALID", "Choose request or review export.")
            self.exchange.validate_document(document)
            raw = encode_json(document)
            export_id = self.workspace.new_id()
            filename = f"study-{study.study_id[:8]}-{revision_id[:8]}.{kind}.json"
            summary = {
                "export_id": export_id,
                "filename": filename,
                "sha256": hashlib.sha256(raw).hexdigest(),
                "byte_length": len(raw),
                "study_id": study_id,
                "saved_version": saved.saved_version,
                "revision_id": revision_id,
                "kind": kind,
                "review_status": status,
                "target_count": len(revision.targets),
                "candidate_count": sum(
                    len(item.bundle.candidates) for item in evidence
                ),
                "collection_count": len(selected),
                "unresolved_count": count,
                "dependency_count": len(
                    {
                        (dependency.uri, dependency.description)
                        for item in evidence
                        for dependency in item.bundle.dependencies
                    }
                ),
            }
            self.files[export_id] = ExportFile(raw, filename, summary)
            while len(self.files) > 5:
                _ = self.files.popitem(last=False)
            return summary

    def download(self, export_id: str) -> ExportFile:
        """Find the prepared download or ask for a new preview."""
        with self.workspace.lock:
            if export_id not in self.files:
                raise DomainError(
                    "PREVIEW_EXPIRED", "Export preview expired. Generate a new preview."
                )
            return self.files[export_id]
