from __future__ import annotations

from oud.core.plugin_model import RemoteTab
from oud.editor.plugin_state import (
    plugin_apply_nav,
    plugin_enter_root,
    plugin_open_list,
    plugin_pop_view,
    plugin_push_view,
    plugin_search_append,
    plugin_search_backspace,
    plugin_search_cancel,
    plugin_search_finish,
    plugin_search_start,
)
from oud.editor.state import EditorState
from oud.petrucci.model import Bar, Piece


def _state() -> EditorState:
    return EditorState(Piece(title="T", bars=[Bar()]), {"style": "french"})


def test_plugin_enter_root_resets_plugin_view() -> None:
    state = _state()
    state.plugins.title = "Old"
    state.plugins.query = "x"
    items = [RemoteTab(title="A", url="plugin:a", is_dir=True)]
    plugin_enter_root(state, items)
    assert state.mode == "plugin"
    assert state.plugins.title == "Plugins"
    assert state.plugins.items == items
    assert state.plugins.index == 0
    assert state.plugins.offset == 0
    assert state.plugins.stack == []
    assert state.plugins.query == ""
    assert state.plugins.query_active is False


def test_plugin_push_pop_restores_view() -> None:
    state = _state()
    plugin_enter_root(state, [RemoteTab(title="Root", url="plugin:x", is_dir=True)])
    state.plugins.name = "x"
    plugin_push_view(state)
    plugin_open_list(
        state,
        title="Nested",
        items=[RemoteTab(title="Song", url="s", is_dir=False)],
        plugin_name="x",
    )
    state.plugins.query = "frog"
    state.plugins.query_active = True
    state.plugins.pending = "g"
    assert plugin_pop_view(state) is True
    assert state.plugins.title == "Plugins"
    assert state.plugins.query == ""
    assert state.plugins.query_active is False
    assert state.plugins.pending == ""
    assert plugin_pop_view(state) is False


def test_plugin_search_reducers_and_nav() -> None:
    state = _state()
    plugin_search_start(state)
    assert state.plugins.query_active is True
    plugin_search_append(state, "f")
    plugin_search_append(state, "r")
    plugin_search_backspace(state)
    assert state.plugins.query == "f"
    query = plugin_search_finish(state)
    assert query == "f"
    assert state.plugins.query_active is False
    plugin_search_start(state)
    plugin_search_append(state, "x")
    plugin_search_cancel(state)
    assert state.plugins.query == ""
    assert state.plugins.query_active is False
    plugin_apply_nav(state, index=3, offset=1, pending="g")
    assert state.plugins.index == 3
    assert state.plugins.offset == 1
    assert state.plugins.pending == "g"
