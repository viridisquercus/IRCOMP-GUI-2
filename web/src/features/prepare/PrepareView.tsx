/*************************************************************************
 * Name: Lukas (Viridis) Dubsik
 *************************************************************************/
import { useWorkspace } from "../../app/WorkspaceProvider";
import { draftProblems, revision } from "../../app/selectors";
import type { TargetDraft } from "../../shared/types";

export function PrepareView() {
  const { state, dispatch, controller } = useWorkspace();
  const study = state.workspace!.study;
  const context = revision(state)!;
  const historical = context.revision_id !== study.active_revision_id;
  const selected = context.targets.find(
    (target) => target.target_id === state.targetId,
  );
  const draft: TargetDraft | null =
    state.buffers.target ??
    (selected
      ? {
          target_id: selected.target_id,
          label: study.target_labels[selected.target_id],
          contig: selected.contig,
          start: String(selected.start),
          end: String(selected.end),
          strand: selected.strand,
        }
      : null);
  const reference = state.catalogue!.references.find(
    (item) => item.reference_id === context.reference_id,
  )!;
  const contextReference = state.fields.reference ?? context.reference_id;
  const replacement = state.catalogue!.references.find(
    (item) => item.reference_id === contextReference,
  )!;
  const profiles = state.catalogue!.profiles.filter((item) =>
    item.reference_ids.includes(contextReference),
  );
  const profile = profiles.some(
    (item) => item.profile_id === state.fields.profile,
  )
    ? state.fields.profile
    : profiles[0].profile_id;
  const localProblems = draftProblems(state, draft);
  const diagnostics = [
    ...localProblems,
    ...(state.validation?.draft_diagnostics ?? []),
    ...(state.validation?.diagnostics ?? state.workspace!.diagnostics),
    ...(state.error?.diagnostics ?? []),
  ];
  function update(name: keyof TargetDraft, value: string) {
    if (draft)
      dispatch({
        type: "draft",
        buffers: { ...state.buffers, target: { ...draft, [name]: value } },
      });
  }
  function field(name: string, value: string) {
    dispatch({ type: "field", name, value });
  }
  function changeContext() {
    const targets = context.targets.map((target) => ({
      ...target,
      contig:
        state.fields[`context-${target.target_id}-contig`] ?? target.contig,
      start: Number(
        state.fields[`context-${target.target_id}-start`] ?? target.start,
      ),
      end: Number(
        state.fields[`context-${target.target_id}-end`] ?? target.end,
      ),
    }));
    for (const target of context.targets)
      for (const key of ["start", "end"] as const) {
        const raw =
          state.fields[`context-${target.target_id}-${key}`] ??
          String(target[key]);
        if (!/^[0-9]+$/.test(raw) || !Number.isSafeInteger(Number(raw))) {
          dispatch({
            type: "patch",
            value: {
              error: {
                code: "INTERVAL_INVALID",
                message:
                  "Enter explicit whole-number coordinates for every replacement target.",
                diagnostics: [],
              },
            },
          });
          return;
        }
      }
    void controller.command({
      type: "set_context",
      reference_id: contextReference,
      profile_id: profile,
      targets,
    });
  }
  return (
    <>
      <div className="section-intro">
        <div>
          <p className="eyebrow">01 / Prepare</p>
          <h1>Prepare the request</h1>
          <p>
            Define targets and their reference context. Check what can be
            checked locally.
          </p>
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
          Viewing a retained revision. Its intervals are read-only; review and
          export keep this exact context. Select the active revision to edit.
        </p>
      )}
      <div className="prepare-grid">
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
              <p>Add an explicit interval to start preparing the request.</p>
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
                  <strong>{study.target_labels[target.target_id]}</strong>
                  <small className="mono">{target.contig}</small>
                  <small>
                    {target.start.toLocaleString()}–
                    {target.end.toLocaleString()} ·{" "}
                    {target.strand === "."
                      ? "strand unspecified"
                      : target.strand}
                  </small>
                </span>
              </button>
            ))}
          </div>
          <div className="panel-footer">
            <span className="badge neutral">0-based · end-exclusive</span>
            <p>
              Labels help navigation. Accessions and revision IDs establish
              context.
            </p>
          </div>
        </aside>
        <section className="panel editor">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">Inline editor</p>
              <h2>
                {draft
                  ? draft.target_id
                    ? "Edit target"
                    : "Add a target"
                  : "Target details"}
              </h2>
            </div>
            {state.buffers.target && (
              <span className="badge amber">Unapplied draft</span>
            )}
          </div>
          {draft ? (
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
                  maxLength={200}
                  placeholder="A short, recognizable label"
                />
                <label htmlFor="target-contig">Contig accession</label>
                <select
                  id="target-contig"
                  value={draft.contig}
                  onChange={(event) => update("contig", event.target.value)}
                >
                  {!reference.contigs.some(
                    (item) => item.accession === draft.contig,
                  ) && (
                    <option value={draft.contig}>
                      {draft.contig || "Choose a contig"}
                    </option>
                  )}
                  {reference.contigs.map((item) => (
                    <option key={item.accession} value={item.accession}>
                      {item.accession} · {item.label} ·{" "}
                      {item.length.toLocaleString()} bp
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
                      maxLength={200}
                    />
                  </div>
                  <div>
                    <label htmlFor="target-end">End (exclusive)</label>
                    <input
                      id="target-end"
                      aria-invalid={diagnostics.some((item) =>
                        item.location?.endsWith("/end"),
                      )}
                      inputMode="numeric"
                      value={draft.end}
                      onChange={(event) => update("end", event.target.value)}
                      placeholder="e.g. 200"
                      maxLength={200}
                    />
                  </div>
                </div>
                <p className="hint">
                  The first base is 0; End is outside the interval. Start must
                  be smaller than End.
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
                  disabled={
                    state.busy || historical || localProblems.length > 0
                  }
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
                    onClick={() => {
                      if (
                        window.confirm(
                          `Remove ${study.target_labels[selected.target_id]} from the active request? Older evidence remains attached to its original revision. You can undo before Save.`,
                        )
                      )
                        void controller.command({
                          type: "remove_target",
                          target_id: selected.target_id,
                        });
                    }}
                  >
                    Remove target
                  </button>
                )}
              </div>
              <p className="hint">
                Apply changes the working model. Save study writes it to local
                storage.
              </p>
            </form>
          ) : (
            <div className="empty">
              <span className="empty-symbol">⌖</span>
              <h3>Choose or add a target</h3>
              <p>
                Accepted intervals remain separate from unfinished editor text.
              </p>
              <button
                className="secondary"
                disabled={historical || state.busy}
                onClick={() => controller.newTarget()}
              >
                Add target
              </button>
            </div>
          )}
        </section>
        <aside className="context-column">
          <section className="panel">
            <div className="panel-heading">
              <h2>Request context</h2>
            </div>
            <span
              className={`badge ${reference.category === "synthetic" ? "amber" : "teal"}`}
            >
              {reference.category === "synthetic"
                ? "Synthetic reference"
                : "Reference metadata"}
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
              Catalogue bounds are checked. Sequence availability, PAMs and
              biological suitability are not.
            </p>
          </section>
          <section className="panel">
            <div className="panel-heading">
              <h2>Checks &amp; problems</h2>
            </div>
            {diagnostics.length ? (
              diagnostics.map((item, index) => (
                <button
                  className="problem"
                  key={index}
                  onClick={() => {
                    const name = item.location?.split("/").at(-1);
                    const targetId = item.location?.split("/")[2];
                    if (
                      context.targets.some(
                        (item) => item.target_id === targetId,
                      )
                    )
                      controller.selectTarget(targetId!);
                    setTimeout(
                      () => document.getElementById(`target-${name}`)?.focus(),
                      0,
                    );
                  }}
                >
                  {item.message}
                  <small>{item.code}</small>
                </button>
              ))
            ) : (
              <p className="hint">
                No blocking issues in accepted values. Run checks to inspect the
                local validation scope.
              </p>
            )}
            {state.validation?.checks.map((check) => (
              <div className="check-line" key={check.name}>
                <span>
                  {check.status === "passed"
                    ? "✓"
                    : check.status === "failed"
                      ? "!"
                      : "—"}
                </span>
                <div>
                  {check.name}
                  <small>{check.status.replaceAll("_", " ")}</small>
                </div>
              </div>
            ))}
          </section>
        </aside>
      </div>
      {!historical && (
        <details className="panel context-editor">
          <summary>Change reference or analysis profile</summary>
          <p className="hint">
            A change creates a new request revision. Existing evidence stays
            with its old context. Enter accession-qualified intervals
            explicitly; no coordinate conversion is performed.
          </p>
          <div className="form-row">
            <div>
              <label htmlFor="reference-choice">Supported reference</label>
              <select
                id="reference-choice"
                value={contextReference}
                onChange={(event) => field("reference", event.target.value)}
              >
                {state.catalogue!.references.map((item) => (
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
              <strong>{study.target_labels[target.target_id]}</strong>
              <label>
                Replacement contig
                <select
                  value={
                    state.fields[`context-${target.target_id}-contig`] ??
                    target.contig
                  }
                  onChange={(event) =>
                    field(
                      `context-${target.target_id}-contig`,
                      event.target.value,
                    )
                  }
                >
                  {!replacement.contigs.some(
                    (item) => item.accession === target.contig,
                  ) && (
                    <option value={target.contig}>
                      {target.contig} — choose compatible accession
                    </option>
                  )}
                  {replacement.contigs.map((item) => (
                    <option key={item.accession}>{item.accession}</option>
                  ))}
                </select>
              </label>
              <label>
                Replacement start
                <input
                  inputMode="numeric"
                  value={
                    state.fields[`context-${target.target_id}-start`] ??
                    target.start
                  }
                  onChange={(event) =>
                    field(
                      `context-${target.target_id}-start`,
                      event.target.value,
                    )
                  }
                />
              </label>
              <label>
                Replacement end (exclusive)
                <input
                  inputMode="numeric"
                  value={
                    state.fields[`context-${target.target_id}-end`] ??
                    target.end
                  }
                  onChange={(event) =>
                    field(`context-${target.target_id}-end`, event.target.value)
                  }
                />
              </label>
            </div>
          ))}
          <button disabled={state.busy} onClick={changeContext}>
            Apply context change
          </button>
        </details>
      )}
    </>
  );
}
