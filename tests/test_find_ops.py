from oud.editor.commands.query.find import perform_find, repeat_find, target_find_col, target_repeat_find
from oud.editor.core.state import EditorState
from petrucci.model import Bar, Piece


def _state() -> EditorState:
    piece = Piece(title="T", bars=[Bar()], strings=6)
    state = EditorState(piece, {"style": "french"})
    state.bar_width = 8
    # Row 0: a - c - a - e -
    state.overrides[(0, 0, 0)] = "a"
    state.overrides[(0, 0, 2)] = "c"
    state.overrides[(0, 0, 4)] = "a"
    state.overrides[(0, 0, 6)] = "e"
    state.cursor_bar = 0
    state.cursor_string = 0
    state.cursor_col = 0
    return state


def test_target_find_col_is_pure() -> None:
    state = _state()
    before = (state.cursor_bar, state.cursor_string, state.cursor_col, state.last_find)
    assert target_find_col(state, "f", "a") == 4
    assert target_find_col(state, "t", "e") == 5
    assert target_find_col(state, "F", "a") is None
    after = (state.cursor_bar, state.cursor_string, state.cursor_col, state.last_find)
    assert after == before


def test_perform_find_matches_target_and_updates_last_find() -> None:
    state = _state()
    target = target_find_col(state, "f", "c")
    assert target == 2
    assert perform_find(state, "f", "c") is True
    assert state.cursor_col == target
    assert state.last_find == ("f", "c")


def test_repeat_find_target_is_pure_and_matches_wrapper() -> None:
    state1 = _state()
    state2 = _state()
    state1.cursor_col = 2
    state2.cursor_col = 2
    state1.last_find = ("f", "a")
    state2.last_find = ("f", "a")

    target = target_repeat_find(state1, reverse=False)
    assert target == ("f", "a", 4)
    # Pure helper should not mutate state.
    assert state1.cursor_col == 2
    assert state1.last_find == ("f", "a")

    assert repeat_find(state2, reverse=False) is True
    assert (state2.cursor_col, state2.last_find) == (4, ("f", "a"))


def test_repeat_find_reverse_preserves_find_semantics() -> None:
    state = _state()
    state.cursor_col = 4
    state.last_find = ("f", "a")
    assert target_repeat_find(state, reverse=True) == ("F", "a", 0)
    assert repeat_find(state, reverse=True) is True
    assert (state.cursor_col, state.last_find) == (0, ("F", "a"))
