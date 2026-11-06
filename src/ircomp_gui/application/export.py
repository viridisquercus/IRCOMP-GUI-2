# ************************************************************************
# @file export.py
# @brief Request and review files prepared from a saved study
# @author Lukas (Viridis) Dubsik
# @date 6-11-2026
# @version 0.1
#
# Detailed description:
#  Exports are always made from the saved study, never from the working
#  copy, so the file matches a save counter the user can refer to.
#  The prepared file is kept in memory and downloaded by its export ID.
#  Only the last MAX_EXPORTS files are kept.
# ************************************************************************

"""Prepare the request and review files from a saved study."""

from __future__ import annotations

import hashlib
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any

from ircomp_gui.application.ports import ExchangePort, SavedStudy
from ircomp_gui.application.workspace import WorkspaceService
from ircomp_gui.domain.constants import MAX_EXPORTS
from ircomp_gui.domain.errors import DomainError
from ircomp_gui.domain.models import (
    Collection,
    EvidenceFile,
    RequestSnapshot,
    Revision,
    Study,
)
from ircomp_gui.domain.rules import (
    request_diagnostics,
    revision_by_id,
    unique,
    unresolved,
)
from ircomp_gui.domain.serialization import encode_json


@dataclass(frozen=True)
class ExportFile:
    """Keep the bytes prepared for one download.

    Attributes
    ----------
    raw : bytes
        Contents of the file
    filename : str
        Name offered to the browser
    summary : dict
        Description shown in the export preview
    """

    raw: bytes
    filename: str
    summary: dict[str, Any]


def request_snapshot(study: Study, revision_id: str) -> RequestSnapshot:
    """Build the request file from the chosen revision and its labels.

    Parameters
    ----------
    study : Study
        Study to export from
    revision_id : str
        Revision to export

    Returns
    -------
    RequestSnapshot
        The request file
    """
    revision = revision_by_id(study, revision_id)

    # Only the labels of the exported targets go into the file
    labels: dict[str, str] = {}
    for target in revision.targets:
        labels[target.target_id] = study.target_labels[target.target_id]

    return RequestSnapshot(
        study_id=study.study_id,
        request_id=study.request_id,
        title=study.title,
        revision=revision,
        target_labels=labels,
    )


def _used_evidence(
    study: Study, revision_id: str, selected: list[Collection]
) -> list[EvidenceFile]:
    # Evidence of the revision
    available: list[EvidenceFile] = []
    for item in study.evidence:
        if item.bundle.context.revision_id == revision_id:
            available.append(item)
    if not available:
        raise DomainError(
            "EXPORT_NOT_READY",
            "Attach evidence before exporting a review package.",
        )

    # Include the source of each member and every supporting source
    bundle_ids: set[str] = set()
    for collection in selected:
        for member in collection.memberships:
            bundle_ids.add(member.candidate.bundle_id)
            for reference in member.evidence_refs:
                bundle_ids.add(reference.bundle_id)

    # No members means nothing to filter by - include everything
    if not bundle_ids:
        return available
    return [item for item in available if item.bundle.bundle_id in bundle_ids]


def _count_dependencies(evidence: list[EvidenceFile]) -> int:
    # The same dependency declared by more bundles is counted once
    dependencies: set[tuple[str, str]] = set()
    for item in evidence:
        for dependency in item.bundle.dependencies:
            dependencies.add((dependency.uri, dependency.description))
    return len(dependencies)


class ExportService:
    """Prepare the downloads from the saved study data.

    Attributes
    ----------
    workspace : WorkspaceService
        Access to the repository, catalogue and lock
    exchange : ExchangePort
        Schema check of the generated documents
    files : OrderedDict[str, ExportFile]
        Prepared downloads, the oldest first
    """

    def __init__(self, workspace: WorkspaceService, exchange: ExchangePort) -> None:
        self.workspace = workspace
        self.exchange = exchange
        self.files: OrderedDict[str, ExportFile] = OrderedDict()

    def _review_document(
        self,
        saved: SavedStudy,
        request: RequestSnapshot,
        revision_id: str,
        collection_ids: list[str],
        selected: list[Collection],
    ) -> tuple[dict[str, Any], list[EvidenceFile], int, str]:
        # All selected collections have to exist and belong to the revision
        belongs = True
        for item in selected:
            if item.revision_id != revision_id:
                belongs = False
        if not collection_ids or len(selected) != len(collection_ids) or not belongs:
            raise DomainError(
                "DANGLING_REFERENCE",
                "Select existing collections belonging to the selected revision.",
            )

        evidence = _used_evidence(saved.study, revision_id, selected)
        count = unresolved(selected)
        status = "draft" if count else "reviewed"

        files: list[dict[str, str]] = []
        for item in evidence:
            files.append(
                {
                    "bundle_id": item.bundle.bundle_id,
                    "sha256": item.sha256,
                    "content_base64": item.content_base64,
                }
            )

        document = {
            "kind": "review",
            "format_version": "1.0",
            "request": request.model_dump(mode="json"),
            "source_saved_version": saved.saved_version,
            "collections": [item.model_dump(mode="json") for item in selected],
            "evidence_files": files,
            "review_status": status,
            "unresolved_count": count,
        }
        return document, evidence, count, status

    def _summary(
        self,
        raw: bytes,
        saved: SavedStudy,
        revision: Revision,
        kind: str,
        status: str | None,
        evidence: list[EvidenceFile],
        selected: list[Collection],
        count: int,
    ) -> dict[str, Any]:
        study = saved.study
        candidates = 0
        for item in evidence:
            candidates += len(item.bundle.candidates)

        return {
            "export_id": self.workspace.new_id(),
            "filename": (
                f"study-{study.study_id[:8]}-{revision.revision_id[:8]}.{kind}.json"
            ),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "byte_length": len(raw),
            "study_id": study.study_id,
            "saved_version": saved.saved_version,
            "revision_id": revision.revision_id,
            "kind": kind,
            "review_status": status,
            "target_count": len(revision.targets),
            "candidate_count": candidates,
            "collection_count": len(selected),
            "unresolved_count": count,
            "dependency_count": _count_dependencies(evidence),
        }

    def prepare(
        self,
        study_id: str,
        revision_id: str,
        kind: str,
        collection_ids: list[str],
    ) -> dict[str, Any]:
        """Prepare the chosen saved data and describe the resulting download.

        Parameters
        ----------
        study_id : str
            Saved study to export
        revision_id : str
            Revision to export
        kind : str
            request or review
        collection_ids : list[str]
            Collections included in a review, empty for a request

        Returns
        -------
        dict
            Summary of the prepared file, with its export ID
        """
        with self.workspace.lock:
            saved = self.workspace.repository.load(study_id)
            study = saved.study
            revision = revision_by_id(study, revision_id)

            # The request has to be valid for both kinds of export
            diagnostics = request_diagnostics(study, revision, self.workspace.catalogue)
            if diagnostics:
                raise DomainError(
                    "EXPORT_NOT_READY",
                    "The saved request is not ready to export.",
                    diagnostics=diagnostics,
                )
            request = request_snapshot(study, revision_id)

            unique(collection_ids, "selected collection")
            selected: list[Collection] = []
            for item in study.collections:
                if item.collection_id in collection_ids:
                    selected.append(item)

            # Build the document of the chosen kind
            evidence: list[EvidenceFile] = []
            count = 0
            status: str | None = None
            if kind == "request":
                if collection_ids:
                    raise DomainError(
                        "SCHEMA_INVALID",
                        "Request exports cannot select review collections.",
                    )
                document: dict[str, Any] = request.model_dump(mode="json")
            elif kind == "review":
                document, evidence, count, status = self._review_document(
                    saved, request, revision_id, collection_ids, selected
                )
            else:
                raise DomainError("SCHEMA_INVALID", "Choose request or review export.")

            # Check against the schema and encode it
            self.exchange.validate_document(document)
            raw = encode_json(document)

            summary = self._summary(
                raw, saved, revision, kind, status, evidence, selected, count
            )
            export_id = summary["export_id"]
            self.files[export_id] = ExportFile(raw, summary["filename"], summary)

            # Drop the oldest prepared files
            while len(self.files) > MAX_EXPORTS:
                self.files.popitem(last=False)
            return summary

    def download(self, export_id: str) -> ExportFile:
        """Find the prepared download.

        Parameters
        ----------
        export_id : str
            ID from the export summary

        Returns
        -------
        ExportFile
            The prepared file

        Raises
        ------
        DomainError
            PREVIEW_EXPIRED if the file is not kept anymore
        """
        with self.workspace.lock:
            if export_id not in self.files:
                raise DomainError(
                    "PREVIEW_EXPIRED", "Export preview expired. Generate a new preview."
                )
            return self.files[export_id]
