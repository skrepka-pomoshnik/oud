import os

from oud.core.model import Bar, Piece
from oud.editor.state import EditorState
from oud.tui.input import (
    complete_command,
    handle_command,
    handle_search,
    history_next,
    history_prev,
    parse_search,
)


def _state() -> EditorState:
    piece = Piece(title="T", bars=[Bar(), Bar()], strings=6)
    settings = {"style": "french", "keys": "vim+arrows"}
    return EditorState(piece, settings)


def test_history_prev_next() -> None:
    state = _state()
    state.command_history = ["one", "two"]
    assert history_prev(state) == "two"
    assert history_prev(state) == "one"
    assert history_next(state) == "two"
    assert history_next(state) == ""


def test_history_empty() -> None:
    state = _state()
    assert history_prev(state) is None
    assert history_next(state) is None
    state.command_history = ["one"]
    state.command_history_index = None
    assert history_next(state) == ""


def test_complete_command_basic(tmp_path) -> None:
    state = _state()
    state.cmdline = "write"
    assert complete_command(state) is True
    assert state.cmdline == "write "
    state.cmdline = "q"
    assert complete_command(state) is True
    assert state.cmdline == "q"
    state.cmdline = "w"
    assert complete_command(state) is True
    assert state.message.startswith("Matches:")

    file_path = tmp_path / "file.tab"
    file_path.write_text("x", encoding="utf-8")
    dir_path = tmp_path / "folder"
    dir_path.mkdir()
    state.cmdline = f"e {tmp_path}{os.sep}f"
    assert complete_command(state) is True
    assert state.cmdline.startswith(f"e {tmp_path}")
    state.cmdline = f"e {dir_path}"
    assert complete_command(state) is True
    assert state.cmdline.endswith(os.sep)
    multi_dir = tmp_path / "many"
    multi_dir.mkdir()
    (multi_dir / "one.tab").write_text("x", encoding="utf-8")
    (multi_dir / "two.ft3").write_text("x", encoding="utf-8")
    state.cmdline = f"e {multi_dir}{os.sep}"
    assert complete_command(state) is True
    assert state.message.startswith("Matches:")
    state.cmdline = "zzzz"
    assert complete_command(state) is True
    state.cmdline = f"set {tmp_path}{os.sep}file"
    assert complete_command(state) is True
    state.cmdline = "set gu"
    assert complete_command(state) is True
    assert state.cmdline == "set guitar "
    state.cmdline = "set lu"
    assert complete_command(state) is True
    assert state.cmdline == "set lute "
    missing_dir = tmp_path / "missing"
    state.cmdline = f"e {missing_dir}{os.sep}x"
    assert complete_command(state) is True


def test_handle_command_paths() -> None:
    state = _state()
    calls: list[str] = []

    def _apply(_state: EditorState, cmdline: str) -> None:
        calls.append(cmdline)

    state.mode = "command"
    handle_command(state, 27, _apply)
    assert state.mode == "normal"
    state.mode = "command"
    state.cmdline = "w"
    handle_command(state, 10, _apply)
    assert calls == ["w"]
    assert state.command_history == ["w"]
    state.mode = "command"
    state.cmdline = "wa"
    handle_command(state, 127, _apply)
    assert state.cmdline == "w"
    state.command_history = ["one", "two"]
    handle_command(state, 259, _apply)  # curses.KEY_UP
    assert state.cmdline == "two"
    handle_command(state, 258, _apply)  # curses.KEY_DOWN
    assert state.cmdline in ("two", "")
    state.mode = "command"
    handle_command(state, ord("a"), _apply)
    assert state.cmdline.endswith("a")


def test_parse_search_and_handle_search() -> None:
    state = _state()
    assert parse_search("") is None
    assert parse_search("0") is None
    assert parse_search("3") == 2
    state.mode = "search"
    state.searchline = "2"
    handle_search(state, 10)
    assert state.cursor_bar == 1
    state.mode = "search"
    state.searchline = "bad"
    handle_search(state, 10)
    assert state.message == "Invalid bar"
    state.mode = "search"
    state.searchline = "12"
    handle_search(state, 27)
    assert state.mode == "normal"
    state.mode = "search"
    state.searchline = "12"
    handle_search(state, 127)
    assert state.searchline == "1"
    state.searchline = ""
    handle_search(state, ord("9"))
    assert state.searchline == "9"


def test_search_prompt_uses_history() -> None:
    state = _state()
    state.search_history = ["2", "7"]
    state.mode = "search"
    handle_search(state, 259)  # KEY_UP
    assert state.searchline == "7"
    handle_search(state, 259)  # KEY_UP
    assert state.searchline == "2"
    handle_search(state, 258)  # KEY_DOWN
    assert state.searchline == "7"
