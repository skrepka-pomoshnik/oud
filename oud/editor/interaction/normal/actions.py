from __future__ import annotations

from oud.editor.core.coordinates import normalize_count_prefix
from oud.editor.core.state import EditorState
from oud.editor.interaction.normal.commands import (
    handle_delete_action,
    handle_primary_action,
    handle_search_action,
    handle_session_action,
)
from oud.editor.interaction.normal.movement import handle_normal_movement, handle_visual_mode
from oud.editor.interaction.normal.pending import handle_prefix_input


def handle_normal(state: EditorState, key: int) -> bool:
    normalize_count_prefix(state)
    if state.mode in {"visual", "visual_line"}:
        return handle_visual_mode(state, key)
    if handle_prefix_input(state, key):
        return True
    session_result = handle_session_action(state, key)
    if session_result is not None:
        return session_result
    for handler in (handle_primary_action, handle_delete_action, handle_search_action):
        if handler(state, key):
            return True
    handle_normal_movement(state, key)
    return True
