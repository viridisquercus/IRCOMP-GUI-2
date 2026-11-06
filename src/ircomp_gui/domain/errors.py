# /************************************************************************
# Name: Lukas (Viridis) Dubsik
# ************************************************************************/

"""Pass error information from the model to the user interface."""

from __future__ import annotations

from ircomp_gui.domain.models import Diagnostic


class DomainError(Exception):
    """Report an operation error with a code, message and optional field."""

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
        self.diagnostics = (
            diagnostics
            if diagnostics is not None
            else [Diagnostic(code=code, message=message, location=location)]
        )
