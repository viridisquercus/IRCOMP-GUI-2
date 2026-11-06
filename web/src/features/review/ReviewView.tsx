/**
 * @file ReviewView.tsx
 * @brief 02 / Review - imported evidence and the decisions about it
 * @author Lukas (Viridis) Dubsik
 * @version 0.1
 *
 * Detailed description:
 *  Layout: candidate list | evidence of the candidate | collection and
 *  decision. The evidence is read-only, only the decisions are edited.
 */
import { useWorkspace } from "../../app/WorkspaceProvider";
import {
  candidates,
  collections,
  keyEqual,
  selectedCollection,
  unresolvedCount,
  type CandidateRecord,
} from "../../app/selectors";
import type { State } from "../../app/state";
import { MAX_LABEL, MAX_RATIONALE } from "../../shared/constants";
import { ImportPreviewPanel } from "../../shared/ImportPreview";
import type {
  Bundle,
  CandidateKey,
  Collection,
  DecisionDraft,
  Disposition,
  Membership,
  Metric,
} from "../../shared/types";
import "./ReviewView.css";

/* Helper functions */
/**
 * @brief Turn snake_case values into readable text
 */
function readable(value: string): string {
  return value.replaceAll("_", " ");
}

/**
 * @brief Unique React key of a candidate
 */
function recordKey(key: CandidateKey): string {
  return `${key.bundle_id}/${key.candidate_id}`;
}

/**
 * @brief Badge colour of a bundle category
 */
function categoryBadge(bundle: Bundle): string {
  return `badge ${bundle.category === "synthetic" ? "amber" : "teal"}`;
}

/**
 * @brief Get the decision shown in the editor
 *
 * The unapplied text for this candidate wins, then the accepted decision.
 */
function shownDecision(
  state: State,
  collection: Collection | undefined,
  record: CandidateRecord | undefined,
  member: Membership | undefined,
): DecisionDraft | null {
  const draft = state.buffers.decision;
  if (
    draft?.collection_id === collection?.collection_id &&
    keyEqual(draft?.candidate ?? null, record?.key ?? null)
  ) {
    return draft;
  }
  if (member && collection)
    return { ...member, collection_id: collection.collection_id };
  return null;
}

/* Evidence */
function EvidenceStrip(props: { bundles: Bundle[] }) {
  const count = props.bundles.length;
  return (
    <div className="evidence-strip">
      <span className="badge neutral">
        {count} source {count === 1 ? "bundle" : "bundles"}
      </span>
      {props.bundles.map((bundle) => (
        <span className={categoryBadge(bundle)} key={bundle.bundle_id}>
          {bundle.category === "synthetic"
            ? "Synthetic example"
            : "Imported prediction"}{" "}
          · {bundle.source.name} {bundle.source.version}
        </span>
      ))}
    </div>
  );
}

function CandidateList(props: {
  records: CandidateRecord[];
  record: CandidateRecord | undefined;
  collection: Collection | undefined;
  select: (candidate: CandidateKey | null) => void;
}) {
  const { state } = useWorkspace();
  const { records, record, collection } = props;
  const labels = state.workspace!.study.target_labels;

  // Disposition of the candidate in the selected collection
  function disposition(key: CandidateKey): string {
    const member = collection?.memberships.find((item) =>
      keyEqual(item.candidate, key),
    );
    return member ? readable(member.disposition) : "Not in collection";
  }

  return (
    <aside className="panel">
      <div className="panel-heading">
        <h2>
          Candidates <span className="count">{records.length}</span>
        </h2>
      </div>
      {!records.length && (
        <p className="hint">
          The file has no candidates. That doesn't mean there aren't any, only
          that none were sent.
        </p>
      )}
      {records.map((item) => (
        <button
          className={`candidate-row ${keyEqual(item.key, record?.key ?? null) ? "selected" : ""}`}
          key={recordKey(item.key)}
          onClick={() => props.select(item.key)}
        >
          <strong>{item.candidate.label}</strong>
          <small>{labels[item.candidate.target_id]}</small>
          <small>{disposition(item.key)}</small>
        </button>
      ))}
    </aside>
  );
}

function MetricCard(props: { metric: Metric }) {
  const { metric } = props;
  const present = metric.availability === "present";
  return (
    <article className="metric">
      <div>
        <h3>{metric.name}</h3>
        <p>{metric.model ?? "Model not supplied"}</p>
      </div>
      {/* A missing value says why it is missing, zero stays zero */}
      <strong className={present ? "metric-value" : "metric-missing"}>
        {present ? metric.value : readable(metric.availability)}
      </strong>
      <small>
        {metric.scale ?? "Scale not supplied"} ·{" "}
        {metric.direction
          ? readable(metric.direction)
          : "Direction not supplied"}
        {metric.unit ? ` · ${metric.unit}` : ""}
      </small>
    </article>
  );
}

function EvidenceDetail(props: { record: CandidateRecord | undefined }) {
  const { state } = useWorkspace();
  const { record } = props;
  const labels = state.workspace!.study.target_labels;

  return (
    <section className="panel evidence-detail">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Imported evidence (read-only)</p>
          <h2>{record?.candidate.label ?? "No supplied candidates"}</h2>
        </div>
        {record && (
          <span className={categoryBadge(record.bundle)}>
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
              <dd>{labels[record.candidate.target_id]}</dd>
            </div>
            <div>
              <dt>Source</dt>
              <dd>
                {record.bundle.source.name} · {record.bundle.source.version}
              </dd>
            </div>
          </dl>
          <div className="metric-list">
            {record.candidate.metrics.map((metric, index) => (
              <MetricCard metric={metric} key={index} />
            ))}
          </div>
          {!record.candidate.metrics.length && (
            <p className="notice">No metrics were supplied for this record.</p>
          )}
          <p className="hint">
            A 0 is a real value, a missing score is shown as missing. Scores
            from different tools are never combined.
          </p>
          <details>
            <summary>Inspect original record &amp; provenance</summary>
            <pre>{JSON.stringify(record.candidate.raw_record, null, 2)}</pre>
            <dl className="metadata">
              <div>
                <dt>Bundle ID</dt>
                <dd className="mono">{record.bundle.bundle_id}</dd>
              </div>
              <div>
                <dt>Request revision</dt>
                <dd className="mono">{record.bundle.context.revision_id}</dd>
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
                External: {dependency.uri} ({dependency.description})
              </p>
            ))}
          </details>
        </>
      )}
    </section>
  );
}

/* Collections and decisions */
function ManageCollections(props: { collection: Collection | undefined }) {
  const { state, dispatch, controller } = useWorkspace();
  const { collection } = props;
  const name = state.fields.collectionName;
  const noName = state.busy || !name?.trim();

  function remove(item: Collection) {
    const question = `Remove ${item.name} with its ${item.memberships.length} decisions? The evidence stays. Undo works until you save.`;
    if (!window.confirm(question)) return;
    void controller.command({
      type: "remove_collection",
      collection_id: item.collection_id,
    });
  }

  return (
    <details className="manage-collections">
      <summary>Manage collections</summary>
      <label htmlFor="collection-name">Collection name</label>
      <input
        id="collection-name"
        value={name ?? ""}
        onChange={(event) =>
          dispatch({
            type: "field",
            name: "collectionName",
            value: event.target.value,
          })
        }
        maxLength={MAX_LABEL}
        placeholder="A named review selection"
      />
      <div className="actions wrap">
        <button
          className="small secondary"
          disabled={noName}
          onClick={() =>
            void controller.command({
              type: "create_collection",
              revision_id: state.revisionId,
              name,
            })
          }
        >
          Create collection
        </button>
        {collection && (
          <>
            <button
              className="small secondary"
              disabled={noName}
              onClick={() =>
                void controller.command({
                  type: "rename_collection",
                  collection_id: collection.collection_id,
                  name,
                })
              }
            >
              Rename collection
            </button>
            <button
              className="text-button danger"
              disabled={state.busy}
              onClick={() => remove(collection)}
            >
              Remove collection
            </button>
          </>
        )}
      </div>
    </details>
  );
}

function DecisionForm(props: {
  decision: DecisionDraft;
  record: CandidateRecord;
  records: CandidateRecord[];
  collection: Collection;
}) {
  const { state, dispatch, controller } = useWorkspace();
  const { decision, record, records, collection } = props;

  // Every change goes into the decision draft only
  function update(change: Partial<DecisionDraft>) {
    dispatch({
      type: "draft",
      buffers: { ...state.buffers, decision: { ...decision, ...change } },
    });
  }

  function toggleReference(key: CandidateKey, checked: boolean) {
    const refs = checked
      ? [...decision.evidence_refs, key]
      : decision.evidence_refs.filter((item) => !keyEqual(item, key));
    update({ evidence_refs: refs });
  }

  function removeMember() {
    const question = `Remove ${record.candidate.label} from ${collection.name}? The evidence stays.`;
    if (!window.confirm(question)) return;
    void controller.command({
      type: "remove_member",
      collection_id: collection.collection_id,
      candidate: record.key,
    });
  }

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        void controller.command({ type: "set_decision", ...decision });
      }}
    >
      <hr />
      <label htmlFor="disposition">Disposition</label>
      <select
        id="disposition"
        value={decision.disposition}
        onChange={(event) =>
          update({ disposition: event.target.value as Disposition })
        }
      >
        <option value="undecided">Undecided</option>
        <option value="include_for_review">Include for further review</option>
        <option value="exclude">Exclude</option>
        <option value="needs_clarification">Needs clarification</option>
      </select>
      <label htmlFor="rationale">Rationale</label>
      <textarea
        id="rationale"
        rows={5}
        value={decision.rationale}
        onChange={(event) => update({ rationale: event.target.value })}
        maxLength={MAX_RATIONALE}
        placeholder="Why this decision? Anything still unclear?"
      />
      {decision.disposition !== "undecided" && !decision.rationale.trim() && (
        <p className="field-error">
          Without a reason the decision still counts as unfinished.
        </p>
      )}
      <details>
        <summary>Supporting evidence references</summary>
        {records.map((item) => (
          <label className="checkbox" key={recordKey(item.key)}>
            <input
              type="checkbox"
              checked={decision.evidence_refs.some((key) =>
                keyEqual(key, item.key),
              )}
              onChange={(event) =>
                toggleReference(item.key, event.target.checked)
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
          onClick={removeMember}
        >
          Remove from collection
        </button>
      </div>
      <p className="hint">The decision only applies in this collection.</p>
    </form>
  );
}

function DecisionPanel(props: {
  records: CandidateRecord[];
  record: CandidateRecord | undefined;
  collection: Collection | undefined;
  select: (candidate: CandidateKey | null, collectionId?: string) => void;
}) {
  const { state, controller } = useWorkspace();
  const { records, record, collection } = props;
  const items = collections(state);

  const member = collection?.memberships.find((item) =>
    keyEqual(item.candidate, record?.key ?? null),
  );
  const decision = shownDecision(state, collection, record, member);

  // What to show under the collection controls
  let body = null;
  if (record && collection && member && decision) {
    body = (
      <DecisionForm
        decision={decision}
        record={record}
        records={records}
        collection={collection}
      />
    );
  } else if (record && collection) {
    body = (
      <div className="empty compact">
        <p>This candidate isn't in the collection yet.</p>
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
    );
  }

  return (
    <aside className="panel decision-panel">
      <div className="panel-heading">
        <div>
          <p className="eyebrow">Your decision</p>
          <h2>Collection &amp; decision</h2>
        </div>
      </div>
      <label htmlFor="collection-select">Review collection</label>
      <select
        id="collection-select"
        value={collection?.collection_id ?? ""}
        onChange={(event) =>
          props.select(record?.key ?? null, event.target.value)
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
      <ManageCollections collection={collection} />
      {body}
    </aside>
  );
}

/* Empty state */
function NoEvidence() {
  const { state, controller } = useWorkspace();
  return (
    <section className="panel empty">
      <span className="empty-symbol">≋</span>
      <h2>No evidence attached to this revision</h2>
      <p>
        Import an <span className="mono">.evidence.json</span> file. Before it
        is attached, the preview checks it was made for this request and
        revision.
      </p>
      <p className="hint">
        Importing only stores the file, nothing in it is checked scientifically.
      </p>
      <button
        className="secondary"
        disabled={state.busy}
        onClick={() => void controller.sample("evidence-valid.json")}
      >
        Try the example evidence
      </button>
      <p className="hint">
        The example only fits the sample request, in any other study it is
        refused (on purpose).
      </p>
    </section>
  );
}

/* View */
export function ReviewView() {
  const { state, dispatch, controller } = useWorkspace();
  const records = candidates(state);
  const collection = selectedCollection(state);
  // Without a selection the first candidate is shown
  const record =
    records.find((item) => keyEqual(item.key, state.candidate)) ?? records[0];

  const attached: Bundle[] = [];
  for (const item of state.workspace!.study.evidence) {
    if (item.bundle.context.revision_id === state.revisionId)
      attached.push(item.bundle);
  }

  // Changing the selection throws away the unapplied decision (after asking)
  function select(candidate: CandidateKey | null, collectionId?: string) {
    if (
      state.buffers.decision &&
      !window.confirm("Throw away the decision you haven't applied yet?")
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
          <h1>Review the evidence</h1>
          <p>
            Go through the imported candidates and decide about each of them.
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
              // Clear it, so the same file can be chosen again
              event.target.value = "";
            }}
          />
        </label>
      </div>
      <ImportPreviewPanel />
      {!attached.length ? (
        <NoEvidence />
      ) : (
        <>
          <EvidenceStrip bundles={attached} />
          <div className="review-grid">
            <CandidateList
              records={records}
              record={record}
              collection={collection}
              select={select}
            />
            <EvidenceDetail record={record} />
            <DecisionPanel
              records={records}
              record={record}
              collection={collection}
              select={select}
            />
          </div>
        </>
      )}
    </>
  );
}
