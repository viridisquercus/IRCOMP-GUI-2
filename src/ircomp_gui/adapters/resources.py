# /************************************************************************
# Name: Lukas (Viridis) Dubsik
# ************************************************************************/

"""Find the catalogue and example files in the installed project."""

import json
from pathlib import Path

from ircomp_gui.domain.catalogue import Catalogue


def resource_path(name: str) -> Path:
    """Find a data file in the checkout or the installed Python package."""
    repository = Path(__file__).resolve().parents[3] / "contracts" / name
    return (
        repository
        if repository.is_file()
        else Path(__file__).resolve().parents[1] / "resources" / name
    )


def load_catalogue() -> Catalogue:
    """Read the pinned catalogue without a network operation."""
    return Catalogue.model_validate(
        json.loads(resource_path("catalogue.json").read_text(encoding="utf-8"))
    )
