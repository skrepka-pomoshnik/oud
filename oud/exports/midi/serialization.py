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
    _midi_total_ticks,
    _picked_note_ornament,
    _playverse_count,
    _repeat_hop_limit,
    _repeat_play_order,
    _shift_midi_events,
    _show_ornaments,
)
from petrucci.core.imported import project_imported_staff
from petrucci.core.model import Piece

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
    if any(bar.chords or bar.notes for bar in piece.bars):
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
            ),
        )
        voices = {event.voice for bar in projected.bars for event in bar.melody_events}
        channel_offset += max(voices, default=0) + 1
    return events
