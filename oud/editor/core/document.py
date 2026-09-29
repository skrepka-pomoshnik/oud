from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING

from oud.editor.core.feedback.messages import MessageLevel
from petrucci.adapters.duet import is_duet_score_piece
from petrucci.core.model import Piece

if TYPE_CHECKING:
    from oud.editor.core.state import EditorState


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


def _view_only_score(piece: Piece) -> bool:
    # A duet keeps two lute parts in one bar list, and a score without
    # tablature has nothing to edit; both stay view-only.
    return is_duet_score_piece(piece) or not any(bar.chords or bar.notes for bar in piece.bars)


MUSICXML_SUFFIX = ".musicxml"
NEW_DOCUMENT_PATH = "untitled.musicxml"
# Suffix for an edited copy of MusicXML that Oud did not write: Oud keeps only
# its tablature part, so saving over the source could lose other parts.
FOREIGN_MUSICXML_COPY = ".oud.musicxml"


def classify_document(path: str | None, piece: Piece, *, oud_musicxml: bool = False) -> DocumentMode:
    fmt = source_format(path)
    if fmt in {"new", "tab"} or (fmt == "musicxml" and oud_musicxml):
        return DocumentMode.NATIVE
    if fmt == "ft3" and _has_non_tab_score_content(piece) and _view_only_score(piece):
        return DocumentMode.IMPORTED_READ_ONLY
    return DocumentMode.IMPORTED_PROJECTION


def configure_document(
    state: EditorState,
    path: str | None,
    *,
    forced_read_only: bool = False,
    oud_musicxml: bool = False,
) -> None:
    state.path = path
    state.source_format = source_format(path)
    state.document_mode = classify_document(path, state.piece, oud_musicxml=oud_musicxml)
    state.write_path = path if path and state.document_mode is DocumentMode.NATIVE else None
    state.suggested_write_path = None
    state.forced_read_only = forced_read_only
    state.read_only = forced_read_only or state.document_mode is DocumentMode.IMPORTED_READ_ONLY
    state.pending_overwrite_path = None
    state.view_staff_index = 0

    if forced_read_only:
        state.persistent_notice = "Read-only viewer"
        state.persistent_notice_level = MessageLevel.WARNING
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
        target = Path(state.write_path or default_write_path(state)).name
        return f"{fmt} EDIT:{target}"
    if state.write_path:
        return "TAB" if state.write_path.lower().endswith(".tab") else "MUSICXML"
    return f"NEW:{Path(default_write_path(state)).name}"


def default_write_path(state: EditorState) -> str:
    """Return a safe suggested TAB target without claiming it is established."""

    if state.path:
        source = Path(state.path)
        if state.source_format == "musicxml":
            return str(source.with_name(source.stem + FOREIGN_MUSICXML_COPY))
        return str(source.with_suffix(MUSICXML_SUFFIX))
    return state.suggested_write_path or NEW_DOCUMENT_PATH


def display_path(state: EditorState) -> str:
    # Native documents follow their established write target after Save As;
    # imported documents keep naming their source.
    if state.document_mode is DocumentMode.NATIVE:
        path = state.write_path or state.path
    else:
        path = state.path or state.write_path
    return Path(path).name if path else "[No Name]"
