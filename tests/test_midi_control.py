from __future__ import annotations

import subprocess
from typing import cast

from oud.core.model import Bar, Chord, Note, Piece
from oud.core.playback_timeline import PlaybackCursor
from oud.editor.midi_control import midi_output_path, start_midi, stop_midi
from oud.editor.playback import (
    advance_playback_cursor,
    prime_playback_animation,
    reset_playback_animation,
    start_playback_clock,
    update_playback_animation,
)
from oud.editor.state import EditorState


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

    monkeypatch.setattr("oud.editor.midi_control.export_midi", _export_midi)
    monkeypatch.setattr("oud.editor.midi_control.play_midi", _play_midi)
    monkeypatch.setattr("oud.editor.midi_control.time.monotonic", lambda: 123.5)
    start_midi(state, start_bar=1, path="out.mid", bpm=120)
    messages.append(state.message)
    assert state.midi_proc is not None
    assert messages[-1] == "Playing"
    assert state.playback_started_at == 123.5


def test_start_midi_can_loop_selected_bar_range(monkeypatch) -> None:
    state = EditorState(
        Piece(
            title="T",
            bars=[
                Bar(chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)])]),
                Bar(chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 1, 0)])]),
                Bar(chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 2, 0)])]),
            ],
            strings=6,
        ),
        {"style": "french", "tempo": "90", "soundfont": ""},
    )
    exported: dict[str, int] = {}

    def _export_midi(_path: str, piece: Piece, *_args: object, **_kwargs: object) -> str:
        exported["bars"] = len(piece.bars)
        return "Exported"

    def _play_midi(_path: str, *_, **__) -> tuple[str, _Proc]:
        return ("Playing", _Proc())

    monkeypatch.setattr("oud.editor.midi_control.export_midi", _export_midi)
    monkeypatch.setattr("oud.editor.midi_control.play_midi", _play_midi)
    monkeypatch.setattr("oud.editor.midi_control.time.monotonic", lambda: 123.5)

    start_midi(state, start_bar=1, end_bar=2, loop_count=2)

    assert exported["bars"] == 4
    assert state.midi_proc is not None
    assert [cursor.bar for cursor in state.playback.timeline] == [1, 2, 1, 2]


def test_update_playback_animation_tracks_cursor(monkeypatch) -> None:
    state = _state()
    state.playback_timeline = [
        PlaybackCursor(start=0.0, end=0.5, bar=0, col=1),
        PlaybackCursor(start=0.5, end=1.0, bar=0, col=4),
    ]
    state.playback_started_at = 100.0
    state.playback_index = 0
    state.midi_proc = cast(subprocess.Popen[bytes], _Proc())
    monkeypatch.setattr("oud.editor.playback.time.monotonic", lambda: 100.25)
    assert update_playback_animation(state) is True
    assert state.playback_bar == 0
    assert state.playback_col == 1
    assert state.playback.markers == [(0, 1)]
    monkeypatch.setattr("oud.editor.playback.time.monotonic", lambda: 100.3)
    assert update_playback_animation(state) is False
    monkeypatch.setattr("oud.editor.playback.time.monotonic", lambda: 100.75)
    assert update_playback_animation(state) is True
    assert state.playback_col == 4


def test_update_playback_animation_accepts_legacy_tuple_entries(monkeypatch) -> None:
    state = _state()
    state.playback_timeline = cast(
        list[PlaybackCursor],
        [(0.0, 0.5, 0, 2), (0.5, 1.0, 0, 5)],
    )
    state.playback_started_at = 100.0
    state.playback_index = 0
    state.midi_proc = cast(subprocess.Popen[bytes], _Proc())
    monkeypatch.setattr("oud.editor.playback.time.monotonic", lambda: 100.6)
    assert update_playback_animation(state) is True
    assert state.playback_col == 5


def test_playback_reducers_prime_start_advance_reset() -> None:
    state = _state()
    timeline = [PlaybackCursor(start=0.0, end=0.5, bar=2, col=3)]
    prime_playback_animation(state, timeline)
    assert state.playback.timeline == timeline
    assert state.playback.started_at is None
    assert state.playback.index == 0
    assert state.playback.bar is None
    assert state.playback.col is None

    start_playback_clock(state, 10.0)
    assert state.playback.started_at == 10.0

    advance_playback_cursor(state, 0.25)
    assert state.playback.bar == 2
    assert state.playback.col == 3
    assert state.playback.markers == [(2, 3)]

    advance_playback_cursor(state, 0.75)
    assert state.playback.bar is None
    assert state.playback.col is None
    assert state.playback.markers == []

    reset_playback_animation(state)
    assert state.playback.timeline == []
    assert state.playback.started_at is None
    assert state.playback.index == 0


def test_update_playback_animation_tracks_simultaneous_markers(monkeypatch) -> None:
    state = _state()
    state.playback_timeline = [
        PlaybackCursor(start=0.0, end=0.5, bar=0, col=1),
        PlaybackCursor(start=0.0, end=0.5, bar=2, col=3),
    ]
    state.playback_started_at = 10.0
    state.playback_index = 0
    state.midi_proc = cast(subprocess.Popen[bytes], _Proc())
    monkeypatch.setattr("oud.editor.playback.time.monotonic", lambda: 10.25)
    assert update_playback_animation(state) is True
    assert state.playback.markers == [(0, 1), (2, 3)]
