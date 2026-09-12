from __future__ import annotations

from collections.abc import Callable

from oud.editor.core.input.keymap import help_bindings, normal_bindings
from oud.editor.core.input.menu import menu_scroll_offset
from oud.editor.core.session import set_mode
from oud.editor.core.state import EditorState


def _move_overlay_offset(state: EditorState, delta: int) -> None:
    if state.mode == "help":
        state.help_offset = menu_scroll_offset(state.help_offset, delta)
    elif state.mode == "info":
        state.info_offset = menu_scroll_offset(state.info_offset, delta)
    else:
        state.notes_offset = menu_scroll_offset(state.notes_offset, delta)


def _handle_overlay_key(state: EditorState, key: int) -> bool:
    if state.mode not in ("help", "info", "notes"):
        return False
    keycodes = state.keycodes
    bindings = help_bindings()
    if key in (*bindings.exit, keycodes.exit):
        set_mode(state, "normal")
        return True
    if key in (*bindings.down, keycodes.down):
        _move_overlay_offset(state, 1)
        return True
    if key in (*bindings.up, keycodes.up):
        _move_overlay_offset(state, -1)
        return True
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
    if state.pending_quit and key not in normal_bindings(state).quit:
        state.pending_quit = False
    if _handle_overlay_key(state, key):
        return True
    if state.mode == "plugin":
        from oud.editor.commands.plugins.operations import handle_plugin_key  # noqa: PLC0415

        return handle_plugin_key(state, key)
    if state.mode in ("insert", "replace"):
        return handle_insert(state, key)
    if state.mode == "command":
        return handle_command(state, key)
    if state.mode == "search":
        return handle_search(state, key)
    return handle_normal(state, key)
