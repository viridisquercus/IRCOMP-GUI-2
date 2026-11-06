/*************************************************************************
 * Name: Lukas (Viridis) Dubsik
 *************************************************************************/
import { useWorkspace } from "./WorkspaceProvider";
import { dirty, revision } from "./selectors";
import { PrepareView } from "../features/prepare/PrepareView";
import { ReviewView } from "../features/review/ReviewView";
import { ExportView } from "../features/export/ExportView";
import { ImportPreviewPanel } from "../shared/ImportPreview";

function StudyControls() {
  const { state, dispatch, controller } = useWorkspace();
  return (
    <details className="study-controls panel">
      <summary>New / Open / Rename / Duplicate</summary>
      <div className="study-controls-grid">
        <form
          onSubmit={(event) => {
            event.preventDefault();
            void controller.create({
              source: "new",
              title: state.fields.newTitle,
            });
          }}
        >
          <label htmlFor="new-study-title">New study title</label>
          <input
            id="new-study-title"
            value={state.fields.newTitle ?? ""}
            onChange={(event) =>
              dispatch({
                type: "field",
                name: "newTitle",
                value: event.target.value,
              })
            }
            maxLength={200}
            placeholder="A clear name for this request"
          />
          <button
            className="secondary"
            disabled={state.busy || !state.fields.newTitle?.trim()}
          >
            Create study
          </button>
        </form>
        <div>
          <label htmlFor="saved-study">Open saved study</label>
          <select
            id="saved-study"
            value={state.fields.savedStudy ?? ""}
            onChange={(event) =>
              dispatch({
                type: "field",
                name: "savedStudy",
                value: event.target.value,
              })
            }
          >
            <option value="">Select a saved study</option>
            {state.studies.map((item) => (
              <option key={item.study_id} value={item.study_id}>
                {item.title} · v{item.saved_version}
              </option>
            ))}
          </select>
          <button
            className="secondary"
            disabled={state.busy || !state.fields.savedStudy}
            onClick={() =>
              void controller.create({
                source: "saved",
                study_id: state.fields.savedStudy,
              })
            }
          >
            Open saved study
          </button>
        </div>
        {state.workspace && (
          <form
            onSubmit={(event) => {
              event.preventDefault();
              void controller.command({
                type: "rename_study",
                title: state.fields.studyTitle ?? state.workspace!.study.title,
              });
            }}
          >
            <label htmlFor="study-title">Current study title</label>
            <input
              id="study-title"
              value={state.fields.studyTitle ?? state.workspace.study.title}
              maxLength={200}
              onChange={(event) =>
                dispatch({
                  type: "field",
                  name: "studyTitle",
                  value: event.target.value,
                })
              }
            />
            <div className="actions wrap">
              <button
                className="secondary"
                disabled={
                  state.busy ||
                  !(
                    state.fields.studyTitle ?? state.workspace.study.title
                  ).trim()
                }
              >
                Rename study
              </button>
              <button
                type="button"
                className="secondary"
                disabled={state.busy}
                onClick={() => {
                  if (
                    window.confirm(
                      "Duplicate the active request with fresh identities? Evidence, decisions and draft buffers will not be copied.",
                    )
                  )
                    void controller.create({
                      source: "duplicate",
                      workspace_id: state.workspace!.workspace_id,
                      title: `${state.workspace!.study.title.slice(0, 180)} (copy)`,
                    });
                }}
              >
                Duplicate request
              </button>
            </div>
          </form>
        )}
        <div className="import-request-control">
          <span className="label">Continue from a file</span>
          <label className="file-button secondary">
            Import request
            <input
              aria-label="Import request file"
              type="file"
              accept=".json,application/json"
              disabled={state.busy}
              onChange={(event) => {
                const file = event.target.files?.[0];
                if (file) void controller.importFile("request", file);
                event.target.value = "";
              }}
            />
          </label>
          {state.workspace && (
            <button
              className="text-button"
              disabled={state.busy}
              onClick={() => void controller.close()}
            >
              Close working copy
            </button>
          )}
        </div>
      </div>
    </details>
  );
}

export function App() {
  const { state, dispatch, controller } = useWorkspace();
  const workspace = state.workspace;
  const context = revision(state);
  return (
    <div className="application">
      <a className="skip-link" href="#main-content">
        Skip to workspace
      </a>
      <header className="app-header">
        <a className="brand" href="#main-content">
          <svg viewBox="0 0 32 32" aria-hidden="true">
            <path d="M8 5v10l16 4v8M24 5v7L8 22v5" />
            <circle cx="8" cy="5" r="3" />
            <circle cx="24" cy="5" r="3" />
            <circle cx="8" cy="27" r="3" />
            <circle cx="24" cy="27" r="3" />
          </svg>
          <strong>IRCOMP</strong>
          <span className="brand-divider" />
          <span>Study Workspace</span>
        </a>
        <div className="header-right">
          <span className="local-indicator">
            <i />
            Local workspace
          </span>
          <span className="badge neutral">Pre-experiment</span>
        </div>
      </header>
      <main id="main-content">
        <div className="workspace-heading">
          <div>
            <p className="eyebrow">Request preparation / evidence review</p>
            <h2>
              {workspace?.study.title ?? "A clear context for every decision."}
            </h2>
          </div>
          {workspace && (
            <div className="save-controls">
              <span
                className={`save-status ${dirty(state) ? "unsaved" : ""}`}
                role="status"
              >
                {state.busy
                  ? "Working…"
                  : state.error?.code === "PERSISTENCE_UNAVAILABLE"
                    ? "Save failed"
                    : dirty(state)
                      ? "● Unsaved changes"
                      : `✓ Saved · v${workspace.base_saved_version}`}
              </span>
              <button
                className="secondary"
                disabled={state.busy || !workspace.can_undo}
                onClick={() => void controller.undo()}
              >
                Undo
              </button>
              <button
                disabled={state.busy}
                onClick={() => void controller.save()}
              >
                Save study
              </button>
            </div>
          )}
        </div>
        <StudyControls />
        {state.error && (
          <section className="error-banner" role="alert">
            <div>
              <strong>{state.error.message}</strong>
              <small>{state.error.code}</small>
            </div>
            <div className="actions wrap">
              <button
                className="secondary small"
                disabled={state.busy}
                onClick={() => void controller.refresh()}
              >
                Refresh working state
              </button>
              {workspace?.base_saved_version ? (
                <button
                  className="secondary small"
                  disabled={state.busy}
                  onClick={() => void controller.reopen()}
                >
                  Reopen saved study
                </button>
              ) : null}
              <button
                className="text-button"
                onClick={() =>
                  dispatch({ type: "patch", value: { error: null } })
                }
              >
                Dismiss
              </button>
            </div>
          </section>
        )}
        <div className="live-status" role="status" aria-live="polite">
          {state.status}
        </div>
        {workspace && context ? (
          <>
            <div className="workspace-toolbar">
              <nav aria-label="Workspace views">
                {(["prepare", "review", "export"] as const).map(
                  (view, index) => (
                    <button
                      key={view}
                      className={state.view === view ? "active" : ""}
                      aria-current={state.view === view ? "page" : undefined}
                      onClick={() =>
                        dispatch({ type: "patch", value: { view } })
                      }
                    >
                      <span>0{index + 1}</span>
                      {view[0].toUpperCase() + view.slice(1)}
                    </button>
                  ),
                )}
              </nav>
              <label className="revision-choice">
                Request revision
                <select
                  aria-label="Request revision"
                  value={state.revisionId}
                  disabled={state.busy}
                  onChange={(event) =>
                    controller.selectRevision(event.target.value)
                  }
                >
                  {workspace.study.revisions.map((item, index) => (
                    <option key={item.revision_id} value={item.revision_id}>
                      r{index + 1} · {item.revision_id.slice(0, 8)}
                      {item.revision_id === workspace.study.active_revision_id
                        ? " · active"
                        : " · retained"}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <div className="context-strip">
              <span>
                <span className="context-dot" />
                {context.reference_id}
              </span>
              <span>{context.profile_id}</span>
              <span>{context.targets.length} accepted targets</span>
              {context.reference_id === "demo-reference-v1" && (
                <strong>Synthetic reference · example context</strong>
              )}
              {context.revision_id !== workspace.study.active_revision_id && (
                <strong>Historical request context</strong>
              )}
            </div>
            {state.importPreview?.kind === "request" && <ImportPreviewPanel />}
            {state.view === "prepare" ? (
              <PrepareView />
            ) : state.view === "review" ? (
              <ReviewView />
            ) : (
              <ExportView />
            )}
          </>
        ) : (
          <>
            <section className="welcome-grid">
              <div className="welcome-copy">
                <p className="eyebrow">Explicit inputs. Traceable review.</p>
                <h1>
                  Prepare the request.
                  <br />
                  Keep the reasoning.
                </h1>
                <p>
                  Create a study above or inspect the synthetic sample to
                  explore a complete local workflow.
                </p>
                <button
                  disabled={state.busy || !state.catalogue}
                  onClick={() => void controller.sample("request-valid.json")}
                >
                  Inspect sample request <span aria-hidden="true">↗</span>
                </button>
                <p className="hint">
                  Sample records are labelled synthetic. No genomic analysis has
                  been performed.
                </p>
              </div>
              <div className="welcome-steps">
                <article>
                  <span>01</span>
                  <div>
                    <h3>Prepare</h3>
                    <p>
                      Explicit intervals, reference identities and recoverable
                      drafts.
                    </p>
                  </div>
                </article>
                <article>
                  <span>02</span>
                  <div>
                    <h3>Review</h3>
                    <p>
                      Source-specific evidence and independent collection
                      decisions.
                    </p>
                  </div>
                </article>
                <article>
                  <span>03</span>
                  <div>
                    <h3>Export</h3>
                    <p>
                      Identified snapshots with source bytes and unresolved
                      work.
                    </p>
                  </div>
                </article>
              </div>
            </section>
            <ImportPreviewPanel />
            {state.studies.length > 0 && (
              <section className="panel">
                <div className="panel-heading">
                  <h2>Saved studies</h2>
                </div>
                {state.studies.map((item) => (
                  <button
                    className="saved-study-row"
                    key={item.study_id}
                    disabled={state.busy}
                    onClick={() =>
                      void controller.create({
                        source: "saved",
                        study_id: item.study_id,
                      })
                    }
                  >
                    <strong>{item.title}</strong>
                    <span>Saved v{item.saved_version}</span>
                    <span>Open →</span>
                  </button>
                ))}
              </section>
            )}
          </>
        )}
        <footer className="workspace-footer">
          <span>IRCOMP / Local study tools</span>
          <span>
            Editing and imported evidence review · scientific execution is
            external
          </span>
        </footer>
      </main>
    </div>
  );
}
