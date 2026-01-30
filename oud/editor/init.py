from __future__ import annotations

from oud.core.ft3 import build_durations
from oud.core.model import Bar
from oud.core.tuning_utils import tuning_count
from oud.editor.load_ops import load_piece_data
from oud.editor.state import EditorState
from oud.settings import DEFAULT_SETTINGS, load_settings


def init_state(path: str | None, *, config_path: str) -> EditorState:  # noqa: C901, PLR0912
    settings = load_settings(config_path)
    piece, overrides, durations, dotted, bar_width = load_piece_data(path)
    if not piece.bars:
        piece.bars = [Bar()]

    state = EditorState(piece, settings, config_path=config_path)
    state.overrides = overrides
    state.durations = durations
    state.dotted = dotted
    state.path = path
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
    elif not piece.tuning:
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
    return state
