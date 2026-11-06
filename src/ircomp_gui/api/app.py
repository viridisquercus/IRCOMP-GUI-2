# ************************************************************************
# @file app.py
# @brief HTTP interface of the application and serving of the GUI
# @author Lukas (Viridis) Dubsik
# @date 6-11-2026
# @version 0.1
#
# Detailed description:
#  The routes only translate HTTP to the services and back, no logic of
#  its own is here. Every request firstly passes LocalBoundary, which
#  refuses foreign hosts and origins and checks the JSON body before any
#  route reads it.
# ************************************************************************

"""Connect the application functions to HTTP and serve the GUI."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from ircomp_gui.adapters.exchange import Exchange
from ircomp_gui.adapters.resources import REPOSITORY, load_catalogue, resource_path
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
from ircomp_gui.application.responses import (
    CatalogueView,
    ErrorDetail,
    ErrorResponse,
    ExportPreviewView,
    ImportPreviewView,
    StudyList,
    ValidationView,
    WorkspaceView,
)
from ircomp_gui.application.workspace import WorkspaceService
from ircomp_gui.domain.constants import (
    MAX_BODY,
)
from ircomp_gui.domain.errors import DomainError
from ircomp_gui.domain.serialization import parse_json

LOG = logging.getLogger(__name__)

# HTTP status of each error code, anything else is 422
ERROR_STATUS = {
    "MALFORMED_JSON": 400,
    "DUPLICATE_KEY": 400,
    "INVALID_BASE64": 400,
    "ORIGIN_REJECTED": 403,
    "NOT_FOUND": 404,
    "SESSION_EXPIRED": 404,
    "PREVIEW_EXPIRED": 404,
    "IDENTITY_EXISTS": 409,
    "IDENTITY_CONFLICT": 409,
    "BUNDLE_ID_COLLISION": 409,
    "UNDO_UNAVAILABLE": 409,
    "LIMIT_EXCEEDED": 413,
    "INTERNAL_ERROR": 500,
    "PERSISTENCE_UNAVAILABLE": 503,
}
# Origins used when none are given - the service and the Vite dev server
DEFAULT_ORIGINS = {
    "http://127.0.0.1:8000",
    "http://localhost:8000",
    "http://127.0.0.1:5173",
    "http://localhost:5173",
}
# Example files which can be downloaded
EXAMPLES = {
    "request-valid.json",
    "evidence-valid.json",
    "evidence-context-mismatch.json",
    "evidence-empty.json",
}
# Methods which don't change anything and so need no body
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def error_status(code: str) -> int:
    """Choose the HTTP status for an error code.

    Parameters
    ----------
    code : str
        Code of the DomainError

    Returns
    -------
    int
        HTTP status
    """
    return ERROR_STATUS.get(code, 422)


def error_response(error: DomainError) -> JSONResponse:
    """Prepare the JSON error response read by the client.

    Parameters
    ----------
    error : DomainError
        Error to send

    Returns
    -------
    JSONResponse
        Response with the code, message and diagnostics
    """
    return JSONResponse(
        status_code=error_status(error.code),
        content=ErrorResponse(
            error=ErrorDetail(
                code=error.code, message=error.message, diagnostics=error.diagnostics
            )
        ).model_dump(mode="json"),
    )


class LocalBoundary:
    """Check the local requests before their body reaches a route.

    Attributes
    ----------
    app : ASGIApp
        The wrapped application
    origins : set[str]
        Allowed origins (scheme, host and port)
    hosts : set[str]
        Allowed values of the Host header
    """

    def __init__(self, app: ASGIApp, origins: set[str]) -> None:
        self.app = app
        self.origins = origins
        self.hosts = {urlsplit(origin).netloc for origin in origins}

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Check the local address and size of the request before reading JSON.

        Parameters
        ----------
        scope : Scope
            ASGI connection scope
        receive : Receive
            ASGI receive channel
        send : Send
            ASGI send channel
        """
        # Only HTTP is checked (lifespan events go through)
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope["headers"])
        host = headers.get(b"host", b"").decode("latin1")
        origin = headers.get(b"origin", b"").decode("latin1")

        try:
            # Refuse anything not addressed to us, protects from DNS rebinding
            if host not in self.hosts or (origin and origin not in self.origins):
                raise DomainError(
                    "ORIGIN_REJECTED",
                    "Use the local address the application was started with.",
                )

            if scope["method"] in SAFE_METHODS:
                await self.app(scope, receive, send)
                return

            raw = await self._read_body(headers, receive)
            if raw is None:
                return

            # Give the route the body we already read
            delivered = False

            async def cached_receive() -> Message:
                nonlocal delivered
                if not delivered:
                    delivered = True
                    return {"type": "http.request", "body": raw, "more_body": False}
                return await receive()

            await self.app(scope, cached_receive, send)
        except DomainError as error:
            await error_response(error)(scope, receive, send)

    async def _read_body(
        self, headers: dict[bytes, bytes], receive: Receive
    ) -> bytes | None:
        # Changing requests have to be JSON - a form can't be sent cross site then
        content_type = headers.get(b"content-type", b"").split(b";")[0].strip()
        if content_type != b"application/json":
            raise DomainError(
                "SCHEMA_INVALID", "Changing requests require application/json."
            )

        # Read the whole body, but stop as soon as it is too big
        raw = bytearray()
        more = True
        while more:
            event = await receive()
            if event["type"] == "http.disconnect":
                return None
            raw.extend(event.get("body", b""))
            if len(raw) > MAX_BODY:
                raise DomainError("LIMIT_EXCEEDED", "HTTP body exceeds 2 MiB.")
            more = event.get("more_body", False)

        # Check it is a valid JSON object (no duplicates, NaN, deep nesting)
        parse_json(bytes(raw), limit=MAX_BODY)
        return bytes(raw)


def create_app(
    database: Path | None = None,
    *,
    web_directory: Path | None = None,
    origins: set[str] | None = None,
) -> FastAPI:
    """Create the application with the chosen database and web directory.

    Parameters
    ----------
    database : Path | None
        Path to the SQLite file, by default IRCOMP_GUI_DATABASE or
        ~/.local/share/ircomp-gui/workspace.sqlite3
    web_directory : Path | None
        Built web client, by default IRCOMP_GUI_WEB or web/dist
    origins : set[str] | None
        Allowed origins, by default DEFAULT_ORIGINS

    Returns
    -------
    FastAPI
        The application ready to be run by uvicorn
    """
    # Build the services
    catalogue = load_catalogue()
    exchange = Exchange(catalogue)
    if database is None:
        default = Path.home() / ".local/share/ircomp-gui/workspace.sqlite3"
        database = Path(os.environ.get("IRCOMP_GUI_DATABASE", str(default)))
    repository = SQLiteRepository(database, catalogue, exchange)
    workspace = WorkspaceService(repository, catalogue)
    imports = ImportService(workspace, exchange)
    exports = ExportService(workspace, exchange)

    app = FastAPI(
        title="IRCOMP Study Workspace",
        version="0.1.0",
        responses={
            code: {"model": ErrorResponse}
            for code in sorted(set(ERROR_STATUS.values()))
        },
        description="Local editing of requests and review of evidence.",
    )
    app.state.workspace = workspace
    app.state.repository = repository
    app.state.imports = imports
    app.state.exports = exports
    app.add_middleware(LocalBoundary, origins=origins or DEFAULT_ORIGINS)

    # -----------------------------------------------------------------------
    # Errors
    # -----------------------------------------------------------------------
    @app.exception_handler(DomainError)
    async def domain_error(_request: Request, error: DomainError) -> JSONResponse:
        return error_response(error)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(
        _request: Request, error: RequestValidationError
    ) -> JSONResponse:
        # Point to the first wrong field, without the "body" prefix
        location = None
        for item in error.errors():
            parts = [str(part) for part in item["loc"] if part != "body"]
            location = "/" + "/".join(parts)
            break
        return error_response(
            DomainError(
                "SCHEMA_INVALID",
                "Request fields are missing, unknown or have invalid types.",
                location,
            )
        )

    @app.exception_handler(ValidationError)
    async def invalid_model(_request: Request, _error: ValidationError) -> JSONResponse:
        return error_response(
            DomainError("SCHEMA_INVALID", "The change goes over one of the limits.")
        )

    @app.exception_handler(Exception)
    async def unexpected(_request: Request, error: Exception) -> JSONResponse:
        # Only the type is logged, the message could contain study data
        LOG.error("Unexpected local application failure: %s", type(error).__name__)
        return error_response(
            DomainError(
                "INTERNAL_ERROR",
                "Something went wrong in the service, see its log for details. "
                "Your work is still here.",
            )
        )

    # -----------------------------------------------------------------------
    # Catalogue and saved studies
    # -----------------------------------------------------------------------
    @app.get("/api/v1/catalogue")
    def get_catalogue() -> CatalogueView:
        return CatalogueView(**catalogue.model_dump())

    @app.get("/api/v1/studies")
    def studies() -> StudyList:
        return StudyList(studies=repository.list())

    # -----------------------------------------------------------------------
    # Workspaces
    # -----------------------------------------------------------------------
    @app.post("/api/v1/workspaces", status_code=201)
    def create(payload: CreateInput) -> WorkspaceView:
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
    def get(workspace_id: str) -> WorkspaceView:
        with workspace.lock:
            return workspace.view(workspace.get(workspace_id))

    @app.delete("/api/v1/workspaces/{workspace_id}", status_code=204)
    def close(workspace_id: str, payload: CloseInput) -> Response:
        imports.close_workspace(workspace_id)
        return Response(status_code=204)

    @app.post("/api/v1/workspaces/{workspace_id}/commands")
    def command(workspace_id: str, payload: CommandInput) -> WorkspaceView:
        with workspace.lock:
            # Attaching needs the preview, so it goes to imports
            operation = payload.command
            if isinstance(operation, AttachEvidence):
                session = imports.attach(
                    workspace_id, payload.draft_buffers, operation.preview_id
                )
            else:
                session = workspace.command(
                    workspace_id, payload.draft_buffers, operation
                )
            return workspace.view(session)

    @app.post("/api/v1/workspaces/{workspace_id}/save")
    def save(workspace_id: str, payload: SaveInput) -> WorkspaceView:
        with workspace.lock:
            session = workspace.save(workspace_id, payload.draft_buffers)
            return workspace.view(session)

    @app.post("/api/v1/workspaces/{workspace_id}/undo")
    def undo(workspace_id: str) -> WorkspaceView:
        with workspace.lock:
            return workspace.view(workspace.undo(workspace_id))

    @app.post("/api/v1/workspaces/{workspace_id}/validate")
    def validate(workspace_id: str, payload: ValidateInput) -> ValidationView:
        return workspace.validate(
            workspace_id, payload.revision_id, payload.target_draft
        )

    # -----------------------------------------------------------------------
    # Imports and exports
    # -----------------------------------------------------------------------
    @app.post("/api/v1/imports", status_code=201)
    def preview(payload: ImportInput) -> ImportPreviewView:
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
    def export(payload: ExportInput) -> ExportPreviewView:
        return exports.prepare(
            payload.study_id,
            payload.revision_id,
            payload.kind,
            payload.collection_ids,
        )

    @app.get("/api/v1/exports/{export_id}/file")
    def download(export_id: str) -> Response:
        exported = exports.download(export_id)
        disposition = f'attachment; filename="{exported.filename}"'
        return Response(
            exported.raw,
            media_type="application/json",
            headers={"Content-Disposition": disposition},
        )

    @app.get("/api/v1/examples/{name}")
    def example(name: str) -> Response:
        # Only the known files, the name never becomes a free path
        if name not in EXAMPLES:
            raise DomainError("NOT_FOUND", "Example file was not found.")
        return Response(
            resource_path("examples/" + name).read_bytes(),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{name}"'},
        )

    # -----------------------------------------------------------------------
    # Web client
    # -----------------------------------------------------------------------
    if web_directory is None:
        default_web = REPOSITORY / "web/dist"
        web_directory = Path(os.environ.get("IRCOMP_GUI_WEB", str(default_web)))
    directory = web_directory

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
