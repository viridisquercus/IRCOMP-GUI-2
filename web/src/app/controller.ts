/*************************************************************************
 * Name: Lukas (Viridis) Dubsik
 *************************************************************************/
import { api, ApiError, fileBase64 } from "../shared/api";
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

export function createController(
  current: () => State,
  dispatch: (action: Action) => void,
) {
  let running = false;
  const patch = (value: Partial<State>) => dispatch({ type: "patch", value });
  // Run one operation at a time and show its result in the common status area.
  async function run(work: () => Promise<void>, message = "") {
    if (running) return;
    running = true;
    patch({ busy: true, error: null, status: "" });
    try {
      await work();
      if (message) patch({ status: message });
    } catch (error) {
      const failure =
        error instanceof ApiError
          ? error
          : new ApiError(
              "CLIENT_ERROR",
              error instanceof Error
                ? error.message
                : "The operation could not complete.",
            );
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
  function guardStudy(): boolean {
    return (
      !dirty(current()) ||
      window.confirm(
        "This study has unsaved changes. Leave this working copy? Save first to preserve them.",
      )
    );
  }
  function guardDraft(): boolean {
    return (
      !unapplied(current()) ||
      window.confirm(
        "Discard unapplied editor drafts and continue? Choose Cancel to stay and apply or save them.",
      )
    );
  }
  function received(workspace: Workspace, generation: number, opening = false) {
    sessionStorage.setItem("ircomp.workspace", workspace.workspace_id);
    dispatch({ type: "received", workspace, generation, opening });
  }
  async function create(body: unknown) {
    if (!guardStudy()) return;
    await run(async () => {
      const previous = current().workspace;
      const result = await api<Workspace>("/workspaces", body);
      received(result, current().generation, true);
      if (previous && previous.workspace_id !== result.workspace_id) {
        // The leave guard already confirmed discarding this working session.
        await api(
          `/workspaces/${previous.workspace_id}`,
          { discard: true },
          "DELETE",
        ).catch(() => undefined);
      }
      patch({ view: "prepare" });
      await listStudies();
    }, "Study opened.");
  }
  // Send the current editor text together with the requested change.
  async function command(operation: Command) {
    await run(async () => {
      const before = current();
      const workspace = before.workspace!;
      const result = await api<Workspace>(
        `/workspaces/${workspace.workspace_id}/commands`,
        {
          draft_buffers: before.buffers,
          command: operation,
        },
      );
      received(result, before.generation);
      if (operation.type === "apply_target") {
        const previousIds = new Set(
          workspace.study.revisions
            .find(
              (item) => item.revision_id === workspace.study.active_revision_id,
            )
            ?.targets.map((item) => item.target_id),
        );
        const active = result.study.revisions.find(
          (item) => item.revision_id === result.study.active_revision_id,
        )!;
        patch({
          targetId:
            operation.draft.target_id ??
            active.targets.find((item) => !previousIds.has(item.target_id))
              ?.target_id ??
            null,
        });
      }
      if (operation.type === "attach_evidence") patch({ importPreview: null });
    }, "Working change accepted. Save study to keep it.");
  }
  return {
    run,
    command,
    create,
    listStudies,
    async boot() {
      await run(async () => {
        patch({ catalogue: await api<Catalogue>("/catalogue") });
        await listStudies();
        const id = sessionStorage.getItem("ircomp.workspace");
        if (id) {
          try {
            received(await api<Workspace>(`/workspaces/${id}`), 0, true);
          } catch {
            sessionStorage.removeItem("ircomp.workspace");
            patch({
              status:
                "Previous session is unavailable. Open a saved study; unsaved work may be lost.",
            });
          }
        }
      }, "");
    },
    // Save the accepted study and the unapplied text as separate values.
    async save() {
      await run(async () => {
        const before = current();
        const workspace = before.workspace!;
        const result = await api<Workspace>(
          `/workspaces/${workspace.workspace_id}/save`,
          {
            draft_buffers: before.buffers,
          },
        );
        received(result, before.generation);
        await listStudies();
      }, "Study saved. Unapplied drafts are retained separately.");
    },
    async refresh() {
      await run(async () => {
        const workspace = current().workspace;
        if (workspace)
          received(
            await api<Workspace>(`/workspaces/${workspace.workspace_id}`),
            -1,
          );
        else {
          patch({ catalogue: await api<Catalogue>("/catalogue") });
          await listStudies();
        }
      }, "Working state refreshed; local editor text retained. Inspect accepted changes before retrying.");
    },
    async reopen() {
      const workspace = current().workspace;
      if (workspace)
        await create({ source: "saved", study_id: workspace.study.study_id });
    },
    async close() {
      if (!guardStudy()) return;
      await run(async () => {
        const workspace = current().workspace!;
        await api(
          `/workspaces/${workspace.workspace_id}`,
          { discard: true },
          "DELETE",
        );
        sessionStorage.removeItem("ircomp.workspace");
        patch({
          workspace: null,
          buffers: { target: null, decision: null },
          importPreview: null,
        });
        await listStudies();
      });
    },
    async undo() {
      if (!guardDraft()) return;
      await run(async () => {
        const before = current();
        const workspace = before.workspace!;
        received(
          await api<Workspace>(
            `/workspaces/${workspace.workspace_id}/undo`,
            {},
          ),
          before.generation,
        );
      }, "Last accepted action undone.");
    },
    selectRevision(id: string) {
      if (!guardDraft()) return;
      dispatch({ type: "draft", buffers: { target: null, decision: null } });
      patch({
        revisionId: id,
        targetId: null,
        candidate: null,
        collectionId: "",
        validation: null,
        exportPreview: null,
        selectedCollections: [],
      });
    },
    selectTarget(id: string | null) {
      if (current().buffers.target && !guardDraft()) return;
      dispatch({
        type: "draft",
        buffers: { ...current().buffers, target: null },
      });
      patch({ targetId: id });
    },
    newTarget() {
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
    },
    async validate() {
      await run(async () => {
        const before = current();
        const result = await api<Validation>(
          `/workspaces/${before.workspace!.workspace_id}/validate`,
          {
            revision_id: before.revisionId,
            target_draft: before.buffers.target,
          },
        );
        patch({ validation: result });
      }, "Local checks complete.");
    },
    async importFile(kind: "request" | "evidence", file: File) {
      await run(async () => {
        const before = current();
        if (before.importPreview)
          await api(
            `/imports/${before.importPreview.preview_id}`,
            {},
            "DELETE",
          );
        const body =
          kind === "request"
            ? { kind, content_base64: await fileBase64(file) }
            : {
                kind,
                content_base64: await fileBase64(file),
                workspace_id: before.workspace!.workspace_id,
                revision_id: before.revisionId,
              };
        patch({ importPreview: await api<ImportPreview>("/imports", body) });
      });
    },
    async sample(name: string) {
      try {
        const response = await fetch(`/api/v1/examples/${name}`);
        if (!response.ok) throw new Error("Example unavailable");
        const file = new File([await response.blob()], name, {
          type: "application/json",
        });
        await this.importFile(
          name.startsWith("request") ? "request" : "evidence",
          file,
        );
      } catch {
        patch({
          error: {
            code: "CONNECTION_FAILED",
            message: "Example is unavailable. Reconnect to the local service.",
            diagnostics: [],
          },
        });
      }
    },
    async cancelImport() {
      await run(async () => {
        const preview = current().importPreview;
        if (preview) await api(`/imports/${preview.preview_id}`, {}, "DELETE");
        patch({ importPreview: null });
      });
    },
    async acceptImport() {
      const preview = current().importPreview!;
      if (preview.kind === "request")
        await create({
          source: "request_import",
          preview_id: preview.preview_id,
        });
      else
        await command({
          type: "attach_evidence",
          preview_id: preview.preview_id,
        });
    },
    // Export saved data only. Newer unsaved work remains in the editor.
    async previewExport(lastSaved: boolean) {
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
            if (
              !source.study.revisions.some(
                (item) => item.revision_id === revisionId,
              )
            )
              revisionId = source.study.active_revision_id;
          }
          patch({
            exportPreview: await api<ExportPreview>("/exports", {
              study_id: workspace.study.study_id,
              revision_id: revisionId,
              kind: before.exportKind,
              collection_ids:
                before.exportKind === "request"
                  ? []
                  : before.selectedCollections,
            }),
          });
        } finally {
          if (source)
            await api(
              `/workspaces/${source.workspace_id}`,
              { discard: true },
              "DELETE",
            ).catch(() => undefined);
        }
      });
    },
  };
}
