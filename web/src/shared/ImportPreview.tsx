/*************************************************************************
 * Name: Lukas (Viridis) Dubsik
 *************************************************************************/
import { useWorkspace } from "../app/WorkspaceProvider";

export function ImportPreviewPanel() {
  const { state, controller } = useWorkspace();
  const preview = state.importPreview;
  if (!preview) return null;
  const expected = preview.summary.expected_context;
  const received = preview.summary.received_context;
  return (
    <section
      className={`panel import-preview ${preview.status === "blocked" ? "warning-border" : ""}`}
      aria-label="Import preview"
    >
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Inspect before accepting</p>
          <h2>
            {preview.kind === "request" ? "Request" : "Evidence"} import preview
          </h2>
        </div>
        <span
          className={`badge ${preview.status === "blocked" ? "amber" : "teal"}`}
        >
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
            {preview.summary.candidate_count ??
              preview.summary.target_count ??
              "Not available"}
          </dd>
        </div>
        <div>
          <dt>Evidence category</dt>
          <dd>{preview.summary.category ?? "Request only"}</dd>
        </div>
      </dl>
      {preview.summary.existing_study_id && (
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
          disabled={
            state.busy ||
            preview.status === "blocked" ||
            !!preview.summary.existing_study_id
          }
          onClick={() => void controller.acceptImport()}
        >
          {preview.kind === "request"
            ? "Open request"
            : preview.status === "duplicate"
              ? "Acknowledge duplicate"
              : "Attach evidence"}
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
