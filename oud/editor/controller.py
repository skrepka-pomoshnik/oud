from __future__ import annotations

from collections.abc import Callable

from oud.editor.insert_session import set_mode
from oud.editor.keymap import help_bindings, normal_bindings
from oud.editor.list_menu import menu_scroll_offset
from oud.editor.state import EditorState


def handle_key(  # noqa: C901, PLR0911, PLR0912
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
    if state.mode in ("help", "info"):
        keycodes = state.keycodes
        bindings = help_bindings()
        exit_keys = (*bindings.exit, keycodes.exit)
        up_keys = (*bindings.up, keycodes.up)
        down_keys = (*bindings.down, keycodes.down)
        if key in exit_keys:
            set_mode(state, "normal")
            return True
        if key in down_keys:
            if state.mode == "help":
                state.help_offset = menu_scroll_offset(state.help_offset, 1)
            else:
                state.info_offset = menu_scroll_offset(state.info_offset, 1)
            return True
        if key in up_keys:
            if state.mode == "help":
                state.help_offset = menu_scroll_offset(state.help_offset, -1)
            else:
                state.info_offset = menu_scroll_offset(state.info_offset, -1)
            return True
        return True
    if state.mode == "plugin":
        from oud.editor.plugin_ops import handle_plugin_key  # noqa: PLC0415

        return handle_plugin_key(state, key)
    if state.mode == "insert":
        return handle_insert(state, key)
    if state.mode == "command":
        return handle_command(state, key)
    if state.mode == "search":
        return handle_search(state, key)
    return handle_normal(state, key)
