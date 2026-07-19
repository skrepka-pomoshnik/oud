from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING

from oud.editor.messages import MessageLevel
from petrucci.duet_score import is_duet_score_piece
from petrucci.model import Piece

if TYPE_CHECKING:
    from oud.editor.state import EditorState


class DocumentMode(StrEnum):
    NATIVE = "native"
    IMPORTED_PROJECTION = "imported-projection"
    IMPORTED_READ_ONLY = "imported-read-only"


def source_format(path: str | None) -> str:
    if path is None:
        return "new"
    lowered = path.lower()
    if lowered.endswith(".tab"):
        return "tab"
    if lowered.endswith((".musicxml", ".xml")):
        return "musicxml"
    if lowered.endswith(".mxl"):
        return "mxl"
    return "ft3"


def _has_non_tab_score_content(piece: Piece) -> bool:
    imported = piece.imported_score
    return bool(imported and imported.staffs) or is_duet_score_piece(piece)


def classify_document(path: str | None, piece: Piece) -> DocumentMode:
    fmt = source_format(path)
    if fmt in {"new", "tab"}:
        return DocumentMode.NATIVE
    if fmt == "ft3" and _has_non_tab_score_content(piece):
        return DocumentMode.IMPORTED_READ_ONLY
    return DocumentMode.IMPORTED_PROJECTION


def configure_document(
    state: EditorState,
    path: str | None,
    *,
    forced_read_only: bool = False,
) -> None:
    state.path = path
    state.source_format = source_format(path)
    state.document_mode = classify_document(path, state.piece)
    state.write_path = path if state.source_format == "tab" else None
    state.forced_read_only = forced_read_only
    state.read_only = forced_read_only or state.document_mode is DocumentMode.IMPORTED_READ_ONLY
    state.pending_overwrite_path = None
    state.view_staff_index = 0

    if forced_read_only:
        state.persistent_notice = "Read-only viewer"
        state.persistent_notice_level = MessageLevel.WARNING
    elif state.document_mode is DocumentMode.IMPORTED_READ_ONLY:
        state.persistent_notice = ""
        state.persistent_notice_level = MessageLevel.INFO
    elif state.document_mode is DocumentMode.IMPORTED_PROJECTION:
        state.persistent_notice = "source unchanged"
        state.persistent_notice_level = MessageLevel.INFO
    elif path is None:
        state.persistent_notice = ""
        state.persistent_notice_level = MessageLevel.INFO
    else:
        state.persistent_notice = ""
        state.persistent_notice_level = MessageLevel.INFO

    state.settings["filepath"] = path or ""
    _sync_document_settings(state)


def set_write_target(state: EditorState, path: str) -> None:
    state.write_path = path
    state.pending_overwrite_path = None
    if state.path is None:
        state.persistent_notice = ""
    _sync_document_settings(state)


def _sync_document_settings(state: EditorState) -> None:
    state.settings["writepath"] = state.write_path or ""
    state.settings["documentmode"] = state.document_mode.value


def document_status_label(state: EditorState) -> str:
    fmt = state.source_format.upper()
    if state.read_only:
        return f"{fmt} VIEW" if fmt != "NEW" else "VIEW"
    if state.document_mode is DocumentMode.IMPORTED_PROJECTION:
        target = Path(state.write_path).name if state.write_path else "TAB?"
        return f"{fmt}->{target}"
    if state.write_path:
        return "TAB"
    return "NEW->TAB?"


def display_path(state: EditorState) -> str:
    path = state.path or state.write_path
    return Path(path).name if path else "[No Name]"
