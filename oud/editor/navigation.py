from __future__ import annotations

from oud.core.model import Bar
from oud.core.render_utils import chord_positions, spread_flag_positions
from oud.editor.state import EditorState


def move_left(state: EditorState) -> None:
    if state.cursor_col > 0:
        state.cursor_col -= 1
    elif state.cursor_bar > 0:
        state.cursor_bar -= 1
        state.cursor_col = state.bar_width - 1


def move_right(state: EditorState) -> None:
    if state.cursor_col < state.bar_width - 1:
        state.cursor_col += 1
    elif state.cursor_bar < len(state.piece.bars) - 1:
        state.cursor_bar += 1
        state.cursor_col = 0
    else:
        state.piece.bars.append(Bar())
        state.cursor_bar += 1
        state.cursor_col = 0
        state.modified = True


def _bar_has_grid_data(state: EditorState, bar_index: int) -> bool:
    return any(b == bar_index for (b, _s, _c) in state.overrides) or any(
        b == bar_index for (b, _s, _c) in state.durations
    )


def _chord_cols(state: EditorState, bar_index: int) -> list[int]:
    if bar_index < 0 or bar_index >= len(state.piece.bars):
        return []
    bar = state.piece.bars[bar_index]
    if not bar.chords or _bar_has_grid_data(state, bar_index):
        return []
    positions = spread_flag_positions(
        chord_positions(bar, state.bar_width, default_duration=4),
        state.bar_width,
        min_gap=1,
    )
    return sorted({col for col, _denom, _dot in positions})


def move_left_note(state: EditorState) -> None:
    cols = _chord_cols(state, state.cursor_bar)
    if cols:
        for col in reversed(cols):
            if col < state.cursor_col:
                state.cursor_col = col
                return
    move_left(state)


def move_right_note(state: EditorState) -> None:
    cols = _chord_cols(state, state.cursor_bar)
    if cols:
        for col in cols:
            if col > state.cursor_col:
                state.cursor_col = col
                return
    move_right(state)
