from __future__ import annotations

import math
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple

from model import Bar, Chord, Note, Piece

TICKS_PER_QUARTER = 480


def _note_type_to_denom(note_type: int) -> int | None:
    mapping = {
        2: 1,
        3: 2,
        4: 4,
        5: 8,
        6: 16,
        7: 32,
        8: 64,
        9: 128,
        10: 256,
    }
    return mapping.get(note_type)


def _duration_ticks(denom: int, dotted: bool) -> int:
    base = TICKS_PER_QUARTER * 4
    ticks = max(1, base // max(1, denom))
    if dotted:
        ticks = int(math.ceil(ticks * 1.5))
    return ticks


def _parse_tuning(tuning: str) -> List[int]:
    pitches: List[int] = []
    idx = 0
    text = tuning.strip()
    while idx < len(text):
        ch = text[idx]
        if ch.isalpha():
            note = ch.upper()
            idx += 1
            accidental = ""
            if idx < len(text) and text[idx] in "+-#b":
                accidental = text[idx]
                idx += 1
            start = idx
            while idx < len(text) and text[idx].isdigit():
                idx += 1
            octave = text[start:idx]
            if not octave:
                octave_num = 3
            else:
                octave_num = int(octave)
            semis = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}.get(
                note, 0
            )
            if accidental in ("+", "#"):
                semis += 1
            elif accidental in ("-", "b"):
                semis -= 1
            midi = (octave_num + 1) * 12 + semis
            if 0 <= midi <= 127:
                pitches.append(midi)
        else:
            idx += 1
    return pitches


def _default_tuning(strings: int) -> List[int]:
    defaults = [
        "g4",
        "d4",
        "a3",
        "f3",
        "c3",
        "g2",
        "f2",
        "e2",
        "d2",
        "c2",
    ]
    pitches = _parse_tuning("".join(defaults))
    return pitches[:strings]


def _fret_from_override(ch: str, style: str) -> int | None:
    if style == "italian":
        if ch.isdigit():
            return int(ch)
        if ch == "x":
            return 10
        return None
    if "a" <= ch <= "p":
        return ord(ch) - ord("a")
    return None


def _collect_manual_chords(
    bar_index: int,
    strings: int,
    bar_width: int,
    overrides: Dict[Tuple[int, int, int], str],
    durations: Dict[Tuple[int, int, int], int],
    style: str,
    default_duration: int,
) -> List[tuple[int, int, List[Note]]]:
    columns = sorted({col for (b, _s, col) in overrides.keys() if b == bar_index})
    events: List[tuple[int, List[Note]]] = []
    current_time = 0
    for col in columns:
        notes: List[Note] = []
        for s_idx in range(strings):
            key = (bar_index, s_idx, col)
            if key not in overrides:
                continue
            fret = _fret_from_override(overrides[key], style)
            if fret is None:
                continue
            notes.append(Note(string=s_idx + 1, fret=fret, raw_pos=0))
        if not notes:
            continue
        denom = default_duration
        for s_idx in range(strings):
            key = (bar_index, s_idx, col)
            if key in durations:
                denom = durations[key]
                break
        duration = _duration_ticks(denom, False)
        events.append((current_time, duration, notes))
        current_time += duration
    return events


def _chord_positions(
    chords: List[Chord], bar_width: int, default_duration: int
) -> List[int]:
    denoms: List[int] = []
    dotted: List[bool] = []
    for chord in chords:
        denom = _note_type_to_denom(chord.note_type) or default_duration
        denoms.append(denom)
        dotted.append(bool(chord.dotted))
    if not denoms:
        return []
    max_denom = max(denoms)
    base = max_denom * 2
    units: List[int] = []
    for denom, dot in zip(denoms, dotted, strict=False):
        u = max(1, base // denom)
        if dot:
            u = max(1, (u * 3) // 2)
        units.append(u)
    total = sum(units)
    if total <= 0:
        return []
    positions: List[int] = []
    cum = 0
    for u in units:
        pos = min(bar_width - 1, (cum * (bar_width - 1)) // total)
        positions.append(pos)
        cum += u
    return positions


def _apply_overrides(
    notes: List[Note],
    overrides: Dict[Tuple[int, int, int], str],
    bar_index: int,
    col: int,
    style: str,
    strings: int,
) -> List[Note]:
    if not overrides:
        return notes
    by_string: Dict[int, Note] = {note.string: note for note in notes}
    for s_idx in range(strings):
        key = (bar_index, s_idx, col)
        if key not in overrides:
            continue
        fret = _fret_from_override(overrides[key], style)
        if fret is None:
            continue
        by_string[s_idx + 1] = Note(string=s_idx + 1, fret=fret, raw_pos=0)
    return list(by_string.values())


def _bar_chord_events(
    bar: Bar,
    bar_index: int,
    strings: int,
    overrides: Dict[Tuple[int, int, int], str],
    durations: Dict[Tuple[int, int, int], int],
    bar_width: int,
    style: str,
    default_duration: int,
) -> List[tuple[int, int, List[Note]]]:
    events: List[tuple[int, int, List[Note]]] = []
    if not bar.chords:
        manual = _collect_manual_chords(
            bar_index,
            strings,
            bar_width,
            overrides,
            durations,
            style,
            default_duration,
        )
        for start, duration, notes in manual:
            events.append((start, duration, notes))
        return events
    time = 0
    positions = _chord_positions(bar.chords, bar_width, default_duration)
    for chord, col in zip(bar.chords, positions, strict=False):
        denom = _note_type_to_denom(chord.note_type) or default_duration
        duration = _duration_ticks(denom, chord.dotted)
        if chord.notes:
            notes = _apply_overrides(chord.notes, overrides, bar_index, col, style, strings)
            events.append((time, duration, notes))
        time += duration
    return events


def _note_on(channel: int, pitch: int, velocity: int) -> bytes:
    return bytes([0x90 | (channel & 0x0F), pitch & 0x7F, velocity & 0x7F])


def _note_off(channel: int, pitch: int, velocity: int) -> bytes:
    return bytes([0x80 | (channel & 0x0F), pitch & 0x7F, velocity & 0x7F])


def _program_change(channel: int, program: int) -> bytes:
    return bytes([0xC0 | (channel & 0x0F), program & 0x7F])


def _meta_tempo(bpm: int) -> bytes:
    mpqn = int(60_000_000 / max(1, bpm))
    return bytes([0xFF, 0x51, 0x03, (mpqn >> 16) & 0xFF, (mpqn >> 8) & 0xFF, mpqn & 0xFF])


def _end_of_track() -> bytes:
    return bytes([0xFF, 0x2F, 0x00])


def _vlq(value: int) -> bytes:
    value = max(0, value)
    out = [value & 0x7F]
    value >>= 7
    while value:
        out.append(0x80 | (value & 0x7F))
        value >>= 7
    out.reverse()
    return bytes(out)


def _write_track(events: List[tuple[int, bytes]]) -> bytes:
    events.sort(key=lambda item: item[0])
    data = bytearray()
    last_time = 0
    for time, payload in events:
        delta = time - last_time
        data.extend(_vlq(delta))
        data.extend(payload)
        last_time = time
    data.extend(_vlq(0))
    data.extend(_end_of_track())
    header = b"MTrk" + len(data).to_bytes(4, "big")
    return header + data


def export_midi(
    path: str,
    piece: Piece,
    overrides: Dict[Tuple[int, int, int], str],
    durations: Dict[Tuple[int, int, int], int],
    bar_width: int,
    settings: Dict[str, str | None] | None = None,
    bpm: int = 90,
    start_bar: int = 0,
) -> str:
    settings = settings or {}
    tuning = settings.get("tuning", "") or ""
    pitches = _parse_tuning(tuning) if tuning else _default_tuning(piece.strings)
    if len(pitches) < piece.strings:
        pitches.extend(_default_tuning(piece.strings)[len(pitches) :])
    program = int(settings.get("midipatch", "0") or "0")
    style = settings.get("style", "french")
    events: List[tuple[int, bytes]] = []
    events.append((0, _meta_tempo(bpm)))
    events.append((0, _program_change(0, program)))

    current_time = 0
    default_duration = 4
    for b_idx, bar in enumerate(piece.bars):
        if b_idx < start_bar:
            continue
        chord_events = _bar_chord_events(
            bar,
            b_idx,
            piece.strings,
            overrides,
            durations,
            bar_width,
            style,
            default_duration,
        )
        if not chord_events:
            continue
        max_end = 0
        for start, duration, notes in chord_events:
            for note in notes:
                s_idx = note.string - 1
                if s_idx < 0 or s_idx >= len(pitches):
                    continue
                pitch = pitches[s_idx] + note.fret
                events.append((current_time + start, _note_on(0, pitch, 80)))
                events.append((current_time + start + duration, _note_off(0, pitch, 64)))
            max_end = max(max_end, start + duration)
        current_time += max_end

    track = _write_track(events)
    header = b"MThd" + (6).to_bytes(4, "big") + (0).to_bytes(2, "big") + (1).to_bytes(2, "big")
    header += TICKS_PER_QUARTER.to_bytes(2, "big")
    data = header + track
    Path(path).write_bytes(data)
    return f"Wrote {path}"


def play_midi(path: str) -> str:
    player = shutil.which("timidity") or shutil.which("fluidsynth")
    if player is None:
        return "No MIDI player found (timidity/fluidsynth)"
    cmd = [player, path]
    try:
        subprocess.Popen(cmd)
    except OSError as exc:
        return f"Failed to play MIDI: {exc}"
    return f"Playing {path}"
