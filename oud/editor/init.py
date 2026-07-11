from __future__ import annotations

from pathlib import Path

from oud.core.ft3 import build_durations
from oud.core.tab_parser import load_tab_data
from oud.editor.document import configure_document
from oud.editor.load_ops import import_warning_summary, load_piece_data
from oud.editor.messages import READ_ONLY_VIEWER
from oud.editor.state import EditorState
from oud.petrucci.model import Bar
from oud.petrucci.tuning_utils import tuning_count
from oud.settings import DEFAULT_SETTINGS, load_settings


def init_state(  # noqa: C901, PLR0912
    path: str | None,
    *,
    config_path: str,
    read_only: bool = False,
) -> EditorState:
    settings = load_settings(config_path)
    requested_path = path
    piece, overrides, durations, dotted, bar_width = load_piece_data(path)
    invalid_source = bool(
        requested_path
        and (
            Path(requested_path).is_dir()
            or (piece.import_warnings and not piece.bars)
        ),
    )
    if not piece.bars:
        try:
            initial_bars = int(settings.get("newbars", DEFAULT_SETTINGS.get("newbars", "8")))
        except ValueError:
            initial_bars = int(DEFAULT_SETTINGS.get("newbars", "8"))
        initial_bars = max(1, initial_bars)
        piece.bars = [Bar() for _ in range(initial_bars)]

    state = EditorState(piece, settings, config_path=config_path)
    state.overrides = overrides
    state.durations = durations
    state.dotted = dotted
    if path and path.lower().endswith(".tab"):
        state.tab_data = load_tab_data(path)
    valid_path = None if invalid_source else path
    configure_document(state, valid_path, forced_read_only=read_only)
    is_tab = bool(path and path.lower().endswith(".tab"))
    if piece.style:
        state.settings["style"] = piece.style
    if piece.tuning:
        tuned_strings = tuning_count(piece.tuning)
        if tuned_strings:
            state.piece.strings = tuned_strings
            state.settings["tuning"] = piece.tuning
    if not is_tab and path is None:
        try:
            strings = int(settings.get("strings", DEFAULT_SETTINGS["strings"]))
        except ValueError:
            strings = int(DEFAULT_SETTINGS["strings"])
        if 4 <= strings <= 7:
            state.piece.strings = strings
    elif is_tab and not piece.tuning:
        # Legacy .tab files often omit explicit tuning; keep default 6-course fallback
        # only for TAB import, not FT3/MusicXML where parser may already infer >6 courses.
        state.piece.strings = int(DEFAULT_SETTINGS["strings"])
        if not state.settings.get("tuning"):
            state.settings["tuning"] = "g2c3f3a3d4g4"
    try:
        spacing = int(settings.get("spacing", DEFAULT_SETTINGS["spacing"]))
    except ValueError:
        spacing = int(DEFAULT_SETTINGS["spacing"])
    if bar_width:
        state.bar_width = max(4, bar_width)
    else:
        state.bar_width = max(4, spacing)
    if piece.bars and piece.bars[0].time_sig:
        state.settings["time"] = piece.bars[0].time_sig or state.settings.get("time", "C")
    if piece.tuning:
        state.settings["tuning"] = piece.tuning
    if not state.durations:
        state.durations = build_durations(piece)
    if piece.import_warnings:
        warning = import_warning_summary(piece)
        state.persistent_notice = warning
        state.message = warning
    elif read_only:
        state.message = READ_ONLY_VIEWER
    return state
