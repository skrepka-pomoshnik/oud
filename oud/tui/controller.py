from __future__ import annotations

from oud.editor.controller import handle_key as dispatch_key
from oud.editor.state import EditorState


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
