from __future__ import annotations

import re
from dataclasses import replace
from statistics import median

from petrucci.core.model import (
    Bar,
    MelodyEvent,
    Piece,
)
from petrucci.core.music.key_signature import key_signature_accidentals


def _time_signature_sixteenth_units(time_sig: str | None) -> int | None:
    common = {
        None: None,
        "": None,
        "C": 16,
        "C|": 8,
    }
    if time_sig in common:
        return common[time_sig]
    if time_sig is None or "/" not in time_sig:
        return None
    num_text, denom_text = time_sig.split("/", 1)
    if not (num_text.isdigit() and denom_text.isdigit()):
        return None
    denominator = int(denom_text)
    if denominator <= 0:
        return None
    return (16 * int(num_text)) // denominator


def _sixteenth_units_from_event(event: MelodyEvent) -> int | None:
    if event.note_type is None:
        return None
    denom = note_type_to_denominator(event.note_type)
    if denom is None or denom <= 0:
        return None
    units = 16 // denom
    if event.dotted:
        units = (units * 3) // 2
    return units


def _event_from_units(event: MelodyEvent, units: int) -> MelodyEvent:
    mapping = {
        16: (2, False),
        12: (3, True),
        8: (3, False),
        6: (4, True),
        4: (4, False),
        3: (5, True),
        2: (5, False),
        1: (6, False),
    }
    note_type, dotted = mapping.get(units, (4, event.dotted))
    return replace(event, note_type=note_type, dotted=dotted)


def _finalize_explicit_vocal_melody(bar: Bar) -> None:
    events = list(getattr(bar, "melody_events", None) or [])
    if not events:
        return
    if events[0].note_type is not None:
        return
    total_units = _time_signature_sixteenth_units(bar.time_sig)
    if total_units is None:
        return
    used_units = 0
    for event in events[1:]:
        units = _sixteenth_units_from_event(event)
        if units is None:
            return
        used_units += units
    remaining = total_units - used_units
    if remaining <= 0:
        return
    events[0] = _event_from_units(events[0], remaining)
    bar.melody_events = events


def _bar_uses_raw_vocal_fallback(bar: Bar) -> bool:
    for row in getattr(bar, "structured_text_rows", None) or []:
        if row.kind != "vocal":
            continue
        text = (row.text or "").strip()
        if text and text[0].isdigit():
            return True
    return False


def _normalize_vocal_event_accidentals(  # noqa: C901
    bar: Bar,
    *,
    key: str | None,
    raw_fallback: bool = False,
) -> None:
    defaults = key_signature_accidentals(key)
    if not defaults:
        return
    normalized: list[MelodyEvent] = []
    for event in getattr(bar, "melody_events", None) or []:
        if event.is_rest:
            normalized.append(event)
            continue
        match = re.fullmatch(r"([a-g])([#b]?)([',]*)", event.text)
        if match is None:
            normalized.append(event)
            continue
        name, _accidental, octave = match.groups()
        flags = event.accidental_flags or 0
        if flags & 0x1000:
            accidental = "b"
        elif flags & 0x0002:
            accidental = "#"
        elif flags & 0x2000:
            accidental = defaults.get(name, "") if raw_fallback else ""
        else:
            accidental = defaults.get(name, "")
        normalized.append(replace(event, text=f"{name}{accidental}{octave}"))
    bar.melody_events = normalized


def _bar_sum_quarter_beats(bar: Bar) -> float:
    total = 0.0
    for chord in bar.chords:
        denom = note_type_to_denominator(chord.note_type)
        if denom is None:
            continue
        value = 4.0 / denom
        if chord.dotted:
            value *= 1.5
        total += value
    return total


def _bar_sums_with_chords(bars: list[Bar]) -> list[float]:
    return [_bar_sum_quarter_beats(bar) for bar in bars if bar.chords]


def _needs_legacy_duration_fix(bars: list[Bar]) -> bool:
    if not bars or any(bar.time_sig for bar in bars):
        return False
    sums = _bar_sums_with_chords(bars)
    if not sums:
        return False
    return abs(median(sums) - 1.5) < 0.05


def _needs_common_time_halfbar_fix(bars: list[Bar]) -> bool:
    if not bars:
        return False
    if any((bar.time_sig not in (None, "C")) for bar in bars):
        return False
    sums = _bar_sums_with_chords(bars)
    if not sums:
        return False
    med = median(sums)
    near_half = sum(1 for value in sums if abs(value - 2.0) <= 0.2)
    # Avoid scaling already-correct 4/4 material.
    near_full = sum(1 for value in sums if abs(value - 4.0) <= 0.2)
    return abs(med - 2.0) <= 0.15 and near_half >= int(len(sums) * 0.7) and near_full == 0


def _shift_note_types_one_step_longer(bars: list[Bar], time_sig: str) -> None:
    for bar in bars:
        if bar.time_sig is None:
            bar.time_sig = time_sig
        for chord in bar.chords:
            if chord.note_type > 2:
                chord.note_type -= 1


def _apply_legacy_duration_fix(bars: list[Bar]) -> None:
    # Some FT3 files encode rhythms one step faster (e.g. 7 meaning 16th).
    # Detect this pattern and shift note_type by one to restore musical lengths.
    if _needs_legacy_duration_fix(bars):
        _shift_note_types_one_step_longer(bars, time_sig="O")
        return
    # Another legacy encoding pattern stores 4/4 bars at half-length (2.0).
    if _needs_common_time_halfbar_fix(bars):
        _shift_note_types_one_step_longer(bars, time_sig="C")


def _infer_meter_from_sum(sum_quarter_beats: float) -> str | None:
    if abs(sum_quarter_beats - 1.5) <= 0.15:
        return "O"
    if abs(sum_quarter_beats - 2.0) <= 0.15:
        return "C|"
    if abs(sum_quarter_beats - 4.0) <= 0.2:
        return "C"
    return None


def _fill_missing_time_signatures(bars: list[Bar]) -> None:  # noqa: C901
    if not bars:
        return
    explicit = [idx for idx, bar in enumerate(bars) if bar.time_sig]
    if not explicit:
        for bar in bars:
            if bar.time_sig is None and bar.chords:
                guessed = _infer_meter_from_sum(_bar_sum_quarter_beats(bar))
                if guessed:
                    bar.time_sig = guessed
        return

    first = explicit[0]
    first_meter = bars[first].time_sig
    for bar in bars[:first]:
        if bar.time_sig is None:
            bar.time_sig = first_meter
    current_meter: str | None = None
    for bar in bars[first:]:
        if bar.time_sig is not None:
            current_meter = bar.time_sig
        else:
            bar.time_sig = current_meter


def parse_time_signature(bar_data: bytes) -> str | None:
    if len(bar_data) < 10:
        return None
    # Repeats, endings, closers, and an observed 0x08 control flag share byte 0.
    time_signature = bar_data[0] & 0x07
    if time_signature == 0x01:
        return "C"
    if time_signature == 0x02:
        return "C|"
    if time_signature == 0x03:
        return "3/4"
    if time_signature == 0x06:
        beats = bar_data[9]
        beat_type = bar_data[8]
        if beats and beat_type:
            return f"{beats}/{beat_type}"
    return None


def note_type_to_denominator(note_type: int) -> int | None:
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


def build_durations(piece: Piece) -> dict[tuple[int, int, int], int]:
    durations: dict[tuple[int, int, int], int] = {}
    for b_idx, bar in enumerate(piece.bars):
        col = 0
        for chord in bar.chords:
            denom = note_type_to_denominator(chord.note_type)
            if denom is None:
                continue
            durations[(b_idx, 0, col)] = denom
            col += 1
    return durations
