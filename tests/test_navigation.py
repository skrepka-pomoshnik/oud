from oud.core.model import Bar, Piece
from oud.editor.navigation import move_left, move_right
from oud.editor.state import EditorState


def _state() -> EditorState:
    piece = Piece(title="T", bars=[Bar(), Bar()], strings=6)
    state = EditorState(piece, {"style": "french"})
    state.bar_width = 4
    return state


def test_move_left_across_bars() -> None:
    state = _state()
    state.cursor_bar = 0
    state.cursor_col = 0
    move_left(state)
    assert state.cursor_bar == 0
    state.cursor_col = 2
    move_left(state)
    assert state.cursor_col == 1
    state.cursor_bar = 1
    state.cursor_col = 0
    move_left(state)
    assert state.cursor_bar == 0
    assert state.cursor_col == 3


def test_move_right_across_bars_and_extend() -> None:
    state = _state()
    state.cursor_bar = 0
    state.cursor_col = 2
    move_right(state)
    assert state.cursor_col == 3
    move_right(state)
    assert state.cursor_bar == 1
    assert state.cursor_col == 0
    state.cursor_col = 3
    move_right(state)
    assert state.cursor_bar == 2
    assert state.modified is True
