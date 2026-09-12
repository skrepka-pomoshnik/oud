from __future__ import annotations

import math

from oud.exports.midi.bytes import (
    BASE_NOTE_VELOCITY,
    TICKS_PER_QUARTER,
)
from oud.exports.midi.bytes import (
    accent_velocity as _accent_velocity,
)
from oud.exports.midi.bytes import (
    meter_for_bar as _meter_for_bar,
)
from oud.exports.midi.bytes import (
    note_off as _note_off,
)
from oud.exports.midi.bytes import (
    note_on as _note_on,
)
from oud.services.playback.timeline import PlaybackCursor, build_timeline_from_events
from petrucci.adapters.duet import duet_logical_bar_count, duet_raw_bar_index, is_duet_score_piece
from petrucci.adapters.vocal import VocalEvent, infer_vocal_events
from petrucci.core.model import Bar, Chord, Note, Piece
from petrucci.core.music.tuning import (
    default_bass_strings,
    default_tuning_pitches,
    parse_bass_strings,
    tuning_count,
)
from petrucci.input.tablature.input import editor_event_columns, editor_fret_at


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


def _show_ornaments(settings: dict[str, str]) -> bool:
    if settings.get("showornaments", settings.get("showft3extras", "on")) != "on":
        return False
    return settings.get("ft3ornaments", "both") != "off"


def _picked_note_ornament(note: Note, *, ornament_mode: str) -> str | None:
    left = note.left_ornament
    right = note.right_ornament
    if ornament_mode == "left":
        return left
    if ornament_mode == "right":
        return right
    return left or right


def _ornament_pitch_delta(symbol: str | None) -> int:
    if not symbol:
        return 0
    if symbol == "x":
        return -1
    if symbol == "+":
        return 2
    if symbol in {"parenthesis", "brackets"}:
        return 0
    if symbol in {"#", "dot-left"}:
        return 1
    return 1


def _append_note_messages(
    events: list[tuple[int, bytes]],
    *,
    channel: int,
    start_tick: int,
    note_len: int,
    pitch: int,
    velocity: int,
    ornament_symbol: str | None,
) -> None:
    grace_len = 0
    minimum_ornament_note_length = 3
    if ornament_symbol and note_len >= minimum_ornament_note_length:
        delta = _ornament_pitch_delta(ornament_symbol)
        grace_pitch = max(0, min(127, pitch + delta))
        if grace_pitch != pitch:
            grace_len = max(1, min(note_len // 3, TICKS_PER_QUARTER // 16))
            events.append((start_tick, _note_on(channel, grace_pitch, min(127, velocity + 6))))
            events.append((start_tick + grace_len, _note_off(channel, grace_pitch, 64)))
    main_start = start_tick + grace_len
    main_len = max(1, note_len - grace_len)
    events.append((main_start, _note_on(channel, pitch, velocity)))
    events.append((main_start + main_len, _note_off(channel, pitch, 64)))


def _duration_ticks(denom: int, dotted: bool) -> int:
    base = TICKS_PER_QUARTER * 4
    ticks = max(1, base // max(1, denom))
    if dotted:
        ticks = math.ceil(ticks * 1.5)
    return ticks


def _parse_tuning(tuning: str) -> list[int]:  # noqa: C901
    pitches: list[int] = []
    midi_min = 0
    midi_max = 127
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
                note,
                0,
            )
            if accidental in ("+", "#"):
                semis += 1
            elif accidental in ("-", "b"):
                semis -= 1
            midi = (octave_num + 1) * 12 + semis
            if midi_min <= midi <= midi_max:
                pitches.append(midi)
        else:
            idx += 1
    pitches.reverse()
    return pitches


def _default_tuning(strings: int) -> list[int]:
    return default_tuning_pitches(strings)


def _resolved_tuning_for_piece(piece: Piece, settings: dict[str, str]) -> str:
    tuning = (piece.tuning or settings.get("tuning", "") or "").strip()
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
        return 10 if ch == "x" else None
    letters = "abcdefghiklmnopqrst"
    return letters.index(ch) if ch in letters else None


def _collect_manual_chords(  # noqa: C901, PLR0917 - legacy grid projection pending typed export context
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
    columns = editor_event_columns(overrides, bar_index=bar_index)
    events: list[tuple[int, int, int, list[Note]]] = []
    current_time = 0
    for col in columns:
        notes: list[Note] = []
        for s_idx in range(strings):
            key = (bar_index, s_idx, col)
            if key not in overrides:
                continue
            fret = editor_fret_at(
                overrides,
                durations,
                bar_index=bar_index,
                string_index=s_idx,
                column=col,
                style=style,
            )
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
    chords: list[Chord],
    bar_width: int,
    default_duration: int,
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


def _apply_overrides(  # noqa: PLR0917 - legacy grid projection pending typed export context
    notes: list[Note],
    overrides: dict[tuple[int, int, int], str],
    bar_index: int,
    col: int,
    style: str,
    strings: int,
    durations: dict[tuple[int, int, int], int],
) -> list[Note]:
    if not overrides:
        return notes
    by_string: dict[int, Note] = {note.string: note for note in notes}
    for s_idx in range(strings):
        key = (bar_index, s_idx, col)
        if key not in overrides:
            continue
        fret = editor_fret_at(
            overrides,
            durations,
            bar_index=bar_index,
            string_index=s_idx,
            column=col,
            style=style,
        )
        if fret is None:
            continue
        by_string[s_idx + 1] = Note(string=s_idx + 1, fret=fret, raw_pos=0)
    return list(by_string.values())


def _bar_chord_events(  # noqa: PLR0917 - legacy grid projection pending typed export context
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
        if not events:
            voice_times: dict[int, int] = {}
            for event in bar.melody_events:
                denom = _note_type_to_denom(event.note_type or default_duration) or default_duration
                duration = _duration_ticks(denom, event.dotted)
                start = voice_times.get(event.voice, 0)
                events.append((start, duration, event.onset_index, []))
                voice_times[event.voice] = start + duration
        return events
    time = 0
    positions = _chord_positions(bar.chords, bar_width, default_duration)
    for chord, col in zip(bar.chords, positions, strict=False):
        denom = _note_type_to_denom(chord.note_type) or default_duration
        is_dotted = chord.dotted or (dotted is not None and (bar_index, col) in dotted)
        duration = _duration_ticks(denom, is_dotted)
        if chord.notes:
            notes = _apply_overrides(chord.notes, overrides, bar_index, col, style, strings, durations)
            events.append((time, duration, col, notes))
        time += duration
    return events


def _repeat_hop_limit(count: int, settings: dict[str, str]) -> int:
    text = (settings.get("maxrepeats", "30") or "30").strip()
    limit = int(text) if text.isdigit() else 30
    return max(count * 2, limit)


def _duet_pair_bar_indices(
    piece: Piece,
    start_bar: int,
    *,
    max_repeat_hops: int,
) -> list[tuple[int | None, int | None]]:
    start_pair = max(0, start_bar // 2)
    total_pairs = duet_logical_bar_count(piece)
    pair_order = _repeat_play_order(
        total_pairs,
        start_pair,
        get_repeat=lambda pair_idx: _duet_pair_repeat(piece, pair_idx),
        get_endings=lambda pair_idx: _duet_pair_endings(piece, pair_idx),
        max_repeat_hops=max_repeat_hops,
    )
    pairs: list[tuple[int | None, int | None]] = []
    for pair_idx in pair_order:
        first = duet_raw_bar_index(0, pair_idx, piece=piece)
        second = duet_raw_bar_index(1, pair_idx, piece=piece)
        pairs.append(
            (
                first if first < len(piece.bars) else None,
                second if second < len(piece.bars) else None,
            ),
        )
    return pairs


def _repeat_play_order(
    count: int,
    start_index: int,
    *,
    get_repeat,
    get_endings=None,
    max_repeat_hops: int,
) -> list[int]:
    if count <= 0 or start_index >= count:
        return []
    order: list[int] = []
    idx = max(0, start_index)
    section_start = idx
    section_pass = 1
    jumped_back = False
    repeated_endings: set[int] = set()
    limit = max(count, count * (max_repeat_hops + 1))
    steps = 0
    while 0 <= idx < count and steps < limit:
        steps += 1
        endings = tuple(sorted(set(get_endings(idx) or ()))) if get_endings else ()
        if not endings or section_pass in endings:
            order.append(idx)
        repeat = (get_repeat(idx) or "").strip()
        if repeat in {":.", ":|:", "."} and idx not in repeated_endings:
            repeated_endings.add(idx)
            section_pass += 1
            idx = section_start
            jumped_back = True
            continue
        if repeat == ".:" and not jumped_back:
            section_start = idx
            section_pass = 1
        elif (repeat == ":." and idx in repeated_endings) or (repeat in {":|:", "."} and not jumped_back):
            section_start = min(idx + 1, count - 1)
            section_pass = section_pass if endings else 1
        jumped_back = False
        idx += 1
    return order


def _duet_pair_repeat(piece: Piece, pair_idx: int) -> str:
    for staff_idx in (0, 1):
        raw = duet_raw_bar_index(staff_idx, pair_idx, piece=piece)
        if 0 <= raw < len(piece.bars):
            repeat = (piece.bars[raw].repeat or "").strip()
            if repeat:
                return repeat
    return ""


def _duet_pair_endings(piece: Piece, pair_idx: int) -> tuple[int, ...]:
    values: set[int] = set()
    for staff_idx in (0, 1):
        raw = duet_raw_bar_index(staff_idx, pair_idx, piece=piece)
        if 0 <= raw < len(piece.bars):
            values.update(piece.bars[raw].ending_numbers)
    return tuple(sorted(values))


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
    max_repeat_hops: int,
) -> list[tuple[int, int, int, int]]:
    timeline_events: list[tuple[int, int, int, int]] = []
    current_time = 0
    for first_idx, second_idx in _duet_pair_bar_indices(
        piece,
        start_bar,
        max_repeat_hops=max_repeat_hops,
    ):
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


def _duet_note_events(  # noqa: C901
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
    ornaments: dict[tuple[int, int], str] | None = None,
    max_repeat_hops: int,
) -> list[tuple[int, bytes]]:
    events: list[tuple[int, bytes]] = []
    current_time = 0
    show_ornaments = _show_ornaments(settings)
    ornament_mode = settings.get("ft3ornaments", "both")
    for first_idx, second_idx in _duet_pair_bar_indices(
        piece,
        start_bar,
        max_repeat_hops=max_repeat_hops,
    ):
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
            for start, duration, col, notes in chord_events:
                velocity = _accent_velocity(start, beats, unit)
                note_len = max(1, int(duration * gate))
                bar_ornament = ornaments.get((b_idx, col)) if (show_ornaments and ornaments) else None
                for note in notes:
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
                        events,
                        channel=0,
                        start_tick=pair_base_time + start,
                        note_len=note_len,
                        pitch=pitch,
                        velocity=velocity,
                        ornament_symbol=ornament_symbol,
                    )
                max_end = max(max_end, start + duration)
            _append_vocal_messages(
                events,
                bar=bar,
                chord_events=chord_events,
                base_time=pair_base_time,
                tuning_pitches=pitches,
                settings=settings,
            )
            pair_max_end = max(pair_max_end, max_end)
        current_time += pair_max_end
    return events


def _append_vocal_messages(  # noqa: C901
    events: list[tuple[int, bytes]],
    *,
    bar: Bar,
    chord_events: list[tuple[int, int, int, list[Note]]],
    base_time: int,
    tuning_pitches: list[int],
    settings: dict[str, str],
    channel: int = 1,
    enabled: bool = True,
    target_ticks: int | None = None,
) -> None:
    if not enabled:
        return
    has_explicit_melody = bool(
        (getattr(bar, "melody_events", None) or []) or (getattr(bar, "melody_grid", None) or "").strip(),
    )
    allow_inferred = settings.get("midivocalinfer", "off") == "on"
    if not has_explicit_melody and not allow_inferred:
        return
    vocal_events = infer_vocal_events(bar, tuning_pitches=tuning_pitches)
    if not vocal_events:
        return
    gate = _vocal_gate(settings)
    for event, start, duration in _timed_vocal_events(
        vocal_events,
        chord_events,
        has_explicit_melody=has_explicit_melody,
        target_ticks=target_ticks,
    ):
        if getattr(event, "is_rest", False):
            continue
        if event.pitch is None:
            continue
        note_len = max(1, int(duration * gate))
        if event.fermata:
            note_len = max(note_len, int(duration * 1.5))
        _append_note_messages(
            events,
            channel=_vocal_channel(channel, event.voice),
            start_tick=base_time + start,
            note_len=note_len,
            pitch=event.pitch,
            velocity=min(127, BASE_NOTE_VELOCITY + 4),
            ornament_symbol=None,
        )


def _vocal_gate(settings: dict[str, str]) -> float:
    gate_text = settings.get("midigate", "85")
    gate_percent = max(10, min(100, int(gate_text))) if gate_text.isdigit() else 85
    return gate_percent / 100.0


def _timed_vocal_events(
    vocal_events: list[VocalEvent],
    chord_events: list[tuple[int, int, int, list[Note]]],
    *,
    has_explicit_melody: bool,
    target_ticks: int | None = None,
) -> list[tuple[VocalEvent, int, int]]:
    if has_explicit_melody:
        timed: list[tuple[VocalEvent, int, int]] = []
        voice_starts: dict[int, int] = {}
        for event in vocal_events:
            denominator = _note_type_to_denom(event.note_type) or 4
            duration = _duration_ticks(denominator, event.dotted)
            start = voice_starts.get(event.voice, 0)
            timed.append((event, start, duration))
            voice_starts[event.voice] = start + duration
        return _scale_timed_vocal_events(timed, target_ticks)
    timed = [
        (event, chord_events[event.chord_index][0], chord_events[event.chord_index][1])
        for event in vocal_events
        if 0 <= event.chord_index < len(chord_events)
    ]
    return _scale_timed_vocal_events(timed, target_ticks)


def _scale_timed_vocal_events(
    timed: list[tuple[VocalEvent, int, int]],
    target_ticks: int | None,
) -> list[tuple[VocalEvent, int, int]]:
    if not timed or target_ticks is None or target_ticks <= 0:
        return timed
    source_ticks = max(start + duration for _event, start, duration in timed)
    if source_ticks <= 0 or source_ticks == target_ticks:
        return timed
    return [
        (
            event,
            round(start * target_ticks / source_ticks),
            max(1, round(duration * target_ticks / source_ticks)),
        )
        for event, start, duration in timed
    ]


def _vocal_channel(base_channel: int, voice: int) -> int:
    midi_drum_channel = 9
    channels = tuple(channel for channel in range(1, 16) if channel != midi_drum_channel)
    try:
        base_index = channels.index(base_channel)
    except ValueError:
        base_index = 0
    return channels[(base_index + max(0, voice)) % len(channels)]


def _playverse_count(piece: Piece, settings: dict[str, str]) -> int:
    mode = settings.get("playverses", "once")
    if mode == "once":
        return 1
    count = 1
    for bar in piece.bars:
        lyric_rows = getattr(bar, "lyric_event_rows", None) or []
        if lyric_rows:
            count = max(count, len(lyric_rows))
            continue
        raw_lyrics = [line for line in (getattr(bar, "lyrics", None) or []) if line.strip()]
        if raw_lyrics:
            count = max(count, len(raw_lyrics))
    return count


def _shift_timeline_events(
    events: list[tuple[int, int, int, int]],
    *,
    tick_offset: int,
) -> list[tuple[int, int, int, int]]:
    if tick_offset <= 0:
        return list(events)
    return [(bar, start + tick_offset, duration, col) for bar, start, duration, col in events]


def _timeline_total_ticks(events: list[tuple[int, int, int, int]]) -> int:
    return max((start + duration for _bar, start, duration, _col in events), default=0)


def _shift_midi_events(
    events: list[tuple[int, bytes]],
    *,
    tick_offset: int,
) -> list[tuple[int, bytes]]:
    if tick_offset <= 0:
        return list(events)
    return [(start + tick_offset, payload) for start, payload in events]


def _midi_total_ticks(events: list[tuple[int, bytes]]) -> int:
    return max((start for start, _payload in events), default=0)


def build_playback_timeline(  # noqa: C901
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
    max_repeat_hops = _repeat_hop_limit(len(piece.bars), settings)
    if is_duet_score_piece(piece):
        base_events = _duet_timeline_events(
            piece,
            overrides=overrides,
            durations=durations,
            bar_width=bar_width,
            style=style,
            default_duration=default_duration,
            start_bar=start_bar,
            dotted=dotted,
            max_repeat_hops=max_repeat_hops,
        )
        pass_count = _playverse_count(piece, settings)
        pass_ticks = _timeline_total_ticks(base_events)
        timeline: list[PlaybackCursor] = []
        for pass_idx in range(pass_count):
            shifted = _shift_timeline_events(base_events, tick_offset=pass_idx * pass_ticks)
            timeline.extend(build_timeline_from_events(shifted, sec_per_tick=sec_per_tick, verse=pass_idx))
        return timeline
    current_time = 0
    bar_order = _repeat_play_order(
        len(piece.bars),
        start_bar,
        get_repeat=lambda idx: piece.bars[idx].repeat,
        get_endings=lambda idx: piece.bars[idx].ending_numbers,
        max_repeat_hops=max_repeat_hops,
    )
    for b_idx in bar_order:
        bar = piece.bars[b_idx]
        has_explicit_melody = bool(bar.melody_events)
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
            if not notes and not has_explicit_melody:
                continue
            marker_col = event_idx if bar.chords else col
            timeline_events.append(
                (b_idx, current_time + start, duration, marker_col),
            )
            max_end = max(max_end, start + duration)
        current_time += max_end
    base_events = list(timeline_events)
    pass_count = _playverse_count(piece, settings)
    pass_ticks = _timeline_total_ticks(base_events)
    if pass_count > 1 and pass_ticks > 0:
        timeline: list[PlaybackCursor] = []
        for pass_idx in range(pass_count):
            shifted = _shift_timeline_events(base_events, tick_offset=pass_idx * pass_ticks)
            timeline.extend(build_timeline_from_events(shifted, sec_per_tick=sec_per_tick, verse=pass_idx))
        return timeline
    return build_timeline_from_events(timeline_events, sec_per_tick=sec_per_tick)
