from oud.editor.search_ops import (
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
from oud.editor.state import EditorState
from petrucci.model import Bar, Piece


def _state() -> EditorState:
    piece = Piece(title="T", bars=[Bar(), Bar(), Bar()], strings=6)
    state = EditorState(piece, {"style": "french"})
    state.bar_width = 8
    # Searchable row content on top row across bars.
    state.overrides[(0, 0, 0)] = "a"
    state.overrides[(0, 0, 2)] = "b"
    state.overrides[(1, 0, 1)] = "a"
    state.overrides[(2, 0, 3)] = "a"
    state.cursor_bar = 0
    state.cursor_string = 0
    state.cursor_col = 0
    return state


def test_target_search_word_under_cursor_is_pure() -> None:
    state = _state()
    before = (state.cursor_bar, state.cursor_string, state.cursor_col, state.last_word_search)
    target = target_search_word_under_cursor(state, 1)
    assert target == ("a", 1, (1, 0, 1))
    after = (state.cursor_bar, state.cursor_string, state.cursor_col, state.last_word_search)
    assert after == before


def test_search_word_under_cursor_matches_pure_target() -> None:
    state = _state()
    target = target_search_word_under_cursor(state, 1)
    assert target is not None
    assert search_word_under_cursor(state, 1) is True
    _term, _dir, (bar, _s, col) = target
    assert (state.cursor_bar, state.cursor_col) == (bar, col)
    assert state.last_word_search == ("a", 1)


def test_target_repeat_word_search_is_pure_and_matches_wrapper() -> None:
    state1 = _state()
    state2 = _state()
    state1.cursor_bar, state1.cursor_col = 1, 1
    state2.cursor_bar, state2.cursor_col = 1, 1
    state1.last_word_search = ("a", 1)
    state2.last_word_search = ("a", 1)
    target = target_repeat_word_search(state1, reverse=False)
    assert target == ("a", 1, (2, 0, 3))
    assert (state1.cursor_bar, state1.cursor_col, state1.last_word_search) == (1, 1, ("a", 1))
    assert repeat_word_search(state2, reverse=False) is True
    assert (state2.cursor_bar, state2.cursor_col, state2.last_word_search) == (2, 3, ("a", 1))


def test_target_jump_match_handles_span_and_repeat_pairs() -> None:
    state = _state()
    state.cursor_bar = 0
    state.cursor_col = 2
    state.slurs = [(0, 2, 5)]
    assert target_jump_match(state) == (0, 5)
    assert jump_match(state) is True
    assert (state.cursor_bar, state.cursor_col) == (0, 5)

    state = _state()
    state.piece.bars[0].repeat = ".:"
    state.piece.bars[2].repeat = ":."
    state.cursor_bar = 0
    state.cursor_col = 4
    assert target_jump_match(state) == (2, 0)
    assert jump_match(state) is True
    assert (state.cursor_bar, state.cursor_col) == (2, 0)


def test_target_jump_mark_is_pure_and_wrapper_uses_it() -> None:
    state = _state()
    state.cursor_bar = 1
    state.cursor_string = 2
    state.cursor_col = 4
    assert set_mark(state, "a") is True
    state.cursor_bar = 0
    state.cursor_string = 0
    state.cursor_col = 0
    target = target_jump_mark(state, "a")
    assert target is not None
    assert jump_mark(state, "a") is True
    bar, _actual, col = target
    assert (state.cursor_bar, state.cursor_col) == (bar, col)
