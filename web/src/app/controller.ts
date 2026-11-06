/**
 * @file controller.ts
 * @brief Operations of the web client, sent to the local service
 * @author Lukas (Viridis) Dubsik
 * @date 6-11-2026
 * @version 0.1
 *
 * Detailed description:
 *  The views never call the service themselves, they call the functions
 *  here. Only one operation runs at a time; its result or error is shown
 *  in the common status area.
 */
import { api, ApiError, fileBase64 } from "../shared/api";
import { NO_DRAFTS, SESSION_KEY } from "../shared/constants";
import type {
  Catalogue,
  Command,
  ExportPreview,
  ImportPreview,
  StudySummary,
  TargetDraft,
  Validation,
  Workspace,
} from "../shared/types";
import { dirty, revision, unapplied } from "./selectors";
import type { Action, State } from "./state";

/* Messages */
const LEAVE_STUDY =
  "The study has unsaved changes. Leave it anyway? (Cancel and save first to keep them.)";
const DISCARD_DRAFT =
  "You have edits which are not applied yet. Throw them away?";

/* Helper functions */
/**
 * @brief Find the active revision of the study in the workspace
 */
function activeRevision(workspace: Workspace) {
  return workspace.study.revisions.find(
    (item) => item.revision_id === workspace.study.active_revision_id,
  );
}

/**
 * @brief Close a workspace on the service, ignoring any failure
 *
 * Used for copies the user does not see anymore, so an error there
 * would only be confusing.
 */
async function discardQuietly(workspaceId: string) {
  await api(`/workspaces/${workspaceId}`, { discard: true }, "DELETE").catch(
    () => undefined,
  );
}

/* Controller */
/**
 * @brief Create the operations working on the shared state
 *
 * @param current Returns the current state (always the newest one)
 * @param dispatch Sends an action to the reducer
 * @return Object with all the operations
 */
export function createController(
  current: () => State,
  dispatch: (action: Action) => void,
) {
  let running = false; // Some operation is in progress
  const patch = (value: Partial<State>) => dispatch({ type: "patch", value });

  /**
   * @brief Run one operation and show its result in the status area
   *
   * @param work The operation itself
   * @param message Status shown when it succeeds
   */
  async function run(work: () => Promise<void>, message = "") {
    // Ignore clicks while something else is running
    if (running) return;
    running = true;
    patch({ busy: true, error: null, status: "" });

    try {
      await work();
      if (message) patch({ status: message });
    } catch (error) {
      // Anything else than ApiError is a bug of the client
      let failure: ApiError;
      if (error instanceof ApiError) {
        failure = error;
      } else {
        const text =
          error instanceof Error ? error.message : "Something went wrong.";
        failure = new ApiError("CLIENT_ERROR", text);
      }
      patch({
        error: {
          code: failure.code,
          message: failure.message,
          diagnostics: failure.diagnostics,
        },
      });
    } finally {
      running = false;
      patch({ busy: false });
    }
  }

  async function listStudies() {
    const result = await api<{ studies: StudySummary[] }>("/studies");
    patch({ studies: result.studies });
  }

  // Ask before leaving a study with unsaved changes
  function guardStudy(): boolean {
    return !dirty(current()) || window.confirm(LEAVE_STUDY);
  }

  // Ask before throwing away unapplied editor text
  function guardDraft(): boolean {
    return !unapplied(current()) || window.confirm(DISCARD_DRAFT);
  }

  function received(workspace: Workspace, generation: number, opening = false) {
    // Remember the workspace, so a reload of the page can reconnect to it
    sessionStorage.setItem(SESSION_KEY, workspace.workspace_id);
    dispatch({ type: "received", workspace, generation, opening });
  }

  /**
   * @brief Open a new workspace (new, saved, duplicated or imported study)
   *
   * @param body Body of POST /workspaces
   */
  async function create(body: unknown) {
    if (!guardStudy()) return;

    await run(async () => {
      const previous = current().workspace;
      const result = await api<Workspace>("/workspaces", body);
      received(result, current().generation, true);

      // The guard already confirmed the old working copy can go
      if (previous && previous.workspace_id !== result.workspace_id) {
        await discardQuietly(previous.workspace_id);
      }
      patch({ view: "prepare" });
      await listStudies();
    }, "Study opened.");
  }

  /**
   * @brief Send a command together with the current editor text
   *
   * @param operation The command
   */
  async function command(operation: Command) {
    await run(async () => {
      const before = current();
      const workspace = before.workspace!;
      const result = await api<Workspace>(
        `/workspaces/${workspace.workspace_id}/commands`,
        { draft_buffers: before.buffers, command: operation },
      );
      received(result, before.generation);

      // Select the applied target - for a new one find which ID is new
      if (operation.type === "apply_target") {
        const previousIds = new Set(
          activeRevision(workspace)?.targets.map((item) => item.target_id),
        );
        const added = activeRevision(result)!.targets.find(
          (item) => !previousIds.has(item.target_id),
        );
        patch({
          targetId: operation.draft.target_id ?? added?.target_id ?? null,
        });
      }
      if (operation.type === "attach_evidence") patch({ importPreview: null });
    }, "Change applied. Don't forget to save the study.");
  }

  /**
   * @brief Inspect a file, the previous preview is cancelled first
   *
   * @param kind request or evidence
   * @param file File chosen by the user
   */
  async function importFile(kind: "request" | "evidence", file: File) {
    await run(async () => {
      const before = current();
      if (before.importPreview) {
        await api(`/imports/${before.importPreview.preview_id}`, {}, "DELETE");
      }

      // Evidence also says which request it is meant for
      const content = await fileBase64(file);
      let body: object = { kind, content_base64: content };
      if (kind === "evidence") {
        body = {
          ...body,
          workspace_id: before.workspace!.workspace_id,
          revision_id: before.revisionId,
        };
      }
      patch({ importPreview: await api<ImportPreview>("/imports", body) });
    });
  }

  /* Study */
  async function boot() {
    await run(async () => {
      patch({ catalogue: await api<Catalogue>("/catalogue") });
      await listStudies();

      // Reconnect to the workspace from before the page reload
      const id = sessionStorage.getItem(SESSION_KEY);
      if (!id) return;
      try {
        received(await api<Workspace>(`/workspaces/${id}`), 0, true);
      } catch {
        sessionStorage.removeItem(SESSION_KEY);
        patch({
          status:
            "The previous session is gone (was the service restarted?). Open the saved study again, unsaved changes are lost.",
        });
      }
    }, "");
  }

  // Save the accepted study, the unapplied text is saved apart from it
  async function save() {
    await run(async () => {
      const before = current();
      const workspace = before.workspace!;
      const result = await api<Workspace>(
        `/workspaces/${workspace.workspace_id}/save`,
        { draft_buffers: before.buffers },
      );
      received(result, before.generation);
      await listStudies();
    }, "Study saved. Edits not applied yet were saved too, but stay unapplied.");
  }

  async function refresh() {
    await run(async () => {
      const workspace = current().workspace;
      if (workspace) {
        // -1 never matches, so the local editor text is kept
        received(
          await api<Workspace>(`/workspaces/${workspace.workspace_id}`),
          -1,
        );
      } else {
        patch({ catalogue: await api<Catalogue>("/catalogue") });
        await listStudies();
      }
    }, "Reloaded from the service and your typing was kept. Check what was applied before trying again.");
  }

  async function reopen() {
    const workspace = current().workspace;
    if (workspace)
      await create({ source: "saved", study_id: workspace.study.study_id });
  }

  async function close() {
    if (!guardStudy()) return;
    await run(async () => {
      const workspace = current().workspace!;
      await api(
        `/workspaces/${workspace.workspace_id}`,
        { discard: true },
        "DELETE",
      );
      sessionStorage.removeItem(SESSION_KEY);
      patch({ workspace: null, buffers: NO_DRAFTS, importPreview: null });
      await listStudies();
    });
  }

  async function undo() {
    if (!guardDraft()) return;
    await run(async () => {
      const before = current();
      const workspace = before.workspace!;
      const result = await api<Workspace>(
        `/workspaces/${workspace.workspace_id}/undo`,
        {},
      );
      received(result, before.generation);
    }, "Last change undone.");
  }

  /* Selection */
  function selectRevision(id: string) {
    if (!guardDraft()) return;
    dispatch({ type: "draft", buffers: NO_DRAFTS });
    patch({
      revisionId: id,
      targetId: null,
      candidate: null,
      collectionId: "",
      validation: null,
      exportPreview: null,
      selectedCollections: [],
    });
  }

  function selectTarget(id: string | null) {
    if (current().buffers.target && !guardDraft()) return;
    dispatch({
      type: "draft",
      buffers: { ...current().buffers, target: null },
    });
    patch({ targetId: id });
  }

  // Open the editor with an empty target on the first contig
  function newTarget() {
    if (!guardDraft()) return;
    const selected = revision(current());
    const reference = current().catalogue?.references.find(
      (item) => item.reference_id === selected?.reference_id,
    );
    const draft: TargetDraft = {
      target_id: null,
      label: "",
      contig: reference?.contigs[0]?.accession ?? "",
      start: "",
      end: "",
      strand: ".",
    };
    dispatch({
      type: "draft",
      buffers: { ...current().buffers, target: draft },
    });
    patch({ targetId: null, view: "prepare" });
  }

  /* Checks, import and export */
  async function validate() {
    await run(async () => {
      const before = current();
      const result = await api<Validation>(
        `/workspaces/${before.workspace!.workspace_id}/validate`,
        { revision_id: before.revisionId, target_draft: before.buffers.target },
      );
      patch({ validation: result });
    }, "Local checks complete.");
  }

  // Download one of the shipped example files and import it
  async function sample(name: string) {
    try {
      const response = await fetch(`/api/v1/examples/${name}`);
      if (!response.ok) throw new Error("Example unavailable");
      const file = new File([await response.blob()], name, {
        type: "application/json",
      });
      const kind = name.startsWith("request") ? "request" : "evidence";
      await importFile(kind, file);
    } catch {
      patch({
        error: {
          code: "CONNECTION_FAILED",
          message: "Couldn't load the example, is the service running?",
          diagnostics: [],
        },
      });
    }
  }

  async function cancelImport() {
    await run(async () => {
      const preview = current().importPreview;
      if (preview) await api(`/imports/${preview.preview_id}`, {}, "DELETE");
      patch({ importPreview: null });
    });
  }

  // A request opens a new study, evidence is attached to the open one
  async function acceptImport() {
    const preview = current().importPreview!;
    if (preview.kind === "request") {
      await create({
        source: "request_import",
        preview_id: preview.preview_id,
      });
    } else {
      await command({
        type: "attach_evidence",
        preview_id: preview.preview_id,
      });
    }
  }

  /**
   * @brief Prepare an export of the saved data
   *
   * The newer unsaved work stays in the editor. With lastSaved the saved
   * study is opened in a temporary workspace to find its revisions.
   *
   * @param lastSaved Export the last saved snapshot despite unsaved changes
   */
  async function previewExport(lastSaved: boolean) {
    if (!lastSaved && (dirty(current()) || unapplied(current()))) return;

    await run(async () => {
      const before = current();
      const workspace = before.workspace!;
      let source: Workspace | null = null;
      try {
        let revisionId = before.revisionId;
        if (lastSaved) {
          source = await api<Workspace>("/workspaces", {
            source: "saved",
            study_id: workspace.study.study_id,
          });
          // The shown revision may not be saved yet - use the saved active one
          const saved = source.study.revisions.some(
            (item) => item.revision_id === revisionId,
          );
          if (!saved) revisionId = source.study.active_revision_id;
        }

        const preview = await api<ExportPreview>("/exports", {
          study_id: workspace.study.study_id,
          revision_id: revisionId,
          kind: before.exportKind,
          collection_ids:
            before.exportKind === "request" ? [] : before.selectedCollections,
        });
        patch({ exportPreview: preview });
      } finally {
        // Close the temporary workspace again
        if (source) await discardQuietly(source.workspace_id);
      }
    });
  }

  return {
    run,
    command,
    create,
    listStudies,
    boot,
    save,
    refresh,
    reopen,
    close,
    undo,
    selectRevision,
    selectTarget,
    newTarget,
    validate,
    importFile,
    sample,
    cancelImport,
    acceptImport,
    previewExport,
  };
}

export type Controller = ReturnType<typeof createController>;
