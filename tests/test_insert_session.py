from oud.editor.insert_session import enter_insert_mode, enter_replace_mode, set_mode
from oud.editor.state import EditorState
from petrucci.model import Bar, Piece


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


def test_set_mode_clears_visual_anchor_when_leaving_visual_context() -> None:
    state = _state()
    state.mode = "visual"
    state.visual_anchor = (0, 1, 2)
    set_mode(state, "normal")
    assert state.mode == "normal"
    assert state.visual_anchor is None


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


def test_enter_replace_mode_resets_prefix_and_sets_replace_context() -> None:
    state = _state()
    state.insert_prefix = "/"
    state.replace_once = True
    enter_replace_mode(state)
    assert state.mode == "replace"
    assert state.insert_prefix == ""
    assert state.replace_once is False
