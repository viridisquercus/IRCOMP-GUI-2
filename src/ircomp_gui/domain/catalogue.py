# ************************************************************************
# @file catalogue.py
# @brief Supported references, their contigs and analysis profiles
# @author Lukas (Viridis) Dubsik
# @date 6-11-2026
# @version 0.1
#
# Detailed description:
#  The catalogue is read from contracts/catalogue.json. Only the metadata
#  are known here, the sequences themselves are never checked.
# ************************************************************************

"""Store the supported references and the lengths of their chromosomes."""

from __future__ import annotations

from typing import Annotated

from pydantic import Field, JsonValue

from ircomp_gui.domain.errors import DomainError
from ircomp_gui.domain.models import Value


class Contig(Value):
    """Describe one contig of a reference (metadata only).

    Attributes
    ----------
    accession : str
        Exact accession, such as NC_000001.11
    label : str
        Human readable name, such as chr1
    length : int
        Length of the contig in bases
    """

    accession: str
    label: str
    length: Annotated[int, Field(gt=0)]


class Reference(Value):
    """Describe the supported part of a reference and where it came from."""

    reference_id: str
    category: str
    assembly: str | None
    contigs: list[Contig]
    provenance: dict[str, JsonValue] | None


class Profile(Value):
    """Describe the analysis settings available for some references."""

    profile_id: str
    reference_ids: list[str]
    nuclease: str
    pam: str
    intent: str


class Catalogue(Value):
    """Keep the references and profiles known to the application."""

    catalogue_version: str
    references: list[Reference]
    profiles: list[Profile]

    def reference(self, reference_id: str) -> Reference:
        """Find a reference by its exact catalogue ID.

        Parameters
        ----------
        reference_id : str
            ID of the reference to find

        Returns
        -------
        Reference
            The found reference

        Raises
        ------
        DomainError
            REFERENCE_UNSUPPORTED if there is no such reference
        """
        for item in self.references:
            if item.reference_id == reference_id:
                return item

        raise DomainError(
            "REFERENCE_UNSUPPORTED",
            "Choose an exact supported reference.",
            "/reference_id",
        )

    def profile(self, profile_id: str, reference_id: str) -> Profile:
        """Find a profile and check if it supports the given reference.

        Parameters
        ----------
        profile_id : str
            ID of the profile to find
        reference_id : str
            Reference the profile has to support

        Returns
        -------
        Profile
            The found profile

        Raises
        ------
        DomainError
            PROFILE_UNSUPPORTED if not found or not usable with the reference
        """
        for item in self.profiles:
            if item.profile_id == profile_id and reference_id in item.reference_ids:
                return item

        raise DomainError(
            "PROFILE_UNSUPPORTED",
            "The profile is not supported for this reference.",
            "/profile_id",
        )
