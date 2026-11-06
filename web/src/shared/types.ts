/**
 * @file types.ts
 * @brief Types of the data exchanged with the local service
 * @author Lukas (Viridis) Dubsik
 * @date 6-11-2026
 * @version 0.1
 *
 * Detailed description:
 *  The types themselves are generated from the Python models into
 *  types.generated.ts (make contracts), this file only picks the ones the
 *  views use. The meaning of the fields is described in domain/models.py.
 */
export type {
  Target,
  Revision,
  CandidateKey,
  Membership,
  Metric,
  Candidate,
  Bundle,
  TargetDraft,
  DecisionDraft,
  DraftBuffers,
  Study,
  Diagnostic,
  Workspace,
  Reference,
  Catalogue,
  StudySummary,
  ImportPreview,
  ExportPreview,
  Validation,
  Command,
  Collection,
  StudyList,
  ErrorResponse,
} from "./types.generated";
import type { Membership } from "./types.generated";
export type Disposition = Membership["disposition"];
