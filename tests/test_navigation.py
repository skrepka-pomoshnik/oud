from oud.core.model import Bar, Chord, Note, Piece
from oud.editor.navigation import move_left, move_left_note, move_right, move_right_note
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


def test_note_movement_uses_chord_positions() -> None:
    state = _state()
    state.bar_width = 8
    state.piece.bars[0] = Bar(
        chords=[
            Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)]),
            Chord(note_type=6, dotted=False, grid=None, notes=[Note(1, 1, 0)]),
            Chord(note_type=5, dotted=False, grid=None, notes=[Note(1, 2, 0)]),
        ],
    )
    state.cursor_bar = 0
    state.cursor_col = 5
    move_left_note(state)
    assert state.cursor_col == 3
    move_left_note(state)
    assert state.cursor_col == 0
    move_right_note(state)
    assert state.cursor_col == 3
