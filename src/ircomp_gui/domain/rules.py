# /************************************************************************
# Name: Lukas (Viridis) Dubsik
# ************************************************************************/

"""Check study data before it is used or saved."""

from __future__ import annotations

import re
from typing import Literal, cast

from ircomp_gui.domain.catalogue import Catalogue
from ircomp_gui.domain.errors import DomainError
from ircomp_gui.domain.models import (
    CandidateKey,
    Collection,
    Diagnostic,
    EvidenceBundle,
    Revision,
    Study,
    Target,
    TargetDraft,
)


def active_revision(study: Study) -> Revision:
    """Get the active request revision from the study."""
    return revision_by_id(study, study.active_revision_id)


def revision_by_id(study: Study, revision_id: str) -> Revision:
    """Find the revision with the given ID in the study."""
    for revision in study.revisions:
        if revision.revision_id == revision_id:
            return revision
    raise DomainError("DANGLING_REFERENCE", "Request revision does not exist.")


def same_context(left: Revision, right: Revision) -> bool:
    """Check whether two revisions describe the same request.

    Target order can change when a target is edited. Compare the targets by ID
    after checking the reference, profile and coordinate system.
    """
    if left.revision_id != right.revision_id:
        return False
    if left.reference_id != right.reference_id or left.profile_id != right.profile_id:
        return False
    if left.coordinate_system != right.coordinate_system:
        return False

    left_targets = sorted(left.targets, key=lambda target: target.target_id)
    right_targets = sorted(right.targets, key=lambda target: target.target_id)
    return left_targets == right_targets


def unique(values: list[str], subject: str) -> None:
    """Check that an ID occurs only once in the given list."""
    if len(values) != len(set(values)):
        raise DomainError("SCHEMA_INVALID", f"Duplicate {subject} identity.")


def validate_revision(
    revision: Revision, catalogue: Catalogue, *, require_targets: bool = False
) -> None:
    """Check the selected reference, profile and target coordinates."""
    reference = catalogue.reference(revision.reference_id)
    _ = catalogue.profile(revision.profile_id, revision.reference_id)
    unique([target.target_id for target in revision.targets], "target")
    if require_targets and not revision.targets:
        raise DomainError(
            "EXPORT_NOT_READY", "Add at least one accepted target.", "/targets"
        )
    lengths = {contig.accession: contig.length for contig in reference.contigs}
    for target in revision.targets:
        pointer = f"/targets/{target.target_id}"
        if target.contig not in lengths:
            raise DomainError(
                "INTERVAL_INVALID",
                "Use an exact supported contig accession.",
                f"{pointer}/contig",
            )
        if not 0 <= target.start < target.end <= lengths[target.contig]:
            raise DomainError(
                "INTERVAL_INVALID",
                f"Require 0 ≤ start < end ≤ {lengths[target.contig]:,} "
                "(end-exclusive).",
                f"{pointer}/end",
            )


def parse_target(draft: TargetDraft, target_id: str) -> Target:
    """Read decimal coordinates from the editor and create a target."""
    for name, value in [("start", draft.start), ("end", draft.end)]:
        if not re.fullmatch(r"[0-9]+", value) or int(value) > 9007199254740991:
            raise DomainError(
                "INTERVAL_INVALID",
                "Enter a nonnegative whole number within the supported range.",
                f"/target/{name}",
            )
    if not draft.label.strip():
        raise DomainError("SCHEMA_INVALID", "Enter a target label.", "/target/label")
    if draft.strand not in {"+", "-", "."}:
        raise DomainError(
            "INTERVAL_INVALID", "Choose +, - or unspecified strand.", "/target/strand"
        )
    return Target(
        target_id=target_id,
        contig=draft.contig,
        start=int(draft.start),
        end=int(draft.end),
        strand=cast(Literal["+", "-", "."], draft.strand),
    )


def validate_bundle(bundle: EvidenceBundle, catalogue: Catalogue) -> None:
    """Check the bundle context, candidate references and metric availability."""
    validate_revision(bundle.context, catalogue)
    if (
        bundle.category == "computational_prediction"
        and bundle.context.reference_id == "demo-reference-v1"
    ):
        raise DomainError(
            "CONTEXT_MISMATCH",
            "A demo reference cannot be declared real computational evidence.",
        )
    unique([candidate.candidate_id for candidate in bundle.candidates], "candidate")
    targets = {target.target_id for target in bundle.context.targets}
    for candidate in bundle.candidates:
        if candidate.target_id not in targets:
            raise DomainError(
                "DANGLING_REFERENCE",
                "Candidate refers to a target outside its declared context.",
            )
        for metric in candidate.metrics:
            if (metric.availability == "present") != (metric.value is not None):
                raise DomainError(
                    "SCHEMA_INVALID", "Metric availability and value disagree."
                )


def resolve_candidate(study: Study, key: CandidateKey, revision_id: str) -> None:
    """Check that a candidate belongs to evidence for the selected revision."""
    for evidence in study.evidence:
        bundle = evidence.bundle
        if bundle.bundle_id != key.bundle_id:
            continue
        if bundle.context.revision_id != revision_id:
            continue
        for candidate in bundle.candidates:
            if candidate.candidate_id == key.candidate_id:
                return
    raise DomainError(
        "DANGLING_REFERENCE",
        "Candidate is missing or belongs to another request revision.",
    )


def unresolved(collections: list[Collection]) -> int:
    """Count decisions that still need to be completed.

    An empty collection also counts as one unfinished item. A decision needs
    both a finished disposition and a reason before it can be counted as done.
    """
    count = 0
    for collection in collections:
        if not collection.memberships:
            count += 1
            continue
        for member in collection.memberships:
            if member.disposition in {"undecided", "needs_clarification"}:
                count += 1
            elif not member.rationale.strip():
                count += 1
    return count


def validate_study(study: Study, catalogue: Catalogue) -> None:
    """Check all study data and the references between its parts."""
    unique([revision.revision_id for revision in study.revisions], "revision")
    unique([item.bundle.bundle_id for item in study.evidence], "bundle")
    unique([item.collection_id for item in study.collections], "collection")
    _ = active_revision(study)
    for revision in study.revisions:
        validate_revision(revision, catalogue)
    # Collect target IDs from all revisions, including targets removed later.
    target_ids: set[str] = set()
    for revision in study.revisions:
        for target in revision.targets:
            target_ids.add(target.target_id)
    if set(study.target_labels) != target_ids:
        raise DomainError(
            "DANGLING_REFERENCE",
            "Target labels must cover retained target identities exactly.",
        )
    for item in study.evidence:
        validate_bundle(item.bundle, catalogue)
        context = revision_by_id(study, item.bundle.context.revision_id)
        if item.bundle.request_id != study.request_id or not same_context(
            context, item.bundle.context
        ):
            raise DomainError(
                "CONTEXT_MISMATCH",
                "Evidence does not match its exact retained request context.",
            )
    if sum(len(collection.memberships) for collection in study.collections) > 1000:
        raise DomainError(
            "LIMIT_EXCEEDED", "A study supports at most 1,000 memberships."
        )
    for collection in study.collections:
        _ = revision_by_id(study, collection.revision_id)
        unique(
            [member.candidate.model_dump_json() for member in collection.memberships],
            "membership",
        )
        for member in collection.memberships:
            resolve_candidate(study, member.candidate, collection.revision_id)
            unique(
                [key.model_dump_json() for key in member.evidence_refs],
                "supporting evidence reference",
            )
            for key in member.evidence_refs:
                resolve_candidate(study, key, collection.revision_id)
    target_draft = study.draft_buffers.target
    if (
        target_draft
        and target_draft.target_id is not None
        and target_draft.target_id
        not in {target.target_id for target in active_revision(study).targets}
    ):
        raise DomainError(
            "DANGLING_REFERENCE", "Target draft refers to a missing active target."
        )
    decision = study.draft_buffers.decision
    if decision:
        collection = next(
            (
                item
                for item in study.collections
                if item.collection_id == decision.collection_id
            ),
            None,
        )
        if collection is None or not any(
            member.candidate == decision.candidate for member in collection.memberships
        ):
            raise DomainError(
                "DANGLING_REFERENCE", "Decision draft refers to a missing membership."
            )
        for key in decision.evidence_refs:
            resolve_candidate(study, key, collection.revision_id)


def request_diagnostics(
    study: Study, revision: Revision, catalogue: Catalogue
) -> list[Diagnostic]:
    """Return the local problems that prevent this request from being exported."""
    try:
        validate_revision(revision, catalogue, require_targets=True)
    except DomainError as error:
        return error.diagnostics
    if not study.title.strip():
        return [
            Diagnostic(
                code="SCHEMA_INVALID", message="Enter a study title.", location="/title"
            )
        ]
    return []
