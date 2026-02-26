from __future__ import annotations

from pathlib import Path

from oud.core.model import Bar, Piece
from oud.core.plugin_model import RemoteTab
from oud.editor.plugin_ops import enter_plugin_mode, handle_plugin_key
from oud.editor.state import EditorState


def _state() -> EditorState:
    piece = Piece(title="T", bars=[Bar()], strings=6)
    settings = {"style": "french", "tuning": "g2c3f3a3d4g4", "strings": "6"}
    return EditorState(piece, settings)


def test_enter_plugin_mode_sets_root_items() -> None:
    state = _state()
    state.insert_prefix = "/"
    state.replace_once = True
    enter_plugin_mode(state)
    assert state.mode == "plugin"
    assert state.plugin_items
    assert state.plugin_index == 0
    assert state.insert_prefix == ""
    assert state.replace_once is False


def test_handle_plugin_key_selects_index_item(monkeypatch) -> None:
    state = _state()
    enter_plugin_mode(state)
    items = [RemoteTab(title="Song", url="https://example.com/song.tab", is_dir=False)]
    monkeypatch.setattr("oud.plugins.lutemusic.fetch_supported_tabs", lambda _url: items)
    handle_plugin_key(state, 10)
    assert state.plugin_title == "Lutemusic"
    assert state.plugin_items
    handle_plugin_key(state, 10)
    assert state.plugin_items == items


def test_handle_plugin_key_downloads_item(monkeypatch, tmp_path: Path) -> None:
    state = _state()
    enter_plugin_mode(state)
    state.plugin_name = "lutemusic"
    state.plugin_items = [RemoteTab(title="Song", url="https://example.com/song.tab", is_dir=False)]
    monkeypatch.setattr("oud.plugins.lutemusic.download_tab", lambda _item, _dest: tmp_path / "song.tab")
    handle_plugin_key(state, ord("d"))
    assert state.message.startswith("Downloaded")


def test_handle_plugin_key_jump_to_top_and_bottom() -> None:
    state = _state()
    enter_plugin_mode(state)
    state.plugin_items = [
        RemoteTab(title="One", url="https://example.com/one.tab", is_dir=False),
        RemoteTab(title="Two", url="https://example.com/two.tab", is_dir=False),
        RemoteTab(title="Three", url="https://example.com/three.tab", is_dir=False),
    ]
    handle_plugin_key(state, ord("G"))
    assert state.plugin_index == 2
    handle_plugin_key(state, ord("g"))
    handle_plugin_key(state, ord("g"))
    assert state.plugin_index == 0
