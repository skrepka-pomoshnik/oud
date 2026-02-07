from __future__ import annotations

from oud.core.render_utils import bar_cells, bar_cells_from_chords
from oud.editor.controller_utils import string_index
from oud.editor.state import EditorState


def _row_chars(state: EditorState, bar_index: int, row_index: int) -> list[str]:
    if bar_index < 0 or bar_index >= len(state.piece.bars):
        return ["-" for _ in range(state.bar_width)]
    bar = state.piece.bars[bar_index]
    style = state.settings.get("style", "french")
    french_c = state.settings.get("frenchc", "normal")
    cells = (
        bar_cells_from_chords(
            bar,
            state.piece.strings,
            state.bar_width,
            4,
            style,
            french_c=french_c,
        )
        if bar.chords
        else bar_cells(
            bar,
            state.piece.strings,
            state.bar_width,
            style,
            french_c=french_c,
        )
    )
    row = cells[row_index] if 0 <= row_index < len(cells) else ["-" for _ in range(state.bar_width)]
    for col in range(state.bar_width):
        key = (bar_index, row_index, col)
        if key in state.overrides:
            row[col] = state.overrides[key]
    return row


def _find_target_col(
    row: list[str],
    cursor_col: int,
    target: str,
    find_mode: str,
    count: int,
) -> int | None:
    index = cursor_col
    remaining = max(1, count)
    if find_mode in ("f", "t"):
        while remaining > 0:
            found = None
            for pos in range(index + 1, len(row)):
                if row[pos] == target:
                    found = pos
                    break
            if found is None:
                return None
            index = found
            remaining -= 1
        return max(0, index - 1) if find_mode == "t" else index
    while remaining > 0:
        found = None
        for pos in range(index - 1, -1, -1):
            if row[pos] == target:
                found = pos
                break
        if found is None:
            return None
        index = found
        remaining -= 1
    return min(len(row) - 1, index + 1) if find_mode == "T" else index


def perform_find(state: EditorState, find_mode: str, target: str, count: int = 1) -> bool:
    row_index = string_index(state, state.cursor_string)
    row = _row_chars(state, state.cursor_bar, row_index)
    col = _find_target_col(row, state.cursor_col, target, find_mode, count)
    if col is None:
        state.message = f"Not found: {target}"
        return False
    state.cursor_col = col
    state.last_find = (find_mode, target)
    return True


def repeat_find(state: EditorState, *, reverse: bool, count: int = 1) -> bool:
    if state.last_find is None:
        state.message = "No previous find"
        return False
    find_mode, target = state.last_find
    if reverse:
        mode_map = {"f": "F", "F": "f", "t": "T", "T": "t"}
        find_mode = mode_map[find_mode]
    return perform_find(state, find_mode, target, count=count)
