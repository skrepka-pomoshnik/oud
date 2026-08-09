import os

from oud.editor.core.state import EditorState
from oud.presentation.tui.input import complete_command
from petrucci.core.model import Bar, Piece


def _state() -> EditorState:
    piece = Piece(title="T", bars=[Bar()])
    settings = {"style": "french"}
    return EditorState(piece, settings)


def test_complete_command_single_match() -> None:
    state = _state()
    state.cmdline = "pdf"
    complete_command(state)
    assert state.cmdline == "pdf "


def test_complete_command_exact_quit() -> None:
    state = _state()
    state.cmdline = "q"
    complete_command(state)
    assert state.cmdline == "q"


def test_complete_command_path(tmp_path) -> None:
    target = tmp_path / "example.tab"
    target.write_text("data", encoding="utf-8")
    state = _state()
    state.cmdline = f"e {target}"
    complete_command(state)
    assert state.cmdline == f"e {target}"


def test_complete_command_directory(tmp_path) -> None:
    subdir = tmp_path / "nested"
    subdir.mkdir()
    state = _state()
    state.cmdline = f"e {os.fspath(subdir)}"
    complete_command(state)
    assert state.cmdline.endswith(os.sep)


def test_complete_command_ignores_hidden_entries(tmp_path) -> None:
    (tmp_path / ".hidden.tab").write_text("data", encoding="utf-8")
    (tmp_path / "visible.tab").write_text("data", encoding="utf-8")
    state = _state()
    state.cmdline = f"e {tmp_path}{os.sep}."
    complete_command(state)
    assert state.cmdline == f"e {tmp_path}{os.sep}."
