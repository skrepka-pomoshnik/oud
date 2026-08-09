import os
import subprocess

from oud.editor.core.state import EditorState
from oud.presentation.tui.input import (
    complete_command,
    complete_command_text,
    handle_command,
    handle_search,
    history_next,
    history_prev,
    parse_search,
)
from petrucci.core.model import Bar, Piece


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
    assert state.cmdline == "w "
    assert state.message == ""

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


def test_path_completion_lists_every_candidate(tmp_path) -> None:
    state = _state()
    for index in range(12):
        (tmp_path / f"piece-{index:02}.tab").write_text("x", encoding="utf-8")

    text, message = complete_command_text(state, f"e {tmp_path}{os.sep}")

    assert text == f"e {tmp_path}{os.sep}piece-"
    assert message is None
    text, message = complete_command_text(state, text)
    assert text == f"e {tmp_path}{os.sep}piece-"
    assert message is not None
    assert all(f"piece-{index:02}.tab" in message for index in range(12))


def test_path_completion_lists_directory_children_without_repeating_prefix(tmp_path) -> None:
    state = _state()
    directory = tmp_path / "examples"
    directory.mkdir()
    (directory / "alpha.tab").write_text("x", encoding="utf-8")
    (directory / "zeta.ft3").write_text("x", encoding="utf-8")

    text, message = complete_command_text(state, f"e {directory}{os.sep}")

    assert text == f"e {directory}{os.sep}"
    assert message is not None
    assert "alpha.tab" in message
    assert "zeta.ft3" in message


def test_fzf_path_completion_uses_system_filter(monkeypatch, tmp_path) -> None:
    state = _state()
    state.settings["completion"] = "fzf"
    first = tmp_path / "first-piece.tab"
    second = tmp_path / "second-piece.tab"
    first.write_text("x", encoding="utf-8")
    second.write_text("x", encoding="utf-8")
    monkeypatch.setattr("oud.presentation.tui.input.completion.shutil.which", lambda _name: "/usr/bin/fzf")

    def _run(command, **kwargs):
        assert command == ["/usr/bin/fzf", "--filter", "scd"]
        assert "first-piece.tab" in kwargs["input"]
        return subprocess.CompletedProcess(command, 0, stdout="second-piece.tab\n", stderr="")

    monkeypatch.setattr("oud.presentation.tui.input.completion.subprocess.run", _run)

    text, message = complete_command_text(state, f"e {tmp_path}{os.sep}scd")

    assert text == f"e {second}"
    assert message is None


def test_complete_set_value_uses_legit_options_only() -> None:
    state = _state()
    text, msg = complete_command_text(state, "set tabnotation=")
    assert text == "set tabnotation="
    assert msg is not None and "full" in msg and "minimal" in msg

    text, msg = complete_command_text(state, "set timesigstyle=n")
    assert text == "set timesigstyle=numeric"
    assert msg is None

    text, msg = complete_command_text(state, "set multifretspacing=s")
    assert text in {"set multifretspacing=separated", "set multifretspacing=s"}
    assert msg is None or msg.startswith("Options:")

    text, msg = complete_command_text(state, "set fretlabelmode=l")
    assert text in {"set fretlabelmode=letters", "set fretlabelmode=l"}
    assert msg is None or msg.startswith("Options:")

    text, msg = complete_command_text(state, "set beatsnap=")
    assert text == "set beatsnap="
    assert msg is not None and "off" in msg and "soft" in msg

    text, msg = complete_command_text(state, "set flaglean=l")
    assert text in {"set flaglean=left", "set flaglean=l"}
    assert msg is None or msg.startswith("Options:")

    text, msg = complete_command_text(state, "set movementmode=n")
    assert text in {"set movementmode=note", "set movementmode=n"}
    assert msg is None or msg.startswith("Options:")

    text, msg = complete_command_text(state, "set minimumfret=")
    assert text == "set minimumfret="
    assert msg is not None and "0" in msg and "7" in msg

    text, msg = complete_command_text(state, "set restrainopenstrings=")
    assert text == "set restrainopenstrings=o"
    assert msg is None

    text, msg = complete_command_text(state, "set flagredundant=")
    assert text == "set flagredundant=o"
    assert msg is None

    text, msg = complete_command_text(state, "set vocalpos=")
    assert text == "set vocalpos="
    assert msg is not None and "top" in msg and "bottom" in msg

    text, msg = complete_command_text(state, "set vocalpos=t")
    assert text in {"set vocalpos=top", "set vocalpos=t"}
    assert msg is None or msg.startswith("Options:")

    text, msg = complete_command_text(state, "set layout=s")
    # layout accepts "spread" and legacy alias "stretch" route
    assert text.startswith("set layout=s")
    assert msg is None or msg.startswith("Options:")

    text, msg = complete_command_text(state, "set madeup=")
    assert text == "set madeup="
    assert msg is None

    text, msg = complete_command_text(state, "set completion=f")
    assert text == "set completion=fzf"
    assert msg is None


def test_complete_set_hides_deprecated_show_keys_and_offers_explicit_ones() -> None:
    state = _state()
    text, msg = complete_command_text(state, "set show")
    assert text == "set show"
    assert msg is not None
    assert "showspans" in msg
    assert "showfingerings" in msg
    assert "showornaments" in msg
    assert "showextras" not in msg
    assert "showft3extras" not in msg


def test_complete_set_offers_vim_style_bool_prefix_forms() -> None:
    state = _state()
    text, msg = complete_command_text(state, "set nogr")
    assert text in {"set nogrid ", "set nogr"}
    assert msg is None or msg.startswith(("Options:", "Matches:"))

    text, msg = complete_command_text(state, "set invgr")
    assert text in {"set invgrid ", "set invgr"}
    assert msg is None or msg.startswith(("Options:", "Matches:"))


def test_handle_command_paths() -> None:
    state = _state()
    calls: list[str] = []

    def _apply(_state: EditorState, cmdline: str) -> None:
        calls.append(cmdline)

    state.mode = "command"
    state.message = "Matches: old.tab"
    handle_command(state, 27, _apply)
    assert state.mode == "normal"
    assert state.message == ""
    assert state.insert_prefix == ""
    assert state.replace_once is False
    state.mode = "command"
    state.cmdline = "w"
    state.insert_prefix = "/"
    state.replace_once = True
    handle_command(state, 10, _apply)
    assert calls == ["w"]
    assert state.command_history == ["w"]
    assert state.insert_prefix == ""
    assert state.replace_once is False
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
    state.insert_prefix = ",1"
    state.replace_once = True
    handle_search(state, 10)
    assert state.cursor_bar == 1
    assert state.insert_prefix == ""
    assert state.replace_once is False
    state.mode = "search"
    state.searchline = "bad"
    handle_search(state, 10)
    assert state.message == "Invalid bar"
    state.mode = "search"
    state.searchline = "12"
    state.insert_prefix = "/"
    state.replace_once = True
    handle_search(state, 27)
    assert state.mode == "normal"
    assert state.insert_prefix == ""
    assert state.replace_once is False
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
