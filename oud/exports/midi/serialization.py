from __future__ import annotations

from pathlib import Path

from oud.exports.midi.bytes import (
    TICKS_PER_QUARTER,
)
from oud.exports.midi.bytes import (
    accent_velocity as _accent_velocity,
)
from oud.exports.midi.bytes import (
    meta_tempo as _meta_tempo,
)
from oud.exports.midi.bytes import (
    meter_for_bar as _meter_for_bar,
)
from oud.exports.midi.bytes import (
    program_change as _program_change,
)
from oud.exports.midi.bytes import (
    write_track as _write_track,
)
from oud.exports.midi.projection import (
    _append_note_messages,
    _append_vocal_messages,
    _bar_chord_events,
    _duet_note_events,
    _duration_ticks,
    _midi_total_ticks,
    _picked_note_ornament,
    _playverse_count,
    _repeat_hop_limit,
    _repeat_play_order,
    _shift_midi_events,
    _show_ornaments,
)
from petrucci.core.imported import project_imported_staff
from petrucci.core.model import Bar, MelodyEvent, Note, Piece

_VOCAL_CHANNELS = tuple(channel for channel in range(1, 16) if channel != 9)


def _repeated_midi_note_events(
    base_note_events: list[tuple[int, bytes]],
    *,
    piece: Piece,
    settings: dict[str, str],
) -> list[tuple[int, bytes]]:
    pass_count = _playverse_count(piece, settings)
    pass_ticks = _midi_total_ticks(base_note_events)
    if pass_count <= 1 or pass_ticks <= 0:
        return list(base_note_events)
    note_events: list[tuple[int, bytes]] = []
    for pass_idx in range(pass_count):
        note_events.extend(
            _shift_midi_events(base_note_events, tick_offset=pass_idx * pass_ticks),
        )
    return note_events


def _write_midi_file(
    path: str,
    *,
    bpm: int,
    program: int,
    vocal_program: int,
    note_events: list[tuple[int, bytes]],
) -> str:
    events: list[tuple[int, bytes]] = []
    events.append((0, _meta_tempo(bpm)))
    events.append((0, _program_change(0, program)))
    events.extend((0, _program_change(channel, vocal_program)) for channel in _VOCAL_CHANNELS)
    events.extend(note_events)
    track = _write_track(events)
    header = b"MThd" + (6).to_bytes(4, "big") + (0).to_bytes(2, "big") + (1).to_bytes(2, "big")
    header += TICKS_PER_QUARTER.to_bytes(2, "big")
    data = header + track
    Path(path).write_bytes(data)
    return f"Wrote {path}"


def _duet_midi_note_events(
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
    ornaments: dict[tuple[int, int], str] | None,
    max_repeat_hops: int,
) -> list[tuple[int, bytes]]:
    base_note_events = _duet_note_events(
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
    return _repeated_midi_note_events(base_note_events, piece=piece, settings=settings)


def _melody_chord_events(
    bar: Bar,
    default_duration: int,
    *,
    enabled: bool,
) -> list[tuple[int, int, int, list[Note]]]:
    if not enabled:
        return []
    grouped: dict[int, list[MelodyEvent]] = {}
    for event in bar.melody_events:
        grouped.setdefault(event.onset_index, []).append(event)
    result: list[tuple[int, int, int, list[Note]]] = []
    start = 0
    for onset_index, events in sorted(grouped.items()):
        duration = max(_duration_ticks(event.note_type or default_duration, event.dotted) for event in events)
        result.append((start, duration, onset_index, []))
        start += duration
    return result


def _scale_chord_events_to_bar(
    chord_events: list[tuple[int, int, int, list[Note]]],
    target_ticks: int | None,
) -> list[tuple[int, int, int, list[Note]]]:
    if not chord_events or target_ticks is None or target_ticks <= 0:
        return chord_events
    source_ticks = max(start + duration for start, duration, _column, _notes in chord_events)
    if source_ticks <= 0 or source_ticks == target_ticks:
        return chord_events
    return [
        (
            round(start * target_ticks / source_ticks),
            max(1, round(duration * target_ticks / source_ticks)),
            column,
            notes,
        )
        for start, duration, column, notes in chord_events
    ]


def _tablature_bar_tick_lengths(
    piece: Piece,
    *,
    overrides: dict[tuple[int, int, int], str],
    durations: dict[tuple[int, int, int], int],
    bar_width: int,
    style: str,
    default_duration: int,
    dotted: set[tuple[int, int]] | None,
) -> dict[int, int]:
    lengths: dict[int, int] = {}
    for bar_index, bar in enumerate(piece.bars):
        chord_events = _bar_chord_events(
            bar,
            bar_index,
            piece.strings,
            overrides,
            durations,
            bar_width,
            style,
            default_duration,
            dotted=dotted,
        )
        if chord_events:
            lengths[bar_index] = max(start + duration for start, duration, _column, _notes in chord_events)
    return lengths


def _single_score_midi_note_events(
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
    ornaments: dict[tuple[int, int], str] | None,
    vocal_channel: int = 1,
    include_tablature: bool = True,
    include_vocal: bool = True,
    bar_tick_lengths: dict[int, int] | None = None,
) -> list[tuple[int, bytes]]:
    note_events: list[tuple[int, bytes]] = []
    show_ornaments = _show_ornaments(settings)
    ornament_mode = settings.get("ft3ornaments", "both")
    current_time = 0
    max_repeat_hops = _repeat_hop_limit(len(piece.bars), settings)
    bar_order = _repeat_play_order(
        len(piece.bars),
        start_bar,
        get_repeat=lambda idx: piece.bars[idx].repeat,
        get_endings=lambda idx: piece.bars[idx].ending_numbers,
        max_repeat_hops=max_repeat_hops,
    )
    for b_idx in bar_order:
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
        chord_events = chord_events or _melody_chord_events(
            bar,
            default_duration,
            enabled=include_vocal,
        )
        chord_events = _scale_chord_events_to_bar(
            chord_events,
            bar_tick_lengths.get(b_idx) if bar_tick_lengths is not None else None,
        )
        if not chord_events:
            continue
        max_end = 0
        for start, duration, col, notes in chord_events:
            velocity = _accent_velocity(start, beats, unit)
            note_len = max(1, int(duration * gate))
            bar_ornament = ornaments.get((b_idx, col)) if (show_ornaments and ornaments) else None
            for note in notes if include_tablature else ():
                s_idx = note.string - 1
                if s_idx < 0 or s_idx >= len(pitches):
                    continue
                pitch = pitches[s_idx] + note.fret
                ornament_symbol = None
                if show_ornaments:
                    ornament_symbol = (
                        _picked_note_ornament(
                            note,
                            ornament_mode=ornament_mode,
                        )
                        or bar_ornament
                    )
                _append_note_messages(
                    note_events,
                    channel=0,
                    start_tick=current_time + start,
                    note_len=note_len,
                    pitch=pitch,
                    velocity=velocity,
                    ornament_symbol=ornament_symbol,
                )
            max_end = max(max_end, start + duration)
        _append_vocal_messages(
            note_events,
            bar=bar,
            chord_events=chord_events,
            base_time=current_time,
            tuning_pitches=pitches,
            settings=settings,
            channel=vocal_channel,
            enabled=include_vocal,
            target_ticks=bar_tick_lengths.get(b_idx) if bar_tick_lengths is not None else None,
        )
        current_time += max_end
    return _repeated_midi_note_events(note_events, piece=piece, settings=settings)


def _polyphonic_score_midi_note_events(
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
    ornaments: dict[tuple[int, int], str] | None,
) -> list[tuple[int, bytes]]:
    imported = piece.imported_score
    if imported is None:
        return []
    note_indices = [index for index, staff in enumerate(imported.staffs) if staff.kind == "note"]
    events: list[tuple[int, bytes]] = []
    has_tablature = any(bar.chords or bar.notes for bar in piece.bars)
    bar_tick_lengths = (
        _tablature_bar_tick_lengths(
            piece,
            overrides=overrides,
            durations=durations,
            bar_width=bar_width,
            style=style,
            default_duration=default_duration,
            dotted=dotted,
        )
        if has_tablature
        else None
    )
    if has_tablature:
        events.extend(
            _single_score_midi_note_events(
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
                include_vocal=False,
            ),
        )
    channel_offset = 0
    for staff_index in note_indices:
        projected = project_imported_staff(piece, staff_index)
        staff_bar_tick_lengths = bar_tick_lengths if len(imported.staffs[staff_index].bars) == len(piece.bars) else None
        events.extend(
            _single_score_midi_note_events(
                projected,
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
                vocal_channel=_VOCAL_CHANNELS[channel_offset % len(_VOCAL_CHANNELS)],
                include_tablature=False,
                bar_tick_lengths=staff_bar_tick_lengths,
            ),
        )
        voices = {event.voice for bar in projected.bars for event in bar.melody_events}
        channel_offset += max(voices, default=0) + 1
    return events
