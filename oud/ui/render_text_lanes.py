from __future__ import annotations

import re

from oud.core.model import Chord, LyricEvent, MelodyEvent

_MELODY_STAFF_ROWS = 5
_CENTER_STAFF_ROW = _MELODY_STAFF_ROWS // 2
_DIATONIC_BASE = {"c": 0, "d": 2, "e": 4, "f": 5, "g": 7, "a": 9, "b": 11, "h": 11}


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
        dest = min(width - 1, (src_pos * width) // src_width)
        if dest <= last_end:
            dest = min(width - 1, last_end + 1)
        if dest >= width:
            break
        avail = width - dest
        if avail <= 0:
            break
        tok_text = tok[:avail]
        for i, ch in enumerate(tok_text):
            if dest + i < width:
                out[dest + i] = ch
        last_end = dest + len(tok_text) - 1
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


def _token_pitch_value(token: str) -> int | None:
    raw = token.strip().lower()
    if not raw:
        return None
    letter = next((ch for ch in raw if ch in _DIATONIC_BASE), None)
    if letter is None:
        return None
    pitch = 60 + _DIATONIC_BASE[letter]
    pitch += raw.count("#")
    if "b" in raw and letter != "b":
        pitch -= 1
    pitch += 12 * raw.count("'")
    pitch -= 12 * raw.count(",")
    return pitch


def _chord_top_pitch(chord: Chord, tuning_pitches: list[int] | None) -> int | None:
    if not chord.notes or not tuning_pitches:
        return None
    pitches: list[int] = []
    for note in chord.notes:
        idx = note.string - 1
        if 0 <= idx < len(tuning_pitches):
            pitches.append(tuning_pitches[idx] + note.fret)
    return max(pitches) if pitches else None


def _pitch_to_staff_row(pitch: int, lo: int, hi: int) -> int:
    if hi <= lo:
        return _CENTER_STAFF_ROW
    span = hi - lo
    normalized = (pitch - lo) / span
    row = (_MELODY_STAFF_ROWS - 1) - round(normalized * (_MELODY_STAFF_ROWS - 1))
    return max(0, min(_MELODY_STAFF_ROWS - 1, row))


def _event_pitch_map(events: list[MelodyEvent] | None) -> dict[int, int]:
    mapping: dict[int, int] = {}
    for ev in events or []:
        if ev.onset_index in mapping:
            continue
        pitch = _token_pitch_value(ev.text)
        if pitch is not None:
            mapping[ev.onset_index] = pitch
    return mapping


def _merge_chord_pitch_map(
    onset_pitch: dict[int, int],
    bar_chords: list[Chord] | None,
    tuning_pitches: list[int] | None,
) -> None:
    if not bar_chords:
        return
    for onset_idx, chord in enumerate(bar_chords):
        pitch = _chord_top_pitch(chord, tuning_pitches)
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


def melody_staff_rows(
    events: list[MelodyEvent] | None,
    *,
    onset_cols: list[int],
    width: int,
    left_pad: int = 0,
    bar_chords: list[Chord] | None = None,
    tuning_pitches: list[int] | None = None,
) -> list[list[str]]:
    rows = [["-"] * max(0, width) for _ in range(_MELODY_STAFF_ROWS)]
    if width <= 0 or not onset_cols:
        return rows
    onset_pitch = _event_pitch_map(events)
    _merge_chord_pitch_map(onset_pitch, bar_chords, tuning_pitches)
    _fill_unpitched_event_rows(onset_pitch, events)
    if not onset_pitch:
        return rows
    pitch_values = list(onset_pitch.values())
    lo = min(pitch_values)
    hi = max(pitch_values)
    floor = max(0, left_pad)
    for onset_idx, pitch in sorted(onset_pitch.items()):
        if onset_idx < 0 or onset_idx >= len(onset_cols):
            continue
        col = max(floor, min(width - 1, onset_cols[onset_idx]))
        row = _pitch_to_staff_row(pitch, lo, hi)
        rows[row][col] = "o"
    return rows


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
    for ev in events:
        target = _event_target_col(onset_cols, ev.onset_index)
        if target is None:
            continue
        start = max(floor, min(len(cells) - 1, target))
        if start <= last_end + 1:
            start = last_end + 2
        if start >= len(cells):
            continue
        if ev.extender and not ev.text:
            cells[start] = "_"
            placed_spans.append((ev, start, start))
            last_end = start
            continue
        text = ev.text or ""
        if not text:
            continue
        end = min(len(cells) - 1, start + len(text) - 1)
        if end < start:
            continue
        for idx, ch in enumerate(text[: end - start + 1]):
            cells[start + idx] = ch
        placed_spans.append((ev, start, end))
        last_end = end
    _place_lyric_link_cues(cells, placed_spans)
    return cells


def _place_lyric_link_cues(
    cells: list[str],
    placed_spans: list[tuple[LyricEvent, int, int]],
) -> None:
    for idx, (ev, _start, end) in enumerate(placed_spans):
        if idx + 1 >= len(placed_spans):
            continue
        _next_ev, next_start, _next_end = placed_spans[idx + 1]
        if next_start <= end + 1:
            continue
        if ev.syllabic in {"begin", "middle"}:
            gap_mid = end + max(1, (next_start - end) // 2)
            for col in range(max(end + 1, gap_mid - 1), min(next_start, gap_mid + 2)):
                if 0 <= col < len(cells) and cells[col] == " ":
                    cells[col] = "-"
        elif ev.extender:
            for col in range(end + 1, next_start):
                if 0 <= col < len(cells) and cells[col] == " ":
                    cells[col] = "_"
