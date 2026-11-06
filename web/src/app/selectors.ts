/**
 * @file selectors.ts
 * @brief Values derived from the client state
 * @author Lukas (Viridis) Dubsik
 * @date 6-11-2026
 * @version 0.1
 */
import type { State } from "./state";
import type {
  Bundle,
  Candidate,
  CandidateKey,
  Collection,
  Diagnostic,
  Revision,
  TargetDraft,
} from "../shared/types";

/* Types */
/**
 * @brief Candidate together with the bundle it came from
 */
export type CandidateRecord = {
  candidate: Candidate;
  bundle: Bundle;
  key: CandidateKey; // Identity of the candidate across bundles
};

/* Functions */
/**
 * @brief Compare two candidate keys (null is equal only to null)
 */
export function keyEqual(
  left: CandidateKey | null,
  right: CandidateKey | null,
): boolean {
  return (
    left?.bundle_id === right?.bundle_id &&
    left?.candidate_id === right?.candidate_id
  );
}

/**
 * @brief Get the revision currently shown
 */
export function revision(state: State): Revision | undefined {
  return state.workspace?.study.revisions.find(
    (item) => item.revision_id === state.revisionId,
  );
}

/**
 * @brief Check if there is anything not saved yet
 *
 * Both accepted changes and editor text typed after the last save count.
 */
export function dirty(state: State): boolean {
  if (state.workspace?.dirty) return true;
  return state.generation !== state.syncedGeneration;
}

/**
 * @brief Check if some editor text is not applied yet
 */
export function unapplied(state: State): boolean {
  return state.buffers.target !== null || state.buffers.decision !== null;
}

/**
 * @brief Get the collections of the shown revision
 */
export function collections(state: State): Collection[] {
  if (!state.workspace) return [];
  return state.workspace.study.collections.filter(
    (item) => item.revision_id === state.revisionId,
  );
}

/**
 * @brief Get the selected collection, or the first one if none is selected
 */
export function selectedCollection(state: State): Collection | undefined {
  const items = collections(state);
  const found = items.find((item) => item.collection_id === state.collectionId);
  return found ?? items[0];
}

/**
 * @brief Count the decisions which still need a disposition or a reason
 *
 * The service calculates each count with unresolved() in domain/rules.py.
 *
 * @param items Collections to count in
 * @return Number of unfinished items
 */
export function unresolvedCount(items: Collection[]): number {
  let count = 0;
  for (const collection of items) count += collection.unresolved_count;
  return count;
}

/**
 * @brief Get the candidates from the evidence of the shown revision
 */
export function candidates(state: State): CandidateRecord[] {
  const records: CandidateRecord[] = [];
  if (!state.workspace) return records;

  for (const evidence of state.workspace.study.evidence) {
    const bundle = evidence.bundle;
    // Skip the evidence of other revisions
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

/**
 * @brief Check if the text is a whole number the browser can hold exactly
 */
export function isWholeNumber(text: string): boolean {
  return /^[0-9]+$/.test(text) && Number.isSafeInteger(Number(text));
}

/**
 * @brief Check the typed coordinates before they are sent to the service
 *
 * Only an early hint for the user, the service checks it all again.
 *
 * @param state Current state (for the catalogue and revision)
 * @param draft Target editor text
 * @return Found problems, empty if none
 */
export function draftProblems(
  state: State,
  draft: TargetDraft | null,
): Diagnostic[] {
  if (!draft) return [];

  const errors: Diagnostic[] = [];
  const add = (field: string, message: string) =>
    errors.push({
      code: "INTERVAL_INVALID",
      severity: "error",
      location: `/target/${field}`,
      message,
    });

  if (!draft.label.trim()) add("label", "Enter a target label.");

  // Contig has to be one of the reference of the shown revision
  const reference = state.catalogue?.references.find(
    (item) => item.reference_id === revision(state)?.reference_id,
  );
  const contig = reference?.contigs.find(
    (item) => item.accession === draft.contig,
  );
  if (!contig) add("contig", "Choose one of the contigs of this reference.");

  let numbersValid = true;
  for (const field of ["start", "end"] as const) {
    if (!isWholeNumber(draft[field])) {
      add(
        field,
        `${field === "start" ? "Start" : "End"} has to be a whole number (0 or more).`,
      );
      numbersValid = false;
    }
  }

  // Compare the bounds only if both of them are numbers
  if (!numbersValid) return errors;
  const start = Number(draft.start);
  const end = Number(draft.end);
  if (start >= end || (contig && end > contig.length)) {
    const length = contig?.length.toLocaleString() ?? "contig length";
    add(
      "end",
      `Start has to be smaller than end, and end at most ${length} (end is not included).`,
    );
  }
  return errors;
}
