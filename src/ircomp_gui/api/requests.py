# ************************************************************************
# @file requests.py
# @brief Bodies of the HTTP requests sent by the web client
# @author Lukas (Viridis) Dubsik
# @version 0.1
# ************************************************************************

"""Define the data received from the web client."""

from typing import Annotated, Literal

from pydantic import Field

from ircomp_gui.application.commands import Command
from ircomp_gui.domain.constants import MAX_BASE64, MAX_COLLECTIONS
from ircomp_gui.domain.models import DraftBuffers, Id, Label, TargetDraft, Value

# ---------------------------------------------------------------------------
# Opening of a workspace - the source field says from what
# ---------------------------------------------------------------------------


class NewWorkspace(Value):
    """Create a new empty request."""

    source: Literal["new"]
    title: Label


class SavedWorkspace(Value):
    """Open a saved study in a new session."""

    source: Literal["saved"]
    study_id: Id


class DuplicateWorkspace(Value):
    """Duplicate only the active request of a session."""

    source: Literal["duplicate"]
    workspace_id: Id
    title: Label


class ImportedWorkspace(Value):
    """Accept a ready request preview."""

    source: Literal["request_import"]
    preview_id: Id


CreateInput = Annotated[
    NewWorkspace | SavedWorkspace | DuplicateWorkspace | ImportedWorkspace,
    Field(discriminator="source"),
]

# ---------------------------------------------------------------------------
# Work in a workspace
# ---------------------------------------------------------------------------


class CommandInput(Value):
    """Receive a study operation together with the current editor text."""

    draft_buffers: DraftBuffers
    command: Command


class SaveInput(Value):
    """Save the accepted data and the current editor text."""

    draft_buffers: DraftBuffers


class CloseInput(Value):
    """Confirm that the working copy can be thrown away."""

    discard: Literal[True]


class ValidateInput(Value):
    """Run the local checks, the unapplied editor text is checked apart."""

    revision_id: Id
    target_draft: TargetDraft | None


# ---------------------------------------------------------------------------
# Import and export
# ---------------------------------------------------------------------------


class RequestImport(Value):
    """Exact bytes of a request file, base64 encoded for JSON."""

    kind: Literal["request"]
    content_base64: Annotated[str, Field(max_length=MAX_BASE64)]


class EvidenceImport(Value):
    """Exact bytes of an evidence file and the request it is meant for."""

    kind: Literal["evidence"]
    content_base64: Annotated[str, Field(max_length=MAX_BASE64)]
    workspace_id: Id
    revision_id: Id


ImportInput = Annotated[RequestImport | EvidenceImport, Field(discriminator="kind")]


class ExportInput(Value):
    """Choose the saved request or review data to export."""

    study_id: Id
    revision_id: Id
    kind: Literal["request", "review"]
    collection_ids: Annotated[list[Id], Field(max_length=MAX_COLLECTIONS)]
