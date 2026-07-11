from __future__ import annotations

import re

from oud.petrucci.model import Bar, LyricEvent, MelodyEvent
from oud.petrucci.render_text_lanes import (
    lyric_event_cells,
    melody_staff_rows,
    text_bar_cells,
)
from oud.petrucci.render_text_lanes import (
    melody_row_count as _melody_row_count,
)


def melody_row_count(view: str | None = None) -> int:
    return _melody_row_count(view)


def _bar_melody_events(bar: Bar) -> list[MelodyEvent]:
    events = list(getattr(bar, "melody_events", None) or [])
    if events:
        return events
    return _grid_melody_events(getattr(bar, "melody_grid", None))


def _grid_melody_events(text: str | None) -> list[MelodyEvent]:
    if not text:
        return []
    out: list[MelodyEvent] = []
    for onset_idx, match in enumerate(re.finditer(r"\S+", text)):
        out.append(MelodyEvent(text=match.group(0), onset_index=onset_idx, src_pos=match.start()))
    return out


def melody_rows_for_bar(
    bar: Bar,
    *,
    onset_cols: list[int],
    width: int,
    left_pad: int,
    tuning_pitches: list[int] | None,
    melody_view: str | None = None,
) -> list[list[str]]:
    events = _bar_melody_events(bar)
    return melody_staff_rows(
        events,
        onset_cols=onset_cols,
        width=width,
        left_pad=left_pad,
        bar=bar,
        bar_chords=getattr(bar, "chords", None),
        tuning_pitches=tuning_pitches,
        melody_view=melody_view,
    )


def _grid_lyric_events(text: str | None) -> list[LyricEvent]:
    if not text:
        return []
    out: list[LyricEvent] = []
    for onset_idx, match in enumerate(re.finditer(r"\S+", text)):
        out.append(
            LyricEvent(
                text=match.group(0),
                onset_index=onset_idx,
                verse=0,
                src_pos=match.start(),
            ),
        )
    return out


def _scaled_onset_cols_from_lyrics(
    lyric_rows: list[list[LyricEvent]],
    *,
    event_count: int,
    width: int,
    left_pad: int,
) -> list[int]:
    if event_count <= 0 or width <= 0:
        return []
    by_onset: dict[int, int] = {}
    for row in lyric_rows:
        for ev in row:
            if ev.src_pos < 0 or ev.onset_index in by_onset:
                continue
            by_onset[ev.onset_index] = ev.src_pos
    if not by_onset:
        return []
    max_src = max(by_onset.values())
    span = max(1, width - left_pad)
    src_den = max(1, max_src + 1)
    cols: list[int] = []
    prev = max(0, left_pad)
    for onset_idx in range(event_count):
        src = (
            by_onset[onset_idx]
            if onset_idx in by_onset
            else round((onset_idx / max(1, event_count - 1)) * max_src)
        )
        col = max(0, left_pad) + min(span - 1, (src * span) // src_den)
        col = min(width - 1, max(prev, col))
        cols.append(col)
        prev = min(width - 1, col + 1)
    return cols


def _lyric_token_score(ev: LyricEvent) -> tuple[int, int, int]:
    text = (ev.text or "").strip()
    alpha = sum(ch.isalpha() for ch in text)
    punct = sum(not ch.isalnum() and ch not in {"'", "-"} for ch in text)
    return (alpha, -punct, len(text))


def _is_strong_lyric_token(ev: LyricEvent) -> bool:
    text = (ev.text or "").strip()
    if not text:
        return False
    alpha = sum(ch.isalpha() for ch in text)
    if alpha >= 2:
        return True
    return text.lower() in {"i", "a", "o"}


def _primary_lyric_events(event_rows: list[list[LyricEvent]]) -> list[LyricEvent]:
    by_onset: dict[int, list[LyricEvent]] = {}
    for row in event_rows:
        for ev in row:
            text = (ev.text or "").strip()
            if not text and not ev.extender:
                continue
            by_onset.setdefault(ev.onset_index, []).append(ev)
    out: list[LyricEvent] = []
    for onset in sorted(by_onset):
        candidates = by_onset[onset]
        best = next((ev for ev in candidates if _is_strong_lyric_token(ev)), None)
        if best is None:
            best = max(candidates, key=_lyric_token_score)
        out.append(
            LyricEvent(
                text=best.text,
                onset_index=best.onset_index,
                verse=best.verse,
                syllabic=best.syllabic,
                src_pos=best.src_pos,
                extender=best.extender,
            ),
        )
    return out


def _dedup_lyric_rows(event_rows: list[list[LyricEvent]]) -> list[list[LyricEvent]]:
    out: list[list[LyricEvent]] = []
    seen: set[tuple[tuple[int, str], ...]] = set()
    for row in event_rows:
        key = tuple(
            (ev.onset_index, (ev.text or "").strip())
            for ev in row
            if (ev.text or "").strip()
        )
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def _lyric_row_key(row: list[LyricEvent]) -> tuple[tuple[int, str], ...]:
    return tuple((ev.onset_index, (ev.text or "").strip()) for ev in row if (ev.text or "").strip())


def _lyric_row_score(row: list[LyricEvent]) -> int:
    return sum(sum(ch.isalpha() for ch in (ev.text or "")) for ev in row)


def _lyric_row_verse(row: list[LyricEvent]) -> int:
    verses = [ev.verse for ev in row]
    return min(verses) if verses else 0


def lyric_rows_for_bar(
    bar: Bar,
    *,
    onset_cols: list[int],
    width: int,
    left_pad: int,
    lyric_rows_count: int,
) -> list[list[str]]:
    if _raw_vocal_fallback_text_rows(bar):
        raw_lines = _raw_vocal_fallback_text_rows(bar)[: max(lyric_rows_count, 1)]
        out: list[list[str]] = []
        for text in raw_lines:
            cells = [" "] * max(0, width)
            payload = text_bar_cells(text, max(0, width - left_pad))
            for idx, ch in enumerate(payload):
                dest = left_pad + idx
                if 0 <= dest < len(cells):
                    cells[dest] = ch
            out.append(cells)
        while len(out) < lyric_rows_count:
            out.append([" "] * max(0, width))
        return out
    event_rows = _dedup_lyric_rows(_bar_lyric_rows(bar))
    ordered_rows = sorted(
        event_rows,
        key=lambda row: (_lyric_row_verse(row), -_lyric_row_score(row), _lyric_row_key(row)),
    )
    target_rows = max(lyric_rows_count, len(ordered_rows))
    out: list[list[str]] = []
    for idx in range(target_rows):
        events = ordered_rows[idx] if idx < len(ordered_rows) else []
        out.append(
            lyric_event_cells(
                events,
                onset_cols=onset_cols,
                width=width,
                left_pad=left_pad,
            ),
        )
    return out


def _raw_vocal_fallback_text_rows(bar: Bar) -> list[str]:
    for row in getattr(bar, "structured_text_rows", None) or []:
        if row.kind != "vocal":
            continue
        text = (row.text or "").strip()
        if text and text[0].isdigit():
            return [line for line in (getattr(bar, "lyrics", None) or []) if line.strip()]
    return []


def _max_onset_index(rows: list[list[LyricEvent]], melody_events: list[MelodyEvent]) -> int:
    max_idx = -1
    for ev in melody_events:
        max_idx = max(max_idx, ev.onset_index)
    for row in rows:
        for ev in row:
            max_idx = max(max_idx, ev.onset_index)
    return max_idx


def _scaled_onset_cols_from_events(
    events: list[MelodyEvent],
    *,
    event_count: int,
    width: int,
    left_pad: int,
) -> list[int]:
    if event_count <= 0 or width <= 0:
        return []
    by_onset = {ev.onset_index: ev.src_pos for ev in events if ev.src_pos >= 0}
    if not by_onset:
        return []
    max_src = max(by_onset.values())
    span = max(1, width - left_pad)
    src_den = max(1, max_src + 1)
    cols: list[int] = []
    prev = max(0, left_pad)
    for onset_idx in range(event_count):
        src = (
            by_onset[onset_idx]
            if onset_idx in by_onset
            else round((onset_idx / max(1, event_count - 1)) * max_src)
        )
        col = max(0, left_pad) + min(span - 1, (src * span) // src_den)
        col = min(width - 1, max(prev, col))
        cols.append(col)
        prev = min(width - 1, col + 1)
    return cols


def _spread_onset_cols(
    *,
    event_count: int,
    width: int,
    left_pad: int,
) -> list[int]:
    if event_count <= 0 or width <= 0:
        return []
    span = max(1, width - left_pad)
    cols: list[int] = []
    for onset_idx in range(event_count):
        frac = onset_idx / max(1, event_count - 1)
        col = max(0, left_pad) + min(span - 1, round(frac * (span - 1)))
        cols.append(min(width - 1, col))
    return cols


def _bar_lyric_rows(bar: Bar) -> list[list[LyricEvent]]:
    lyric_rows: list[list[LyricEvent]] = []
    for row in getattr(bar, "lyric_event_rows", None) or []:
        filtered = [ev for ev in row if (ev.text or "").strip() or ev.extender]
        if filtered:
            lyric_rows.append(filtered)
    if lyric_rows:
        return lyric_rows
    for text in getattr(bar, "lyrics", None) or []:
        events = _grid_lyric_events(text)
        if events:
            lyric_rows.append(events)
    return lyric_rows


def vocal_onset_cols_for_bar(
    bar: Bar,
    *,
    onset_cols: list[int],
    width: int,
    left_pad: int,
) -> list[int]:
    melody_events = _bar_melody_events(bar)
    lyric_rows = _bar_lyric_rows(bar)
    max_onset = _max_onset_index(lyric_rows, melody_events)
    event_count = max_onset + 1 if max_onset >= 0 else len(onset_cols)
    # When melody is inferred from tablature (no explicit melody lane), chord
    # onsets define the real melodic attacks and must not be clipped by sparse
    # lyric-token onsets.
    chord_count = len(getattr(bar, "chords", None) or [])
    event_count = max(event_count, chord_count)
    if event_count <= 0:
        return list(onset_cols)
    if len(onset_cols) == event_count:
        return list(onset_cols)
    scaled: list[int] = []
    if len(melody_events) >= event_count:
        scaled = _scaled_onset_cols_from_events(
            melody_events,
            event_count=event_count,
            width=width,
            left_pad=left_pad,
        )
    if scaled:
        return scaled
    scaled = _scaled_onset_cols_from_lyrics(
        lyric_rows,
        event_count=event_count,
        width=width,
        left_pad=left_pad,
    )
    if scaled:
        return scaled
    return _spread_onset_cols(event_count=event_count, width=width, left_pad=left_pad)
