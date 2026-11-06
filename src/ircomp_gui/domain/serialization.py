# ************************************************************************
# @file serialization.py
# @brief Reading and writing of the JSON files
# @author Lukas (Viridis) Dubsik
# @date 6-11-2026
# @version 0.1
#
# Detailed description:
#  The standard json module accepts duplicate keys, NaN and Infinity.
#  None of these can be represented in the exchange format, so they are
#  refused here before the data reach the models.
# ************************************************************************

"""Read and write the JSON files used by the application."""

from __future__ import annotations

import base64
import binascii
import json
import math
from collections.abc import Mapping
from typing import cast

from pydantic import JsonValue

from ircomp_gui.domain.constants import (
    MAX_BASE64,
    MAX_DEPTH,
    MAX_DOCUMENT,
    MAX_FILE,
)
from ircomp_gui.domain.errors import DomainError


def _refuse_duplicates(pairs: list[tuple[str, JsonValue]]) -> dict[str, JsonValue]:
    # Build the object ourselves so the duplicate key is noticed
    result: dict[str, JsonValue] = {}
    for key, value in pairs:
        if key in result:
            raise DomainError("DUPLICATE_KEY", "JSON contains a duplicate object key.")
        result[key] = value
    return result


def _refuse_nonfinite(_value: str) -> None:
    # Called by json for NaN, Infinity and -Infinity
    raise DomainError("SCHEMA_INVALID", "Nonfinite numbers are not supported.")


def _check_depth(document: dict[str, JsonValue]) -> None:
    # Go through the document without recursion, so deep nesting can't crash it
    stack: list[tuple[JsonValue, int]] = [(document, 1)]
    while stack:
        value, depth = stack.pop()
        if depth > MAX_DEPTH:
            raise DomainError("LIMIT_EXCEEDED", "JSON nesting exceeds 32 levels.")

        if isinstance(value, dict):
            for child in value.values():
                stack.append((child, depth + 1))
        elif isinstance(value, list):
            for child in value:
                stack.append((child, depth + 1))
        elif isinstance(value, float) and not math.isfinite(value):
            raise DomainError("SCHEMA_INVALID", "Nonfinite numbers are not supported.")


def parse_json(raw: bytes, *, limit: int = MAX_FILE) -> dict[str, JsonValue]:
    """Read a JSON object and refuse unsupported size, nesting or values.

    Parameters
    ----------
    raw : bytes
        Bytes of the file, expected to be UTF-8
    limit : int
        Max allowed size in bytes

    Returns
    -------
    dict
        The parsed JSON object

    Raises
    ------
    DomainError
        If the file is too big, not valid JSON or not an object
    """
    # Check the size first, before anything is decoded
    if len(raw) > limit:
        raise DomainError("LIMIT_EXCEEDED", "Input exceeds the supported byte limit.")

    try:
        document = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_refuse_duplicates,
            parse_constant=_refuse_nonfinite,
        )
    except (ValueError, UnicodeError, RecursionError) as error:
        raise DomainError(
            "MALFORMED_JSON", "Choose a valid UTF-8 JSON object."
        ) from error

    # Only objects are accepted on the top level
    if not isinstance(document, dict):
        raise DomainError("SCHEMA_INVALID", "The file must contain a JSON object.")

    document = cast("dict[str, JsonValue]", document)
    _check_depth(document)
    return document


def decode_base64(content: str) -> bytes:
    """Check the size of the file and decode its base64 data.

    Parameters
    ----------
    content : str
        Base64 encoded file

    Returns
    -------
    bytes
        Decoded bytes of the file

    Raises
    ------
    DomainError
        If the file is bigger than MAX_FILE or not valid base64
    """
    # Refuse a too long text before decoding it
    if len(content) > MAX_BASE64:
        raise DomainError("LIMIT_EXCEEDED", "Import files must be at most 1 MiB.")

    try:
        raw = base64.b64decode(content, validate=True)
    except (binascii.Error, ValueError) as error:
        raise DomainError("INVALID_BASE64", "File encoding is invalid.") from error

    if len(raw) > MAX_FILE:
        raise DomainError("LIMIT_EXCEEDED", "Import files must be at most 1 MiB.")
    return raw


def encode_json(document: Mapping[str, object]) -> bytes:
    """Write the JSON in a fixed form and check the size of the result.

    Parameters
    ----------
    document : Mapping
        Object to be written

    Returns
    -------
    bytes
        UTF-8 encoded JSON ending with a newline

    Raises
    ------
    DomainError
        If the result is bigger than MAX_DOCUMENT
    """
    text = json.dumps(document, ensure_ascii=False, indent=2, allow_nan=False)
    raw = (text + "\n").encode("utf-8")

    if len(raw) > MAX_DOCUMENT:
        raise DomainError("LIMIT_EXCEEDED", "The resulting document exceeds 20 MiB.")
    return raw
