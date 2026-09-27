from __future__ import annotations

from collections.abc import Callable

from oud.editor.core.input.keymap import Action, keymap_for
from oud.editor.core.input.menu import menu_scroll_offset
from oud.editor.core.input.modes import INSERT_MODES, OVERLAY_MODES, Mode
from oud.editor.core.session import set_mode
from oud.editor.core.state import EditorState


def _move_overlay_offset(state: EditorState, delta: int) -> None:
    if state.mode == Mode.HELP:
        state.help_offset = menu_scroll_offset(state.help_offset, delta)
    elif state.mode == Mode.INFO:
        state.info_offset = menu_scroll_offset(state.info_offset, delta)
    else:
        state.notes_offset = menu_scroll_offset(state.notes_offset, delta)


def _handle_overlay_key(state: EditorState, key: int) -> bool:
    if state.mode not in OVERLAY_MODES:
        return False
    action = keymap_for(state, Mode.HELP).lookup((key,))
    if action is Action.PAGE_CLOSE:
        set_mode(state, Mode.NORMAL)
    elif action is Action.PAGE_DOWN:
        _move_overlay_offset(state, 1)
    elif action is Action.PAGE_UP:
        _move_overlay_offset(state, -1)
    # Pages swallow every other key.
    return True


def handle_key(
    state: EditorState,
    key: int,
    *,
    handle_insert: Callable[[EditorState, int], bool],
    handle_normal: Callable[[EditorState, int], bool],
    handle_command: Callable[[EditorState, int], bool],
    handle_search: Callable[[EditorState, int], bool],
) -> bool:
    if state.pending_quit and key not in keymap_for(state, Mode.NORMAL).keys_for(Action.QUIT):
        state.pending_quit = False
    if _handle_overlay_key(state, key):
        return True
    if state.mode == Mode.PLUGIN:
        from oud.editor.commands.plugins.operations import handle_plugin_key  # noqa: PLC0415

        return handle_plugin_key(state, key)
    if state.mode in INSERT_MODES:
        return handle_insert(state, key)
    if state.mode == Mode.COMMAND:
        return handle_command(state, key)
    if state.mode == Mode.SEARCH:
        return handle_search(state, key)
    return handle_normal(state, key)
