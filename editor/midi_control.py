from __future__ import annotations

from pathlib import Path

from editor.state import EditorState
from exports.midi import export_midi, play_midi


def midi_output_path(state: EditorState) -> str:
    base = "out"
    if state.path:
        base = str(Path(state.path).with_suffix(""))
    return base + ".mid"


def stop_midi(state: EditorState) -> None:
    if state.midi_proc is None:
        return
    proc = state.midi_proc
    state.midi_proc = None
    if proc.poll() is None:
        proc.terminate()
    state.message = "MIDI stopped"


def start_midi(
    state: EditorState,
    start_bar: int | None = None,
    path: str | None = None,
    bpm: int | None = None,
) -> None:
    if state.midi_proc is not None and state.midi_proc.poll() is None:
        stop_midi(state)
    path = path or midi_output_path(state)
    start_bar = state.cursor_bar if start_bar is None else start_bar
    if bpm is None:
        try:
            bpm = int(state.settings.get("tempo", "90") or "90")
        except ValueError:
            bpm = 90
    state.message = export_midi(
        path,
        state.piece,
        state.overrides,
        state.durations,
        state.bar_width,
        settings=state.settings,
        bpm=bpm,
        start_bar=start_bar,
        dotted=state.dotted,
    )
    soundfont = state.settings.get("soundfont", "") or None
    state.message, state.midi_proc = play_midi(path, soundfont=soundfont)
