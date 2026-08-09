from __future__ import annotations

from pathlib import Path

import pytest

from oud.editor.commands import dispatch
from oud.editor.core.state import EditorState
from oud.editor.services.io.files import render_ascii_snapshot
from oud.presentation.tui import commands
from oud.settings import DEFAULT_SETTINGS
from petrucci.core.model import Bar, Piece

_EXIT_COMMANDS = {"q", "quit", "wq", "x"}


def _state(tmp_path: Path) -> EditorState:
    state = EditorState(
        Piece(title="Command smoke", bars=[Bar(), Bar()], strings=6),
        dict(DEFAULT_SETTINGS),
        config_path=str(tmp_path / "config.toml"),
    )
    state.screen_width = 80
    state.screen_height = 24
    return state


def _command_line(name: str, tmp_path: Path) -> str:
    targets = {
        "w": tmp_path / "score.tab",
        "write": tmp_path / "score.tab",
        "wa": tmp_path / "score.txt",
        "wascii": tmp_path / "score.txt",
        "midi": tmp_path / "score.mid",
        "lilypond": tmp_path / "score.ly",
        "musicxml": tmp_path / "score.musicxml",
        "pdf": tmp_path / "score.pdf",
        "print": tmp_path / "score.pdf",
        "wq": tmp_path / "score.tab",
        "x": tmp_path / "score.tab",
    }
    target = targets.get(name)
    return f"{name} {target}" if target is not None else name


def _isolate_external_commands(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dispatch, "export_midi", lambda *_args, **_kwargs: "MIDI exported")
    monkeypatch.setattr(dispatch, "export_lilypond", lambda *_args, **_kwargs: "LilyPond exported")
    monkeypatch.setattr(dispatch, "export_musicxml", lambda *_args, **_kwargs: "MusicXML exported")
    monkeypatch.setattr(dispatch, "export_mxl", lambda *_args, **_kwargs: "MXL exported")
    monkeypatch.setattr(dispatch, "print_lilypond_pdf", lambda *_args, **_kwargs: "PDF printed")
    monkeypatch.setattr(dispatch, "save_settings", lambda *_args, **_kwargs: None)

    def start_midi(state: EditorState, **_kwargs: object) -> None:
        state.message = "MIDI started"

    monkeypatch.setattr("oud.editor.services.media.midi.start_midi", start_midi)


@pytest.mark.parametrize("name", commands.command_names())
def test_every_registered_command_smokes(
    name: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _isolate_external_commands(monkeypatch)
    state = _state(tmp_path)
    command = _command_line(name, tmp_path)

    if name in _EXIT_COMMANDS:
        with pytest.raises(SystemExit):
            commands.apply_command(state, command, state.config_path)
    else:
        commands.apply_command(state, command, state.config_path)

    if state.pdf_job is not None:
        state.pdf_job.join(timeout=1)
        assert not state.pdf_job.is_alive()
    if name not in _EXIT_COMMANDS:
        assert render_ascii_snapshot(state)


def test_command_name_inventory_matches_dispatch_table() -> None:
    registered = set(commands._command_map())
    advertised = set(commands.command_names())
    assert advertised == registered | _EXIT_COMMANDS
