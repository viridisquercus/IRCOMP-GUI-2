/**
 * @file state.ts
 * @brief State of the web client and the reducer changing it
 * @author Lukas (Viridis) Dubsik
 * @version 0.1
 *
 * Detailed description:
 *  The editor text (buffers) is local and changes on every key press.
 *  Each change increases generation. When the service answers, the answer
 *  only replaces the buffers if no typing happened in the meantime
 *  (generation is still the one the request was sent with).
 */
import type {
  CandidateKey,
  Catalogue,
  Diagnostic,
  DraftBuffers,
  ExportPreview,
  ImportPreview,
  StudySummary,
  Validation,
  Workspace,
} from "../shared/types";
import { NO_DRAFTS } from "../shared/constants";

/* Types */
export type View = "prepare" | "review" | "export";

export type State = {
  workspace: Workspace | null; // Open workspace, null on the welcome page
  catalogue: Catalogue | null;
  studies: StudySummary[]; // Saved studies for the selector
  view: View;
  revisionId: string; // Revision shown, can be an older one
  targetId: string | null; // Selected target in Prepare
  candidate: CandidateKey | null; // Selected candidate in Review
  collectionId: string; // Selected collection in Review
  buffers: DraftBuffers; // Unapplied editor text
  generation: number; // Increased on every change of the buffers
  syncedGeneration: number; // Generation last sent to (and saved by) the service
  busy: boolean; // An operation is running
  status: string; // Message of the last finished operation
  error: { code: string; message: string; diagnostics: Diagnostic[] } | null;
  importPreview: ImportPreview | null;
  exportPreview: ExportPreview | null;
  validation: Validation | null; // Result of Check request
  fields: Record<string, string>; // Free form inputs not belonging to the study
  exportKind: "request" | "review";
  selectedCollections: string[]; // Collections chosen for a review export
};

export type Action =
  | { type: "patch"; value: Partial<State> }
  | { type: "field"; name: string; value: string }
  | { type: "draft"; buffers: DraftBuffers }
  | {
      type: "received";
      workspace: Workspace;
      generation: number;
      opening?: boolean;
    };

/* Values */
export const initialState: State = {
  workspace: null,
  catalogue: null,
  studies: [],
  view: "prepare",
  revisionId: "",
  targetId: null,
  candidate: null,
  collectionId: "",
  buffers: NO_DRAFTS,
  generation: 0,
  syncedGeneration: 0,
  busy: false,
  status: "",
  error: null,
  importPreview: null,
  exportPreview: null,
  validation: null,
  fields: {},
  exportKind: "request",
  selectedCollections: [],
};

/* Functions */
/**
 * @brief Change the drafts, anything derived from the old ones is dropped
 *
 * @param state Current state
 * @param buffers New editor text
 * @return The new state
 */
function changeDrafts(state: State, buffers: DraftBuffers): State {
  // Nothing changed, keep the same state (and generation)
  if (JSON.stringify(buffers) === JSON.stringify(state.buffers)) return state;

  return {
    ...state,
    buffers,
    generation: state.generation + 1,
    error: null,
    exportPreview: null,
    validation: null,
  };
}

/**
 * @brief Take over the workspace sent back by the service
 *
 * @param state Current state
 * @param workspace Workspace from the response
 * @param generation Generation the request was sent with
 * @param opening True if a (new) study was just opened
 * @return The new state
 */
function receiveWorkspace(
  state: State,
  workspace: Workspace,
  generation: number,
  opening: boolean,
): State {
  // Keep newer typing if the response belongs to an older editor state
  const sameGeneration = opening || state.generation === generation;

  // Stay on the shown older revision, unless a new study was opened
  // or the shown one was the active one (then follow the new active)
  let revisionId = state.revisionId;
  const revisionExists = workspace.study.revisions.some(
    (item) => item.revision_id === revisionId,
  );
  const wasActive = revisionId === state.workspace?.study.active_revision_id;
  if (opening || !revisionExists || wasActive) {
    revisionId = workspace.study.active_revision_id;
  }

  const next: State = {
    ...state,
    workspace,
    revisionId,
    error: null,
    validation: null,
    exportPreview: null,
  };
  if (sameGeneration) {
    next.buffers = workspace.study.draft_buffers;
    next.syncedGeneration = state.generation;
  }

  // Opening a study starts with nothing selected
  if (opening) {
    next.targetId = null;
    next.candidate = null;
    next.collectionId = "";
    next.importPreview = null;
    next.fields = {};
  }
  return next;
}

/**
 * @brief Apply a local change or a response of the Python service
 *
 * @param state Current state
 * @param action What happened
 * @return The new state
 */
export function reducer(state: State, action: Action): State {
  switch (action.type) {
    case "patch":
      return { ...state, ...action.value };
    case "field":
      return {
        ...state,
        fields: { ...state.fields, [action.name]: action.value },
      };
    case "draft":
      return changeDrafts(state, action.buffers);
    case "received":
      return receiveWorkspace(
        state,
        action.workspace,
        action.generation,
        action.opening ?? false,
      );
  }
}
