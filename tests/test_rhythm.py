from __future__ import annotations

from oud.editor.core.state import EditorState
from oud.editor.editing.primitives.rhythm import (
    advance_if_bar_full,
    advance_if_overflow,
    advance_to_next_bar,
    bar_duration_sum_by_col,
    column_denom,
    column_duration,
    column_has_duration,
    expected_beats,
    row_duration_sum,
)
from petrucci.model import Bar, Chord, Note, Piece


def _state(*, strings: int = 6, bars: int = 1) -> EditorState:
    piece = Piece(title="T", bars=[Bar() for _ in range(bars)], strings=strings)
    return EditorState(piece, {"style": "french", "time": "C"})


def test_expected_beats_variants() -> None:
    state = _state()
    assert expected_beats(state) == 4.0
    state.settings["time"] = "O"
    assert expected_beats(state) == 3.0
    state.settings["time"] = "6/8"
    assert expected_beats(state) == 3.0
    state.settings["time"] = "bad"
    assert expected_beats(state) is None


def test_column_duration_and_denom() -> None:
    state = _state()
    state.overrides[(0, 1, 2)] = "a"
    state.durations[(0, 0, 2)] = 8
    state.durations[(0, 1, 2)] = 16
    assert column_has_duration(state, 0, 2)
    assert column_denom(state, 0, 2) == 16
    assert column_duration(state, 0, 2) == 0.25
    state.dotted.add((0, 2))
    assert column_duration(state, 0, 2) == 0.375
    assert column_duration(state, 0, 3) is None


def test_row_duration_sum_with_chords() -> None:
    state = _state()
    state.piece.bars[0].chords = [
        Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)]),
        Chord(note_type=5, dotted=True, grid=None, notes=[Note(1, 2, 0)]),
        Chord(note_type=6, dotted=False, grid=None, notes=[Note(2, 0, 0)]),
    ]
    assert row_duration_sum(state, 0, 0) == 1.75
    assert row_duration_sum(state, 0, 1) == 0.25
    assert row_duration_sum(state, 9, 0) == 0.0


def test_row_duration_sum_manual_grid() -> None:
    state = _state()
    state.bar_width = 4
    state.overrides[(0, 0, 0)] = "a"
    state.overrides[(0, 0, 1)] = "b"
    state.durations[(0, 0, 0)] = 4
    state.durations[(0, 0, 1)] = 8
    state.dotted.add((0, 1))
    assert row_duration_sum(state, 0, 0) == 1.75


def test_bar_duration_sum_by_col_modes() -> None:
    state = _state()
    state.piece.bars[0].chords = [
        Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)]),
        Chord(note_type=6, dotted=True, grid=None, notes=[Note(2, 0, 0)]),
    ]
    assert bar_duration_sum_by_col(state, 0) == 1.375
    state.piece.bars[0].chords = []
    state.overrides[(0, 0, 0)] = "a"
    state.durations[(0, 0, 0)] = 4
    state.overrides[(0, 1, 1)] = "c"
    state.durations[(0, 1, 1)] = 8
    state.dotted.add((0, 1))
    assert bar_duration_sum_by_col(state, 0) == 1.75


def test_advance_to_next_bar_appends() -> None:
    state = _state(bars=1)
    state.cursor_bar = 0
    state.cursor_col = 3
    advance_to_next_bar(state)
    assert len(state.piece.bars) == 2
    assert state.modified is True
    assert state.cursor_bar == 1
    assert state.cursor_col == 0


def test_advance_if_bar_full_and_overflow() -> None:
    state = _state(strings=2, bars=2)
    state.bar_width = 4
    state.settings["time"] = "4/4"
    state.cursor_bar = 0
    state.overrides[(0, 0, 0)] = "a"
    state.overrides[(0, 0, 1)] = "b"
    state.overrides[(0, 0, 2)] = "c"
    state.overrides[(0, 0, 3)] = "d"
    state.durations[(0, 0, 0)] = 4
    state.durations[(0, 0, 1)] = 4
    state.durations[(0, 0, 2)] = 4
    state.durations[(0, 0, 3)] = 4
    advance_if_bar_full(state)
    assert state.cursor_bar == 1

    state.cursor_bar = 0
    state.cursor_col = 0
    state.overrides.clear()
    state.durations.clear()
    state.settings["time"] = "3/4"
    state.overrides[(0, 0, 0)] = "a"
    state.overrides[(0, 0, 1)] = "b"
    state.overrides[(0, 0, 2)] = "c"
    state.durations[(0, 0, 0)] = 4
    state.durations[(0, 0, 1)] = 4
    state.durations[(0, 0, 2)] = 4
    state.cursor_col = 3
    advance_if_overflow(state, 4, 0)
    assert state.cursor_bar == 1
