from __future__ import annotations

from oud.editor.core.coordinates import string_index
from oud.editor.core.session import set_mode
from oud.editor.core.state import EditorState
from oud.editor.editing.primitives.edits import clear_cell_note, undo_group
from oud.editor.editing.primitives.ranges import BarRange
from petrucci.rendering.primitives.utils import bar_cells, bar_cells_from_chords


def enter_visual_mode(state: EditorState, *, linewise: bool = False) -> None:
    if state.visual_anchor is None:
        state.visual_anchor = (state.cursor_bar, state.cursor_string, state.cursor_col)
    state.mode = "visual_line" if linewise else "visual"
    state.message = "VISUAL LINE" if linewise else "VISUAL"


def clear_visual_mode(state: EditorState) -> None:
    state.visual_anchor = None
    set_mode(state, "normal")


def yank_visual_rows(state: EditorState) -> int:
    out: list[tuple[int, int, str]] = []
    for bar_index, actual_string, start_col, end_col in _visual_selection_ranges(state):
        rows = _bar_rows_with_overrides(state, bar_index)
        if not (0 <= actual_string < len(rows)):
            continue
        text = "".join(rows[actual_string])
        snippet = text if state.mode == "visual_line" else text[start_col : end_col + 1]
        out.append((bar_index, actual_string, snippet))
    state.yanked_rows = out
    state.message = f"Rows yanked: {len(out)}"
    clear_visual_mode(state)
    return len(out)


def delete_visual_rows(state: EditorState, *, change: bool = False) -> int:
    ranges = _visual_selection_ranges(state)
    count = yank_visual_rows(state)
    with undo_group(state, label="visual-change" if change else "visual-delete"):
        for bar_index, actual_string, start_col, end_col in ranges:
            for col in range(start_col, end_col + 1):
                clear_cell_note(state, bar_index, actual_string, col)
    if ranges:
        first_bar, first_string, first_col, _end_col = ranges[0]
        state.cursor_bar = first_bar
        state.cursor_string = first_string
        state.cursor_col = first_col
    if change:
        set_mode(state, "insert")
        state.message = f"Rows changed: {count}"
    else:
        state.message = f"Rows deleted: {count}"
    return count


def visual_bar_range(state: EditorState) -> BarRange:
    if state.visual_anchor is None:
        return BarRange.single(state.cursor_bar).clamp(len(state.piece.bars))
    anchor_bar, _anchor_row, _anchor_col = state.visual_anchor
    start = min(anchor_bar, state.cursor_bar)
    end = max(anchor_bar, state.cursor_bar) + 1
    return BarRange(start, end).clamp(len(state.piece.bars))


def _visual_selection_columns(
    *,
    bar_index: int,
    anchor_bar: int,
    cursor_bar: int,
    anchor_col: int,
    cursor_col: int,
    col_lo: int,
    col_hi: int,
    bar_width: int,
    linewise: bool,
    forward: bool,
) -> tuple[int, int]:
    if linewise or anchor_bar == cursor_bar:
        start_col = 0 if linewise else col_lo
        end_col = bar_width - 1 if linewise else col_hi
    elif forward:
        start_col = anchor_col if bar_index == anchor_bar else 0
        end_col = cursor_col if bar_index == cursor_bar else bar_width - 1
    else:
        start_col = cursor_col if bar_index == cursor_bar else 0
        end_col = anchor_col if bar_index == anchor_bar else bar_width - 1
    start_col = max(0, min(start_col, bar_width - 1))
    end_col = max(start_col, min(end_col, bar_width - 1))
    return start_col, end_col


def _visual_selection_ranges(state: EditorState) -> list[tuple[int, int, int, int]]:
    anchor = state.visual_anchor or (state.cursor_bar, state.cursor_string, state.cursor_col)
    a_bar, a_row, a_col = anchor
    c_bar, c_row, c_col = state.cursor_bar, state.cursor_string, state.cursor_col
    bar_start, bar_end = sorted((a_bar, c_bar))
    row_start, row_end = sorted((a_row, c_row))
    col_lo = min(a_col, c_col)
    col_hi = max(a_col, c_col)
    linewise = state.mode == "visual_line"
    forward = (c_bar, c_col) >= (a_bar, a_col)

    out: list[tuple[int, int, int, int]] = []
    for bar_index in range(bar_start, bar_end + 1):
        for display_row in range(row_start, row_end + 1):
            actual_string = string_index(state, display_row)
            if not (0 <= actual_string < state.piece.strings):
                continue
            start_col, end_col = _visual_selection_columns(
                bar_index=bar_index,
                anchor_bar=a_bar,
                cursor_bar=c_bar,
                anchor_col=a_col,
                cursor_col=c_col,
                col_lo=col_lo,
                col_hi=col_hi,
                bar_width=state.bar_width,
                linewise=linewise,
                forward=forward,
            )
            out.append((bar_index, actual_string, start_col, end_col))
    return out


def _bar_rows_with_overrides(state: EditorState, bar_index: int) -> list[list[str]]:
    bar = state.piece.bars[bar_index]
    style = state.settings.get("style", "french")
    french_c = state.settings.get("frenchc", "normal")
    fretlabelmode = state.settings.get("fretlabelmode", "auto")
    default_duration = max(1, state.current_duration)
    if bar.chords:
        rows = bar_cells_from_chords(
            bar,
            state.piece.strings,
            state.bar_width,
            default_duration,
            style,
            french_c_shape=french_c,
            label_mode=fretlabelmode,
        )
    else:
        rows = bar_cells(
            bar,
            state.piece.strings,
            state.bar_width,
            style,
            french_c_shape=french_c,
            label_mode=fretlabelmode,
        )
    for s_idx in range(state.piece.strings):
        for col in range(state.bar_width):
            key = (bar_index, s_idx, col)
            if key not in state.overrides:
                continue
            value = state.overrides[key]
            rows[s_idx][col] = "_" if value == "r" else value
    return rows
