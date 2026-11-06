"""Check API serialization and the generated exchange format."""

import asyncio
import base64
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.routing import APIRoute
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from ircomp_gui.api.app import create_app
from ircomp_gui.application.responses import WorkspaceView
from ircomp_gui.domain.constants import MAX_FILE, MAX_TARGETS

ROOT = Path(__file__).resolve().parents[1]


class ContractTests(unittest.TestCase):
    def setUp(self):
        async def inline(function, /, *args, **kwargs):
            return function(*args, **kwargs)

        # Exercise routes in process; no socket or worker-thread scheduling needed.
        runner = patch("fastapi.routing.run_in_threadpool", inline)
        runner.start()
        self.addCleanup(runner.stop)
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.app = create_app(Path(self.directory.name) / "study.sqlite3")
        self.schema = json.loads((ROOT / "contracts/exchange.schema.json").read_text())
        self.validator = Draft202012Validator(self.schema)

    def request(self, method, path, body=None):
        """Call the ASGI app directly, without opening a socket."""

        async def call():
            messages = []
            raw = json.dumps(body).encode() if body is not None else b""
            scope = {
                "type": "http",
                "asgi": {"version": "3.0"},
                "http_version": "1.1",
                "method": method,
                "scheme": "http",
                "path": path,
                "raw_path": path.encode(),
                "query_string": b"",
                "root_path": "",
                "server": ("127.0.0.1", 8000),
                "client": ("127.0.0.1", 12345),
                "headers": [
                    (b"host", b"127.0.0.1:8000"),
                    (b"content-type", b"application/json"),
                ],
            }

            async def receive():
                return {"type": "http.request", "body": raw, "more_body": False}

            async def send(message):
                messages.append(message)

            try:
                await asyncio.wait_for(self.app(scope, receive, send), timeout=5)
            except Exception:
                # Starlette sends the handled 500 response and then re-raises.
                if not messages or messages[0].get("status") != 500:
                    raise
            status = messages[0]["status"]
            data = b"".join(message.get("body", b"") for message in messages[1:])
            return status, json.loads(data) if data else None

        return asyncio.run(call())

    def test_typed_routes_and_published_limits(self):
        status, catalogue = self.request("GET", "/api/v1/catalogue")
        self.assertEqual(status, 200)
        self.assertEqual(catalogue["limits"]["targets"], MAX_TARGETS)
        self.assertEqual(catalogue["limits"]["import_bytes"], MAX_FILE)
        status, view = self.request(
            "POST", "/api/v1/workspaces", {"source": "new", "title": "Typed study"}
        )
        self.assertEqual(status, 201)
        self.assertEqual(WorkspaceView.model_validate(view).study.title, "Typed study")
        document = self.app.openapi()
        for path, methods in document["paths"].items():
            if path.endswith("/file") or "/examples/" in path:
                continue  # File downloads use the exchange schema rather than a view.
            for operation in methods.values():
                for code, response in operation.get("responses", {}).items():
                    if code.startswith("2") and "application/json" in response.get(
                        "content", {}
                    ):
                        schema = response["content"]["application/json"]["schema"]
                        self.assertIn("$ref", schema, path)

    def test_response_model_rejects_invalid_service_output(self):
        for route in self.app.routes:
            if isinstance(route, APIRoute) and route.path == "/api/v1/studies":
                route.dependant.call = lambda: {"studies": [{"study_id": 17}]}
                break
        with self.assertLogs("ircomp_gui.api.app", level="ERROR") as logs:
            status, body = self.request("GET", "/api/v1/studies")
        self.assertIn("ResponseValidationError", " ".join(logs.output))
        self.assertEqual(status, 500)
        self.assertEqual(body["error"]["code"], "INTERNAL_ERROR")

    def test_import_review_save_export_keeps_original_bytes(self):
        raw = (ROOT / "contracts/examples/request-valid.json").read_bytes()
        status, preview = self.request(
            "POST",
            "/api/v1/imports",
            {"kind": "request", "content_base64": base64.b64encode(raw).decode()},
        )
        self.assertEqual(status, 201)
        status, view = self.request(
            "POST",
            "/api/v1/workspaces",
            {"source": "request_import", "preview_id": preview["preview_id"]},
        )
        self.assertEqual(status, 201)
        workspace = view["workspace_id"]
        revision = view["study"]["active_revision_id"]
        evidence = (ROOT / "contracts/examples/evidence-valid.json").read_bytes()
        status, preview = self.request(
            "POST",
            "/api/v1/imports",
            {
                "kind": "evidence",
                "content_base64": base64.b64encode(evidence).decode(),
                "workspace_id": workspace,
                "revision_id": revision,
            },
        )
        self.assertEqual(status, 201)
        status, view = self.request(
            "POST",
            f"/api/v1/workspaces/{workspace}/commands",
            {
                "draft_buffers": {"target": None, "decision": None},
                "command": {
                    "type": "attach_evidence",
                    "preview_id": preview["preview_id"],
                },
            },
        )
        self.assertEqual(status, 200)
        self.assertNotIn("content_base64", view["study"]["evidence"][0])
        self.assertEqual(view["study"]["collections"][0]["unresolved_count"], 1)
        status, view = self.request(
            "POST",
            f"/api/v1/workspaces/{workspace}/save",
            {"draft_buffers": {"target": None, "decision": None}},
        )
        self.assertEqual(status, 200)
        status, preview = self.request(
            "POST",
            "/api/v1/exports",
            {
                "study_id": view["study"]["study_id"],
                "revision_id": revision,
                "kind": "review",
                "collection_ids": [view["study"]["collections"][0]["collection_id"]],
            },
        )
        self.assertEqual(status, 201)
        status, exported = self.request(
            "GET", f"/api/v1/exports/{preview['export_id']}/file"
        )
        self.assertEqual(status, 200)
        self.validator.validate(exported)
        self.assertEqual(
            base64.b64decode(exported["evidence_files"][0]["content_base64"]), evidence
        )

    def test_exchange_constraints_still_reject_invalid_files(self):
        request = json.loads(
            (ROOT / "contracts/examples/request-valid.json").read_text()
        )
        evidence = json.loads(
            (ROOT / "contracts/examples/evidence-valid.json").read_text()
        )
        self.validator.validate(request)
        self.validator.validate(evidence)
        request["revision"]["targets"] = []
        self.assertFalse(self.validator.is_valid(request))
        evidence["candidates"][0]["metrics"][0]["value"] = None
        self.assertFalse(self.validator.is_valid(evidence))

    def test_exchange_rejects_invalid_label_keys_and_values(self):
        request = json.loads(
            (ROOT / "contracts/examples/request-valid.json").read_text()
        )
        valid_labels = request["target_labels"].copy()
        request["target_labels"] = {"not-a-uuid": "Label"}
        self.assertFalse(self.validator.is_valid(request))
        request["target_labels"] = {next(iter(valid_labels)): 17}
        self.assertFalse(self.validator.is_valid(request))
        request["target_labels"] = valid_labels
        self.validator.validate(request)

    def test_workspace_response_requires_nested_fields(self):
        with self.assertRaises(ValidationError):
            WorkspaceView.model_validate({"workspace_id": "bad", "study": {}})


if __name__ == "__main__":
    unittest.main()
