/**
 * @file types.ts
 * @brief Types of the data exchanged with the local service
 * @author Lukas (Viridis) Dubsik
 * @date 6-11-2026
 * @version 0.1
 *
 * Detailed description:
 *  These mirror the pydantic models in domain/models.py. The field names
 *  are kept the same (snake_case) so the JSON is used as it comes.
 */

/* Request */
export type Target = {
  target_id: string; // UUID, stays the same through revisions
  contig: string; // Exact contig accession
  start: number; // First base, 0-based
  end: number; // End of the interval, exclusive
  strand: "+" | "-" | "."; // "." when not specified
};

export type Revision = {
  revision_id: string;
  reference_id: string; // Catalogue ID of the reference
  profile_id: string; // Catalogue ID of the analysis profile
  coordinate_system: "0-based-half-open";
  targets: Target[];
};

/* Evidence */
export type CandidateKey = { bundle_id: string; candidate_id: string };

export type Metric = {
  name: string;
  model: string | null;
  unit: string | null;
  scale: string | null;
  direction: "higher" | "lower" | "not_ordered" | null;
  availability:
    "present" | "not_supplied" | "unsupported" | "failed" | "unknown";
  value: number | null; // Only set when availability is present
};

export type Candidate = {
  candidate_id: string;
  target_id: string; // Target the candidate belongs to
  label: string;
  metrics: Metric[];
  raw_record: Record<string, unknown>; // Untouched record of the producer
};

export type Bundle = {
  bundle_id: string;
  request_id: string;
  context: Revision; // Exact revision the producer received
  category: "synthetic" | "computational_prediction";
  source: { name: string; version: string; uri: string | null };
  candidates: Candidate[];
  dependencies: { uri: string; description: string }[];
};

/* Review */
export type Disposition =
  "undecided" | "include_for_review" | "exclude" | "needs_clarification";

export type Membership = {
  candidate: CandidateKey;
  disposition: Disposition;
  rationale: string; // Why the decision was made
  evidence_refs: CandidateKey[]; // Other candidates supporting it
};

export type Collection = {
  collection_id: string;
  revision_id: string; // Revision the collection belongs to
  name: string;
  memberships: Membership[];
};

/* Unapplied editor text */
export type TargetDraft = {
  target_id: string | null; // null when adding a new target
  label: string;
  contig: string;
  start: string; // Kept as text so unfinished input can be saved
  end: string;
  strand: string;
};
export type DecisionDraft = Membership & { collection_id: string };
export type DraftBuffers = {
  target: TargetDraft | null;
  decision: DecisionDraft | null;
};

/* Study and workspace */
export type Study = {
  study_id: string;
  request_id: string;
  title: string;
  active_revision_id: string; // Revision currently edited
  revisions: Revision[]; // All retained revisions
  target_labels: Record<string, string>; // Labels by target ID
  evidence: { bundle: Bundle; sha256: string }[]; // Bytes are not sent to the client
  collections: Collection[];
  draft_buffers: DraftBuffers;
};

export type Diagnostic = {
  code: string;
  severity: "error" | "warning" | "info";
  location: string | null; // JSON pointer to the field
  message: string;
};

export type Workspace = {
  workspace_id: string;
  base_saved_version: number; // 0 if never saved
  dirty: boolean; // Accepted changes not saved yet
  can_undo: boolean;
  study: Study;
  diagnostics: Diagnostic[];
};

export type StudySummary = {
  study_id: string;
  title: string;
  saved_version: number;
  updated_at: string;
};

/* Catalogue */
export type Reference = {
  reference_id: string;
  category: string;
  assembly: string | null;
  contigs: { accession: string; label: string; length: number }[];
};

export type Catalogue = {
  references: Reference[];
  profiles: {
    profile_id: string;
    reference_ids: string[]; // References the profile can be used with
    nuclease: string;
    pam: string;
    intent: string;
  }[];
};

/* Responses of import, export and checks */
export type ImportPreview = {
  preview_id: string;
  kind: "request" | "evidence";
  status: "ready" | "blocked" | "duplicate";
  diagnostics: Diagnostic[];
  summary: {
    request_id?: string;
    bundle_id?: string;
    reference_id?: string;
    candidate_count?: number;
    category?: string;
    target_count?: number;
    existing_study_id?: string | null;
    expected_context: Revision | null; // What the evidence should match
    received_context: Revision | null; // What the file declares
  };
};

export type ExportPreview = {
  export_id: string;
  filename: string;
  sha256: string;
  byte_length: number;
  study_id: string;
  saved_version: number;
  revision_id: string;
  kind: "request" | "review";
  review_status: "draft" | "reviewed" | null; // null for a request
  target_count: number;
  candidate_count: number;
  collection_count: number;
  unresolved_count: number;
  dependency_count: number;
};

export type Validation = {
  export_ready: boolean;
  checks: {
    name: string;
    status: "passed" | "failed" | "not_performed";
    message: string;
  }[];
  diagnostics: Diagnostic[]; // Problems of the accepted values
  draft_diagnostics: Diagnostic[]; // Problems of the unapplied target text
};

/* Commands sent to the service */
export type Command =
  | { type: "rename_study"; title: string }
  | { type: "apply_target"; draft: TargetDraft }
  | { type: "remove_target"; target_id: string }
  | { type: "rename_target"; target_id: string; label: string }
  | {
      type: "set_context";
      reference_id: string;
      profile_id: string;
      targets: Target[];
    }
  | { type: "attach_evidence"; preview_id: string }
  | { type: "create_collection"; revision_id: string; name: string }
  | { type: "rename_collection"; collection_id: string; name: string }
  | { type: "remove_collection"; collection_id: string }
  | {
      type: "add_member" | "remove_member";
      collection_id: string;
      candidate: CandidateKey;
    }
  | ({ type: "set_decision"; collection_id: string } & Membership);
