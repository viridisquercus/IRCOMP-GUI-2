/*************************************************************************
 * Name: Lukas (Viridis) Dubsik
 *************************************************************************/
import { useWorkspace } from "../../app/WorkspaceProvider";
import {
  collections,
  dirty,
  revision,
  unapplied,
  unresolvedCount,
} from "../../app/selectors";

export function ExportView() {
  const { state, dispatch, controller } = useWorkspace();
  const workspace = state.workspace!;
  const context = revision(state)!;
  const items = collections(state);
  const selected = items.filter((item) =>
    state.selectedCollections.includes(item.collection_id),
  );
  const unsaved = dirty(state);
  const preview = state.exportPreview;
  return (
    <>
      <div className="section-intro">
        <div>
          <p className="eyebrow">03 / Export</p>
          <h1>Export the study</h1>
          <p>
            Inspect the saved revision, source records and unresolved decisions
            before downloading.
          </p>
        </div>
      </div>
      <div className="export-grid">
        <section className="panel">
          <div className="panel-heading">
            <h2>Choose the handover</h2>
          </div>
          <div className="export-options">
            {(["request", "review"] as const).map((kind) => (
              <label
                key={kind}
                className={`export-option ${state.exportKind === kind ? "selected" : ""}`}
              >
                <input
                  type="radio"
                  name="export-kind"
                  checked={state.exportKind === kind}
                  onChange={() =>
                    dispatch({
                      type: "patch",
                      value: { exportKind: kind, exportPreview: null },
                    })
                  }
                />
                <span>
                  <strong>
                    {kind === "request"
                      ? "Local request snapshot"
                      : "Review / evidence package"}
                  </strong>
                  <small>
                    {kind === "request"
                      ? "One exact request revision and its labels. No drafts or review state."
                      : "Selected collections, decisions and complete original evidence bytes."}
                  </small>
                </span>
                <span className="mono">.{kind}.json</span>
              </label>
            ))}
          </div>
          {state.exportKind === "review" && (
            <fieldset>
              <legend>Collections for this revision</legend>
              {!items.length && (
                <p className="hint">
                  Import evidence and create a review collection first.
                </p>
              )}
              {items.map((item) => (
                <label className="checkbox" key={item.collection_id}>
                  <input
                    type="checkbox"
                    checked={state.selectedCollections.includes(
                      item.collection_id,
                    )}
                    onChange={(event) =>
                      dispatch({
                        type: "patch",
                        value: {
                          selectedCollections: event.target.checked
                            ? [...state.selectedCollections, item.collection_id]
                            : state.selectedCollections.filter(
                                (id) => id !== item.collection_id,
                              ),
                          exportPreview: null,
                        },
                      })
                    }
                  />
                  <span>
                    {item.name}
                    <small>
                      {item.memberships.length} members ·{" "}
                      {unresolvedCount([item])} unresolved
                    </small>
                  </span>
                </label>
              ))}
            </fieldset>
          )}
          {!workspace.base_saved_version && (
            <p className="notice">
              Save the study before generating an export.
            </p>
          )}
          {unsaved && (
            <p className="notice">
              There are unsaved changes. Apply pending edits and Save, or
              explicitly export the last saved snapshot. Its values may differ
              from the working view.
            </p>
          )}
          {unapplied(state) && (
            <p className="notice">
              Unapplied editor drafts are excluded from exports, even when saved
              for recovery. Apply them first to include their values.
            </p>
          )}
          <div className="actions wrap">
            <button
              disabled={
                state.busy ||
                !workspace.base_saved_version ||
                unsaved ||
                unapplied(state) ||
                (state.exportKind === "review" && !selected.length)
              }
              onClick={() => void controller.previewExport(false)}
            >
              Preview saved export
            </button>
            {(unsaved || unapplied(state)) && (
              <button
                className="secondary"
                disabled={
                  state.busy ||
                  !workspace.base_saved_version ||
                  (state.exportKind === "review" && !selected.length)
                }
                onClick={() => void controller.previewExport(true)}
              >
                Export last saved
              </button>
            )}
          </div>
        </section>
        <aside className="panel">
          <div className="panel-heading">
            <h2>Selected context</h2>
          </div>
          <dl className="metadata">
            <div>
              <dt>Saved version</dt>
              <dd>{workspace.base_saved_version || "Not saved"}</dd>
            </div>
            <div>
              <dt>Request revision</dt>
              <dd className="mono">{context.revision_id}</dd>
            </div>
            <div>
              <dt>Reference</dt>
              <dd>{context.reference_id}</dd>
            </div>
            <div>
              <dt>Working target count</dt>
              <dd>{context.targets.length}</dd>
            </div>
            <div>
              <dt>Selected collections</dt>
              <dd>{selected.length}</dd>
            </div>
          </dl>
          <p className="hint">
            The frozen export preview below is authoritative for the downloaded
            file.
          </p>
        </aside>
      </div>
      {preview && (
        <section className="panel export-preview" aria-label="Export preview">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">Frozen saved snapshot</p>
              <h2>
                {preview.review_status === "draft"
                  ? "Draft review"
                  : preview.kind === "request"
                    ? "Request snapshot"
                    : "Review bookkeeping complete"}
              </h2>
            </div>
            <span
              className={`badge ${preview.review_status === "draft" ? "amber" : "teal"}`}
            >
              {preview.review_status ?? "Request"}
            </span>
          </div>
          <div className="stat-grid">
            <div>
              <strong>{preview.target_count}</strong>
              <span>Targets</span>
            </div>
            <div>
              <strong>{preview.candidate_count}</strong>
              <span>Source candidates</span>
            </div>
            <div>
              <strong>{preview.collection_count}</strong>
              <span>Collections</span>
            </div>
            <div>
              <strong>{preview.unresolved_count}</strong>
              <span>Unresolved</span>
            </div>
            <div>
              <strong>{preview.dependency_count}</strong>
              <span>External dependencies</span>
            </div>
          </div>
          <p>
            {preview.kind === "review"
              ? "Original source files are included byte-for-byte. External dependencies are declared and have not been fetched."
              : "This is a local request file, not a compiled workflow or an IRCOMP-compatible YAML specification."}
          </p>
          {preview.review_status === "reviewed" && (
            <p className="notice">
              Review bookkeeping complete; scientific conclusions not verified.
            </p>
          )}
          <dl className="metadata">
            <div>
              <dt>Filename</dt>
              <dd className="mono">{preview.filename}</dd>
            </div>
            <div>
              <dt>Saved version / revision</dt>
              <dd>
                {preview.saved_version} /{" "}
                <span className="mono">{preview.revision_id}</span>
              </dd>
            </div>
            <div>
              <dt>SHA-256</dt>
              <dd className="mono">{preview.sha256}</dd>
            </div>
            <div>
              <dt>Size</dt>
              <dd>{preview.byte_length.toLocaleString()} bytes</dd>
            </div>
          </dl>
          <a
            className="button"
            download
            href={`/api/v1/exports/${preview.export_id}/file`}
          >
            {preview.review_status === "draft"
              ? "Download draft review"
              : "Download snapshot"}{" "}
            ↓
          </a>
        </section>
      )}
    </>
  );
}
