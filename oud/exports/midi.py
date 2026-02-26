from __future__ import annotations

import math
import shutil
import subprocess
import sys
from pathlib import Path

from oud.core.duet_score import duet_logical_bar_count, duet_raw_bar_index, is_duet_score_piece
from oud.core.model import Bar, Chord, Note, Piece
from oud.core.playback_timeline import PlaybackCursor, build_timeline_from_events
from oud.core.time_utils import parse_time_signature_value
from oud.core.tuning_utils import default_bass_strings, parse_bass_strings, tuning_count

TICKS_PER_QUARTER = 480
BASE_NOTE_VELOCITY = 80


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
        ticks = math.ceil(ticks * 1.5)
    return ticks


def _parse_tuning(tuning: str) -> list[int]:
    pitches: list[int] = []
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
            octave_num = 3 if not octave else int(octave)
            semis = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}.get(
                note, 0,
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
    pitches.reverse()
    return pitches


def _default_tuning(strings: int) -> list[int]:
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


def _resolved_tuning_for_piece(piece: Piece, settings: dict[str, str]) -> str:
    tuning = (settings.get("tuning", "") or "").strip()
    if not tuning:
        return tuning
    missing = max(0, piece.strings - tuning_count(tuning))
    if missing <= 0:
        return tuning
    bass_tokens = parse_bass_strings(settings.get("bassstrings", ""))
    if not bass_tokens:
        bass_tokens = default_bass_strings(missing)
    # Tuning strings are stored low->high before _parse_tuning() reverses them.
    # Extra bass courses must be prepended (lower than the existing lowest course).
    return "".join(bass_tokens[:missing]) + tuning


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
    overrides: dict[tuple[int, int, int], str],
    durations: dict[tuple[int, int, int], int],
    style: str,
    default_duration: int,
    dotted: set[tuple[int, int]] | None,
) -> list[tuple[int, int, int, list[Note]]]:
    _ = bar_width
    columns = sorted({col for (b, _s, col) in overrides if b == bar_index})
    events: list[tuple[int, int, int, list[Note]]] = []
    current_time = 0
    for col in columns:
        notes: list[Note] = []
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
        is_dotted = dotted is not None and (bar_index, col) in dotted
        duration = _duration_ticks(denom, is_dotted)
        events.append((current_time, duration, col, notes))
        current_time += duration
    return events


def _chord_positions(
    chords: list[Chord], bar_width: int, default_duration: int,
) -> list[int]:
    denoms: list[int] = []
    dotted: list[bool] = []
    for chord in chords:
        denom = _note_type_to_denom(chord.note_type) or default_duration
        denoms.append(denom)
        dotted.append(bool(chord.dotted))
    if not denoms:
        return []
    max_denom = max(denoms)
    base = max_denom * 2
    units: list[int] = []
    for denom, dot in zip(denoms, dotted, strict=False):
        u = max(1, base // denom)
        if dot:
            u = max(1, (u * 3) // 2)
        units.append(u)
    total = sum(units)
    if total <= 0:
        return []
    positions: list[int] = []
    cum = 0
    prev_pos = -1
    for u in units:
        raw_pos = min(bar_width - 1, (cum * (bar_width - 1)) // total)
        pos = min(bar_width - 1, max(raw_pos, prev_pos + 1))
        positions.append(pos)
        prev_pos = pos
        cum += u
    return positions


def _apply_overrides(
    notes: list[Note],
    overrides: dict[tuple[int, int, int], str],
    bar_index: int,
    col: int,
    style: str,
    strings: int,
) -> list[Note]:
    if not overrides:
        return notes
    by_string: dict[int, Note] = {note.string: note for note in notes}
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
    overrides: dict[tuple[int, int, int], str],
    durations: dict[tuple[int, int, int], int],
    bar_width: int,
    style: str,
    default_duration: int,
    dotted: set[tuple[int, int]] | None,
) -> list[tuple[int, int, int, list[Note]]]:
    events: list[tuple[int, int, int, list[Note]]] = []
    if not bar.chords:
        manual = _collect_manual_chords(
            bar_index,
            strings,
            bar_width,
            overrides,
            durations,
            style,
            default_duration,
            dotted,
        )
        for start, duration, col, notes in manual:
            events.append((start, duration, col, notes))
        return events
    time = 0
    positions = _chord_positions(bar.chords, bar_width, default_duration)
    for chord, col in zip(bar.chords, positions, strict=False):
        denom = _note_type_to_denom(chord.note_type) or default_duration
        is_dotted = chord.dotted or (dotted is not None and (bar_index, col) in dotted)
        duration = _duration_ticks(denom, is_dotted)
        if chord.notes:
            notes = _apply_overrides(chord.notes, overrides, bar_index, col, style, strings)
            events.append((time, duration, col, notes))
        time += duration
    return events


def _duet_pair_bar_indices(piece: Piece, start_bar: int) -> list[tuple[int | None, int | None]]:
    start_pair = max(0, start_bar // 2)
    total_pairs = duet_logical_bar_count(piece)
    pairs: list[tuple[int | None, int | None]] = []
    for pair_idx in range(start_pair, total_pairs):
        first = duet_raw_bar_index(0, pair_idx, piece=piece)
        second = duet_raw_bar_index(1, pair_idx, piece=piece)
        pairs.append(
            (
                first if first < len(piece.bars) else None,
                second if second < len(piece.bars) else None,
            ),
        )
    return pairs


def _duet_timeline_events(
    piece: Piece,
    *,
    overrides: dict[tuple[int, int, int], str],
    durations: dict[tuple[int, int, int], int],
    bar_width: int,
    style: str,
    default_duration: int,
    start_bar: int,
    dotted: set[tuple[int, int]] | None,
) -> list[tuple[int, int, int, int]]:
    timeline_events: list[tuple[int, int, int, int]] = []
    current_time = 0
    for first_idx, second_idx in _duet_pair_bar_indices(piece, start_bar):
        pair_base_time = current_time
        pair_max_end = 0
        for b_idx in (first_idx, second_idx):
            if b_idx is None:
                continue
            bar = piece.bars[b_idx]
            chord_events = _bar_chord_events(
                bar,
                b_idx,
                piece.strings,
                overrides,
                durations,
                bar_width,
                style,
                default_duration,
                dotted=dotted,
            )
            if not chord_events:
                continue
            max_end = 0
            for event_idx, (start, duration, col, notes) in enumerate(chord_events):
                if not notes:
                    continue
                marker_col = event_idx if bar.chords else col
                timeline_events.append((b_idx, pair_base_time + start, duration, marker_col))
                max_end = max(max_end, start + duration)
            pair_max_end = max(pair_max_end, max_end)
        current_time += pair_max_end
    return timeline_events


def _duet_note_events(
    piece: Piece,
    *,
    overrides: dict[tuple[int, int, int], str],
    durations: dict[tuple[int, int, int], int],
    bar_width: int,
    style: str,
    default_duration: int,
    start_bar: int,
    dotted: set[tuple[int, int]] | None,
    settings: dict[str, str],
    gate: float,
    pitches: list[int],
) -> list[tuple[int, bytes]]:
    events: list[tuple[int, bytes]] = []
    current_time = 0
    for first_idx, second_idx in _duet_pair_bar_indices(piece, start_bar):
        pair_base_time = current_time
        pair_max_end = 0
        for b_idx in (first_idx, second_idx):
            if b_idx is None:
                continue
            bar = piece.bars[b_idx]
            beats, unit = _meter_for_bar(bar, settings)
            chord_events = _bar_chord_events(
                bar,
                b_idx,
                piece.strings,
                overrides,
                durations,
                bar_width,
                style,
                default_duration,
                dotted=dotted,
            )
            if not chord_events:
                continue
            max_end = 0
            for start, duration, _col, notes in chord_events:
                velocity = _accent_velocity(start, beats, unit)
                note_len = max(1, int(duration * gate))
                for note in notes:
                    s_idx = note.string - 1
                    if s_idx < 0 or s_idx >= len(pitches):
                        continue
                    pitch = pitches[s_idx] + note.fret
                    events.append((pair_base_time + start, _note_on(0, pitch, velocity)))
                    events.append((pair_base_time + start + note_len, _note_off(0, pitch, 64)))
                max_end = max(max_end, start + duration)
            pair_max_end = max(pair_max_end, max_end)
        current_time += pair_max_end
    return events


def build_playback_timeline(
    piece: Piece,
    overrides: dict[tuple[int, int, int], str],
    durations: dict[tuple[int, int, int], int],
    bar_width: int,
    settings: dict[str, str] | None = None,
    *,
    bpm: int = 90,
    start_bar: int = 0,
    dotted: set[tuple[int, int]] | None = None,
) -> list[PlaybackCursor]:
    settings = settings or {}
    style = settings.get("style") or "french"
    default_duration = 4
    timeline_events: list[tuple[int, int, int, int]] = []
    sec_per_tick = 60.0 / (max(1, bpm) * TICKS_PER_QUARTER)
    if is_duet_score_piece(piece):
        timeline_events = _duet_timeline_events(
            piece,
            overrides=overrides,
            durations=durations,
            bar_width=bar_width,
            style=style,
            default_duration=default_duration,
            start_bar=start_bar,
            dotted=dotted,
        )
        return build_timeline_from_events(timeline_events, sec_per_tick=sec_per_tick)
    current_time = 0
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
            dotted=dotted,
        )
        if not chord_events:
            continue
        max_end = 0
        for event_idx, (start, duration, col, notes) in enumerate(chord_events):
            if not notes:
                continue
            marker_col = event_idx if bar.chords else col
            timeline_events.append(
                (b_idx, current_time + start, duration, marker_col),
            )
            max_end = max(max_end, start + duration)
        current_time += max_end
    return build_timeline_from_events(timeline_events, sec_per_tick=sec_per_tick)


def _note_on(channel: int, pitch: int, velocity: int) -> bytes:
    return bytes([0x90 | (channel & 0x0F), pitch & 0x7F, velocity & 0x7F])


def _note_off(channel: int, pitch: int, velocity: int) -> bytes:
    return bytes([0x80 | (channel & 0x0F), pitch & 0x7F, velocity & 0x7F])


def _program_change(channel: int, program: int) -> bytes:
    return bytes([0xC0 | (channel & 0x0F), program & 0x7F])


def _meta_tempo(bpm: int) -> bytes:
    mpqn = int(60_000_000 / max(1, bpm))
    return bytes([0xFF, 0x51, 0x03, (mpqn >> 16) & 0xFF, (mpqn >> 8) & 0xFF, mpqn & 0xFF])


def _meter_for_bar(bar: Bar, settings: dict[str, str]) -> tuple[int, int]:
    if bar.time_sig:
        parsed = parse_time_signature_value(bar.time_sig)
        if parsed is not None:
            return parsed
    parsed = parse_time_signature_value(settings.get("time", ""))
    if parsed is not None:
        return parsed
    return 4, 4


def _accent_velocity(start: int, beats: int, unit: int, base: int = BASE_NOTE_VELOCITY) -> int:
    beat_ticks = _duration_ticks(unit, dotted=False)
    if beat_ticks <= 0 or start % beat_ticks != 0:
        return base
    beat_index = (start // beat_ticks) % max(1, beats)
    if beats == 4:
        if beat_index == 0:
            return min(127, base + 18)
        if beat_index == 2:
            return min(127, base + 8)
    elif beats == 3:
        if beat_index == 0:
            return min(127, base + 16)
    elif beat_index == 0:
        return min(127, base + 14)
    return base


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


def _write_track(events: list[tuple[int, bytes]]) -> bytes:
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
    overrides: dict[tuple[int, int, int], str],
    durations: dict[tuple[int, int, int], int],
    bar_width: int,
    settings: dict[str, str] | None = None,
    bpm: int = 90,
    start_bar: int = 0,
    dotted: set[tuple[int, int]] | None = None,
) -> str:
    settings = settings or {}
    tuning = _resolved_tuning_for_piece(piece, settings)
    pitches = _parse_tuning(tuning) if tuning else _default_tuning(piece.strings)
    if len(pitches) < piece.strings:
        pitches.extend(_default_tuning(piece.strings)[len(pitches) :])
    program = int(settings.get("midipatch", "0") or "0")
    style = settings.get("style") or "french"
    gate_text = settings.get("midigate", "85")
    gate_percent = 85
    if gate_text.isdigit():
        gate_percent = max(10, min(100, int(gate_text)))
    gate = gate_percent / 100.0
    events: list[tuple[int, bytes]] = []
    events.append((0, _meta_tempo(bpm)))
    events.append((0, _program_change(0, program)))

    default_duration = 4
    if is_duet_score_piece(piece):
        events.extend(
            _duet_note_events(
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
            ),
        )
        track = _write_track(events)
        header = b"MThd" + (6).to_bytes(4, "big") + (0).to_bytes(2, "big") + (1).to_bytes(2, "big")
        header += TICKS_PER_QUARTER.to_bytes(2, "big")
        data = header + track
        Path(path).write_bytes(data)
        return f"Wrote {path}"
    current_time = 0
    for b_idx, bar in enumerate(piece.bars):
        if b_idx < start_bar:
            continue
        beats, unit = _meter_for_bar(bar, settings)
        chord_events = _bar_chord_events(
            bar,
            b_idx,
            piece.strings,
            overrides,
            durations,
            bar_width,
            style,
            default_duration,
            dotted=dotted,
        )
        if not chord_events:
            continue
        max_end = 0
        for start, duration, _col, notes in chord_events:
            velocity = _accent_velocity(start, beats, unit)
            note_len = max(1, int(duration * gate))
            for note in notes:
                s_idx = note.string - 1
                if s_idx < 0 or s_idx >= len(pitches):
                    continue
                pitch = pitches[s_idx] + note.fret
                events.append((current_time + start, _note_on(0, pitch, velocity)))
                events.append((current_time + start + note_len, _note_off(0, pitch, 64)))
            max_end = max(max_end, start + duration)
        current_time += max_end

    track = _write_track(events)
    header = b"MThd" + (6).to_bytes(4, "big") + (0).to_bytes(2, "big") + (1).to_bytes(2, "big")
    header += TICKS_PER_QUARTER.to_bytes(2, "big")
    data = header + track
    Path(path).write_bytes(data)
    return f"Wrote {path}"


def _midi_command(
    path: str,
    soundfont: str | None,
    platform: str,
    fluidsynth: str | None,
    timidity: str | None,
    opener: str | None,
) -> list[str] | None:
    soundfont_path = None
    if soundfont:
        soundfont_path = str(Path(soundfont).expanduser())
    if fluidsynth and (soundfont_path or platform == "darwin"):
        player = fluidsynth
    else:
        player = timidity or fluidsynth
    if player is None:
        if platform == "darwin" and opener:
            return [opener, path]
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
