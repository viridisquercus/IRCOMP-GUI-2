# ************************************************************************
# @file rules.py
# @brief Checks of the study data before it is used or saved
# @author Lukas (Viridis) Dubsik
# @version 0.1
#
# Detailed description:
#  Pydantic only checks the shape of the data. The rules here check what
#  the shape can't: that the IDs point to existing objects, that the
#  intervals fit into their contigs and that evidence matches its request.
# ************************************************************************

"""Check the study data before it is used or saved."""

from __future__ import annotations

import re
from typing import cast

from ircomp_gui.domain.catalogue import Catalogue
from ircomp_gui.domain.constants import (
    DEMO_REFERENCE,
    MAX_MEMBERSHIPS,
    MAX_SAFE_INTEGER,
)
from ircomp_gui.domain.errors import DomainError
from ircomp_gui.domain.models import (
    CandidateKey,
    Collection,
    Diagnostic,
    EvidenceBundle,
    Revision,
    Strand,
    Study,
    Target,
    TargetDraft,
)

# Dispositions which still need more work before the review is complete
OPEN_DISPOSITIONS = {"undecided", "needs_clarification"}


# ---------------------------------------------------------------------------
# Lookups
# ---------------------------------------------------------------------------
def active_revision(study: Study) -> Revision:
    """Get the active request revision of the study.

    Parameters
    ----------
    study : Study
        Study to look into

    Returns
    -------
    Revision
        The revision currently edited
    """
    return revision_by_id(study, study.active_revision_id)


def revision_by_id(study: Study, revision_id: str) -> Revision:
    """Find the revision with the given ID in the study.

    Parameters
    ----------
    study : Study
        Study to look into
    revision_id : str
        ID of the wanted revision

    Returns
    -------
    Revision
        The found revision

    Raises
    ------
    DomainError
        DANGLING_REFERENCE if the study has no such revision
    """
    for revision in study.revisions:
        if revision.revision_id == revision_id:
            return revision
    raise DomainError("DANGLING_REFERENCE", "Request revision does not exist.")


def find_collection(study: Study, collection_id: str) -> Collection | None:
    """Find the collection with the given ID, None if there is none.

    Parameters
    ----------
    study : Study
        Study to look into
    collection_id : str
        ID of the wanted collection

    Returns
    -------
    Collection | None
        The found collection or None
    """
    for collection in study.collections:
        if collection.collection_id == collection_id:
            return collection
    return None


# ---------------------------------------------------------------------------
# Basic checks
# ---------------------------------------------------------------------------
def same_context(left: Revision, right: Revision) -> bool:
    """Check if two revisions describe the same request.

    The order of the targets can change when one of them is edited, so the
    targets are compared sorted by their ID.

    Parameters
    ----------
    left, right : Revision
        Revisions to compare

    Returns
    -------
    bool
        True if they describe the same request
    """
    # Firstly compare everything apart from the targets
    if left.revision_id != right.revision_id:
        return False
    if left.reference_id != right.reference_id or left.profile_id != right.profile_id:
        return False
    if left.coordinate_system != right.coordinate_system:
        return False

    # Then the targets, independently of their order
    left_targets = sorted(left.targets, key=lambda target: target.target_id)
    right_targets = sorted(right.targets, key=lambda target: target.target_id)
    return left_targets == right_targets


def unique(values: list[str], subject: str) -> None:
    """Check that every ID occurs only once in the list.

    Parameters
    ----------
    values : list[str]
        IDs to check
    subject : str
        What the IDs are, only used in the error message

    Raises
    ------
    DomainError
        SCHEMA_INVALID if some ID is there twice
    """
    if len(values) != len(set(values)):
        raise DomainError("SCHEMA_INVALID", f"The same {subject} ID is there twice.")


# ---------------------------------------------------------------------------
# Request
# ---------------------------------------------------------------------------
def validate_revision(
    revision: Revision, catalogue: Catalogue, *, require_targets: bool = False
) -> None:
    """Check the chosen reference, profile and the target coordinates.

    Parameters
    ----------
    revision : Revision
        Revision to check
    catalogue : Catalogue
        Supported references and profiles
    require_targets : bool
        If True, a revision without targets is refused (used for export)

    Raises
    ------
    DomainError
        On the first problem found
    """
    # Both of these raise if not supported
    reference = catalogue.reference(revision.reference_id)
    catalogue.profile(revision.profile_id, revision.reference_id)

    unique([target.target_id for target in revision.targets], "target")
    if require_targets and not revision.targets:
        raise DomainError(
            "EXPORT_NOT_READY", "Add at least one accepted target.", "/targets"
        )

    # Check each target against the length of its contig
    lengths = {contig.accession: contig.length for contig in reference.contigs}
    for target in revision.targets:
        pointer = "/targets/" + target.target_id
        if target.contig not in lengths:
            raise DomainError(
                "INTERVAL_INVALID",
                "Choose one of the contigs of this reference.",
                pointer + "/contig",
            )
        length = lengths[target.contig]
        if not 0 <= target.start < target.end <= length:
            raise DomainError(
                "INTERVAL_INVALID",
                f"Start has to be smaller than end, and end at most {length:,} "
                "(end is not included).",
                pointer + "/end",
            )


def parse_target(draft: TargetDraft, target_id: str) -> Target:
    """Read the decimal coordinates from the editor and create a target.

    Parameters
    ----------
    draft : TargetDraft
        Text from the target editor
    target_id : str
        ID given to the created target

    Returns
    -------
    Target
        The created target, its bounds are not checked yet

    Raises
    ------
    DomainError
        If some of the fields is not a valid value
    """
    # Only plain digits are accepted, no signs, spaces or exponents
    for name, value in [("start", draft.start), ("end", draft.end)]:
        if not re.fullmatch(r"[0-9]+", value) or int(value) > MAX_SAFE_INTEGER:
            raise DomainError(
                "INTERVAL_INVALID",
                "Enter a whole number (0 or more).",
                "/target/" + name,
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
        strand=cast("Strand", draft.strand),
    )


def request_diagnostics(
    study: Study, revision: Revision, catalogue: Catalogue
) -> list[Diagnostic]:
    """Return the local problems which stop the request from being exported.

    Parameters
    ----------
    study : Study
        Study the revision belongs to
    revision : Revision
        Revision to check
    catalogue : Catalogue
        Supported references and profiles

    Returns
    -------
    list[Diagnostic]
        Found problems, empty if the request is ready
    """
    try:
        validate_revision(revision, catalogue, require_targets=True)
    except DomainError as error:
        return error.diagnostics

    if not study.title.strip():
        diagnostic = Diagnostic(
            code="SCHEMA_INVALID", message="Enter a study title.", location="/title"
        )
        return [diagnostic]
    return []


# ---------------------------------------------------------------------------
# Evidence and review
# ---------------------------------------------------------------------------
def validate_bundle(bundle: EvidenceBundle, catalogue: Catalogue) -> None:
    """Check the context of the bundle, its candidates and metrics.

    Parameters
    ----------
    bundle : EvidenceBundle
        Bundle to check
    catalogue : Catalogue
        Supported references and profiles

    Raises
    ------
    DomainError
        On the first problem found
    """
    validate_revision(bundle.context, catalogue)

    # The demo reference is not real, so nothing computed on it can be real
    if (
        bundle.category == "computational_prediction"
        and bundle.context.reference_id == DEMO_REFERENCE
    ):
        raise DomainError(
            "CONTEXT_MISMATCH",
            "Evidence for the demo reference can only be synthetic.",
        )

    unique([candidate.candidate_id for candidate in bundle.candidates], "candidate")

    targets = {target.target_id for target in bundle.context.targets}
    for candidate in bundle.candidates:
        if candidate.target_id not in targets:
            raise DomainError(
                "DANGLING_REFERENCE",
                "A candidate refers to a target which is not in the file's revision.",
            )
        # Value has to be there exactly when the metric says it is present
        for metric in candidate.metrics:
            present = metric.availability == "present"
            if present != (metric.value is not None):
                raise DomainError(
                    "SCHEMA_INVALID",
                    "A metric has a value but says it is missing (or the reverse).",
                )


def resolve_candidate(study: Study, key: CandidateKey, revision_id: str) -> None:
    """Check that the candidate is in evidence of the given revision.

    Parameters
    ----------
    study : Study
        Study to look into
    key : CandidateKey
        Candidate to find
    revision_id : str
        Revision the candidate's evidence has to belong to

    Raises
    ------
    DomainError
        DANGLING_REFERENCE if the candidate is not found
    """
    for evidence in study.evidence:
        bundle = evidence.bundle
        # Skip the other bundles and bundles of other revisions
        if bundle.bundle_id != key.bundle_id:
            continue
        if bundle.context.revision_id != revision_id:
            continue

        for candidate in bundle.candidates:
            if candidate.candidate_id == key.candidate_id:
                return

    raise DomainError(
        "DANGLING_REFERENCE",
        "The candidate is not in the evidence of this revision.",
    )


def unresolved(collections: list[Collection]) -> int:
    """Count the decisions that still need to be finished.

    An empty collection counts as one unfinished item. A decision is done
    only when it has a final disposition and also a reason.

    Parameters
    ----------
    collections : list[Collection]
        Collections to count in

    Returns
    -------
    int
        Number of unfinished items
    """
    count = 0
    for collection in collections:
        if not collection.memberships:
            count += 1
            continue

        for member in collection.memberships:
            if member.disposition in OPEN_DISPOSITIONS:
                count += 1
            elif not member.rationale.strip():
                count += 1
    return count


# ---------------------------------------------------------------------------
# Whole study
# ---------------------------------------------------------------------------
def _check_target_labels(study: Study) -> None:
    # Collect the target IDs from all revisions, also the targets removed later
    target_ids: set[str] = set()
    for revision in study.revisions:
        for target in revision.targets:
            target_ids.add(target.target_id)

    if set(study.target_labels) != target_ids:
        raise DomainError(
            "DANGLING_REFERENCE",
            "Every target needs exactly one label.",
        )


def _check_evidence(study: Study, catalogue: Catalogue) -> None:
    # Each bundle has to match the retained revision it was produced for
    for item in study.evidence:
        validate_bundle(item.bundle, catalogue)
        context = revision_by_id(study, item.bundle.context.revision_id)
        if item.bundle.request_id != study.request_id or not same_context(
            context, item.bundle.context
        ):
            raise DomainError(
                "CONTEXT_MISMATCH",
                "Stored evidence doesn't match its revision.",
            )


def _check_collections(study: Study) -> None:
    # Firstly the limit over all collections together
    total = 0
    for collection in study.collections:
        total += len(collection.memberships)
    if total > MAX_MEMBERSHIPS:
        raise DomainError(
            "LIMIT_EXCEEDED", "A study supports at most 1,000 memberships."
        )

    # Then each membership and its supporting references
    for collection in study.collections:
        revision_by_id(study, collection.revision_id)
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


def _check_drafts(study: Study) -> None:
    # Target draft can only edit a target of the active revision
    target_draft = study.draft_buffers.target
    if target_draft and target_draft.target_id is not None:
        active_ids = {target.target_id for target in active_revision(study).targets}
        if target_draft.target_id not in active_ids:
            raise DomainError(
                "DANGLING_REFERENCE", "The target being edited doesn't exist anymore."
            )

    # Decision draft needs an existing membership to belong to
    decision = study.draft_buffers.decision
    if not decision:
        return

    collection = find_collection(study, decision.collection_id)
    member_found = False
    if collection is not None:
        for member in collection.memberships:
            if member.candidate == decision.candidate:
                member_found = True
                break
    if collection is None or not member_found:
        raise DomainError(
            "DANGLING_REFERENCE",
            "The decision being edited is for a candidate not in the collection.",
        )

    for key in decision.evidence_refs:
        resolve_candidate(study, key, collection.revision_id)


def validate_study(study: Study, catalogue: Catalogue) -> None:
    """Check all the data of the study and the references between its parts.

    Parameters
    ----------
    study : Study
        Study to check
    catalogue : Catalogue
        Supported references and profiles

    Raises
    ------
    DomainError
        On the first problem found
    """
    # IDs have to be unique
    unique([revision.revision_id for revision in study.revisions], "revision")
    unique([item.bundle.bundle_id for item in study.evidence], "bundle")
    unique([item.collection_id for item in study.collections], "collection")

    # Active revision has to exist and all revisions have to be valid
    active_revision(study)
    for revision in study.revisions:
        validate_revision(revision, catalogue)

    _check_target_labels(study)
    _check_evidence(study, catalogue)
    _check_collections(study)
    _check_drafts(study)
