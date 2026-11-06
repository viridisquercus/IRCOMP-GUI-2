/*************************************************************************
 * Name: Lukas (Viridis) Dubsik
 *************************************************************************/
export type Target = {
  target_id: string;
  contig: string;
  start: number;
  end: number;
  strand: "+" | "-" | ".";
};
export type Revision = {
  revision_id: string;
  reference_id: string;
  profile_id: string;
  coordinate_system: "0-based-half-open";
  targets: Target[];
};
export type CandidateKey = { bundle_id: string; candidate_id: string };
export type Disposition =
  "undecided" | "include_for_review" | "exclude" | "needs_clarification";
export type Membership = {
  candidate: CandidateKey;
  disposition: Disposition;
  rationale: string;
  evidence_refs: CandidateKey[];
};
export type Collection = {
  collection_id: string;
  revision_id: string;
  name: string;
  memberships: Membership[];
};
export type Metric = {
  name: string;
  model: string | null;
  unit: string | null;
  scale: string | null;
  direction: "higher" | "lower" | "not_ordered" | null;
  availability:
    "present" | "not_supplied" | "unsupported" | "failed" | "unknown";
  value: number | null;
};
export type Candidate = {
  candidate_id: string;
  target_id: string;
  label: string;
  metrics: Metric[];
  raw_record: Record<string, unknown>;
};
export type Bundle = {
  bundle_id: string;
  request_id: string;
  context: Revision;
  category: "synthetic" | "computational_prediction";
  source: { name: string; version: string; uri: string | null };
  candidates: Candidate[];
  dependencies: { uri: string; description: string }[];
};
export type TargetDraft = {
  target_id: string | null;
  label: string;
  contig: string;
  start: string;
  end: string;
  strand: string;
};
export type DecisionDraft = Membership & { collection_id: string };
export type DraftBuffers = {
  target: TargetDraft | null;
  decision: DecisionDraft | null;
};
export type Study = {
  study_id: string;
  request_id: string;
  title: string;
  active_revision_id: string;
  revisions: Revision[];
  target_labels: Record<string, string>;
  evidence: { bundle: Bundle; sha256: string }[];
  collections: Collection[];
  draft_buffers: DraftBuffers;
};
export type Diagnostic = {
  code: string;
  severity: "error" | "warning" | "info";
  location: string | null;
  message: string;
};
export type Workspace = {
  workspace_id: string;
  base_saved_version: number;
  dirty: boolean;
  can_undo: boolean;
  study: Study;
  diagnostics: Diagnostic[];
};
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
    reference_ids: string[];
    nuclease: string;
    pam: string;
    intent: string;
  }[];
};
export type StudySummary = {
  study_id: string;
  title: string;
  saved_version: number;
  updated_at: string;
};
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
    expected_context: Revision | null;
    received_context: Revision | null;
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
  review_status: "draft" | "reviewed" | null;
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
  diagnostics: Diagnostic[];
  draft_diagnostics: Diagnostic[];
};
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
