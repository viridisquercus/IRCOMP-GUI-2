# ************************************************************************
# @file generate_contracts.py
# @brief Generation of the exchange schema and browser types from Python
# @author Lukas (Viridis) Dubsik
# @version 0.1
#
# Detailed description:
#  The Python models are the only place where the data are defined. This
#  script writes from them:
#   - contracts/exchange.schema.json  (schema of the exchange files)
#   - web/src/shared/types.generated.ts  (TypeScript types for the client)
#   - web/src/shared/constants.generated.ts  (the MAX_* limits)
#  Run it with `make contracts` after changing the models, `make check`
#  runs it with --check and fails if the files are out of date.
# ************************************************************************

"""Generate the exchange schema and browser types from the Python models."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

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
WEB_SHARED = ROOT / "web/src/shared"
PRETTIER = ROOT / "web/node_modules/.bin/prettier"

# Name of the TypeScript type -> Python model it is made from
BROWSER_TYPES: dict[str, Any] = {
    "Catalogue": CatalogueView,
    "Workspace": WorkspaceView,
    "StudyList": StudyList,
    "ImportPreview": ImportPreviewView,
    "ExportPreview": ExportPreviewView,
    "Validation": ValidationView,
    "ErrorResponse": ErrorResponse,
    "Command": Command,
    "Bundle": EvidenceBundle,
    "Study": StudyView,
    "Collection": CollectionView,
}
# Plain JSON types and their TypeScript names
SIMPLE_TYPES = {
    "string": "string",
    "number": "number",
    "integer": "number",
    "boolean": "boolean",
    "null": "null",
}

Schema = dict[str, Any]


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
def prepare_schema(schema: Schema) -> Schema:
    """Make the typed dictionaries strict, in the whole schema.

    Pydantic writes dict[Id, Label] as patternProperties, which still lets
    keys not matching the pattern through. It is changed to propertyNames
    plus additionalProperties, so a wrong key is refused too.

    Parameters
    ----------
    schema : Schema
        Schema to change (it is changed in place)

    Returns
    -------
    Schema
        The same schema
    """
    patterns = schema.pop("patternProperties", None)
    if patterns:
        if len(patterns) != 1:
            raise ValueError("Expected one key constraint for a typed dictionary")
        pattern, value = next(iter(patterns.items()))
        schema["propertyNames"] = {"type": "string", "pattern": pattern}
        schema["additionalProperties"] = value

    # Then go through all the nested schemas
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


def exchange_schema() -> Schema:
    """Build the schema of the request, evidence and review files.

    Returns
    -------
    Schema
        The schema written into contracts/exchange.schema.json
    """
    union = RequestSnapshot | EvidenceBundle | ReviewPackage
    schema = prepare_schema(TypeAdapter(union).json_schema(mode="serialization"))
    schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    schema["$id"] = (
        "https://viridisquercus.github.io/IRCOMP-GUI/contracts/exchange-1.0.schema.json"
    )
    schema["title"] = "IRCOMP-GUI local exchange 1.0"
    schema["description"] = "Generated from the Python models. Domain rules also apply."

    # Rules only for the files - a working revision may still have no targets
    defs = schema["$defs"]
    request = defs["RequestSnapshot"]["properties"]
    request["revision"] = {
        "allOf": [request["revision"], {"properties": {"targets": {"minItems": 1}}}]
    }
    request["target_labels"]["maxProperties"] = limits.MAX_TARGETS

    # A metric has a value exactly when it says it is present
    defs["Metric"]["allOf"] = [
        {
            "if": {"properties": {"availability": {"const": "present"}}},
            "then": {"properties": {"value": {"type": "number"}}},
            "else": {"properties": {"value": {"type": "null"}}},
        }
    ]
    # A review without unfinished decisions is reviewed, otherwise a draft
    defs["ReviewPackage"]["allOf"] = [
        {
            "if": {"properties": {"unresolved_count": {"const": 0}}},
            "then": {"properties": {"review_status": {"const": "reviewed"}}},
            "else": {"properties": {"review_status": {"const": "draft"}}},
        }
    ]
    return schema


# ---------------------------------------------------------------------------
# TypeScript
# ---------------------------------------------------------------------------
def ts_type(schema: Schema) -> str:
    """Translate one JSON schema into a TypeScript type.

    Parameters
    ----------
    schema : Schema
        Schema to translate

    Returns
    -------
    str
        The TypeScript type
    """
    if "$ref" in schema:
        return schema["$ref"].rsplit("/", 1)[1]
    if "const" in schema:
        return json.dumps(schema["const"])
    if "enum" in schema:
        return " | ".join(json.dumps(item) for item in schema["enum"])
    for keyword in ("anyOf", "oneOf"):
        if keyword in schema:
            # dict.fromkeys removes duplicates and keeps the order
            options = dict.fromkeys(ts_type(item) for item in schema[keyword])
            return " | ".join(options)

    kind = schema.get("type")
    if kind == "array":
        return f"Array<{ts_type(schema['items'])}>"
    if kind == "object":
        return ts_object(schema)
    if kind in SIMPLE_TYPES:
        return SIMPLE_TYPES[kind]
    if not schema:
        return "unknown"
    raise ValueError(f"Unsupported TypeScript schema: {schema}")


def ts_object(schema: Schema) -> str:
    """Translate an object schema - either a class or a dictionary.

    Parameters
    ----------
    schema : Schema
        Schema with type object

    Returns
    -------
    str
        The TypeScript type
    """
    # Class with named fields, the not required ones are optional
    fields = schema.get("properties", {})
    if fields:
        required = schema.get("required", [])
        text = "{ "
        for name, item in fields.items():
            optional = "" if name in required else "?"
            text += f"{json.dumps(name)}{optional}: {ts_type(item)}; "
        return text + "}"

    # Dictionary, the values are described by additionalProperties
    extra = schema.get("additionalProperties", {})
    value = ts_type(extra) if isinstance(extra, dict) else "unknown"
    return f"Record<string, {value}>"


def browser_types() -> str:
    """Write the TypeScript types of all the data the client works with.

    Returns
    -------
    str
        Contents of types.generated.ts (not formatted yet)
    """
    definitions: dict[str, Schema] = {}
    roots: dict[str, Schema] = {}
    for name, model in BROWSER_TYPES.items():
        schema = prepare_schema(TypeAdapter(model).json_schema(mode="serialization"))

        # Collect the shared definitions, the same name has to mean the same
        for key, value in schema.pop("$defs", {}).items():
            if key in definitions and definitions[key] != value:
                raise ValueError(f"Conflicting definition: {key}")
            definitions[key] = value

        # A class is a definition of its own, the name is only an alias of it
        if isinstance(model, type):
            definitions[model.__name__] = schema
            roots[name] = {"$ref": f"#/$defs/{model.__name__}"}
        else:
            roots[name] = schema

    # Commands are input of the browser, so the defaulted fields may be left
    # out there (everything else is output, where they are always present)
    command = prepare_schema(TypeAdapter(Command).json_schema(mode="validation"))
    for key, schema in command.pop("$defs", {}).items():
        definitions.setdefault(key, schema)
    roots["Command"] = command

    text = "// Generated by scripts/generate_contracts.py. Edit the Python models instead.\n"
    for name, schema in sorted(definitions.items()):
        text += f"export type {name} = {ts_type(schema)};\n"
    for name, schema in roots.items():
        # Skip the aliases with the same name as their class
        if name not in definitions:
            text += f"export type {name} = {ts_type(schema)};\n"
    return text


def browser_constants() -> str:
    """Write the MAX_* limits for the client.

    Returns
    -------
    str
        Contents of constants.generated.ts (not formatted yet)
    """
    text = "// Generated from ircomp_gui.domain.constants.\n"
    for name, value in sorted(vars(limits).items()):
        if name.startswith("MAX_"):
            text += f"export const {name} = {value};\n"
    return text


def prettier(path: Path, text: str) -> str:
    """Format the TypeScript the same way as the rest of the client.

    Parameters
    ----------
    path : Path
        Where the file will be written (Prettier picks its settings by it)
    text : str
        Unformatted contents

    Returns
    -------
    str
        Formatted contents
    """
    result = subprocess.run(  # noqa: S603 - only our own Prettier is run
        [str(PRETTIER), "--stdin-filepath", str(path)],
        input=text,
        text=True,
        capture_output=True,
        check=True,
    )
    return result.stdout


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def generate() -> dict[Path, str]:
    """Generate all the files.

    Returns
    -------
    dict[Path, str]
        Contents of every generated file by its path
    """
    output = {
        ROOT / "contracts/exchange.schema.json": json.dumps(exchange_schema(), indent=2)
        + "\n"
    }
    types_path = WEB_SHARED / "types.generated.ts"
    constants_path = WEB_SHARED / "constants.generated.ts"
    output[types_path] = prettier(types_path, browser_types())
    output[constants_path] = prettier(constants_path, browser_constants())
    return output


def main() -> None:
    """Write the generated files, or with --check only compare them."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    stale: list[str] = []
    for path, text in generate().items():
        if not args.check:
            path.write_text(text)
        elif not path.exists() or path.read_text() != text:
            stale.append(str(path.relative_to(ROOT)))

    if stale:
        parser.exit(1, "Regenerate contracts: " + ", ".join(stale) + "\n")


if __name__ == "__main__":
    main()
