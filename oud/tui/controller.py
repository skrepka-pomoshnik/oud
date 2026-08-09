from __future__ import annotations

from oud.editor.core.state import EditorState
from oud.editor.interaction.dispatch.controller import handle_key as dispatch_key


def handle_key(
    state: EditorState,
    key: int,
    *,
    handle_insert,
    handle_normal,
    handle_command,
    handle_search,
) -> bool:
    return dispatch_key(
        state,
        key,
        handle_insert=handle_insert,
        handle_normal=handle_normal,
        handle_command=handle_command,
        handle_search=handle_search,
    )
