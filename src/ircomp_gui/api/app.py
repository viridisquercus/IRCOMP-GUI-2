# /************************************************************************
# Name: Lukas (Viridis) Dubsik
# ************************************************************************/

"""Connect the application functions to HTTP and serve the GUI."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from ircomp_gui.adapters.exchange import Exchange
from ircomp_gui.adapters.resources import load_catalogue, resource_path
from ircomp_gui.adapters.sqlite import SQLiteRepository
from ircomp_gui.api.requests import (
    CloseInput,
    CommandInput,
    CreateInput,
    DuplicateWorkspace,
    EvidenceImport,
    ExportInput,
    ImportInput,
    NewWorkspace,
    SavedWorkspace,
    SaveInput,
    ValidateInput,
)
from ircomp_gui.application.commands import AttachEvidence
from ircomp_gui.application.export import ExportService
from ircomp_gui.application.imports import ImportService
from ircomp_gui.application.workspace import WorkspaceService
from ircomp_gui.domain.errors import DomainError
from ircomp_gui.domain.serialization import parse_json

LOG = logging.getLogger(__name__)


def error_status(code: str) -> int:
    """Choose the HTTP status for an application error code."""
    if code in {"MALFORMED_JSON", "DUPLICATE_KEY", "INVALID_BASE64"}:
        return 400
    if code in {"NOT_FOUND", "SESSION_EXPIRED", "PREVIEW_EXPIRED"}:
        return 404
    if code in {
        "IDENTITY_EXISTS",
        "IDENTITY_CONFLICT",
        "BUNDLE_ID_COLLISION",
        "UNDO_UNAVAILABLE",
    }:
        return 409
    if code == "LIMIT_EXCEEDED":
        return 413
    if code == "ORIGIN_REJECTED":
        return 403
    if code == "PERSISTENCE_UNAVAILABLE":
        return 503
    return 500 if code == "INTERNAL_ERROR" else 422


def error_response(error: DomainError) -> JSONResponse:
    """Prepare the JSON error response read by the client."""
    return JSONResponse(
        status_code=error_status(error.code),
        content={
            "error": {
                "code": error.code,
                "message": error.message,
                "diagnostics": [item.model_dump() for item in error.diagnostics],
            },
        },
    )


class LocalBoundary:
    """Check local requests before passing their body to a route."""

    def __init__(self, app: ASGIApp, origins: set[str]) -> None:
        self.app = app
        self.origins = origins
        self.hosts = {urlsplit(origin).netloc for origin in origins}

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Check the local address and request size before reading JSON."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = dict(scope["headers"])
        host = headers.get(b"host", b"").decode("latin1")
        origin = headers.get(b"origin", b"").decode("latin1")
        changing = scope["method"] not in {"GET", "HEAD", "OPTIONS"}
        try:
            if host not in self.hosts or (origin and origin not in self.origins):
                raise DomainError(
                    "ORIGIN_REJECTED",
                    "Use this application's configured local address.",
                )
            if changing:
                if (
                    headers.get(b"content-type", b"").split(b";")[0].strip()
                    != b"application/json"
                ):
                    raise DomainError(
                        "SCHEMA_INVALID", "Changing requests require application/json."
                    )
                raw = bytearray()
                more = True
                while more:
                    event = await receive()
                    if event["type"] == "http.disconnect":
                        return
                    raw.extend(event.get("body", b""))
                    if len(raw) > 2 * 1024 * 1024:
                        raise DomainError("LIMIT_EXCEEDED", "HTTP body exceeds 2 MiB.")
                    more = event.get("more_body", False)
                _ = parse_json(bytes(raw), limit=2 * 1024 * 1024)
                delivered = False

                async def cached_receive() -> Message:
                    nonlocal delivered
                    if not delivered:
                        delivered = True
                        return {
                            "type": "http.request",
                            "body": bytes(raw),
                            "more_body": False,
                        }
                    return await receive()

                await self.app(scope, cached_receive, send)
            else:
                await self.app(scope, receive, send)
        except DomainError as error:
            await error_response(error)(scope, receive, send)


def create_app(
    database: Path | None = None,
    *,
    web_directory: Path | None = None,
    origins: set[str] | None = None,
) -> FastAPI:
    """Create the application using the selected database and web directory."""
    catalogue = load_catalogue()
    exchange = Exchange(catalogue)
    database = database or Path(
        os.environ.get(
            "IRCOMP_GUI_DATABASE",
            str(Path.home() / ".local/share/ircomp-gui/workspace.sqlite3"),
        )
    )
    repository = SQLiteRepository(database, catalogue, exchange)
    workspace = WorkspaceService(repository, catalogue)
    imports = ImportService(workspace, exchange)
    exports = ExportService(workspace, exchange)
    app = FastAPI(
        title="IRCOMP Study Workspace",
        version="0.1.0",
        description=(
            "Local request editing and evidence review. No compiler or "
            "scientific execution."
        ),
    )
    app.state.workspace = workspace
    app.state.repository = repository
    app.state.imports = imports
    app.state.exports = exports
    configured = origins or {
        "http://127.0.0.1:8000",
        "http://localhost:8000",
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    }
    app.add_middleware(LocalBoundary, origins=configured)

    @app.exception_handler(DomainError)
    async def domain_error(_request: Request, error: DomainError) -> JSONResponse:
        return error_response(error)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(
        _request: Request, error: RequestValidationError
    ) -> JSONResponse:
        locations = [
            "/" + "/".join(str(part) for part in item["loc"] if part != "body")
            for item in error.errors()
        ]
        return error_response(
            DomainError(
                "SCHEMA_INVALID",
                "Request fields are missing, unknown or have invalid types.",
                locations[0] if locations else None,
            )
        )

    @app.exception_handler(ValidationError)
    async def invalid_model(_request: Request, _error: ValidationError) -> JSONResponse:
        return error_response(
            DomainError(
                "SCHEMA_INVALID", "The proposed change exceeds a field or state limit."
            )
        )

    @app.exception_handler(Exception)
    async def unexpected(_request: Request, error: Exception) -> JSONResponse:
        LOG.error("Unexpected local application failure: %s", type(error).__name__)
        return error_response(
            DomainError(
                "INTERNAL_ERROR",
                (
                    "The operation could not complete. Retain your work and "
                    "inspect local service logs."
                ),
            )
        )

    @app.get("/api/v1/catalogue")
    def get_catalogue() -> dict[str, Any]:
        return {
            **catalogue.model_dump(mode="json"),
            "format_versions": ["1.0"],
            "limits": {
                "import_bytes": 1048576,
                "targets": 50,
                "bundles": 10,
                "collections": 20,
                "memberships": 1000,
                "revisions": 200,
            },
        }

    @app.get("/api/v1/studies")
    def studies() -> dict[str, Any]:
        return {"studies": [item.model_dump() for item in repository.list()]}

    @app.post("/api/v1/workspaces", status_code=201)
    def create(payload: CreateInput) -> dict[str, Any]:
        with workspace.lock:
            if isinstance(payload, NewWorkspace):
                session = workspace.create(payload.title)
            elif isinstance(payload, SavedWorkspace):
                session = workspace.open(payload.study_id)
            elif isinstance(payload, DuplicateWorkspace):
                session = workspace.duplicate(payload.workspace_id, payload.title)
            else:
                session = imports.accept_request(payload.preview_id)
            return workspace.view(session)

    @app.get("/api/v1/workspaces/{workspace_id}")
    def get(workspace_id: str) -> dict[str, Any]:
        with workspace.lock:
            return workspace.view(workspace.get(workspace_id))

    @app.delete("/api/v1/workspaces/{workspace_id}", status_code=204)
    def close(workspace_id: str, payload: CloseInput) -> Response:
        imports.close_workspace(workspace_id)
        return Response(status_code=204)

    @app.post("/api/v1/workspaces/{workspace_id}/commands")
    def command(workspace_id: str, payload: CommandInput) -> dict[str, Any]:
        with workspace.lock:
            operation = payload.command
            if isinstance(operation, AttachEvidence):
                session = imports.attach(
                    workspace_id,
                    payload.draft_buffers,
                    operation.preview_id,
                )
            else:
                session = workspace.command(
                    workspace_id,
                    payload.draft_buffers,
                    operation,
                )
            return workspace.view(session)

    @app.post("/api/v1/workspaces/{workspace_id}/save")
    def save(workspace_id: str, payload: SaveInput) -> dict[str, Any]:
        with workspace.lock:
            return workspace.view(
                workspace.save(
                    workspace_id,
                    payload.draft_buffers,
                )
            )

    @app.post("/api/v1/workspaces/{workspace_id}/undo")
    def undo(workspace_id: str) -> dict[str, Any]:
        with workspace.lock:
            return workspace.view(workspace.undo(workspace_id))

    @app.post("/api/v1/workspaces/{workspace_id}/validate")
    def validate(workspace_id: str, payload: ValidateInput) -> dict[str, Any]:
        return workspace.validate(
            workspace_id, payload.revision_id, payload.target_draft
        )

    @app.post("/api/v1/imports", status_code=201)
    def preview(payload: ImportInput) -> dict[str, Any]:
        if isinstance(payload, EvidenceImport):
            return imports.preview(
                payload.kind,
                payload.content_base64,
                payload.workspace_id,
                payload.revision_id,
            )
        return imports.preview(payload.kind, payload.content_base64)

    @app.delete("/api/v1/imports/{preview_id}", status_code=204)
    def cancel(preview_id: str) -> Response:
        imports.cancel(preview_id)
        return Response(status_code=204)

    @app.post("/api/v1/exports", status_code=201)
    def export(payload: ExportInput) -> dict[str, Any]:
        return exports.prepare(
            payload.study_id,
            payload.revision_id,
            payload.kind,
            payload.collection_ids,
        )

    @app.get("/api/v1/exports/{export_id}/file")
    def download(export_id: str) -> Response:
        exported = exports.download(export_id)
        return Response(
            exported.raw,
            media_type="application/json",
            headers={
                "Content-Disposition": f'attachment; filename="{exported.filename}"'
            },
        )

    @app.get("/api/v1/examples/{name}")
    def example(name: str) -> Response:
        allowed = {
            "request-valid.json",
            "evidence-valid.json",
            "evidence-context-mismatch.json",
            "evidence-empty.json",
        }
        if name not in allowed:
            raise DomainError("NOT_FOUND", "Example file was not found.")
        return Response(
            resource_path(f"examples/{name}").read_bytes(),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{name}"'},
        )

    directory = web_directory or Path(
        os.environ.get(
            "IRCOMP_GUI_WEB", str(Path(__file__).resolve().parents[3] / "web/dist")
        )
    )
    if (directory / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=directory / "assets"), name="assets")

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        if not (directory / "index.html").is_file():
            raise DomainError(
                "NOT_FOUND",
                "Build the web client with npm ci and npm run build in web/ first.",
            )
        return FileResponse(directory / "index.html")

    return app
