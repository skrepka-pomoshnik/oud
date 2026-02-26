from oud.core.model import Bar, Piece
from oud.editor.insert_session import enter_insert_mode, set_mode
from oud.editor.state import EditorState


def _state() -> EditorState:
    return EditorState(Piece(title="T", bars=[Bar()], strings=6), {"style": "french"})


def test_set_mode_clears_insert_session_when_leaving_insert_context() -> None:
    state = _state()
    state.mode = "insert"
    state.insert_prefix = "/"
    state.replace_once = True
    set_mode(state, "command")
    assert state.mode == "command"
    assert state.insert_prefix == ""
    assert state.replace_once is False


def test_enter_insert_mode_resets_prefix_and_sets_replace_flag() -> None:
    state = _state()
    state.insert_prefix = ",1"
    state.replace_once = True
    enter_insert_mode(state)
    assert state.mode == "insert"
    assert state.insert_prefix == ""
    assert state.replace_once is False

    state.insert_prefix = "/"
    enter_insert_mode(state, replace_once=True)
    assert state.mode == "insert"
    assert state.insert_prefix == ""
    assert state.replace_once is True
