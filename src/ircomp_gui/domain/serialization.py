# /************************************************************************
# Name: Lukas (Viridis) Dubsik
# ************************************************************************/

"""Read and write the JSON files used by the application."""

from __future__ import annotations

import base64
import binascii
import json
import math
from collections.abc import Mapping
from typing import cast

from pydantic import JsonValue

from ircomp_gui.domain.errors import DomainError

MAX_FILE = 1024 * 1024
MAX_DOCUMENT = 20 * 1024 * 1024


def _pairs(pairs: list[tuple[str, JsonValue]]) -> dict[str, JsonValue]:
    result: dict[str, JsonValue] = {}
    for key, value in pairs:
        if key in result:
            raise DomainError("DUPLICATE_KEY", "JSON contains a duplicate object key.")
        result[key] = value
    return result


def _nonfinite(value: str) -> None:
    raise DomainError("SCHEMA_INVALID", "Nonfinite numbers are not supported.")


def parse_json(raw: bytes, *, limit: int = MAX_FILE) -> dict[str, JsonValue]:
    """Read a JSON object and reject unsupported size, nesting or values."""
    if len(raw) > limit:
        raise DomainError("LIMIT_EXCEEDED", "Input exceeds the supported byte limit.")
    try:
        document = json.loads(
            raw.decode("utf-8"), object_pairs_hook=_pairs, parse_constant=_nonfinite
        )
    except (ValueError, UnicodeError, RecursionError) as error:
        raise DomainError(
            "MALFORMED_JSON", "Choose a valid UTF-8 JSON object."
        ) from error
    if not isinstance(document, dict):
        raise DomainError("SCHEMA_INVALID", "The file must contain a JSON object.")
    stack: list[tuple[JsonValue, int]] = [(document, 1)]
    while stack:
        value, depth = stack.pop()
        if depth > 32:
            raise DomainError("LIMIT_EXCEEDED", "JSON nesting exceeds 32 levels.")
        if isinstance(value, dict):
            stack.extend((child, depth + 1) for child in value.values())
        elif isinstance(value, list):
            stack.extend((child, depth + 1) for child in value)
        elif isinstance(value, float) and not math.isfinite(value):
            raise DomainError("SCHEMA_INVALID", "Nonfinite numbers are not supported.")
    return cast("dict[str, JsonValue]", document)


def decode_base64(content: str) -> bytes:
    """Check the file size and decode the base64 data."""
    if len(content) > 4 * ((MAX_FILE + 2) // 3):
        raise DomainError("LIMIT_EXCEEDED", "Import files must be at most 1 MiB.")
    try:
        raw = base64.b64decode(content, validate=True)
    except (binascii.Error, ValueError) as error:
        raise DomainError("INVALID_BASE64", "File encoding is invalid.") from error
    if len(raw) > MAX_FILE:
        raise DomainError("LIMIT_EXCEEDED", "Import files must be at most 1 MiB.")
    return raw


def encode_json(document: Mapping[str, object]) -> bytes:
    """Write JSON in a fixed order and check the resulting file size."""
    raw = (
        json.dumps(document, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    ).encode("utf-8")
    if len(raw) > MAX_DOCUMENT:
        raise DomainError("LIMIT_EXCEEDED", "The resulting document exceeds 20 MiB.")
    return raw
