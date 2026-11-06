/**
 * @file ImportPreview.tsx
 * @brief Panel describing an imported file before it is accepted
 * @author Lukas (Viridis) Dubsik
 * @date 6-11-2026
 * @version 0.1
 *
 * Detailed description:
 *  Used for both request and evidence imports. The study stays untouched
 *  until the user presses Open request / Attach evidence.
 */
import { useWorkspace } from "../app/WorkspaceProvider";
import type { ImportPreview } from "./types";

/* Functions */
/**
 * @brief Text of the accept button
 */
function acceptLabel(preview: ImportPreview): string {
  if (preview.kind === "request") return "Open request";
  if (preview.status === "duplicate") return "Acknowledge duplicate";
  return "Attach evidence";
}

/* Components */
export function ImportPreviewPanel() {
  const { state, controller } = useWorkspace();
  const preview = state.importPreview;
  if (!preview) return null;

  const summary = preview.summary;
  const expected = summary.expected_context;
  const received = summary.received_context;
  const blocked = preview.status === "blocked";
  // A saved request can't be imported again, it has to be opened
  const alreadySaved = !!summary.existing_study_id;

  return (
    <section
      className={`panel import-preview ${blocked ? "warning-border" : ""}`}
      aria-label="Import preview"
    >
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Inspect before accepting</p>
          <h2>
            {preview.kind === "request" ? "Request" : "Evidence"} import preview
          </h2>
        </div>
        <span className={`badge ${blocked ? "amber" : "teal"}`}>
          {preview.status}
        </span>
      </div>
      <p>Parsing and preview leave your accepted study unchanged.</p>
      <dl className="metadata">
        <div>
          <dt>Reference received</dt>
          <dd>{received?.reference_id ?? "Not available"}</dd>
        </div>
        <div>
          <dt>Revision received</dt>
          <dd className="mono">{received?.revision_id ?? "Not available"}</dd>
        </div>
        {expected && (
          <div>
            <dt>Reference expected</dt>
            <dd>{expected.reference_id}</dd>
          </div>
        )}
        <div>
          <dt>Records</dt>
          <dd>
            {summary.candidate_count ?? summary.target_count ?? "Not available"}
          </dd>
        </div>
        <div>
          <dt>Evidence category</dt>
          <dd>{summary.category ?? "Request only"}</dd>
        </div>
      </dl>
      {alreadySaved && (
        <p className="notice">
          This request identity already exists. Open the saved study from the
          study selector; import cannot overwrite it.
        </p>
      )}
      {preview.diagnostics.map((item, index) => (
        <p role="alert" key={index} className="field-error">
          {item.message} <small>{item.code}</small>
        </p>
      ))}
      <div className="actions">
        <button
          disabled={state.busy || blocked || alreadySaved}
          onClick={() => void controller.acceptImport()}
        >
          {acceptLabel(preview)}
        </button>
        <button
          className="secondary"
          disabled={state.busy}
          onClick={() => void controller.cancelImport()}
        >
          Cancel import
        </button>
      </div>
    </section>
  );
}
