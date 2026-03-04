from __future__ import annotations

from oud.core.render_utils import bar_cells, bar_cells_from_chords
from oud.editor.controller_utils import string_index
from oud.editor.insert_session import set_mode
from oud.editor.state import EditorState


def enter_visual_mode(state: EditorState, *, linewise: bool = False) -> None:
    if state.visual_anchor is None:
        state.visual_anchor = (state.cursor_bar, state.cursor_string, state.cursor_col)
    state.mode = "visual_line" if linewise else "visual"
    state.message = "VISUAL LINE" if linewise else "VISUAL"


def clear_visual_mode(state: EditorState) -> None:
    state.visual_anchor = None
    set_mode(state, "normal")


def yank_visual_rows(state: EditorState) -> int:
    anchor = state.visual_anchor or (state.cursor_bar, state.cursor_string, state.cursor_col)
    a_bar, a_row, a_col = anchor
    c_bar, c_row, c_col = state.cursor_bar, state.cursor_string, state.cursor_col
    bar_start, bar_end = sorted((a_bar, c_bar))
    row_start, row_end = sorted((a_row, c_row))
    col_lo = min(a_col, c_col)
    col_hi = max(a_col, c_col)
    linewise = state.mode == "visual_line"
    forward = (c_bar, c_col) >= (a_bar, a_col)

    out: list[tuple[int, int, str]] = []
    for bar_index in range(bar_start, bar_end + 1):
        rows = _bar_rows_with_overrides(state, bar_index)
        for display_row in range(row_start, row_end + 1):
            actual_string = string_index(state, display_row)
            if not (0 <= actual_string < len(rows)):
                continue
            text = "".join(rows[actual_string])
            if linewise or bar_start == bar_end:
                snippet = text if linewise else text[col_lo : col_hi + 1]
            elif forward:
                if bar_index == a_bar:
                    snippet = text[a_col:]
                elif bar_index == c_bar:
                    snippet = text[: c_col + 1]
                else:
                    snippet = text
            elif bar_index == c_bar:
                snippet = text[c_col:]
            elif bar_index == a_bar:
                snippet = text[: a_col + 1]
            else:
                snippet = text
            out.append((bar_index, actual_string, snippet))
    state.yanked_rows = out
    state.message = f"Rows yanked: {len(out)}"
    clear_visual_mode(state)
    return len(out)


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
