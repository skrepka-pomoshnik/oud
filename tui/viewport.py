from __future__ import annotations

from editor.layout import bars_per_line, system_index, system_start_index
from editor.state import EditorState
from ui.render import _block_height


def rows_per_screen(state: EditorState, height: int) -> int:
    include_meta = True
    show_dur = state.settings.get("showdur", "off") == "on"
    show_extras = state.settings.get("showextras", "off") == "on"
    show_tactus = state.settings.get("showtactus", "off") == "on"
    block_h = _block_height(include_meta, state.piece.strings, show_dur, show_extras, show_tactus)
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
