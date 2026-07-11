from oud.editor.edit_range import (
    BarRange,
    ChordRange,
    bar_range_from_cursor,
    chord_range_at_col,
    chord_range_at_col_count,
    deletable_bar_range_from_cursor,
)
from oud.editor.state import EditorState
from oud.petrucci.model import Bar, Chord, Note, Piece


def test_bar_range_single_count_and_indices() -> None:
    r = BarRange.single(3)
    assert (r.start, r.end) == (3, 4)
    assert r.count == 1
    assert list(r.indices()) == [3]


def test_bar_range_from_bounds_normalizes_reversed() -> None:
    r = BarRange.from_bounds(7, 2)
    assert (r.start, r.end) == (2, 7)
    assert r.count == 5


def test_bar_range_from_start_count() -> None:
    r = BarRange.from_start_count(2, 3)
    assert (r.start, r.end) == (2, 5)
    assert r.count == 3


def test_bar_range_clamp_to_piece_bounds() -> None:
    r = BarRange.from_bounds(-5, 99).clamp(4)
    assert (r.start, r.end) == (0, 4)
    assert r.count == 4
    assert r.is_empty is False


def test_bar_range_clamp_empty_piece() -> None:
    r = BarRange.single(2).clamp(0)
    assert (r.start, r.end) == (0, 0)
    assert r.is_empty is True
    assert list(r.indices()) == []


def test_bar_range_from_cursor_clamps_count_to_piece() -> None:
    state = EditorState(Piece(title="T", bars=[Bar(), Bar(), Bar()], strings=6), {})
    state.cursor_bar = 1
    r = bar_range_from_cursor(state, 5)
    assert (r.start, r.end, r.count) == (1, 3, 2)


def test_deletable_bar_range_from_cursor_keeps_one_bar() -> None:
    state = EditorState(Piece(title="T", bars=[Bar(), Bar(), Bar()], strings=6), {})
    state.cursor_bar = 0
    r = deletable_bar_range_from_cursor(state, 99)
    assert (r.start, r.end, r.count) == (0, 2, 2)


def test_chord_range_clamp_and_indices() -> None:
    r = ChordRange.from_bounds(1, 4, 2).clamp(5)
    assert (r.bar_index, r.start, r.end) == (1, 2, 4)
    assert r.count == 2
    assert list(r.indices()) == [2, 3]


def test_chord_range_at_col_resolves_single_chord() -> None:
    bar = Bar(
        chords=[
            Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)]),
            Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 1, 0)]),
        ],
    )
    r = chord_range_at_col(bar, 8, 0, bar_index=3)
    assert (r.bar_index, r.start, r.end) == (3, 0, 1)
    assert r.is_empty is False


def test_chord_range_at_col_empty_bar_returns_empty_range() -> None:
    r = chord_range_at_col(Bar(), 8, 0, bar_index=2)
    assert (r.bar_index, r.start, r.end) == (2, 0, 0)
    assert r.is_empty is True


def test_chord_range_at_col_count_spans_multiple_chords_and_clamps() -> None:
    bar = Bar(
        chords=[
            Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)]),
            Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 1, 0)]),
            Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 2, 0)]),
        ],
    )
    r = chord_range_at_col_count(bar, 8, 0, count=5, bar_index=4)
    assert (r.bar_index, r.start, r.end) == (4, 0, 3)
    assert r.count == 3
