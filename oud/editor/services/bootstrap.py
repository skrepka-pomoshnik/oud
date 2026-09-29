from __future__ import annotations

from pathlib import Path

from oud.editor.core.document import configure_document
from oud.editor.core.feedback.messages import READ_ONLY_VIEWER, MessageLevel
from oud.editor.core.state import EditorState
from oud.editor.services.io.loading import import_warning_summary, load_piece_data
from oud.importers.ft3 import build_durations
from oud.importers.tab import load_tab_data
from oud.settings import DEFAULT_SETTINGS, load_settings
from petrucci.core.model import Bar, Piece
from petrucci.core.music.tuning import tuning_count

_MIN_PIECE_STRINGS = 4
_MAX_PIECE_STRINGS = 7


def _invalid_source(path: str | None, piece: Piece) -> bool:
    return bool(path and (Path(path).is_dir() or (piece.import_warnings and not piece.bars)))


def _is_new_tab(path: str | None) -> bool:
    return bool(path and path.lower().endswith(".tab") and not Path(path).exists())


def _ensure_initial_bars(piece: Piece, settings: dict[str, str]) -> None:
    if piece.bars:
        return
    try:
        initial_bars = int(settings.get("newbars", DEFAULT_SETTINGS.get("newbars", "8")))
    except ValueError:
        initial_bars = int(DEFAULT_SETTINGS.get("newbars", "8"))
    piece.bars = [Bar() for _ in range(max(1, initial_bars))]


def _apply_piece_metadata(state: EditorState) -> None:
    piece = state.piece
    if piece.style:
        state.settings["style"] = piece.style
    if piece.tempo is not None:
        state.settings["tempo"] = str(piece.tempo)
    if not piece.tuning:
        return
    state.settings["tuning"] = piece.tuning
    tuned_strings = tuning_count(piece.tuning)
    if tuned_strings:
        piece.strings = tuned_strings


def _setting_int(settings: dict[str, str], key: str, fallback_key: str) -> int:
    try:
        return int(settings.get(key, DEFAULT_SETTINGS[fallback_key]))
    except ValueError:
        return int(DEFAULT_SETTINGS[fallback_key])


def _apply_path_defaults(state: EditorState, path: str | None) -> None:
    is_tab = bool(path and path.lower().endswith(".tab"))
    if not is_tab and path is None:
        strings = _setting_int(state.settings, "strings", "strings")
        if _MIN_PIECE_STRINGS <= strings <= _MAX_PIECE_STRINGS:
            state.piece.strings = strings
        return
    if is_tab and not state.piece.tuning:
        state.piece.strings = int(DEFAULT_SETTINGS["strings"])
        if not state.settings.get("tuning"):
            state.settings["tuning"] = "g2c3f3a3d4g4"


def _apply_spacing(state: EditorState, imported_bar_width: int | None) -> None:
    if imported_bar_width:
        state.bar_width = max(4, imported_bar_width)
        return
    spacing = _setting_int(state.settings, "spacing", "spacing")
    state.bar_width = max(4, spacing)


def _apply_import_feedback(state: EditorState, *, read_only: bool) -> None:
    if state.piece.import_warnings:
        warning = import_warning_summary(state.piece)
        state.persistent_notice = warning
        state.persistent_notice_level = MessageLevel.WARNING
        state.message = warning
    elif read_only:
        state.message = READ_ONLY_VIEWER


def init_state(
    path: str | None,
    *,
    config_path: str,
    read_only: bool = False,
) -> EditorState:
    settings = load_settings(config_path)
    # A missing .tab path names a new document: nothing is written until the
    # first :w, which asks for the destination with this path filled in.
    new_tab = _is_new_tab(path)
    piece, overrides, durations, dotted, bar_width = load_piece_data(None if new_tab else path)
    if new_tab:
        piece.title = Path(str(path)).stem
    invalid_source = new_tab or _invalid_source(path, piece)
    _ensure_initial_bars(piece, settings)

    state = EditorState(piece, settings, config_path=config_path)
    state.overrides = overrides
    state.durations = durations
    state.dotted = dotted
    if path and path.lower().endswith(".tab") and Path(path).is_file():
        state.tab_data = load_tab_data(path)
    valid_path = None if invalid_source else path
    configure_document(state, valid_path, forced_read_only=read_only)
    if new_tab:
        state.suggested_write_path = path
    _apply_piece_metadata(state)
    _apply_path_defaults(state, path)
    _apply_spacing(state, bar_width)
    if piece.bars and piece.bars[0].time_sig:
        state.settings["time"] = piece.bars[0].time_sig or state.settings.get("time", "C")
    if not state.durations:
        state.durations = build_durations(piece)
    _apply_import_feedback(state, read_only=read_only)
    return state
