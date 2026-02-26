from __future__ import annotations

from pathlib import Path

from oud.core.model import Bar, Piece
from oud.editor.load_ops import cmd_open
from oud.editor.state import EditorState
from oud.editor.tool_ops import cmd_info, cmd_plugins, cmd_tool


def _state() -> EditorState:
    piece = Piece(title="T", bars=[Bar()], strings=6)
    settings = {
        "style": "french",
        "keys": "vim+arrows",
        "layout": "packed",
        "linelen": "80",
        "bargap": "1",
        "flagstyle": "standard",
    }
    state = EditorState(piece, settings)
    state.screen_width = 80
    return state


def test_cmd_info_and_plugins(monkeypatch) -> None:
    state = _state()
    state.insert_prefix = "/"
    state.replace_once = True
    cmd_info(state)
    assert state.mode == "info"
    assert state.info_offset == 0
    assert state.insert_prefix == ""
    assert state.replace_once is False

    called: dict[str, bool] = {"ok": False}

    def _enter_plugin_mode(_state: EditorState) -> None:
        called["ok"] = True

    monkeypatch.setattr("oud.editor.plugin_ops.enter_plugin_mode", _enter_plugin_mode)
    cmd_plugins(state)
    assert called["ok"] is True


def test_cmd_tool_variants(tmp_path: Path) -> None:
    state = _state()
    saves: list[dict[str, str]] = []

    def _save(_path: str, settings: dict[str, str]) -> None:
        saves.append(dict(settings))

    cfg = str(tmp_path / "cfg.toml")
    state.annotations[(0, 0)] = "x"
    cmd_tool(state, "reflow", cfg, save_fn=_save)
    assert state.message == "Reflowed (breaks cleared)"
    cmd_tool(state, "gridflags", cfg, save_fn=_save)
    assert state.settings["flagstyle"] in ("board", "standard")
    cmd_tool(state, "comments", cfg, save_fn=_save)
    assert state.annotations == {}
    cmd_tool(state, "unknown", cfg, save_fn=_save)
    assert state.message == "Tool: reflow|gridflags|flagstyle|comments"
    assert saves


def test_cmd_open_basic_paths(tmp_path: Path) -> None:
    state = _state()
    cmd_open(state, "", no_path_msg="No path", build_durations_fn=None)
    assert state.message == "No path"

    folder = tmp_path / "dir"
    folder.mkdir()
    state.insert_prefix = ",1"
    state.replace_once = True
    cmd_open(state, str(folder), no_path_msg="No path", build_durations_fn=None)
    assert state.message == ""


def test_cmd_open_appends_import_warning_to_message(tmp_path: Path) -> None:
    state = _state()
    target = tmp_path / "warn.ft3"
    target.write_bytes(b"")
    warned_piece = Piece(title="W", bars=[Bar()], strings=6)
    warned_piece.import_warnings.append("FT3 lyric/melody text records are present and currently ignored.")
    state.insert_prefix = "/"
    state.replace_once = True
    cmd_open(
        state,
        str(target),
        no_path_msg="No path",
        load_ft3_fn=lambda _p: warned_piece,
        build_durations_fn=None,
    )
    assert "Opened" in state.message
    assert "lyric/melody text records" in state.message
    assert state.insert_prefix == ""
    assert state.replace_once is False
