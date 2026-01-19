from core.model import Bar, Piece
from editor.state import EditorState


def test_clamp_bounds_cursor() -> None:
    piece = Piece(title="T", bars=[Bar(), Bar()])
    state = EditorState(piece, {"style": "french"})
    state.cursor_bar = 5
    state.cursor_string = 9
    state.cursor_col = 99
    state.bar_width = 4
    state.clamp()
    assert state.cursor_bar == 1
    assert state.cursor_string == piece.strings - 1
    assert state.cursor_col == 3


def test_clamp_minimums() -> None:
    piece = Piece(title="T", bars=[Bar()])
    state = EditorState(piece, {"style": "french"})
    state.cursor_bar = -3
    state.cursor_string = -2
    state.cursor_col = -1
    state.clamp()
    assert state.cursor_bar == 0
    assert state.cursor_string == 0
    assert state.cursor_col == 0
