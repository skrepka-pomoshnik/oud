from __future__ import annotations

from oud.editor.core.input.history import history_next, history_prev
from oud.editor.core.state import EditorState


def command_history_prev(state: EditorState) -> str | None:
    text, index = history_prev(state.history.command, state.history.command_index)
    state.history.command_index = index
    return text


def command_history_next(state: EditorState) -> str | None:
    text, index = history_next(state.history.command, state.history.command_index)
    state.history.command_index = index
    return text


def command_history_reset_nav(state: EditorState) -> None:
    state.history.command_index = None


def command_history_commit(state: EditorState, text: str) -> None:
    if text:
        state.history.command.append(text)
    state.history.command_index = None


def search_history_reset_nav(state: EditorState) -> None:
    state.history.search_index = None


def search_history_commit(state: EditorState, text: str) -> None:
    if text:
        state.history.search.append(text)
    state.history.search_index = None
