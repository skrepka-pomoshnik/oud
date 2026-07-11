from __future__ import annotations

from oud.editor.prompt_state import (
    command_history_commit,
    command_history_next,
    command_history_prev,
    command_history_reset_nav,
    search_history_commit,
    search_history_reset_nav,
)
from oud.editor.state import EditorState
from oud.petrucci.model import Bar, Piece


def _state() -> EditorState:
    return EditorState(Piece(title="T", bars=[Bar()]), {"style": "french"})


def test_command_history_prev_next_updates_history_slice() -> None:
    state = _state()
    state.history.command = ["w", "q"]
    assert command_history_prev(state) == "q"
    assert state.history.command_index == 1
    assert command_history_prev(state) == "w"
    assert state.history.command_index == 0
    assert command_history_next(state) == "q"
    assert state.history.command_index == 1


def test_command_history_commit_and_reset_nav() -> None:
    state = _state()
    state.history.command_index = 4
    command_history_commit(state, "wq")
    assert state.history.command == ["wq"]
    assert state.history.command_index is None
    state.history.command_index = 2
    command_history_reset_nav(state)
    assert state.history.command_index is None


def test_search_history_commit_and_reset_nav() -> None:
    state = _state()
    state.history.search_index = 3
    search_history_commit(state, "10")
    assert state.history.search == ["10"]
    assert state.history.search_index is None
    state.history.search_index = 1
    search_history_reset_nav(state)
    assert state.history.search_index is None
