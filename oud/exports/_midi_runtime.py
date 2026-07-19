from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from oud.exports._midi_bytes import DEFAULT_VOCAL_PATCH
from oud.exports._midi_projection import (
    _default_tuning,
    _parse_tuning,
    _repeat_hop_limit,
    _resolved_tuning_for_piece,
)
from oud.exports._midi_serialization import (
    _duet_midi_note_events,
    _single_score_midi_note_events,
    _write_midi_file,
)
from petrucci.duet_score import is_duet_score_piece
from petrucci.model import Piece


def export_midi(
    path: str,
    piece: Piece,
    overrides: dict[tuple[int, int, int], str],
    durations: dict[tuple[int, int, int], int],
    bar_width: int,
    settings: dict[str, str] | None = None,
    bpm: int = 90,
    start_bar: int = 0,
    dotted: set[tuple[int, int]] | None = None,
    ornaments: dict[tuple[int, int], str] | None = None,
) -> str:
    settings = settings or {}
    tuning = _resolved_tuning_for_piece(piece, settings)
    pitches = _parse_tuning(tuning) if tuning else _default_tuning(piece.strings)
    if len(pitches) < piece.strings:
        pitches.extend(_default_tuning(piece.strings)[len(pitches) :])
    program = int(settings.get("midipatch", "0") or "0")
    vocal_program = int(
        settings.get("midivocalpatch", str(DEFAULT_VOCAL_PATCH)) or str(DEFAULT_VOCAL_PATCH),
    )
    style = settings.get("style") or "french"
    gate_text = settings.get("midigate", "85")
    gate_percent = 85
    if gate_text.isdigit():
        gate_percent = max(10, min(100, int(gate_text)))
    gate = gate_percent / 100.0

    default_duration = 4
    if is_duet_score_piece(piece):
        max_repeat_hops = _repeat_hop_limit(len(piece.bars), settings)
        note_events = _duet_midi_note_events(
            piece,
            overrides=overrides,
            durations=durations,
            bar_width=bar_width,
            style=style,
            default_duration=default_duration,
            start_bar=start_bar,
            dotted=dotted,
            settings=settings,
            gate=gate,
            pitches=pitches,
            ornaments=ornaments,
            max_repeat_hops=max_repeat_hops,
        )
    else:
        note_events = _single_score_midi_note_events(
            piece,
            overrides=overrides,
            durations=durations,
            bar_width=bar_width,
            style=style,
            default_duration=default_duration,
            start_bar=start_bar,
            dotted=dotted,
            settings=settings,
            gate=gate,
            pitches=pitches,
            ornaments=ornaments,
        )
    return _write_midi_file(
        path,
        bpm=bpm,
        program=program,
        vocal_program=vocal_program,
        note_events=note_events,
    )


def _midi_command(  # noqa: C901
    path: str,
    soundfont: str | None,
    platform: str,
    fluidsynth: str | None,
    timidity: str | None,
    opener: str | None,
) -> list[str] | None:
    soundfont_path = None
    if soundfont:
        candidate = Path(soundfont).expanduser()
        if candidate.exists():
            soundfont_path = str(candidate)
    player = None
    if soundfont_path and fluidsynth:
        player = fluidsynth
    elif timidity:
        player = timidity
    elif platform == "darwin" and opener:
        return [opener, path]
    else:
        player = fluidsynth
    if player is None:
        return None
    if player.endswith("fluidsynth"):
        cmd = [player]
        cmd.append("-q")
        if platform == "darwin":
            cmd += ["-a", "coreaudio"]
        if soundfont_path:
            cmd += ["-ni", soundfont_path]
        cmd.append(path)
        return cmd
    return [player, path]


def play_midi(
    path: str,
    soundfont: str | None = None,
) -> tuple[str, subprocess.Popen[bytes] | None]:
    cmd = _midi_command(
        path=path,
        soundfont=soundfont,
        platform=sys.platform,
        fluidsynth=shutil.which("fluidsynth"),
        timidity=shutil.which("timidity"),
        opener=shutil.which("open") if sys.platform == "darwin" else None,
    )
    if cmd is None:
        return "No MIDI player found (timidity/fluidsynth/open)", None
    try:
        proc = subprocess.Popen(  # noqa: S603
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError as exc:
        return f"Failed to play MIDI: {exc}", None
    return f"Playing {path}", proc
