# ************************************************************************
# @file resources.py
# @brief Finding the catalogue and example files
# @author Lukas (Viridis) Dubsik
# @date 6-11-2026
# @version 0.1
#
# Detailed description:
#  When run from the checkout, the files are taken from contracts/.
#  When installed as a wheel, they are copied into the package under
#  resources/ (see force-include in pyproject.toml).
# ************************************************************************

"""Find the catalogue and example files of the project."""

import json
from pathlib import Path

from ircomp_gui.domain.catalogue import Catalogue

# Root of the checkout and of the installed package
REPOSITORY = Path(__file__).resolve().parents[3]
PACKAGE = Path(__file__).resolve().parents[1]


def resource_path(name: str) -> Path:
    """Find a data file in the checkout or in the installed package.

    Parameters
    ----------
    name : str
        Path of the file relative to contracts/

    Returns
    -------
    Path
        Path to the file, the checkout one is preferred
    """
    checkout = REPOSITORY / "contracts" / name
    if checkout.is_file():
        return checkout
    return PACKAGE / "resources" / name


def load_catalogue() -> Catalogue:
    """Read the pinned catalogue, no network is used.

    Returns
    -------
    Catalogue
        The supported references and profiles
    """
    text = resource_path("catalogue.json").read_text(encoding="utf-8")
    return Catalogue.model_validate(json.loads(text))
