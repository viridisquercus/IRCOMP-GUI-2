# ************************************************************************
# @file errors.py
# @brief Error passed from the model up to the user interface
# @author Lukas (Viridis) Dubsik
# @version 0.1
# ************************************************************************

"""Pass the error information from the model to the user interface."""

from __future__ import annotations

from ircomp_gui.domain.models import Diagnostic


class DomainError(Exception):
    """Report an error of an operation with its code, message and field.

    Attributes
    ----------
    code : str
        Error code, the API chooses the HTTP status from it
    message : str
        Text shown to the user
    diagnostics : list[Diagnostic]
        Detailed problems, by default only the one described by code and message
    """

    def __init__(
        self,
        code: str,
        message: str,
        location: str | None = None,
        *,
        diagnostics: list[Diagnostic] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message

        # If no detailed problems were given, create one from the error itself
        if diagnostics is None:
            diagnostics = [Diagnostic(code=code, message=message, location=location)]
        self.diagnostics = diagnostics
