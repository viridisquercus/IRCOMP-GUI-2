# /************************************************************************
# Name: Lukas (Viridis) Dubsik
# ************************************************************************/

"""Store the supported references and their chromosome lengths."""

from __future__ import annotations

from typing import Annotated

from pydantic import Field, JsonValue

from ircomp_gui.domain.errors import DomainError
from ircomp_gui.domain.models import Value


class Contig(Value):
    """Metadata only; sequence content is not verified."""

    accession: str
    label: str
    length: Annotated[int, Field(gt=0)]


class Reference(Value):
    """Describe the supported part of a reference and where its metadata came from."""

    reference_id: str
    category: str
    assembly: str | None
    contigs: list[Contig]
    provenance: dict[str, JsonValue] | None


class Profile(Value):
    """Describe the analysis settings selected for a supported reference."""

    profile_id: str
    reference_ids: list[str]
    nuclease: str
    pam: str
    intent: str


class Catalogue(Value):
    """Keep the reference and analysis profile definitions used by the model."""

    catalogue_version: str
    references: list[Reference]
    profiles: list[Profile]

    def reference(self, reference_id: str) -> Reference:
        """Find a reference by its exact catalogue ID."""
        for item in self.references:
            if item.reference_id == reference_id:
                return item
        raise DomainError(
            "REFERENCE_UNSUPPORTED",
            "Choose an exact supported reference.",
            "/reference_id",
        )

    def profile(self, profile_id: str, reference_id: str) -> Profile:
        """Find a profile and check whether it supports the reference."""
        for item in self.profiles:
            if item.profile_id == profile_id and reference_id in item.reference_ids:
                return item
        raise DomainError(
            "PROFILE_UNSUPPORTED",
            "The profile is not supported for this reference.",
            "/profile_id",
        )
