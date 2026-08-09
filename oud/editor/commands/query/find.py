from __future__ import annotations

from oud.editor.core.coordinates import string_index
from oud.editor.core.state import EditorState
from oud.editor.navigation.motions import CursorMotionTarget, apply_motion_target
from petrucci.render_utils import bar_cells, bar_cells_from_chords


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


def _find_target_col(  # noqa: C901
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


def target_find_col(
    state: EditorState,
    find_mode: str,
    target: str,
    count: int = 1,
) -> int | None:
    row_index = string_index(state, state.cursor_string)
    row = _row_chars(state, state.cursor_bar, row_index)
    return _find_target_col(row, state.cursor_col, target, find_mode, count)


def target_repeat_find(
    state: EditorState,
    *,
    reverse: bool,
    count: int = 1,
) -> tuple[str, str, int] | None:
    if state.last_find is None:
        return None
    find_mode, target = state.last_find
    if reverse:
        mode_map = {"f": "F", "F": "f", "t": "T", "T": "t"}
        find_mode = mode_map[find_mode]
    col = target_find_col(state, find_mode, target, count=count)
    if col is None:
        return None
    return (find_mode, target, col)


def target_find_motion(
    state: EditorState,
    find_mode: str,
    target: str,
    count: int = 1,
) -> CursorMotionTarget | None:
    col = target_find_col(state, find_mode, target, count=count)
    if col is None:
        return None
    return CursorMotionTarget(state.cursor_bar, col)


def target_repeat_find_motion(
    state: EditorState,
    *,
    reverse: bool,
    count: int = 1,
) -> tuple[str, str, CursorMotionTarget] | None:
    target = target_repeat_find(state, reverse=reverse, count=count)
    if target is None:
        return None
    find_mode, target_char, col = target
    return (find_mode, target_char, CursorMotionTarget(state.cursor_bar, col))


def perform_find(state: EditorState, find_mode: str, target: str, count: int = 1) -> bool:
    motion = target_find_motion(state, find_mode, target, count=count)
    if motion is None:
        state.message = f"Not found: {target}"
        return False
    apply_motion_target(state, motion)
    state.last_find = (find_mode, target)
    return True


def repeat_find(state: EditorState, *, reverse: bool, count: int = 1) -> bool:
    motion = target_repeat_find_motion(state, reverse=reverse, count=count)
    if motion is None:
        if state.last_find is None:
            state.message = "No previous find"
        else:
            _mode, ch = state.last_find
            state.message = f"Not found: {ch}"
        return False
    find_mode, target_char, cursor_target = motion
    apply_motion_target(state, cursor_target)
    state.last_find = (find_mode, target_char)
    return True
