from fractions import Fraction

from oud.editor.commands.query.search import (
    jump_mark,
    jump_match,
    repeat_word_search,
    search_word_under_cursor,
    set_mark,
    target_jump_mark,
    target_jump_match,
    target_repeat_word_search,
    target_search_word_under_cursor,
)
from oud.editor.core.coordinates import stop_column
from oud.editor.core.state import EditorState
from petrucci.core.model import Bar, Chord, Note, Piece

QUARTER = Fraction(1, 4)


def _bar(*frets: int) -> Bar:
    return Bar(chords=[Chord(4, False, None, [Note(1, fret, 0)]) for fret in frets])


def _state() -> EditorState:
    # Course 1 in quarters: bar 1 "a b", bar 2 "b a", bar 3 "b b b a".
    piece = Piece(title="T", bars=[_bar(0, 1), _bar(1, 0), _bar(1, 1, 1, 0)], strings=6)
    state = EditorState(piece, {"style": "french", "time": "4/4"})
    state.bar_width = 8
    state.cursor_bar = 0
    state.cursor_string = 0
    state.cursor_onset = Fraction(0)
    return state


def test_target_search_word_under_cursor_is_pure() -> None:
    state = _state()
    before = (state.cursor_bar, state.cursor_string, state.cursor_onset, state.last_word_search)
    target = target_search_word_under_cursor(state, 1)
    assert target == ("a", 1, (1, 0, stop_column(state, 1, QUARTER)))
    after = (state.cursor_bar, state.cursor_string, state.cursor_onset, state.last_word_search)
    assert after == before


def test_search_word_under_cursor_matches_pure_target() -> None:
    state = _state()
    target = target_search_word_under_cursor(state, 1)
    assert target is not None
    assert search_word_under_cursor(state, 1) is True
    assert (state.cursor_bar, state.cursor_onset) == (1, QUARTER)
    assert state.last_word_search == ("a", 1)


def test_target_repeat_word_search_is_pure_and_matches_wrapper() -> None:
    state1 = _state()
    state2 = _state()
    for state in (state1, state2):
        state.cursor_bar, state.cursor_onset = 1, QUARTER
        state.last_word_search = ("a", 1)
    target = target_repeat_word_search(state1, reverse=False)
    assert target == ("a", 1, (2, 0, stop_column(state1, 2, Fraction(3, 4))))
    assert (state1.cursor_bar, state1.cursor_onset, state1.last_word_search) == (1, QUARTER, ("a", 1))
    assert repeat_word_search(state2, reverse=False) is True
    assert (state2.cursor_bar, state2.cursor_onset, state2.last_word_search) == (2, Fraction(3, 4), ("a", 1))


def test_target_jump_match_handles_span_and_repeat_pairs() -> None:
    state = _state()
    state.cursor_bar = 2
    first, last = stop_column(state, 2, Fraction(0)), stop_column(state, 2, Fraction(3, 4))
    state.slurs = [(2, first, last)]
    assert target_jump_match(state) == (2, last)
    assert jump_match(state) is True
    assert (state.cursor_bar, state.cursor_onset) == (2, Fraction(3, 4))

    state = _state()
    state.piece.bars[0].repeat = ".:"
    state.piece.bars[2].repeat = ":."
    state.cursor_bar = 0
    state.cursor_onset = QUARTER
    assert target_jump_match(state) == (2, 0)
    assert jump_match(state) is True
    assert (state.cursor_bar, state.cursor_onset) == (2, Fraction(0))


def test_target_jump_mark_is_pure_and_wrapper_uses_it() -> None:
    state = _state()
    state.cursor_bar = 1
    state.cursor_string = 2
    state.cursor_onset = QUARTER
    assert set_mark(state, "a") is True
    state.cursor_bar = 0
    state.cursor_string = 0
    state.cursor_onset = Fraction(0)
    target = target_jump_mark(state, "a")
    assert target is not None
    assert jump_mark(state, "a") is True
    assert (state.cursor_bar, state.cursor_onset) == (1, QUARTER)
