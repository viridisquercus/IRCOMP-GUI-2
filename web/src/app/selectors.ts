/*************************************************************************
 * Name: Lukas (Viridis) Dubsik
 *************************************************************************/
import type { State } from "./state";
import type {
  Bundle,
  Candidate,
  CandidateKey,
  Collection,
} from "../shared/types";

export const keyEqual = (
  left: CandidateKey | null,
  right: CandidateKey | null,
) =>
  left?.bundle_id === right?.bundle_id &&
  left?.candidate_id === right?.candidate_id;
export const revision = (state: State) =>
  state.workspace?.study.revisions.find(
    (item) => item.revision_id === state.revisionId,
  );
export const dirty = (state: State) =>
  !!state.workspace?.dirty || state.generation !== state.syncedGeneration;
export const unapplied = (state: State) =>
  state.buffers.target !== null || state.buffers.decision !== null;
export const collections = (state: State) =>
  state.workspace?.study.collections.filter(
    (item) => item.revision_id === state.revisionId,
  ) ?? [];
export const selectedCollection = (state: State) =>
  collections(state).find(
    (item) => item.collection_id === state.collectionId,
  ) ?? collections(state)[0];
/** Count the decisions that still need a disposition or a reason. */
export function unresolvedCount(items: Collection[]): number {
  let count = 0;
  for (const collection of items) {
    // An empty collection also means there is unfinished review work.
    if (collection.memberships.length === 0) {
      count += 1;
      continue;
    }
    for (const member of collection.memberships) {
      if (
        member.disposition === "undecided" ||
        member.disposition === "needs_clarification" ||
        !member.rationale.trim()
      ) {
        count += 1;
      }
    }
  }
  return count;
}

type CandidateRecord = {
  candidate: Candidate;
  bundle: Bundle;
  key: CandidateKey;
};

/** Get candidates from the evidence belonging to the selected revision. */
export function candidates(state: State): CandidateRecord[] {
  const records: CandidateRecord[] = [];
  if (!state.workspace) return records;

  for (const evidence of state.workspace.study.evidence) {
    const bundle = evidence.bundle;
    if (bundle.context.revision_id !== state.revisionId) continue;

    for (const candidate of bundle.candidates) {
      records.push({
        candidate,
        bundle,
        key: {
          bundle_id: bundle.bundle_id,
          candidate_id: candidate.candidate_id,
        },
      });
    }
  }
  return records;
}

/** Check typed coordinates before sending them to the model. */
export function draftProblems(
  state: State,
  draft: import("../shared/types").TargetDraft | null,
): import("../shared/types").Diagnostic[] {
  if (!draft) return [];
  const errors: import("../shared/types").Diagnostic[] = [];
  const add = (field: string, message: string) =>
    errors.push({
      code: "INTERVAL_INVALID",
      severity: "error",
      location: `/target/${field}`,
      message,
    });
  if (!draft.label.trim()) add("label", "Enter a target label.");
  const reference = state.catalogue?.references.find(
    (item) => item.reference_id === revision(state)?.reference_id,
  );
  const contig = reference?.contigs.find(
    (item) => item.accession === draft.contig,
  );
  if (!contig) add("contig", "Choose an exact supported contig accession.");
  for (const field of ["start", "end"] as const) {
    if (
      !/^[0-9]+$/.test(draft[field]) ||
      !Number.isSafeInteger(Number(draft[field]))
    )
      add(field, `Enter a nonnegative whole number for ${field}.`);
  }
  if (
    errors.every(
      (item) =>
        !item.location?.endsWith("/start") && !item.location?.endsWith("/end"),
    ) &&
    (Number(draft.start) >= Number(draft.end) ||
      (contig && Number(draft.end) > contig.length))
  )
    add(
      "end",
      `Require 0 ≤ start < end ≤ ${contig?.length.toLocaleString() ?? "contig length"} (end-exclusive).`,
    );
  return errors;
}
