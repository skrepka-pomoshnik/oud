from __future__ import annotations

from oud.editor.core.input.modes import INSERT_MODES, VISUAL_MODES, Mode
from oud.editor.core.state import EditorState


def clear_insert_transient(state: EditorState) -> None:
    state.insert_prefix = ""


def _clear_insert_session(state: EditorState) -> None:
    clear_insert_transient(state)
    state.replace_once = False


def set_mode(state: EditorState, mode: Mode | str) -> None:
    """Central mode transition boundary for insert-session state."""
    mode = Mode(mode)
    if mode not in INSERT_MODES:
        _clear_insert_session(state)
    if mode not in VISUAL_MODES:
        state.visual_anchor = None
    state.mode = mode


def enter_insert_mode(state: EditorState, *, replace_once: bool = False) -> None:
    clear_insert_transient(state)
    state.replace_once = replace_once
    state.mode = Mode.INSERT


def enter_replace_mode(state: EditorState) -> None:
    clear_insert_transient(state)
    state.replace_once = False
    state.mode = Mode.REPLACE


def exit_insert_mode(state: EditorState) -> None:
    set_mode(state, Mode.NORMAL)


def finish_replace_once(state: EditorState) -> bool:
    if not state.replace_once:
        return False
    exit_insert_mode(state)
    return True
