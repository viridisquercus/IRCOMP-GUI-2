# ************************************************************************
# @file exchange.py
# @brief Reading of the request and evidence exchange files
# @author Lukas (Viridis) Dubsik
# @date 6-11-2026
# @version 0.1
#
# Detailed description:
#  A file goes through three checks: JSON parsing (serialization.py),
#  the JSON schema (contracts/exchange.schema.json) and then the models
#  and rules. Only a file passing all three is used.
# ************************************************************************

"""Read the request and evidence files in the local JSON format."""

from __future__ import annotations

import base64
import hashlib
import json
from collections.abc import Iterator, Mapping
from typing import Protocol, cast

from jsonschema import Draft202012Validator, FormatChecker
from pydantic import JsonValue, ValidationError

from ircomp_gui.adapters.resources import resource_path
from ircomp_gui.domain.catalogue import Catalogue
from ircomp_gui.domain.errors import DomainError
from ircomp_gui.domain.models import (
    EvidenceBundle,
    EvidenceFile,
    RequestSnapshot,
    Study,
)
from ircomp_gui.domain.rules import validate_bundle, validate_revision
from ircomp_gui.domain.serialization import decode_base64, parse_json


class SchemaValidator(Protocol):
    """Methods of the jsonschema validator used here (it has no types)."""

    def iter_errors(self, instance: object) -> Iterator[object]:
        """Yield the structural violations."""
        ...

    def validate(self, instance: object) -> None:
        """Refuse a structurally invalid document."""
        ...


def checksum(raw: bytes) -> str:
    """Compute the SHA-256 checksum of the bytes.

    Parameters
    ----------
    raw : bytes
        Bytes to hash

    Returns
    -------
    str
        Hexadecimal digest
    """
    return hashlib.sha256(raw).hexdigest()


class Exchange:
    """Read the exchange files and keep the original evidence bytes.

    Attributes
    ----------
    catalogue : Catalogue
        Supported references and profiles
    validator : SchemaValidator
        Validator of the exchange schema
    """

    def __init__(self, catalogue: Catalogue) -> None:
        self.catalogue = catalogue

        schema_text = resource_path("exchange.schema.json").read_text(encoding="utf-8")
        validator = Draft202012Validator(
            json.loads(schema_text), format_checker=FormatChecker()
        )
        self.validator = cast("SchemaValidator", validator)

    def _decode_request(self, document: dict[str, JsonValue]) -> RequestSnapshot:
        request = RequestSnapshot.model_validate(document)
        validate_revision(request.revision, self.catalogue, require_targets=True)

        # Every target needs its label and there can't be labels for others
        target_ids = {target.target_id for target in request.revision.targets}
        if set(request.target_labels) != target_ids:
            raise DomainError(
                "DANGLING_REFERENCE",
                "Request labels must cover its target identities exactly.",
            )
        return request

    def _decode_evidence(self, document: dict[str, JsonValue]) -> EvidenceBundle:
        bundle = EvidenceBundle.model_validate(document)
        validate_bundle(bundle, self.catalogue)
        return bundle

    def decode(self, raw: bytes, kind: str) -> RequestSnapshot | EvidenceBundle:
        """Read the file, then check its schema and the model rules.

        Parameters
        ----------
        raw : bytes
            Original bytes of the file
        kind : str
            Expected kind, request or evidence

        Returns
        -------
        RequestSnapshot | EvidenceBundle
            The parsed file, its type depends on kind

        Raises
        ------
        DomainError
            If any of the checks fails
        """
        document = parse_json(raw)

        # Check the version and kind first, so the error says what is wrong
        if document.get("format_version") != "1.0":
            raise DomainError(
                "VERSION_UNSUPPORTED", "Only local exchange version 1.0 is supported."
            )
        if document.get("kind") != kind:
            raise DomainError("SCHEMA_INVALID", f"Choose a {kind} file.")

        # Then the JSON schema
        errors = list(self.validator.iter_errors(document))
        if errors:
            raise DomainError(
                "SCHEMA_INVALID", "The file does not match the local exchange schema."
            )

        # And lastly the models and rules
        try:
            if kind == "request":
                return self._decode_request(document)
            return self._decode_evidence(document)
        except ValidationError as error:
            raise DomainError(
                "SCHEMA_INVALID", "The file contains unsupported field values."
            ) from error

    def verify_sources(self, study: Study) -> None:
        """Check the retained evidence before saving or after loading.

        Parameters
        ----------
        study : Study
            Study whose evidence is checked

        Raises
        ------
        DomainError
            If the stored bytes, checksum and parsed bundle don't agree
        """
        for item in study.evidence:
            raw = decode_base64(item.content_base64)
            decoded = self.decode(raw, "evidence")
            if decoded != item.bundle or checksum(raw) != item.sha256:
                raise DomainError(
                    "SCHEMA_INVALID",
                    "Stored evidence bytes, digest or parsed contents disagree.",
                )

    def evidence_file(self, raw: bytes, bundle: EvidenceBundle) -> EvidenceFile:
        """Keep the imported bytes unchanged together with their checksum.

        Parameters
        ----------
        raw : bytes
            Original bytes of the file
        bundle : EvidenceBundle
            Bundle parsed from the bytes

        Returns
        -------
        EvidenceFile
            File ready to be attached to the study
        """
        return EvidenceFile(
            bundle=bundle,
            sha256=checksum(raw),
            content_base64=base64.b64encode(raw).decode("ascii"),
        )

    def validate_document(self, document: Mapping[str, object]) -> None:
        """Check the generated JSON document before it is exported.

        Parameters
        ----------
        document : Mapping
            Document to be exported
        """
        self.validator.validate(document)
