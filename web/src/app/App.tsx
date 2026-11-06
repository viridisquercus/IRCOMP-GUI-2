/**
 * @file App.tsx
 * @brief Frame of the application - header, study controls and the views
 * @author Lukas (Viridis) Dubsik
 * @date 6-11-2026
 * @version 0.1
 *
 * Detailed description:
 *  Without an open study the welcome page is shown. With one, the toolbar
 *  switches between Prepare, Review and Export and chooses the revision.
 */
import { useWorkspace } from "./WorkspaceProvider";
import { dirty, revision } from "./selectors";
import type { View } from "./state";
import { PrepareView } from "../features/prepare/PrepareView";
import { ReviewView } from "../features/review/ReviewView";
import { ExportView } from "../features/export/ExportView";
import { ImportPreviewPanel } from "../shared/ImportPreview";
import { DEMO_REFERENCE, MAX_LABEL } from "../shared/constants";
import "./App.css";

/* Values */
const VIEWS: View[] = ["prepare", "review", "export"];
const DUPLICATE_QUESTION =
  "Copy the active request into a new study? Only the targets are copied, not the evidence, decisions or unapplied edits.";

/* Study controls */
/**
 * @brief Form for a new study title
 */
function NewStudyForm() {
  const { state, dispatch, controller } = useWorkspace();
  const title = state.fields.newTitle;
  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        void controller.create({ source: "new", title });
      }}
    >
      <label htmlFor="new-study-title">New study title</label>
      <input
        id="new-study-title"
        value={title ?? ""}
        onChange={(event) =>
          dispatch({
            type: "field",
            name: "newTitle",
            value: event.target.value,
          })
        }
        maxLength={MAX_LABEL}
        placeholder="e.g. BRCA1 exon screen"
      />
      <button className="secondary" disabled={state.busy || !title?.trim()}>
        Create study
      </button>
    </form>
  );
}

/**
 * @brief Selector of the saved studies
 */
function OpenStudyForm() {
  const { state, dispatch, controller } = useWorkspace();
  const studyId = state.fields.savedStudy;
  return (
    <div>
      <label htmlFor="saved-study">Open saved study</label>
      <select
        id="saved-study"
        value={studyId ?? ""}
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
        disabled={state.busy || !studyId}
        onClick={() =>
          void controller.create({ source: "saved", study_id: studyId })
        }
      >
        Open saved study
      </button>
    </div>
  );
}

/**
 * @brief Rename and duplicate of the open study
 */
function CurrentStudyForm() {
  const { state, dispatch, controller } = useWorkspace();
  const workspace = state.workspace!;
  // Until the user types, show the current title
  const title = state.fields.studyTitle ?? workspace.study.title;

  function duplicate() {
    if (!window.confirm(DUPLICATE_QUESTION)) return;
    void controller.create({
      source: "duplicate",
      workspace_id: workspace.workspace_id,
      title: `${workspace.study.title.slice(0, 180)} (copy)`,
    });
  }

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        void controller.command({ type: "rename_study", title });
      }}
    >
      <label htmlFor="study-title">Current study title</label>
      <input
        id="study-title"
        value={title}
        maxLength={MAX_LABEL}
        onChange={(event) =>
          dispatch({
            type: "field",
            name: "studyTitle",
            value: event.target.value,
          })
        }
      />
      <div className="actions wrap">
        <button className="secondary" disabled={state.busy || !title.trim()}>
          Rename study
        </button>
        <button
          type="button"
          className="secondary"
          disabled={state.busy}
          onClick={duplicate}
        >
          Duplicate request
        </button>
      </div>
    </form>
  );
}

/**
 * @brief Collapsible panel with New / Open / Rename / Duplicate / Import
 */
function StudyControls() {
  const { state, controller } = useWorkspace();
  return (
    <details className="study-controls panel">
      <summary>New / Open / Rename / Duplicate</summary>
      <div className="study-controls-grid">
        <NewStudyForm />
        <OpenStudyForm />
        {state.workspace && <CurrentStudyForm />}
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
                // Clear it, so the same file can be chosen again
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

/* Header parts */
/**
 * @brief Top bar with the logo
 */
function AppHeader() {
  return (
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
        <span className="badge neutral">v0.1</span>
      </div>
    </header>
  );
}

/**
 * @brief Save state, Undo and Save study
 */
function SaveControls() {
  const { state, controller } = useWorkspace();
  const workspace = state.workspace!;
  const unsaved = dirty(state);

  // Text of the save state, the first matching one wins
  let status = `✓ Saved · v${workspace.base_saved_version}`;
  if (state.busy) status = "Working…";
  else if (state.error?.code === "PERSISTENCE_UNAVAILABLE")
    status = "Save failed";
  else if (unsaved) status = "● Unsaved changes";

  return (
    <div className="save-controls">
      <span className={`save-status ${unsaved ? "unsaved" : ""}`} role="status">
        {status}
      </span>
      <button
        className="secondary"
        disabled={state.busy || !workspace.can_undo}
        onClick={() => void controller.undo()}
      >
        Undo
      </button>
      <button disabled={state.busy} onClick={() => void controller.save()}>
        Save study
      </button>
    </div>
  );
}

/**
 * @brief Banner with the last error and the ways to recover from it
 */
function ErrorBanner() {
  const { state, dispatch, controller } = useWorkspace();
  if (!state.error) return null;
  return (
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
        {state.workspace?.base_saved_version ? (
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
          onClick={() => dispatch({ type: "patch", value: { error: null } })}
        >
          Dismiss
        </button>
      </div>
    </section>
  );
}

/* Open study */
/**
 * @brief View tabs and the revision selector
 */
function WorkspaceToolbar() {
  const { state, dispatch, controller } = useWorkspace();
  const study = state.workspace!.study;
  return (
    <div className="workspace-toolbar">
      <nav aria-label="Workspace views">
        {VIEWS.map((view, index) => (
          <button
            key={view}
            className={state.view === view ? "active" : ""}
            aria-current={state.view === view ? "page" : undefined}
            onClick={() => dispatch({ type: "patch", value: { view } })}
          >
            <span>0{index + 1}</span>
            {view[0].toUpperCase() + view.slice(1)}
          </button>
        ))}
      </nav>
      <label className="revision-choice">
        Request revision
        <select
          aria-label="Request revision"
          value={state.revisionId}
          disabled={state.busy}
          onChange={(event) => controller.selectRevision(event.target.value)}
        >
          {study.revisions.map((item, index) => (
            <option key={item.revision_id} value={item.revision_id}>
              r{index + 1} · {item.revision_id.slice(0, 8)}
              {item.revision_id === study.active_revision_id
                ? " · active"
                : " · retained"}
            </option>
          ))}
        </select>
      </label>
    </div>
  );
}

/**
 * @brief Line describing the context of the shown revision
 */
function ContextStrip() {
  const { state } = useWorkspace();
  const study = state.workspace!.study;
  const context = revision(state)!;
  return (
    <div className="context-strip">
      <span>
        <span className="context-dot" />
        {context.reference_id}
      </span>
      <span>{context.profile_id}</span>
      <span>{context.targets.length} accepted targets</span>
      {context.reference_id === DEMO_REFERENCE && (
        <strong>Synthetic reference · example context</strong>
      )}
      {context.revision_id !== study.active_revision_id && (
        <strong>Historical request context</strong>
      )}
    </div>
  );
}

/**
 * @brief Content shown while a study is open
 */
function OpenStudy() {
  const { state } = useWorkspace();
  let view = <ExportView />;
  if (state.view === "prepare") view = <PrepareView />;
  else if (state.view === "review") view = <ReviewView />;

  return (
    <>
      <WorkspaceToolbar />
      <ContextStrip />
      {state.importPreview?.kind === "request" && <ImportPreviewPanel />}
      {view}
    </>
  );
}

/* Welcome page */
/**
 * @brief Short description of one of the three steps
 */
function WelcomeStep(props: { number: string; title: string; text: string }) {
  return (
    <article>
      <span>{props.number}</span>
      <div>
        <h3>{props.title}</h3>
        <p>{props.text}</p>
      </div>
    </article>
  );
}

/**
 * @brief List of the saved studies as buttons
 */
function SavedStudies() {
  const { state, controller } = useWorkspace();
  if (state.studies.length === 0) return null;
  return (
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
            void controller.create({ source: "saved", study_id: item.study_id })
          }
        >
          <strong>{item.title}</strong>
          <span>Saved v{item.saved_version}</span>
          <span>Open</span>
        </button>
      ))}
    </section>
  );
}

/**
 * @brief Page shown when no study is open
 */
function Welcome() {
  const { state, controller } = useWorkspace();
  return (
    <>
      <section className="welcome-grid">
        <div className="welcome-copy">
          <p className="eyebrow">Getting started</p>
          <h1>
            Prepare a request,
            <br />
            then review what comes back
          </h1>
          <p>
            Create a new study above, or open the sample request to try the
            whole workflow.
          </p>
          <button
            disabled={state.busy || !state.catalogue}
            onClick={() => void controller.sample("request-valid.json")}
          >
            Open sample request
          </button>
          <p className="hint">
            The sample data are made up, nothing in them was actually computed.
          </p>
        </div>
        <div className="welcome-steps">
          <WelcomeStep
            number="01"
            title="Prepare"
            text="Choose the reference and set the target intervals."
          />
          <WelcomeStep
            number="02"
            title="Review"
            text="Import the evidence and decide about each candidate."
          />
          <WelcomeStep
            number="03"
            title="Export"
            text="Download the request or the review as a JSON file."
          />
        </div>
      </section>
      <ImportPreviewPanel />
      <SavedStudies />
    </>
  );
}

/* Application */
export function App() {
  const { state } = useWorkspace();
  const workspace = state.workspace;
  const isOpen = workspace && revision(state);

  return (
    <div className="application">
      <a className="skip-link" href="#main-content">
        Skip to workspace
      </a>
      <AppHeader />
      <main id="main-content">
        <div className="workspace-heading">
          <div>
            <p className="eyebrow">Request preparation / evidence review</p>
            <h2>{workspace?.study.title ?? "No study open"}</h2>
          </div>
          {workspace && <SaveControls />}
        </div>
        <StudyControls />
        <ErrorBanner />
        <div className="live-status" role="status" aria-live="polite">
          {state.status}
        </div>
        {isOpen ? <OpenStudy /> : <Welcome />}
        <footer className="workspace-footer">
          <span>IRCOMP / Local study tools</span>
          <span>
            Nothing is computed here, the analysis itself runs in IRCOMP
          </span>
        </footer>
      </main>
    </div>
  );
}
