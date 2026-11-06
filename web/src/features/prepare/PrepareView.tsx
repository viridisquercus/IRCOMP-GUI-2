/**
 * @file PrepareView.tsx
 * @brief 01 / Prepare - targets of the request and their context
 * @author Lukas (Viridis) Dubsik
 * @version 0.1
 *
 * Detailed description:
 *  Layout: target list | target editor | context and problems, and under
 *  them the editor of the reference and profile.
 *  An older (retained) revision is shown read-only.
 */
import { useWorkspace } from "../../app/WorkspaceProvider";
import { draftProblems, isWholeNumber, revision } from "../../app/selectors";
import type { State } from "../../app/state";
import { MAX_LABEL } from "../../shared/constants";
import type {
  Diagnostic,
  Reference,
  Revision,
  Target,
  TargetDraft,
} from "../../shared/types";
import "./PrepareView.css";

/* Helper functions */
/**
 * @brief Get the text shown in the target editor
 *
 * The unapplied draft wins, otherwise the accepted values of the
 * selected target are shown.
 */
function editorDraft(state: State, selected: Target | undefined) {
  if (state.buffers.target) return state.buffers.target;
  if (!selected) return null;

  const draft: TargetDraft = {
    target_id: selected.target_id,
    label: state.workspace!.study.target_labels[selected.target_id],
    contig: selected.contig,
    start: String(selected.start),
    end: String(selected.end),
    strand: selected.strand,
  };
  return draft;
}

/**
 * @brief Name of a context editor field of a target
 */
function contextField(targetId: string, name: "contig" | "start" | "end") {
  return `context-${targetId}-${name}`;
}

/**
 * @brief Symbol shown in front of a check
 */
function checkSymbol(status: string): string {
  if (status === "passed") return "✓";
  if (status === "failed") return "!";
  return "—";
}

/* Target list */
function TargetList(props: { context: Revision; historical: boolean }) {
  const { state, controller } = useWorkspace();
  const { context, historical } = props;
  const labels = state.workspace!.study.target_labels;

  return (
    <aside className="panel target-panel">
      <div className="panel-heading">
        <h2>
          Targets <span className="count">{context.targets.length}</span>
        </h2>
        <button
          className="small secondary"
          disabled={historical || state.busy}
          onClick={() => controller.newTarget()}
        >
          + Add target
        </button>
      </div>
      {!context.targets.length && (
        <div className="empty compact">
          <span className="empty-symbol">⌖</span>
          <h3>No accepted targets</h3>
          <p>Add the first interval to start.</p>
        </div>
      )}
      <div className="target-list">
        {context.targets.map((target, index) => (
          <button
            className={`target-row ${state.targetId === target.target_id ? "selected" : ""}`}
            key={target.target_id}
            onClick={() => controller.selectTarget(target.target_id)}
          >
            <span className="target-number">
              {String(index + 1).padStart(2, "0")}
            </span>
            <span>
              <strong>{labels[target.target_id]}</strong>
              <small className="mono">{target.contig}</small>
              <small>
                {target.start.toLocaleString()}–{target.end.toLocaleString()} ·{" "}
                {target.strand === "." ? "strand unspecified" : target.strand}
              </small>
            </span>
          </button>
        ))}
      </div>
      <div className="panel-footer">
        <span className="badge neutral">0-based, end not included</span>
        <p>
          Labels are only for you, the request itself uses the accessions and
          coordinates.
        </p>
      </div>
    </aside>
  );
}

/* Target editor */
type EditorProps = {
  draft: TargetDraft;
  selected: Target | undefined;
  reference: Reference;
  historical: boolean;
  diagnostics: Diagnostic[];
  blocked: boolean; // Local checks found a problem, Apply is not allowed
};

function TargetForm(props: EditorProps) {
  const { state, dispatch, controller } = useWorkspace();
  const { draft, selected, reference, historical, diagnostics } = props;
  const labels = state.workspace!.study.target_labels;

  // Every key press changes the draft buffer only
  function update(name: keyof TargetDraft, value: string) {
    dispatch({
      type: "draft",
      buffers: { ...state.buffers, target: { ...draft, [name]: value } },
    });
  }

  function remove() {
    const label = labels[selected!.target_id];
    const question = `Remove ${label}? Evidence of the older revisions stays as it is. Undo works until you save.`;
    if (!window.confirm(question)) return;
    void controller.command({
      type: "remove_target",
      target_id: selected!.target_id,
    });
  }

  const knownContig = reference.contigs.some(
    (item) => item.accession === draft.contig,
  );
  const endInvalid = diagnostics.some((item) =>
    item.location?.endsWith("/end"),
  );

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        if (!historical)
          void controller.command({ type: "apply_target", draft });
      }}
    >
      <fieldset disabled={historical}>
        <label htmlFor="target-label">Target label</label>
        <input
          id="target-label"
          value={draft.label}
          onChange={(event) => update("label", event.target.value)}
          maxLength={MAX_LABEL}
          placeholder="e.g. exon 2"
        />
        <label htmlFor="target-contig">Contig accession</label>
        <select
          id="target-contig"
          value={draft.contig}
          onChange={(event) => update("contig", event.target.value)}
        >
          {/* Keep an unknown value visible, instead of silently changing it */}
          {!knownContig && (
            <option value={draft.contig}>
              {draft.contig || "Choose a contig"}
            </option>
          )}
          {reference.contigs.map((item) => (
            <option key={item.accession} value={item.accession}>
              {item.accession} · {item.label} · {item.length.toLocaleString()}{" "}
              bp
            </option>
          ))}
        </select>
        <div className="form-row">
          <div>
            <label htmlFor="target-start">Start (0-based)</label>
            <input
              id="target-start"
              inputMode="numeric"
              value={draft.start}
              onChange={(event) => update("start", event.target.value)}
              placeholder="e.g. 100"
              maxLength={MAX_LABEL}
            />
          </div>
          <div>
            <label htmlFor="target-end">End (exclusive)</label>
            <input
              id="target-end"
              aria-invalid={endInvalid}
              inputMode="numeric"
              value={draft.end}
              onChange={(event) => update("end", event.target.value)}
              placeholder="e.g. 200"
              maxLength={MAX_LABEL}
            />
          </div>
        </div>
        <p className="hint">
          Counting starts at 0 and End itself is not included, so 100 to 200
          means 100 bases.
        </p>
        <label htmlFor="target-strand">Strand</label>
        <select
          id="target-strand"
          value={draft.strand}
          onChange={(event) => update("strand", event.target.value)}
        >
          <option value=".">Unspecified</option>
          <option value="+">+ Forward</option>
          <option value="-">− Reverse</option>
        </select>
      </fieldset>
      {diagnostics
        .filter((item) => item.code === "INTERVAL_INVALID")
        .map((item, index) => (
          <p className="field-error" key={index}>
            {item.message}
          </p>
        ))}
      <div className="actions">
        <button
          type="submit"
          disabled={state.busy || historical || props.blocked}
        >
          Apply target
        </button>
        <button
          type="button"
          className="secondary"
          disabled={state.busy}
          onClick={() =>
            dispatch({
              type: "draft",
              buffers: { ...state.buffers, target: null },
            })
          }
        >
          Discard edits
        </button>
        {selected && !historical && (
          <button
            type="button"
            className="text-button danger"
            disabled={state.busy}
            onClick={remove}
          >
            Remove target
          </button>
        )}
      </div>
      <p className="hint">
        Apply changes the open study, Save study writes it to the disk.
      </p>
    </form>
  );
}

function TargetEditor(
  props: Omit<EditorProps, "draft"> & { draft: TargetDraft | null },
) {
  const { state, controller } = useWorkspace();
  const { draft } = props;

  // Heading depends on what is edited
  let heading = "Target details";
  if (draft) heading = draft.target_id ? "Edit target" : "Add a target";

  return (
    <section className="panel editor">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Inline editor</p>
          <h2>{heading}</h2>
        </div>
        {state.buffers.target && (
          <span className="badge amber">Unapplied draft</span>
        )}
      </div>
      {draft ? (
        <TargetForm {...props} draft={draft} />
      ) : (
        <div className="empty">
          <span className="empty-symbol">⌖</span>
          <h3>Choose or add a target</h3>
          <p>Pick a target on the left or add a new one.</p>
          <button
            className="secondary"
            disabled={props.historical || state.busy}
            onClick={() => controller.newTarget()}
          >
            Add target
          </button>
        </div>
      )}
    </section>
  );
}

/* Context column */
function ContextPanel(props: { context: Revision; reference: Reference }) {
  const { context, reference } = props;
  const synthetic = reference.category === "synthetic";
  return (
    <section className="panel">
      <div className="panel-heading">
        <h2>Request context</h2>
      </div>
      <span className={`badge ${synthetic ? "amber" : "teal"}`}>
        {synthetic ? "Synthetic reference" : "Reference metadata"}
      </span>
      <dl className="metadata">
        <div>
          <dt>Reference</dt>
          <dd>{context.reference_id}</dd>
        </div>
        <div>
          <dt>Declared profile</dt>
          <dd>{context.profile_id}</dd>
        </div>
        <div>
          <dt>Reference sequence</dt>
          <dd>Not checked</dd>
        </div>
        <div>
          <dt>Accepted targets</dt>
          <dd>{context.targets.length}</dd>
        </div>
      </dl>
      <p className="hint">
        Only the contig lengths are checked here. The sequence, PAMs and whether
        the target makes sense biologically aren't.
      </p>
    </section>
  );
}

function ProblemsPanel(props: {
  context: Revision;
  diagnostics: Diagnostic[];
}) {
  const { state, controller } = useWorkspace();
  const { context, diagnostics } = props;

  // Jump to the field the problem is about
  function focusProblem(item: Diagnostic) {
    // Location looks like /targets/<id>/<field> or /target/<field>
    const parts = item.location?.split("/");
    const name = parts?.at(-1);
    const targetId = parts?.[2];
    if (context.targets.some((target) => target.target_id === targetId))
      controller.selectTarget(targetId!);
    // Wait for the editor to render the selected target first
    setTimeout(() => document.getElementById(`target-${name}`)?.focus(), 0);
  }

  return (
    <section className="panel">
      <div className="panel-heading">
        <h2>Checks &amp; problems</h2>
      </div>
      {diagnostics.length ? (
        diagnostics.map((item, index) => (
          <button
            className="problem"
            key={index}
            onClick={() => focusProblem(item)}
          >
            {item.message}
            <small>{item.code}</small>
          </button>
        ))
      ) : (
        <p className="hint">
          No problems found. Check request shows what is (and isn't) checked.
        </p>
      )}
      {state.validation?.checks.map((check) => (
        <div className="check-line" key={check.name}>
          <span>{checkSymbol(check.status)}</span>
          <div>
            {check.name}
            <small>{check.status.replaceAll("_", " ")}</small>
          </div>
        </div>
      ))}
    </section>
  );
}

/* Reference and profile change */
function ContextEditor(props: { context: Revision }) {
  const { state, dispatch, controller } = useWorkspace();
  const { context } = props;
  const catalogue = state.catalogue!;
  const labels = state.workspace!.study.target_labels;

  // Chosen reference and the profiles available for it
  const referenceId = state.fields.reference ?? context.reference_id;
  const replacement = catalogue.references.find(
    (item) => item.reference_id === referenceId,
  )!;
  const profiles = catalogue.profiles.filter((item) =>
    item.reference_ids.includes(referenceId),
  );
  // If the chosen profile does not fit the reference, take the first one
  const profile = profiles.some(
    (item) => item.profile_id === state.fields.profile,
  )
    ? state.fields.profile
    : profiles[0].profile_id;

  function field(name: string, value: string) {
    dispatch({ type: "field", name, value });
  }

  // Value typed in the editor, or the accepted one if nothing was typed
  function value(target: Target, name: "contig" | "start" | "end") {
    return state.fields[contextField(target.target_id, name)] ?? target[name];
  }

  function changeContext() {
    // Every coordinate has to be a whole number, nothing is converted
    for (const target of context.targets) {
      for (const name of ["start", "end"] as const) {
        if (!isWholeNumber(String(value(target, name)))) {
          dispatch({
            type: "patch",
            value: {
              error: {
                code: "INTERVAL_INVALID",
                message: "Every target needs whole-number coordinates.",
                diagnostics: [],
              },
            },
          });
          return;
        }
      }
    }

    const targets = context.targets.map((target) => ({
      ...target,
      contig: String(value(target, "contig")),
      start: Number(value(target, "start")),
      end: Number(value(target, "end")),
    }));
    void controller.command({
      type: "set_context",
      reference_id: referenceId,
      profile_id: profile,
      targets,
    });
  }

  return (
    <details className="panel context-editor">
      <summary>Change reference or analysis profile</summary>
      <p className="hint">
        Changing these creates a new revision, the evidence you already have
        stays with the old one. Coordinates aren't converted between references,
        so enter them for the new one yourself.
      </p>
      <div className="form-row">
        <div>
          <label htmlFor="reference-choice">Supported reference</label>
          <select
            id="reference-choice"
            value={referenceId}
            onChange={(event) => field("reference", event.target.value)}
          >
            {catalogue.references.map((item) => (
              <option key={item.reference_id}>{item.reference_id}</option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="profile-choice">Analysis profile</label>
          <select
            id="profile-choice"
            value={profile}
            onChange={(event) => field("profile", event.target.value)}
          >
            {profiles.map((item) => (
              <option key={item.profile_id}>{item.profile_id}</option>
            ))}
          </select>
        </div>
      </div>
      {context.targets.map((target) => (
        <div className="context-target" key={target.target_id}>
          <strong>{labels[target.target_id]}</strong>
          <label>
            New contig
            <select
              value={value(target, "contig")}
              onChange={(event) =>
                field(
                  contextField(target.target_id, "contig"),
                  event.target.value,
                )
              }
            >
              {!replacement.contigs.some(
                (item) => item.accession === target.contig,
              ) && (
                <option value={target.contig}>
                  {target.contig} (not in this reference)
                </option>
              )}
              {replacement.contigs.map((item) => (
                <option key={item.accession}>{item.accession}</option>
              ))}
            </select>
          </label>
          <label>
            New start
            <input
              inputMode="numeric"
              value={value(target, "start")}
              onChange={(event) =>
                field(
                  contextField(target.target_id, "start"),
                  event.target.value,
                )
              }
            />
          </label>
          <label>
            New end (not included)
            <input
              inputMode="numeric"
              value={value(target, "end")}
              onChange={(event) =>
                field(contextField(target.target_id, "end"), event.target.value)
              }
            />
          </label>
        </div>
      ))}
      <button disabled={state.busy} onClick={changeContext}>
        Apply context change
      </button>
    </details>
  );
}

/* View */
export function PrepareView() {
  const { state, controller } = useWorkspace();
  const study = state.workspace!.study;
  const context = revision(state)!;
  const historical = context.revision_id !== study.active_revision_id;

  const selected = context.targets.find(
    (target) => target.target_id === state.targetId,
  );
  const draft = editorDraft(state, selected);
  const reference = state.catalogue!.references.find(
    (item) => item.reference_id === context.reference_id,
  )!;

  // All the problems: local ones first, then the ones from the service
  const localProblems = draftProblems(state, draft);
  const diagnostics = [
    ...localProblems,
    ...(state.validation?.draft_diagnostics ?? []),
    ...(state.validation?.diagnostics ?? state.workspace!.diagnostics),
    ...(state.error?.diagnostics ?? []),
  ];

  return (
    <>
      <div className="section-intro">
        <div>
          <p className="eyebrow">01 / Prepare</p>
          <h1>Prepare the request</h1>
          <p>Set the targets and the reference they are on.</p>
        </div>
        <button
          className="secondary"
          disabled={state.busy}
          onClick={() => void controller.validate()}
        >
          Check request
        </button>
      </div>
      {historical && (
        <p className="notice">
          This is an older revision, so it can't be edited. Its evidence and
          exports still use it. Choose the active revision to make changes.
        </p>
      )}
      <div className="prepare-grid">
        <TargetList context={context} historical={historical} />
        <TargetEditor
          draft={draft}
          selected={selected}
          reference={reference}
          historical={historical}
          diagnostics={diagnostics}
          blocked={localProblems.length > 0}
        />
        <aside className="context-column">
          <ContextPanel context={context} reference={reference} />
          <ProblemsPanel context={context} diagnostics={diagnostics} />
        </aside>
      </div>
      {!historical && <ContextEditor context={context} />}
    </>
  );
}
