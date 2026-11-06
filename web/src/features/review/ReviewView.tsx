/*************************************************************************
 * Name: Lukas (Viridis) Dubsik
 *************************************************************************/
import { useWorkspace } from "../../app/WorkspaceProvider";
import {
  candidates,
  collections,
  keyEqual,
  selectedCollection,
  unresolvedCount,
} from "../../app/selectors";
import { ImportPreviewPanel } from "../../shared/ImportPreview";
import type {
  CandidateKey,
  DecisionDraft,
  Disposition,
} from "../../shared/types";

export function ReviewView() {
  const { state, dispatch, controller } = useWorkspace();
  const records = candidates(state);
  const items = collections(state);
  const collection = selectedCollection(state);
  const record =
    records.find((item) => keyEqual(item.key, state.candidate)) ?? records[0];
  const member = collection?.memberships.find((item) =>
    keyEqual(item.candidate, record?.key ?? null),
  );
  // First try the unapplied text for this candidate, then its saved decision.
  let decision: DecisionDraft | null = null;
  const draft = state.buffers.decision;
  if (
    draft?.collection_id === collection?.collection_id &&
    keyEqual(draft?.candidate ?? null, record?.key ?? null)
  ) {
    decision = draft;
  } else if (member && collection) {
    decision = { ...member, collection_id: collection.collection_id };
  }
  const attached = state.workspace!.study.evidence.filter(
    (item) => item.bundle.context.revision_id === state.revisionId,
  );
  function update(change: Partial<DecisionDraft>) {
    if (decision)
      dispatch({
        type: "draft",
        buffers: { ...state.buffers, decision: { ...decision, ...change } },
      });
  }
  function select(candidate: CandidateKey | null, collectionId?: string) {
    if (
      state.buffers.decision &&
      !window.confirm(
        "Discard the unapplied decision draft? Cancel to stay and apply it first.",
      )
    )
      return;
    dispatch({ type: "draft", buffers: { ...state.buffers, decision: null } });
    dispatch({
      type: "patch",
      value: { candidate, ...(collectionId ? { collectionId } : {}) },
    });
  }
  return (
    <>
      <div className="section-intro">
        <div>
          <p className="eyebrow">02 / Review</p>
          <h1>Keep evidence and judgment distinct.</h1>
          <p>
            Inspect source-specific observations, then record a
            collection-specific decision.
          </p>
        </div>
        <label className={`file-button ${state.busy ? "disabled" : ""}`}>
          Import evidence
          <input
            aria-label="Import evidence file"
            type="file"
            accept=".json,application/json"
            disabled={state.busy}
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) void controller.importFile("evidence", file);
              event.target.value = "";
            }}
          />
        </label>
      </div>
      <ImportPreviewPanel />
      {!attached.length ? (
        <section className="panel empty">
          <span className="empty-symbol">≋</span>
          <h2>No evidence attached to this revision</h2>
          <p>
            Import a local <span className="mono">.evidence.json</span> file.
            The preview checks exact request, reference and revision context
            before attachment.
          </p>
          <p className="hint">
            Import means received, not executed or scientifically verified.
          </p>
          <button
            className="secondary"
            disabled={state.busy}
            onClick={() => void controller.sample("evidence-valid.json")}
          >
            Inspect synthetic example
          </button>
          <p className="hint">
            The shipped example matches the sample request only. Other contexts
            receive an honest mismatch.
          </p>
        </section>
      ) : (
        <>
          <div className="evidence-strip">
            <span className="badge neutral">
              {attached.length} source{" "}
              {attached.length === 1 ? "bundle" : "bundles"}
            </span>
            {attached.map((item) => (
              <span
                className={`badge ${item.bundle.category === "synthetic" ? "amber" : "teal"}`}
                key={item.bundle.bundle_id}
              >
                {item.bundle.category === "synthetic"
                  ? "Synthetic example"
                  : "Imported prediction"}{" "}
                · {item.bundle.source.name} {item.bundle.source.version}
              </span>
            ))}
          </div>
          <div className="review-grid">
            <aside className="panel">
              <div className="panel-heading">
                <h2>
                  Candidates <span className="count">{records.length}</span>
                </h2>
              </div>
              {!records.length && (
                <p className="hint">
                  The source supplied no candidate records. This does not
                  establish a negative scientific search result.
                </p>
              )}
              {records.map((item) => (
                <button
                  className={`candidate-row ${keyEqual(item.key, record?.key ?? null) ? "selected" : ""}`}
                  key={`${item.key.bundle_id}/${item.key.candidate_id}`}
                  onClick={() => select(item.key)}
                >
                  <strong>{item.candidate.label}</strong>
                  <small>
                    {
                      state.workspace!.study.target_labels[
                        item.candidate.target_id
                      ]
                    }
                  </small>
                  <small>
                    {collection?.memberships
                      .find((membership) =>
                        keyEqual(membership.candidate, item.key),
                      )
                      ?.disposition.replaceAll("_", " ") ?? "Not in collection"}
                  </small>
                </button>
              ))}
            </aside>
            <section className="panel evidence-detail">
              <div className="panel-heading">
                <div>
                  <p className="eyebrow">Immutable source evidence</p>
                  <h2>{record?.candidate.label ?? "No supplied candidates"}</h2>
                </div>
                {record && (
                  <span
                    className={`badge ${record.bundle.category === "synthetic" ? "amber" : "teal"}`}
                  >
                    {record.bundle.category === "synthetic"
                      ? "Synthetic"
                      : "Imported prediction"}
                  </span>
                )}
              </div>
              {record && (
                <>
                  <dl className="metadata horizontal">
                    <div>
                      <dt>Target</dt>
                      <dd>
                        {
                          state.workspace!.study.target_labels[
                            record.candidate.target_id
                          ]
                        }
                      </dd>
                    </div>
                    <div>
                      <dt>Source</dt>
                      <dd>
                        {record.bundle.source.name} ·{" "}
                        {record.bundle.source.version}
                      </dd>
                    </div>
                  </dl>
                  <div className="metric-list">
                    {record.candidate.metrics.map((metric, index) => (
                      <article className="metric" key={index}>
                        <div>
                          <h3>{metric.name}</h3>
                          <p>{metric.model ?? "Model not supplied"}</p>
                        </div>
                        <strong
                          className={
                            metric.availability === "present"
                              ? "metric-value"
                              : "metric-missing"
                          }
                        >
                          {metric.availability === "present"
                            ? metric.value
                            : metric.availability.replaceAll("_", " ")}
                        </strong>
                        <small>
                          {metric.scale ?? "Scale not supplied"} ·{" "}
                          {metric.direction
                            ? metric.direction.replaceAll("_", " ")
                            : "Direction not supplied"}
                          {metric.unit ? ` · ${metric.unit}` : ""}
                        </small>
                      </article>
                    ))}
                  </div>
                  {!record.candidate.metrics.length && (
                    <p className="notice">
                      No metrics were supplied for this record.
                    </p>
                  )}
                  <p className="hint">
                    Zero is a supplied value. Missing, unsupported, failed and
                    unknown remain distinct. Scores are not combined into a
                    universal confidence.
                  </p>
                  <details>
                    <summary>Inspect original record &amp; provenance</summary>
                    <pre>
                      {JSON.stringify(record.candidate.raw_record, null, 2)}
                    </pre>
                    <dl className="metadata">
                      <div>
                        <dt>Bundle ID</dt>
                        <dd className="mono">{record.bundle.bundle_id}</dd>
                      </div>
                      <div>
                        <dt>Request revision</dt>
                        <dd className="mono">
                          {record.bundle.context.revision_id}
                        </dd>
                      </div>
                      <div>
                        <dt>Reference</dt>
                        <dd>{record.bundle.context.reference_id}</dd>
                      </div>
                      <div>
                        <dt>Source location</dt>
                        <dd>{record.bundle.source.uri ?? "Not supplied"}</dd>
                      </div>
                    </dl>
                    {record.bundle.dependencies.map((dependency, index) => (
                      <p key={index} className="hint">
                        External: {dependency.uri} — {dependency.description}
                      </p>
                    ))}
                  </details>
                </>
              )}
            </section>
            <aside className="panel decision-panel">
              <div className="panel-heading">
                <div>
                  <p className="eyebrow">Editable review layer</p>
                  <h2>Collection &amp; decision</h2>
                </div>
              </div>
              <label htmlFor="collection-select">Review collection</label>
              <select
                id="collection-select"
                value={collection?.collection_id ?? ""}
                onChange={(event) =>
                  select(record?.key ?? null, event.target.value)
                }
              >
                {!items.length && <option value="">No collections</option>}
                {items.map((item) => (
                  <option key={item.collection_id} value={item.collection_id}>
                    {item.name}
                  </option>
                ))}
              </select>
              {collection && (
                <p className="hint">
                  {collection.memberships.length} members ·{" "}
                  {unresolvedCount([collection])} unresolved
                </p>
              )}
              <details className="manage-collections">
                <summary>Manage collections</summary>
                <label htmlFor="collection-name">Collection name</label>
                <input
                  id="collection-name"
                  value={state.fields.collectionName ?? ""}
                  onChange={(event) =>
                    dispatch({
                      type: "field",
                      name: "collectionName",
                      value: event.target.value,
                    })
                  }
                  maxLength={200}
                  placeholder="A named review selection"
                />
                <div className="actions wrap">
                  <button
                    className="small secondary"
                    disabled={
                      state.busy || !state.fields.collectionName?.trim()
                    }
                    onClick={() =>
                      void controller.command({
                        type: "create_collection",
                        revision_id: state.revisionId,
                        name: state.fields.collectionName,
                      })
                    }
                  >
                    Create collection
                  </button>
                  {collection && (
                    <>
                      <button
                        className="small secondary"
                        disabled={
                          state.busy || !state.fields.collectionName?.trim()
                        }
                        onClick={() =>
                          void controller.command({
                            type: "rename_collection",
                            collection_id: collection.collection_id,
                            name: state.fields.collectionName,
                          })
                        }
                      >
                        Rename collection
                      </button>
                      <button
                        className="text-button danger"
                        disabled={state.busy}
                        onClick={() => {
                          if (
                            window.confirm(
                              `Remove ${collection.name} and its ${collection.memberships.length} membership decisions? Source evidence remains. Undo is available before Save.`,
                            )
                          )
                            void controller.command({
                              type: "remove_collection",
                              collection_id: collection.collection_id,
                            });
                        }}
                      >
                        Remove collection
                      </button>
                    </>
                  )}
                </div>
              </details>
              {record &&
                collection &&
                (member && decision ? (
                  <form
                    onSubmit={(event) => {
                      event.preventDefault();
                      void controller.command({
                        type: "set_decision",
                        ...decision,
                      });
                    }}
                  >
                    <hr />
                    <label htmlFor="disposition">Disposition</label>
                    <select
                      id="disposition"
                      value={decision.disposition}
                      onChange={(event) =>
                        update({
                          disposition: event.target.value as Disposition,
                        })
                      }
                    >
                      <option value="undecided">Undecided</option>
                      <option value="include_for_review">
                        Include for further review
                      </option>
                      <option value="exclude">Exclude</option>
                      <option value="needs_clarification">
                        Needs clarification
                      </option>
                    </select>
                    <label htmlFor="rationale">Rationale</label>
                    <textarea
                      id="rationale"
                      rows={5}
                      value={decision.rationale}
                      onChange={(event) =>
                        update({ rationale: event.target.value })
                      }
                      maxLength={4000}
                      placeholder="What supports this decision? What remains uncertain?"
                    />
                    {decision.disposition !== "undecided" &&
                      !decision.rationale.trim() && (
                        <p className="field-error">
                          A blank rationale keeps this decision incomplete.
                        </p>
                      )}
                    <details>
                      <summary>Supporting evidence references</summary>
                      {records.map((item) => (
                        <label
                          className="checkbox"
                          key={`${item.key.bundle_id}/${item.key.candidate_id}`}
                        >
                          <input
                            type="checkbox"
                            checked={decision.evidence_refs.some((key) =>
                              keyEqual(key, item.key),
                            )}
                            onChange={(event) =>
                              update({
                                evidence_refs: event.target.checked
                                  ? [...decision.evidence_refs, item.key]
                                  : decision.evidence_refs.filter(
                                      (key) => !keyEqual(key, item.key),
                                    ),
                              })
                            }
                          />
                          {item.candidate.label} · {item.bundle.source.name}
                        </label>
                      ))}
                    </details>
                    <div className="actions wrap">
                      <button disabled={state.busy}>Apply decision</button>
                      <button
                        type="button"
                        className="secondary"
                        onClick={() =>
                          dispatch({
                            type: "draft",
                            buffers: { ...state.buffers, decision: null },
                          })
                        }
                      >
                        Discard edits
                      </button>
                      <button
                        type="button"
                        className="text-button danger"
                        disabled={state.busy}
                        onClick={() => {
                          if (
                            window.confirm(
                              `Remove ${record.candidate.label} from ${collection.name}? Its source evidence remains.`,
                            )
                          )
                            void controller.command({
                              type: "remove_member",
                              collection_id: collection.collection_id,
                              candidate: record.key,
                            });
                        }}
                      >
                        Remove from collection
                      </button>
                    </div>
                    <p className="hint">
                      This disposition applies only to this collection. It is
                      not scientific approval or permission to execute.
                    </p>
                  </form>
                ) : (
                  <div className="empty compact">
                    <p>
                      This candidate is not a member of the selected collection.
                    </p>
                    <button
                      disabled={state.busy}
                      onClick={() =>
                        void controller.command({
                          type: "add_member",
                          collection_id: collection.collection_id,
                          candidate: record.key,
                        })
                      }
                    >
                      Add to collection
                    </button>
                  </div>
                ))}
            </aside>
          </div>
        </>
      )}
    </>
  );
}
