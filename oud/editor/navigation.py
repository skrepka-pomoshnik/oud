from __future__ import annotations

from oud.core.model import Bar
from oud.core.render_utils import chord_positions, spread_flag_positions
from oud.editor.controller_utils import string_index
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


def _grid_cols(state: EditorState, bar_index: int) -> list[int]:
    cols: set[int] = set()
    for b, _s, col in state.durations:
        if b == bar_index:
            cols.add(col)
    if cols:
        return sorted(cols)
    for (b, _s, col), value in state.overrides.items():
        if b == bar_index and value and value != "-":
            cols.add(col)
    return sorted(cols)


def _note_cols(state: EditorState, bar_index: int) -> list[int]:
    chord_cols = _chord_cols(state, bar_index)
    grid_cols = _grid_cols(state, bar_index)
    if not chord_cols:
        return grid_cols
    if not grid_cols:
        return chord_cols
    return sorted(set(chord_cols) | set(grid_cols))


def _row_note_cols(state: EditorState, bar_index: int, actual_string: int) -> list[int]:
    if bar_index < 0 or bar_index >= len(state.piece.bars):
        return []
    cols: set[int] = set()
    bar = state.piece.bars[bar_index]
    for (b, s, col), value in state.overrides.items():
        if b == bar_index and s == actual_string and value and value != "-":
            cols.add(col)
    if bar.chords and not _bar_has_grid_data(state, bar_index):
        positions = spread_flag_positions(
            chord_positions(bar, state.bar_width, default_duration=4),
            state.bar_width,
            min_gap=1,
        )
        for chord, (col, _denom, _dot) in zip(bar.chords, positions, strict=False):
            if any((note.string - 1) == actual_string for note in chord.notes):
                cols.add(col)
    return sorted(cols)


def move_left_note(state: EditorState) -> None:
    actual_string = string_index(state, state.cursor_string)
    cols = _row_note_cols(state, state.cursor_bar, actual_string) or _note_cols(
        state,
        state.cursor_bar,
    )
    if cols:
        for col in reversed(cols):
            if col < state.cursor_col:
                state.cursor_col = col
                return
        if state.cursor_bar > 0:
            state.cursor_bar -= 1
            prev_cols = _note_cols(state, state.cursor_bar)
            state.cursor_col = prev_cols[-1] if prev_cols else state.bar_width - 1
            return
    move_left(state)


def move_right_note(state: EditorState) -> None:
    actual_string = string_index(state, state.cursor_string)
    cols = _row_note_cols(state, state.cursor_bar, actual_string) or _note_cols(
        state,
        state.cursor_bar,
    )
    if cols:
        for col in cols:
            if col > state.cursor_col:
                state.cursor_col = col
                return
        if state.cursor_bar < len(state.piece.bars) - 1:
            state.cursor_bar += 1
        else:
            state.piece.bars.append(Bar())
            state.cursor_bar += 1
            state.modified = True
        next_cols = _note_cols(state, state.cursor_bar)
        if next_cols:
            state.cursor_col = next_cols[0]
        else:
            state.cursor_col = 0
        return
    move_right(state)
