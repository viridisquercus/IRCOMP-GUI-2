"""Generate exchange schemas and browser types from the Python models."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from pydantic import TypeAdapter

from ircomp_gui.application.commands import Command
from ircomp_gui.application.responses import (
    CatalogueView,
    CollectionView,
    ErrorResponse,
    ExportPreviewView,
    ImportPreviewView,
    StudyList,
    StudyView,
    ValidationView,
    WorkspaceView,
)
from ircomp_gui.domain import constants as limits
from ircomp_gui.domain.models import EvidenceBundle, RequestSnapshot, ReviewPackage

ROOT = Path(__file__).resolve().parents[1]
RESPONSES = {
    "Catalogue": CatalogueView,
    "Workspace": WorkspaceView,
    "StudyList": StudyList,
    "ImportPreview": ImportPreviewView,
    "ExportPreview": ExportPreviewView,
    "Validation": ValidationView,
    "ErrorResponse": ErrorResponse,
}


def prepare_schema(schema: dict) -> dict:
    """Normalize keyed maps and stop if the browser cannot check a new keyword."""
    allowed = {
        "$ref",
        "$defs",
        "type",
        "const",
        "enum",
        "anyOf",
        "oneOf",
        "properties",
        "required",
        "additionalProperties",
        "propertyNames",
        "patternProperties",
        "items",
        "minItems",
        "maxItems",
        "minLength",
        "maxLength",
        "pattern",
        "minimum",
        "maximum",
        "exclusiveMinimum",
        "exclusiveMaximum",
        "title",
        "description",
        "default",
        "discriminator",
    }
    unsupported = set(schema) - allowed
    if unsupported:
        raise ValueError(f"Browser validation needs support for {unsupported}")
    patterns = schema.pop("patternProperties", None)
    if patterns:
        if len(patterns) != 1:
            raise ValueError("Expected one key constraint for a typed dictionary")
        pattern, value = next(iter(patterns.items()))
        schema["propertyNames"] = {"type": "string", "pattern": pattern}
        schema["additionalProperties"] = value
    for name in ("$defs", "properties"):
        for child in schema.get(name, {}).values():
            prepare_schema(child)
    for name in ("anyOf", "oneOf"):
        for child in schema.get(name, []):
            prepare_schema(child)
    for name in ("additionalProperties", "propertyNames", "items"):
        if isinstance(schema.get(name), dict):
            prepare_schema(schema[name])
    return schema


def ts_type(schema: dict) -> str:
    if "$ref" in schema:
        return schema["$ref"].rsplit("/", 1)[1]
    if "const" in schema:
        return json.dumps(schema["const"])
    if "enum" in schema:
        return " | ".join(json.dumps(item) for item in schema["enum"])
    for keyword in ("anyOf", "oneOf"):
        if keyword in schema:
            return " | ".join(dict.fromkeys(ts_type(item) for item in schema[keyword]))
    kind = schema.get("type")
    if kind == "array":
        return f"Array<{ts_type(schema['items'])}>"
    if kind == "object":
        fields = schema.get("properties", {})
        if fields:
            required = schema.get("required", [])
            return (
                "{ "
                + " ".join(
                    f"{json.dumps(name)}{'' if name in required else '?'}: {ts_type(item)};"
                    for name, item in fields.items()
                )
                + " }"
            )
        patterns = schema.get("patternProperties", {})
        if patterns:
            return (
                "Record<string, "
                + " | ".join(dict.fromkeys(ts_type(item) for item in patterns.values()))
                + ">"
            )
        extra = schema.get("additionalProperties", {})
        return (
            "Record<string, "
            + (ts_type(extra) if isinstance(extra, dict) else "unknown")
            + ">"
        )
    types = {
        "string": "string",
        "number": "number",
        "integer": "number",
        "boolean": "boolean",
        "null": "null",
    }
    if kind in types:
        return types[kind]
    if not schema:
        return "unknown"
    raise ValueError(f"Unsupported TypeScript schema: {schema}")


def generate() -> dict[Path, str]:
    definitions = {}
    roots = {}
    for name, model in {
        **RESPONSES,
        "Command": Command,
        "Bundle": EvidenceBundle,
        "Study": StudyView,
        "Collection": CollectionView,
    }.items():
        schema = prepare_schema(TypeAdapter(model).json_schema(mode="serialization"))
        for key, value in schema.pop("$defs", {}).items():
            if key in definitions and definitions[key] != value:
                raise ValueError(f"Conflicting definition: {key}")
            definitions[key] = value
        if isinstance(model, type):
            definitions[model.__name__] = schema
            roots[name] = {"$ref": f"#/$defs/{model.__name__}"}
        else:
            roots[name] = schema
    # Commands are browser input, so defaulted fields may be omitted.
    command = prepare_schema(TypeAdapter(Command).json_schema(mode="validation"))
    for key, schema in command.pop("$defs", {}).items():
        if key not in definitions:
            definitions[key] = schema
    roots["Command"] = command

    types = "// Generated by scripts/generate_contracts.py. Edit the Python models instead.\n"
    for name, schema in sorted(definitions.items()):
        types += f"export type {name} = {ts_type(schema)};\n"
    for name, schema in roots.items():
        if name not in definitions:
            types += f"export type {name} = {ts_type(schema)};\n"
    types += (
        "export type ResponseTypes = {\n"
        + "".join(f"{name}: {name};\n" for name in RESPONSES)
        + "};\n"
    )
    runtime = "// Generated by scripts/generate_contracts.py.\n"
    runtime += "import type { Schema } from './responseValidation';\n"
    runtime += (
        "export const definitions: Record<string, Schema> = "
        + json.dumps(definitions, indent=2)
        + ";\n"
    )
    runtime += (
        "export const responseSchemas = "
        + json.dumps({k: roots[k] for k in RESPONSES}, indent=2)
        + " satisfies Record<string, Schema>;\n"
    )
    constants = "// Generated from ircomp_gui.domain.constants.\n" + "".join(
        f"export const {name} = {value};\n"
        for name, value in sorted(vars(limits).items())
        if name.startswith("MAX_")
    )

    exchange = TypeAdapter(
        RequestSnapshot | EvidenceBundle | ReviewPackage
    ).json_schema(mode="serialization")
    exchange["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    exchange["$id"] = (
        "https://viridisquercus.github.io/IRCOMP-GUI/contracts/exchange-1.0.schema.json"
    )
    exchange["title"] = "IRCOMP-GUI local exchange 1.0"
    exchange["description"] = (
        "Generated from the Python models. Domain rules also apply."
    )
    defs = exchange["$defs"]
    # File-only requirements; a working revision may still have no targets.
    request = defs["RequestSnapshot"]["properties"]
    request["revision"] = {
        "allOf": [request["revision"], {"properties": {"targets": {"minItems": 1}}}]
    }
    request["target_labels"]["maxProperties"] = limits.MAX_TARGETS
    defs["Metric"]["allOf"] = [
        {
            "if": {"properties": {"availability": {"const": "present"}}},
            "then": {"properties": {"value": {"type": "number"}}},
            "else": {"properties": {"value": {"type": "null"}}},
        }
    ]
    defs["ReviewPackage"]["allOf"] = [
        {
            "if": {"properties": {"unresolved_count": {"const": 0}}},
            "then": {"properties": {"review_status": {"const": "reviewed"}}},
            "else": {"properties": {"review_status": {"const": "draft"}}},
        }
    ]
    output = {
        ROOT / "contracts/exchange.schema.json": json.dumps(exchange, indent=2) + "\n"
    }
    for name, text in [
        ("types.generated.ts", types),
        ("schemas.generated.ts", runtime),
        ("constants.generated.ts", constants),
    ]:
        path = ROOT / "web/src/shared" / name
        formatter = ROOT / "web/node_modules/.bin/prettier"
        formatted = subprocess.run(
            [str(formatter), "--stdin-filepath", str(path)],
            input=text,
            text=True,
            capture_output=True,
            check=True,
        ).stdout
        output[path] = formatted
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    arguments = parser.parse_args()
    stale = []
    for path, text in generate().items():
        if arguments.check:
            if not path.exists() or path.read_text() != text:
                stale.append(str(path.relative_to(ROOT)))
        else:
            path.write_text(text)
    if stale:
        parser.exit(1, "Regenerate contracts: " + ", ".join(stale) + "\n")


if __name__ == "__main__":
    main()
