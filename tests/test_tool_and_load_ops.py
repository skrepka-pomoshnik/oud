from __future__ import annotations

from pathlib import Path

from oud.editor.load_ops import cmd_open, load_piece_data
from oud.editor.state import EditorState, UndoAction
from oud.editor.tool_ops import cmd_info, cmd_notes, cmd_plugins, cmd_tool
from oud.editor.undo_ops import undo
from petrucci.model import Bar, Piece


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


def test_cmd_info_and_notes_and_plugins(monkeypatch) -> None:
    state = _state()
    state.insert_prefix = "/"
    state.replace_once = True
    cmd_info(state)
    assert state.mode == "info"
    assert state.info_offset == 0
    assert state.insert_prefix == ""
    assert state.replace_once is False
    cmd_notes(state)
    assert state.mode == "notes"
    assert state.notes_offset == 0

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
    state.stave_breaks = {1}
    state.annotations[(0, 0)] = "x"
    cmd_tool(state, "reflow", cfg, save_fn=_save)
    assert state.message == "Reflowed (breaks cleared)"
    assert state.stave_breaks == set()
    assert state.undo_stack[-1].kind == "group"
    assert state.undo_stack[-1].data["label"] == "reflow"
    undo(state, config_path=cfg)
    assert state.stave_breaks == {1}
    cmd_tool(state, "gridflags", cfg, save_fn=_save)
    assert state.settings["flagstyle"] in ("board", "standard")
    cmd_tool(state, "comments", cfg, save_fn=_save)
    assert state.annotations == {}
    undo(state, config_path=cfg)
    assert state.annotations == {(0, 0): "x"}
    cmd_tool(state, "unknown", cfg, save_fn=_save)
    assert state.message == "Tool: reflow|gridflags|flagstyle|comments"
    assert saves


def test_cmd_open_basic_paths(tmp_path: Path) -> None:
    state = _state()
    cmd_open(state, "", no_path_msg="No path", build_durations_fn=None)
    assert state.message == "No path"

    original = state.piece
    missing = tmp_path / "missing.ft3"
    cmd_open(state, str(missing), no_path_msg="No path", build_durations_fn=None)
    assert state.message == f"Missing file: {missing}"
    assert state.piece is original

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
    assert ":info" in state.message
    assert state.insert_prefix == ""
    assert state.replace_once is False


def test_cmd_open_empty_tab_preserves_current_score(tmp_path: Path) -> None:
    state = _state()
    state.piece.title = "Keep me"
    target = tmp_path / "broken.tab"
    target.write_text("not tablature\n", encoding="utf-8")

    cmd_open(state, str(target), no_path_msg="No path", build_durations_fn=None)

    assert state.piece.title == "Keep me"
    assert "no recoverable bars" in state.message


def test_cmd_open_resets_previous_file_state(tmp_path: Path) -> None:
    state = _state()
    target = tmp_path / "fresh.ft3"
    target.write_bytes(b"")
    old_action = UndoAction(kind="noop", data={})
    state.undo_stack.append(old_action)
    state.redo_stack.append(old_action)
    state.annotations[(0, 0)] = "ann"
    state.ornaments[(0, 0)] = "orn"
    state.highlights.add((0, 0, 0))
    state.slurs.append((0, 0, 1))
    state.ties.append((0, 0, 1))
    state.holds.append((0, 0, 1))
    state.glisses.append((0, 0, 1))
    state.stave_breaks.add(1)
    state.marks["a"] = (0, 0, 0)
    state.modified = True
    cmd_open(
        state,
        str(target),
        no_path_msg="No path",
        load_ft3_fn=lambda _p: Piece(title="Fresh", bars=[Bar()], strings=6),
        build_durations_fn=None,
    )
    assert state.undo_stack == []
    assert state.redo_stack == []
    assert state.annotations == {}
    assert state.ornaments == {}
    assert state.highlights == set()
    assert state.slurs == []
    assert state.ties == []
    assert state.holds == []
    assert state.glisses == []
    assert state.stave_breaks == set()
    assert state.marks == {}
    assert state.modified is False


def test_load_piece_data_returns_warning_piece_when_loader_raises(
    tmp_path: Path,
    monkeypatch,
) -> None:
    broken = tmp_path / "broken.ft3"
    broken.write_text("", encoding="utf-8")
    monkeypatch.setattr("oud.editor.load_ops.load_ft3", lambda _p: (_ for _ in ()).throw(ValueError("bad parse")))
    piece, overrides, durations, dotted, bar_width = load_piece_data(str(broken))
    assert piece.title == "broken"
    assert piece.import_warnings
    assert "Could not open broken.ft3" in piece.import_warnings[0]
    assert overrides == {}
    assert durations == {}
    assert dotted == set()
    assert bar_width is None
