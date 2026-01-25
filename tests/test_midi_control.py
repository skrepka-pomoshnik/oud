from __future__ import annotations

import subprocess
from typing import cast

from core.model import Bar, Piece
from editor.midi_control import midi_output_path, start_midi, stop_midi
from editor.state import EditorState


class _Proc:
    def __init__(self) -> None:
        self._terminated = False

    def poll(self) -> int | None:
        return None if not self._terminated else 0

    def terminate(self) -> None:
        self._terminated = True


def _state() -> EditorState:
    piece = Piece(title="T", bars=[Bar()], strings=6)
    settings = {"style": "french", "tempo": "90", "soundfont": ""}
    return EditorState(piece, settings)


def test_midi_output_path_uses_state_path() -> None:
    state = _state()
    assert midi_output_path(state).endswith("out.mid")
    state.path = "example.tab"
    assert midi_output_path(state).endswith("example.mid")


def test_stop_midi_clears_proc() -> None:
    state = _state()
    proc = _Proc()
    state.midi_proc = cast(subprocess.Popen[bytes], proc)
    stop_midi(state)
    assert state.midi_proc is None
    assert state.message == "MIDI stopped"


def test_start_midi(monkeypatch) -> None:
    state = _state()
    messages: list[str] = []

    def _export_midi(_path: str, *_args: object, **_kwargs: object) -> str:
        return "Exported"

    def _play_midi(_path: str, *_, **__) -> tuple[str, _Proc]:
        return ("Playing", _Proc())

    monkeypatch.setattr("editor.midi_control.export_midi", _export_midi)
    monkeypatch.setattr("editor.midi_control.play_midi", _play_midi)
    start_midi(state, start_bar=1, path="out.mid", bpm=120)
    messages.append(state.message)
    assert state.midi_proc is not None
    assert messages[-1] == "Playing"
