# /************************************************************************
# Name: Lukas (Viridis) Dubsik
# ************************************************************************/

"""Define the data received from the web client."""

from typing import Annotated, Literal

from pydantic import Field

from ircomp_gui.application.commands import Command
from ircomp_gui.domain.models import DraftBuffers, Id, Label, TargetDraft, Value


class NewWorkspace(Value):
    """Create an independently usable local request."""

    source: Literal["new"]
    title: Label


class SavedWorkspace(Value):
    """Open a durable study in a separate session."""

    source: Literal["saved"]
    study_id: Id


class DuplicateWorkspace(Value):
    """Duplicate only the active request."""

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


class CommandInput(Value):
    """Receive a study operation and the current editor text."""

    draft_buffers: DraftBuffers
    command: Command


class SaveInput(Value):
    """Explicit Save of accepted data and current editor buffers."""

    draft_buffers: DraftBuffers


class CloseInput(Value):
    """Explicit confirmation of working-copy discard."""

    discard: Literal[True]


class ValidateInput(Value):
    """Local validation only, including a separate unapplied editor buffer."""

    revision_id: Id
    target_draft: TargetDraft | None


class RequestImport(Value):
    """Exact request bytes, base64 encoded for JSON transport."""

    kind: Literal["request"]
    content_base64: Annotated[str, Field(max_length=1398104)]


class EvidenceImport(Value):
    """Exact evidence bytes and explicitly selected request context."""

    kind: Literal["evidence"]
    content_base64: Annotated[str, Field(max_length=1398104)]
    workspace_id: Id
    revision_id: Id


ImportInput = Annotated[RequestImport | EvidenceImport, Field(discriminator="kind")]


class ExportInput(Value):
    """Select saved request or review data for an export."""

    study_id: Id
    revision_id: Id
    kind: Literal["request", "review"]
    collection_ids: Annotated[list[Id], Field(max_length=20)]
