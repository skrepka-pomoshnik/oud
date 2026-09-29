from fractions import Fraction

from oud.editor.commands.query.find import perform_find, repeat_find, target_find_col, target_repeat_find
from oud.editor.core.coordinates import stop_column
from oud.editor.core.state import EditorState
from petrucci.core.model import Bar, Chord, Note, Piece

HALF = Fraction(1, 2)


def _state() -> EditorState:
    # Course 1 in quarters: a c a e
    chords = [Chord(4, False, None, [Note(1, fret, 0)]) for fret in (0, 2, 0, 4)]
    state = EditorState(Piece(title="T", bars=[Bar(chords=chords)], strings=6), {"style": "french", "time": "4/4"})
    state.bar_width = 8
    state.cursor_bar = 0
    state.cursor_string = 0
    state.cursor_onset = Fraction(0)
    return state


def test_target_find_col_is_pure() -> None:
    state = _state()
    before = (state.cursor_bar, state.cursor_string, state.cursor_onset, state.last_find)
    assert target_find_col(state, "f", "a") == stop_column(state, 0, HALF)
    assert target_find_col(state, "t", "e") == stop_column(state, 0, Fraction(3, 4)) - 1
    assert target_find_col(state, "F", "a") is None
    after = (state.cursor_bar, state.cursor_string, state.cursor_onset, state.last_find)
    assert after == before


def test_perform_find_matches_target_and_updates_last_find() -> None:
    state = _state()
    assert target_find_col(state, "f", "c") == stop_column(state, 0, Fraction(1, 4))
    assert perform_find(state, "f", "c") is True
    assert state.cursor_onset == Fraction(1, 4)
    assert state.last_find == ("f", "c")


def test_repeat_find_target_is_pure_and_matches_wrapper() -> None:
    state1 = _state()
    state2 = _state()
    for state in (state1, state2):
        state.cursor_onset = Fraction(1, 4)
        state.last_find = ("f", "a")

    target = target_repeat_find(state1, reverse=False)
    assert target == ("f", "a", stop_column(state1, 0, HALF))
    # Pure helper should not mutate state.
    assert state1.cursor_onset == Fraction(1, 4)
    assert state1.last_find == ("f", "a")

    assert repeat_find(state2, reverse=False) is True
    assert (state2.cursor_onset, state2.last_find) == (HALF, ("f", "a"))


def test_repeat_find_reverse_preserves_find_semantics() -> None:
    state = _state()
    state.cursor_onset = HALF
    state.last_find = ("f", "a")
    assert target_repeat_find(state, reverse=True) == ("F", "a", 0)
    assert repeat_find(state, reverse=True) is True
    assert (state.cursor_onset, state.last_find) == (Fraction(0), ("F", "a"))
