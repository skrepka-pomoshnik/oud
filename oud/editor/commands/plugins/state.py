from __future__ import annotations

from oud.editor.core.session import set_mode
from oud.editor.core.state import EditorState
from oud.plugins.model import RemoteTab


def plugin_enter_root(state: EditorState, items: list[RemoteTab]) -> None:
    set_mode(state, "plugin")
    state.plugins.title = "Plugins"
    state.plugins.items = list(items)
    state.plugins.index = 0
    state.plugins.offset = 0
    state.plugins.stack = []
    state.plugins.name = None
    state.plugins.query = ""
    state.plugins.query_active = False
    state.plugins.pending = ""
    state.plugins.confirm = ""


def plugin_push_view(state: EditorState) -> None:
    state.plugins.stack.append(
        (
            state.plugins.title,
            list(state.plugins.items),
            state.plugins.index,
            state.plugins.offset,
            state.plugins.name,
        ),
    )


def plugin_pop_view(state: EditorState) -> bool:
    if not state.plugins.stack:
        return False
    title, items, index, offset, plugin_name = state.plugins.stack.pop()
    state.plugins.title = title
    state.plugins.items = items
    state.plugins.index = index
    state.plugins.offset = offset
    state.plugins.name = plugin_name
    state.plugins.query = ""
    state.plugins.query_active = False
    state.plugins.pending = ""
    state.plugins.confirm = ""
    return True


def plugin_open_list(
    state: EditorState,
    *,
    title: str,
    items: list[RemoteTab],
    plugin_name: str | None = None,
) -> None:
    state.plugins.title = title
    state.plugins.items = list(items)
    state.plugins.index = 0
    state.plugins.offset = 0
    state.plugins.pending = ""
    state.plugins.confirm = ""
    state.plugins.query = ""
    state.plugins.query_active = False
    if plugin_name is not None:
        state.plugins.name = plugin_name


def plugin_search_start(state: EditorState) -> None:
    state.plugins.query_active = True
    state.plugins.query = ""
    state.plugins.confirm = ""


def plugin_search_cancel(state: EditorState) -> None:
    state.plugins.query_active = False
    state.plugins.query = ""
    state.plugins.confirm = ""


def plugin_search_backspace(state: EditorState) -> None:
    state.plugins.query = state.plugins.query[:-1]


def plugin_search_append(state: EditorState, ch: str) -> None:
    state.plugins.query += ch


def plugin_search_finish(state: EditorState) -> str:
    query = state.plugins.query.strip().lower()
    state.plugins.query_active = False
    return query


def plugin_apply_nav(state: EditorState, *, index: int, offset: int, pending: str) -> None:
    state.plugins.index = index
    state.plugins.offset = offset
    state.plugins.pending = pending
