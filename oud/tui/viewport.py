from __future__ import annotations

from oud.editor.controller_utils import string_index
from oud.editor.layout import bars_per_line, dynamic_system_starts, system_index, system_start_index
from oud.editor.navigation import _system_display_indices_for_bar
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


def ensure_cursor_visible(state: EditorState, width: int, height: int) -> None:  # noqa: C901
    per_line = bars_per_line(state, width)
    rows = rows_per_screen(state, height)
    if state.settings.get("layout", "packed") == "auto":
        starts = dynamic_system_starts(state, width)

        def _row_for_bar(bar_index: int) -> int:
            row = 0
            for idx, start in enumerate(starts):
                next_start = starts[idx + 1] if idx + 1 < len(starts) else len(state.piece.bars)
                if start <= bar_index < next_start:
                    row = idx
                    break
            return row

        def _start_for_row(row_index: int) -> int:
            if row_index <= 0:
                return starts[0] if starts else 0
            if row_index >= len(starts):
                return starts[-1] if starts else 0
            return starts[row_index]

        cursor_row = _row_for_bar(state.cursor_bar)
        first_row = _row_for_bar(state.bar_offset)
    else:
        cursor_row = system_index(state, state.cursor_bar, per_line)
        first_row = system_index(state, state.bar_offset, per_line)
        def _start_for_row(row_index: int) -> int:
            return system_start_index(state, row_index, per_line)
    scroll_mode = state.settings.get("scrollmode", "smooth")

    def _page_start_row(row: int) -> int:
        if rows <= 1:
            return row
        return max(0, (row // rows) * rows)

    if cursor_row < first_row:
        target_row = cursor_row if scroll_mode != "page" else _page_start_row(cursor_row)
        state.bar_offset = _start_for_row(target_row)
    if cursor_row >= first_row + rows:
        target_row = _page_start_row(cursor_row) if scroll_mode == "page" else cursor_row - rows + 1
        state.bar_offset = _start_for_row(target_row)

    # Clamp cursor to rows that are actually visible in the current rendered system.
    # Auto layout hides unused bass rows per system, so a globally valid cursor_string
    # can become invisible after J/K jumps.
    reverse_strings = (
        state.settings.get("viewinvert", "off") == "on"
        or (
            state.settings.get("style") == "italian"
            and state.settings.get("italianorient", "normal") == "reverse"
        )
    )
    display_indices = _system_display_indices_for_bar(state, state.cursor_bar)
    if not display_indices:
        return
    actual = string_index(state, state.cursor_string)
    visual_rows = list(reversed(display_indices)) if reverse_strings else display_indices
    if actual in visual_rows:
        state.cursor_string = visual_rows.index(actual)
    else:
        state.cursor_string = max(0, min(state.cursor_string, len(visual_rows) - 1))
