from __future__ import annotations

from oud.editor.layout import bars_per_line, system_index, system_start_index
from oud.editor.state import EditorState
from oud.ui.layout_map import block_height as _block_height
from oud.ui.render import _bass_strings_used


def rows_per_screen(state: EditorState, height: int) -> int:
    include_meta = True
    show_dur = state.settings.get("showdur", "off") == "on"
    show_extras = state.settings.get("showextras", "off") == "on"
    show_tactus = state.settings.get("showtactus", "off") == "on"
    double_stems = state.settings.get("flagstems", "single") == "double"
    used_bass = _bass_strings_used(state.piece, state.overrides)
    total_strings = state.piece.strings
    base_strings = min(6, total_strings)
    display_indices = list(range(base_strings))
    display_indices.extend(
        idx for idx in sorted(used_bass) if base_strings <= idx < total_strings
    )
    display_strings = len(display_indices)
    block_h = _block_height(
        include_meta,
        display_strings,
        show_dur,
        show_extras,
        show_tactus,
        double_stems,
    )
    available = max(0, height - 2 - 1)
    return max(1, available // block_h)


def ensure_cursor_visible(state: EditorState, width: int, height: int) -> None:
    per_line = bars_per_line(state, width)
    rows = rows_per_screen(state, height)
    cursor_row = system_index(state, state.cursor_bar, per_line)
    first_row = system_index(state, state.bar_offset, per_line)
    if cursor_row < first_row:
        state.bar_offset = system_start_index(state, cursor_row, per_line)
    if cursor_row >= first_row + rows:
        state.bar_offset = system_start_index(
            state,
            cursor_row - rows + 1,
            per_line,
        )
