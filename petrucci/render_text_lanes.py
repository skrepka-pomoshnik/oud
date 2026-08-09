from __future__ import annotations

import re
from dataclasses import dataclass
from itertools import pairwise
from typing import Protocol

from petrucci.key_signature import key_signature_count
from petrucci.model import Bar, Chord, LyricEvent, MelodyEvent
from petrucci.time_utils import parse_time_signature_value
from petrucci.vocal_line import chord_top_pitch, infer_vocal_events, token_pitch_value

MELODY_NOTEHEAD_GLYPH = "◊"
MELODY_FILLED_NOTEHEAD_GLYPH = "◆"
_MELODY_FLAG_ROWS = 1
_MELODY_PITCH_ROWS = 10
_MELODY_STAFF_ROWS = _MELODY_FLAG_ROWS + _MELODY_PITCH_ROWS
_MELODY_STEM_LEN = 3
_TOP_LINE_ROW = _MELODY_FLAG_ROWS
_BOTTOM_LINE_ROW = _MELODY_FLAG_ROWS + 8
_BOTTOM_LINE_PITCH = 64  # E4 in treble staff
_DIATONIC_DEGREES = {
    0: 0,
    1: 0,
    2: 1,
    3: 1,
    4: 2,
    5: 3,
    6: 3,
    7: 4,
    8: 4,
    9: 5,
    10: 5,
    11: 6,
}


def melody_row_count(view: str | None = None) -> int:
    _ = view
    return _MELODY_STAFF_ROWS


def visible_lyric_rows(lines: list[str] | None, max_rows: int = 2) -> list[str]:
    if not lines or max_rows <= 0:
        return []
    out: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        out.append(line.rstrip())
        if len(out) >= max_rows:
            break
    return out


def _place_proportional_token(
    cells: list[str],
    *,
    source_position: int,
    source_width: int,
    token: str,
    last_end: int,
) -> int:
    width = len(cells)
    destination = min(width - 1, (source_position * width) // source_width)
    if destination <= last_end:
        destination = min(width - 1, last_end + 1)
    token_text = token[: width - destination]
    for offset, char in enumerate(token_text):
        cells[destination + offset] = char
    return destination + len(token_text) - 1


def text_bar_cells(text: str | None, width: int) -> list[str]:
    if width <= 0:
        return []
    out = [" "] * width
    if not text:
        return out
    cleaned = text.replace("\t", " ").replace("\r", " ").replace("\n", " ")
    src_width = max(1, len(cleaned))
    tokens = [(m.start(), m.group(0)) for m in re.finditer(r"\S+", cleaned)]
    if not tokens:
        return out
    last_end = -1
    for src_pos, tok in tokens:
        # Preserve relative token positions within the bar instead of collapsing all spaces.
        last_end = _place_proportional_token(
            out,
            source_position=src_pos,
            source_width=src_width,
            token=tok,
            last_end=last_end,
        )
    return out


def tokenized_onset_cells(
    text: str | None,
    *,
    onset_cols: list[int],
    width: int,
    left_pad: int = 0,
) -> list[str]:
    cells = [" "] * max(0, width)
    if not cells or not text or not onset_cols:
        return cells
    tokens = [m.group(0) for m in re.finditer(r"\S+", text)]
    if not tokens:
        return cells
    floor = max(0, left_pad)
    last_end = floor - 1
    for onset_index, token in enumerate(tokens):
        region = _event_region(onset_cols, onset_index, width=len(cells), floor=floor)
        if region is None:
            continue
        start, end = region
        placed = _place_text_in_region(
            cells,
            token,
            start=start,
            end=end,
            after=last_end,
        )
        if placed is not None:
            _s, last_end = placed
    return cells


def _place_text_at(cells: list[str], text: str, start: int) -> tuple[int, int]:
    for i, ch in enumerate(text):
        cells[start + i] = ch
    return start, start + len(text) - 1


def _find_free_slot(
    cells: list[str],
    text_len: int,
    *,
    start: int,
    stop: int,
    step: int,
    floor: int,
) -> int | None:
    for cand in range(start, stop, step):
        if cand < floor:
            continue
        if all(cells[cand + i] == " " for i in range(text_len)):
            return cand
    return None


def _place_text_near(
    cells: list[str],
    text: str,
    target_col: int,
    *,
    floor: int = 0,
) -> tuple[int, int] | None:
    if not text or not cells:
        return None
    width = len(cells)
    target_col = max(floor, min(width - 1, target_col))
    start = max(floor, min(width - len(text), target_col))
    # Prefer exact target, then shift right, then left.
    slot = _find_free_slot(
        cells,
        len(text),
        start=start,
        stop=width - len(text) + 1,
        step=1,
        floor=floor,
    )
    if slot is not None:
        return _place_text_at(cells, text, slot)
    slot = _find_free_slot(
        cells,
        len(text),
        start=start - 1,
        stop=floor - 1,
        step=-1,
        floor=floor,
    )
    if slot is not None:
        return _place_text_at(cells, text, slot)
    # Last resort: overwrite only spaces from target forward within bounds.
    cand = max(floor, min(width - len(text), start))
    for i, ch in enumerate(text):
        if cells[cand + i] == " ":
            cells[cand + i] = ch
    return cand, min(width - 1, cand + len(text) - 1)


def _event_target_col(onset_cols: list[int], onset_index: int) -> int | None:
    if not onset_cols:
        return None
    if 0 <= onset_index < len(onset_cols):
        return onset_cols[onset_index]
    # Clamp out-of-range tokens to the last known onset (common in noisy FT3 text records).
    return onset_cols[-1]


def _event_region(
    onset_cols: list[int],
    onset_index: int,
    *,
    width: int,
    floor: int,
) -> tuple[int, int] | None:
    if not onset_cols or width <= 0:
        return None
    clamped_index = max(0, min(onset_index, len(onset_cols) - 1))
    start = max(floor, min(width - 1, onset_cols[clamped_index]))
    if clamped_index + 1 < len(onset_cols):
        next_start = max(start, min(width, onset_cols[clamped_index + 1]))
        end = max(start, min(width - 1, next_start - 1))
    else:
        end = width - 1
    return start, end


def _place_text_in_region(
    cells: list[str],
    text: str,
    *,
    start: int,
    end: int,
    after: int,
) -> tuple[int, int] | None:
    if not text or not cells:
        return None
    pos = max(start, after + 1)
    if pos > end:
        return None
    avail = end - pos + 1
    if avail <= 0:
        return None
    token = text[:avail]
    return _place_text_at(cells, token, pos)


def melody_event_cells(
    events: list[MelodyEvent] | None,
    *,
    onset_cols: list[int],
    width: int,
    left_pad: int = 0,
) -> list[str]:
    cells = [" "] * max(0, width)
    if not cells or not events or not onset_cols:
        return cells
    floor = max(0, left_pad)
    last_end = floor - 1
    for ev in events:
        region = _event_region(
            onset_cols,
            ev.onset_index,
            width=len(cells),
            floor=floor,
        )
        if region is None:
            continue
        start, end = region
        placed = _place_text_in_region(
            cells,
            ev.text,
            start=start,
            end=end,
            after=last_end,
        )
        if placed is not None:
            _start, last_end = placed
    return cells


def _diatonic_staff_step(pitch: int) -> int:
    octave = (pitch // 12) - 1
    degree = _DIATONIC_DEGREES[pitch % 12]
    return octave * 7 + degree


def _raw_pitch_row(pitch: int) -> int:
    base_step = _diatonic_staff_step(_BOTTOM_LINE_PITCH)
    step = _diatonic_staff_step(pitch)
    row = _BOTTOM_LINE_ROW - (step - base_step)
    note_row_min = _MELODY_FLAG_ROWS
    note_row_max = _MELODY_STAFF_ROWS - 1
    return max(note_row_min, min(note_row_max, row))


def _pitch_rows(pitch: int, view: str | None) -> tuple[int, int]:
    _ = view
    base_step = _diatonic_staff_step(_BOTTOM_LINE_PITCH)
    step = _diatonic_staff_step(pitch)
    raw_row = _BOTTOM_LINE_ROW - (step - base_step)
    clamped_row = max(_MELODY_FLAG_ROWS, min(_MELODY_STAFF_ROWS - 1, raw_row))
    return raw_row, clamped_row


def _event_pitch_map(events: list[MelodyEvent] | None) -> dict[int, int]:
    mapping: dict[int, int] = {}
    for ev in events or []:
        if ev.onset_index in mapping:
            continue
        pitch = token_pitch_value(ev.text)
        if pitch is not None:
            mapping[ev.onset_index] = pitch
    return mapping


def _event_accidental_map(events: list[MelodyEvent] | None) -> dict[int, str]:  # noqa: C901
    mapping: dict[int, str] = {}
    for ev in events or []:
        if ev.onset_index in mapping:
            continue
        if ev.is_rest:
            continue
        flags = ev.accidental_flags or 0
        if flags & 0x1000:
            mapping[ev.onset_index] = _display_accidental("b", ev)
            continue
        if flags & 0x0002:
            mapping[ev.onset_index] = _display_accidental("#", ev)
            continue
        if flags & 0x2000:
            mapping[ev.onset_index] = _display_accidental("n", ev)
            continue
        token = ev.text.strip()
        if "#" in token:
            mapping[ev.onset_index] = _display_accidental("#", ev)
        elif "b" in token[1:]:
            mapping[ev.onset_index] = _display_accidental("b", ev)
    return mapping


def _display_accidental(value: str, event: MelodyEvent) -> str:
    return f"({value})" if event.courtesy_accidental else value


def _bar_uses_raw_vocal_fallback(bar: Bar | None) -> bool:
    if bar is None:
        return False
    for row in getattr(bar, "structured_text_rows", None) or []:
        if row.kind != "vocal":
            continue
        text = (row.text or "").strip()
        if text and text[0].isdigit():
            return True
    return False


def _event_accidental_map_for_bar(
    events: list[MelodyEvent] | None,
    *,
    bar: Bar | None,
) -> dict[int, str]:
    mapping = _event_accidental_map(events)
    if not _bar_uses_raw_vocal_fallback(bar):
        return mapping
    for ev in events or []:
        if (ev.accidental_flags or 0) & 0x2000:
            mapping.pop(ev.onset_index, None)
    return mapping


def _merge_chord_pitch_map(
    onset_pitch: dict[int, int],
    bar_chords: list[Chord] | None,
    tuning_pitches: list[int] | None,
) -> None:
    if not bar_chords:
        return
    for onset_idx, chord in enumerate(bar_chords):
        pitch = chord_top_pitch(chord, tuning_pitches)
        if pitch is not None:
            onset_pitch[onset_idx] = pitch


def _fill_unpitched_event_rows(
    onset_pitch: dict[int, int],
    events: list[MelodyEvent] | None,
) -> None:
    for ev in events or []:
        if ev.onset_index in onset_pitch:
            continue
        if ev.text.strip():
            onset_pitch[ev.onset_index] = 64


def _resampled_onset_cols(
    *,
    onset_cols: list[int],
    event_count: int,
    width: int,
    left_pad: int,
) -> list[int]:
    if event_count <= 0:
        return []
    if len(onset_cols) == event_count:
        return list(onset_cols)
    if len(onset_cols) < event_count:
        span = max(1, width - left_pad)
        out: list[int] = []
        for onset_idx in range(event_count):
            frac = onset_idx / max(1, event_count - 1)
            col = max(0, left_pad) + min(span - 1, round(frac * (span - 1)))
            out.append(min(width - 1, col))
        return out
    first = max(0, left_pad)
    last = min(width - 1, max(onset_cols))
    if event_count == 1:
        return [first if onset_cols else min(width - 1, max(0, left_pad))]
    span = max(1, last - first)
    out: list[int] = []
    for onset_idx in range(event_count):
        frac = onset_idx / max(1, event_count - 1)
        out.append(first + round(frac * span))
    return out


def _draw_vocal_ornament(rows: list[list[str]], *, row: int, col: int, ornament: str | None) -> None:
    if not ornament:
        return
    for ornament_row in range(max(0, row - 1), -1, -1):
        if rows[ornament_row][col] in {" ", "-"}:
            rows[ornament_row][col] = ornament[:1]
            return


@dataclass(frozen=True)
class _FallbackVocalEvent:
    onset_index: int
    pitch: int
    note_type: int = 4
    dotted: bool = False
    is_rest: bool = False
    editorial_brackets: bool = False
    ornament: str | None = None
    beam: str | None = None


class _StaffEvent(Protocol):
    @property
    def onset_index(self) -> int: ...

    @property
    def pitch(self) -> int | None: ...

    @property
    def note_type(self) -> int: ...

    @property
    def dotted(self) -> bool: ...


def _fallback_vocal_events(
    events: list[MelodyEvent] | None,
    bar_chords: list[Chord] | None,
    tuning_pitches: list[int] | None,
) -> list[_StaffEvent]:
    onset_pitch = _event_pitch_map(events)
    _merge_chord_pitch_map(onset_pitch, bar_chords, tuning_pitches)
    _fill_unpitched_event_rows(onset_pitch, events)
    fallback_events: list[_StaffEvent] = []
    for index, pitch in sorted(onset_pitch.items()):
        fallback_events.append(_FallbackVocalEvent(onset_index=index, pitch=pitch))
    return fallback_events


def _inferred_staff_events(bar: Bar | None, tuning_pitches: list[int] | None) -> list[_StaffEvent]:
    inferred_events: list[_StaffEvent] = []
    if bar is not None:
        inferred_events.extend(infer_vocal_events(bar, tuning_pitches=tuning_pitches))
    return inferred_events


def _staff_onset_columns(
    events: list[_StaffEvent],
    onset_cols: list[int],
    *,
    width: int,
    left_pad: int,
) -> tuple[list[int], int]:
    effective_left_pad = max(0, min(width - 1, left_pad))
    required_onsets = max((event.onset_index for event in events), default=-1) + 1
    if len(onset_cols) >= required_onsets:
        return onset_cols, effective_left_pad
    return (
        _resampled_onset_cols(
            onset_cols=onset_cols,
            event_count=required_onsets,
            width=width,
            left_pad=effective_left_pad,
        ),
        effective_left_pad,
    )


def _draw_staff_event(
    rows: list[list[str]],
    event: _StaffEvent,
    *,
    onset_cols: list[int],
    onset_accidental: dict[int, str],
    width: int,
    floor: int,
    melody_view: str | None,
) -> tuple[str, int, int] | None:
    onset_index = event.onset_index
    if onset_index < 0 or onset_index >= len(onset_cols):
        return None
    column = max(floor, min(width - 1, onset_cols[onset_index]))
    if getattr(event, "is_rest", False):
        rows[min(len(rows) - 1, _TOP_LINE_ROW + 2)][column] = "r"
        return None
    pitch = getattr(event, "pitch", None)
    if pitch is None:
        return None
    note_type = event.note_type
    raw_row, row = _pitch_rows(pitch, melody_view)
    _draw_vocal_stem(rows, row=row, col=column, note_type=note_type, dotted=event.dotted)
    _draw_vocal_ledger(rows, raw_row=raw_row, row=row, col=column)
    accidental = onset_accidental.get(onset_index, "")
    if accidental:
        edge = column - 1 if getattr(event, "editorial_brackets", False) else column
        _draw_vocal_accidental(rows, row=row, col=edge, accidental=accidental, floor=floor)
    rows[row][column] = _melody_notehead_glyph(note_type)
    if getattr(event, "editorial_brackets", False):
        _draw_editorial_brackets(rows, row=row, col=column, floor=floor)
    _draw_vocal_ornament(rows, row=row, col=column, ornament=getattr(event, "ornament", None))
    beam = getattr(event, "beam", None)
    return (beam, row, column) if beam else None


def melody_staff_rows(
    events: list[MelodyEvent] | None,
    *,
    onset_cols: list[int],
    width: int,
    left_pad: int = 0,
    bar: Bar | None = None,
    bar_chords: list[Chord] | None = None,
    tuning_pitches: list[int] | None = None,
    melody_view: str | None = None,
) -> list[list[str]]:
    rows = [[" "] * max(0, width) for _ in range(_MELODY_STAFF_ROWS)]
    for staff_row in range(_TOP_LINE_ROW, _BOTTOM_LINE_ROW + 1, 2):
        rows[staff_row] = ["-"] * max(0, width)
    if width <= 0 or not onset_cols:
        return rows
    vocal_events = _inferred_staff_events(bar, tuning_pitches)
    if not vocal_events:
        vocal_events = list(_fallback_vocal_events(events, bar_chords, tuning_pitches))
    if not vocal_events:
        return rows
    onset_cols, effective_left_pad = _staff_onset_columns(
        vocal_events,
        onset_cols,
        width=width,
        left_pad=left_pad,
    )
    onset_accidental = _event_accidental_map_for_bar(events, bar=bar)
    beam_points: list[tuple[str, int, int]] = []
    for event in vocal_events:
        beam_point = _draw_staff_event(
            rows,
            event,
            onset_cols=onset_cols,
            onset_accidental=onset_accidental,
            width=width,
            floor=effective_left_pad,
            melody_view=melody_view,
        )
        if beam_point is not None:
            beam_points.append(beam_point)
    _draw_vocal_beams(rows, beam_points)
    return rows


def draw_melody_time_signature(
    rows: list[list[str]],
    *,
    time_sig: str | None,
    left_pad: int,
) -> None:
    if not rows or not time_sig:
        return
    parsed = parse_time_signature_value(time_sig)
    if parsed is None:
        return
    beats, _unit = parsed
    col = max(0, left_pad - 3)
    if not rows[0] or col >= len(rows[0]):
        return
    numerator = str(beats)
    top_row = min(len(rows) - 1, _TOP_LINE_ROW + 3)
    for offset, ch in enumerate(numerator):
        target = col + offset
        if target < len(rows[top_row]):
            rows[top_row][target] = ch


_TREBLE_SHARP_PITCHES = (77, 72, 79, 74, 69, 76, 71)  # F5 C5 G5 D5 A4 E5 B4
_TREBLE_FLAT_PITCHES = (71, 76, 69, 74, 67, 72, 65)  # B4 E5 A4 D5 G4 C5 F4


def melody_key_signature_width(key: str | None) -> int:
    count = key_signature_count(key)
    if count is None or count == 0:
        return 0
    return abs(count) + 1


def draw_melody_key_signature(
    rows: list[list[str]],
    *,
    key: str | None,
    left_pad: int,
) -> None:
    count = key_signature_count(key)
    if not rows or count is None or count == 0:
        return
    pitches = _TREBLE_SHARP_PITCHES if count > 0 else _TREBLE_FLAT_PITCHES
    glyph = "#" if count > 0 else "b"
    start_col = max(0, left_pad - 1)
    for idx, pitch in enumerate(pitches[: abs(count)]):
        _raw_row, row = _pitch_rows(pitch, None)
        col = start_col + idx
        if 0 <= row < len(rows) and 0 <= col < len(rows[row]):
            rows[row][col] = glyph


def _stem_glyph_rows(*, last_stem_row: int) -> dict[int, str]:
    return dict.fromkeys(range(last_stem_row + 1), "|")


def _melody_notehead_glyph(note_type: int) -> str:
    if note_type >= 4:
        return MELODY_FILLED_NOTEHEAD_GLYPH
    return MELODY_NOTEHEAD_GLYPH


def _draw_vocal_stem(  # noqa: C901
    rows: list[list[str]],
    *,
    row: int,
    col: int,
    note_type: int,
    dotted: bool,
) -> None:
    if not rows or not (0 <= row < len(rows)):
        return
    if note_type <= 1:
        return
    stem_top = max(0, row - _MELODY_STEM_LEN)
    stem_bottom = min(max(0, row - 1), len(rows) - 1)
    stem_glyph = "|"
    for stem_row in range(stem_top, stem_bottom + 1):
        rows[stem_row][col] = stem_glyph
    flag_row = stem_top
    flags = max(0, note_type - 4)
    for idx in range(1, flags + 1):
        tail_col = col + idx
        if tail_col >= len(rows[flag_row]):
            break
        rows[flag_row][tail_col] = "\\"
    if dotted:
        dot_col = col + flags + 1
        if 0 <= dot_col < len(rows[flag_row]):
            rows[flag_row][dot_col] = "."


def _draw_vocal_beams(rows: list[list[str]], points: list[tuple[str, int, int]]) -> None:  # noqa: C901
    group: list[tuple[int, int]] = []
    for beam, row, col in points:
        if beam == "start":
            group = [(row, col)]
            continue
        if beam == "continue" and group:
            group.append((row, col))
            continue
        if beam != "end" or not group:
            group = []
            continue
        group.append((row, col))
        beam_row = min(max(0, note_row - _MELODY_STEM_LEN) for note_row, _note_col in group)
        for note_row, note_col in group:
            for stem_row in range(beam_row, max(beam_row, note_row)):
                rows[stem_row][note_col] = "|"
        start_col = min(note_col for _note_row, note_col in group)
        end_col = max(note_col for _note_row, note_col in group)
        for beam_col in range(start_col + 1, end_col):
            rows[beam_row][beam_col] = "="
        group = []


def _draw_vocal_ledger(
    rows: list[list[str]],
    *,
    raw_row: int,
    row: int,
    col: int,
) -> None:
    if not rows or not (0 <= row < len(rows)):
        return
    needs_top_ledger = raw_row <= (_TOP_LINE_ROW - 2)
    needs_bottom_ledger = raw_row >= (_BOTTOM_LINE_ROW + 2)
    if not (needs_top_ledger or needs_bottom_ledger):
        return
    start = max(0, col - 1)
    stop = min(len(rows[row]), col + 2)
    for idx in range(start, stop):
        if rows[row][idx] == " ":
            rows[row][idx] = "-"


def _draw_vocal_accidental(
    rows: list[list[str]],
    *,
    row: int,
    col: int,
    accidental: str,
    floor: int,
) -> None:
    if not accidental or not rows or not (0 <= row < len(rows)):
        return
    start = col - len(accidental)
    if start >= floor and all(rows[row][target] in {" ", "-"} for target in range(start, col)):
        rows[row][start:col] = accidental
        return
    for target in (col - 1, col - 2):
        if target >= floor and rows[row][target] in {" ", "-"}:
            rows[row][target] = accidental.strip("()")[:1]
            return


def _draw_editorial_brackets(rows: list[list[str]], *, row: int, col: int, floor: int) -> None:
    if not rows or not (0 <= row < len(rows)):
        return
    left = col - 1
    right = col + 1
    if left >= floor and rows[row][left] in {" ", "-"}:
        rows[row][left] = "["
    if right < len(rows[row]) and rows[row][right] in {" ", "-"}:
        rows[row][right] = "]"


def _place_lyric_event(
    cells: list[str],
    event: LyricEvent,
    *,
    onset_cols: list[int],
    floor: int,
    last_end: int,
) -> tuple[int, int] | None:
    target = _event_target_col(onset_cols, event.onset_index)
    if target is None:
        return None
    start = max(floor, min(len(cells) - 1, target))
    if start <= last_end + 1:
        start = last_end + 2
    if start >= len(cells):
        return None
    if event.extender and not event.text:
        cells[start] = "_"
        return start, start
    text = event.text or ""
    if not text:
        return None
    end = min(len(cells) - 1, start + len(text) - 1)
    for offset, char in enumerate(text[: end - start + 1]):
        cells[start + offset] = char
    return start, end


def lyric_event_cells(
    events: list[LyricEvent] | None,
    *,
    onset_cols: list[int],
    width: int,
    left_pad: int = 0,
) -> list[str]:
    cells = [" "] * max(0, width)
    if not cells or not events or not onset_cols:
        return cells
    floor = max(0, left_pad)
    last_end = floor - 1
    placed_spans: list[tuple[LyricEvent, int, int]] = []
    for event in events:
        placed = _place_lyric_event(cells, event, onset_cols=onset_cols, floor=floor, last_end=last_end)
        if placed is None:
            continue
        start, end = placed
        placed_spans.append((event, start, end))
        last_end = end
    _place_lyric_link_cues(cells, placed_spans)
    return cells


def _place_syllable_dash(cells: list[str], end: int, next_start: int) -> None:
    gap_mid = end + max(1, (next_start - end) // 2)
    for column in range(max(end + 1, gap_mid - 1), min(next_start, gap_mid + 2)):
        if 0 <= column < len(cells) and cells[column] == " ":
            cells[column] = "-"


def _place_lyric_extender(cells: list[str], end: int, next_start: int) -> None:
    for column in range(end + 1, next_start):
        if 0 <= column < len(cells) and cells[column] == " ":
            cells[column] = "_"


def _place_lyric_link(cells: list[str], event: LyricEvent, end: int, next_start: int) -> None:
    if event.syllabic in {"begin", "middle"}:
        _place_syllable_dash(cells, end, next_start)
    elif event.extender:
        _place_lyric_extender(cells, end, next_start)


def _place_lyric_link_cues(
    cells: list[str],
    placed_spans: list[tuple[LyricEvent, int, int]],
) -> None:
    for (event, _start, end), (_next_event, next_start, _next_end) in pairwise(placed_spans):
        if next_start <= end + 1:
            continue
        _place_lyric_link(cells, event, end, next_start)
