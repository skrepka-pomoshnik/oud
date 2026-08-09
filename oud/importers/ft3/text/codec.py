from __future__ import annotations

from oud.importers.ft3.musical.note_records import (
    _structured_vocal_events,
    decode_ft3_annotation_group,
    decode_ft3_note_record,
    decode_ft3_vocal_events,
    ft3_note_record_group_count,
)
from oud.importers.ft3.text.rows import (
    _asciiish_lines,
    _classify_raw_line,
    _classify_structured_row,
    _clean_lyric_token,
    _clean_text_token,
    _coalesce_raw_multi_verse_rows,
    _events_from_lyric_tokens,
    _fallback_lyric_tokens_from_text,
    _filtered_structured_lyric_tokens,
    _interleaved_two_verse_rows,
    _keep_lyric_token,
    _line_tokens_with_positions,
    _looks_like_editorial_tokens,
    _lyric_tokens_from_control_row,
    _pick_melody_line,
    _raw_control_tokens_from_row,
    _reconstruct_three_verse_raw_rows,
    _record_with_verse_rows,
    _split_record_rows,
    _structured_lyric_rows,
    _structured_lyric_rows_from_positioned_rows,
    _structured_positioned_lyric_rows,
    _structured_row_text,
    is_ft3_text_record,
)
from oud.importers.ft3.text.types import FT3TextRecord, empty_text_record
from petrucci.core.model import LyricEvent, MelodyEvent

__all__ = [
    "FT3TextRecord",
    "decode_ft3_annotation_group",
    "decode_ft3_note_record",
    "decode_ft3_vocal_events",
    "ft3_note_record_group_count",
    "is_ft3_text_record",
    "parse_ft3_text_record",
    "refine_ft3_raw_text_record",
]


def _parse_structured_text_record(tail: bytes) -> FT3TextRecord | None:  # noqa: C901
    rows = _split_record_rows(tail)
    if not rows:
        return None
    has_controls = any(any(0 < b < 32 and b not in (9, 10, 13) for b in row) for row in rows)
    if not has_controls:
        return None
    classified_rows = [
        (row, classified)
        for row_index, row in enumerate(rows)
        if (classified := _classify_structured_row(row, row_index)) is not None
    ]
    structured_rows = [classified for _row, classified in classified_rows]
    raw_tokens_by_row = [tokens for row in rows if (tokens := _raw_control_tokens_from_row(row))]
    editorial_text: list[str] = []
    if len(raw_tokens_by_row) == 1 and _looks_like_editorial_tokens(raw_tokens_by_row[0]):
        editorial_text = [" ".join(raw_tokens_by_row[0]).strip()]
        return FT3TextRecord(
            melody_grid=None,
            lyrics=[],
            melody_events=[],
            lyric_event_rows=[],
            editorial_text=editorial_text,
            structured_rows=structured_rows,
            parse_mode="structured",
        )
    classified_tokens = [
        (classified.kind, filtered)
        for row, classified in classified_rows
        if classified.kind not in {"font", "control", "editorial"}
        if (
            tokens := (
                _lyric_tokens_from_control_row(row) or _fallback_lyric_tokens_from_text(_structured_row_text(row))
            )
        )
        if (filtered := _filtered_structured_lyric_tokens(tokens))
    ]
    if not classified_tokens:
        return None
    tokens_by_row = [tokens for _kind, tokens in classified_tokens]
    verse_rows = _interleaved_two_verse_rows(classified_tokens) or _structured_lyric_rows(tokens_by_row)
    melody_events = _structured_vocal_events(rows[0]) if rows else []
    lyric_lines = [" ".join(tokens).strip() for tokens in verse_rows if tokens]
    lyric_event_rows = []
    for verse, tokens in enumerate(verse_rows):
        events = _events_from_lyric_tokens(tokens, verse=verse)
        if events:
            lyric_event_rows.append(events)
    if not lyric_lines and not lyric_event_rows:
        return None
    return FT3TextRecord(
        melody_grid=None,
        lyrics=lyric_lines,
        melody_events=melody_events,
        lyric_event_rows=lyric_event_rows,
        editorial_text=[],
        structured_rows=structured_rows,
        parse_mode="structured",
    )


def _melody_events_from_line(line: str | None) -> list[MelodyEvent]:
    if not line:
        return []
    events: list[MelodyEvent] = []
    onset_idx = 0
    for pos, tok in _line_tokens_with_positions(line):
        cleaned = _clean_text_token(tok)
        if not cleaned:
            continue
        events.append(
            MelodyEvent(
                text=cleaned,
                onset_index=onset_idx,
                src_pos=pos,
                is_rest=cleaned.strip().lower() in {"r", "rest"},
            ),
        )
        onset_idx += 1
    return events


def _lyric_events_from_line(line: str) -> list[LyricEvent]:  # noqa: C901
    events: list[LyricEvent] = []
    onset_idx = 0
    chain_open = False
    for pos, tok in _line_tokens_with_positions(line):
        raw = _clean_lyric_token(tok)
        if not raw:
            continue
        if set(raw) <= {"_", "-"} and "_" in raw:
            events.append(
                LyricEvent(
                    text="",
                    onset_index=onset_idx,
                    verse=0,
                    syllabic="single",
                    src_pos=pos,
                    extender=True,
                ),
            )
            onset_idx += 1
            continue
        trailing_hyphen = raw.endswith("-")
        text = raw.rstrip("-").strip()
        if not text and trailing_hyphen:
            text = "-"
        if not text:
            continue
        if text != "-" and not _keep_lyric_token(text):
            continue
        if trailing_hyphen and chain_open:
            syllabic = "middle"
        elif trailing_hyphen:
            syllabic = "begin"
        elif chain_open:
            syllabic = "end"
        else:
            syllabic = "single"
        events.append(
            LyricEvent(
                text=text,
                onset_index=onset_idx,
                verse=0,
                syllabic=syllabic,
                src_pos=pos,
                extender=False,
            ),
        )
        chain_open = trailing_hyphen
        onset_idx += 1
    return events


def parse_ft3_text_record(chunk: bytes) -> FT3TextRecord:  # noqa: C901
    tail = chunk[32:] if len(chunk) > 32 else chunk
    structured = _parse_structured_text_record(tail)
    if structured is not None:
        return structured
    lines = _asciiish_lines(tail)
    if not lines:
        return empty_text_record()

    melody_candidates: list[str] = []
    lyrics: list[str] = []
    for raw in lines:
        melody, lyric = _classify_raw_line(raw)
        if melody:
            melody_candidates.append(melody)
        if lyric:
            lyrics.append(lyric)

    dedup_lyrics: list[str] = []
    lyric_event_rows: list[list[LyricEvent]] = []
    seen: set[str] = set()
    for line in lyrics:
        key = line.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        dedup_lyrics.append(line)
        lyric_events = _lyric_events_from_line(line)
        if lyric_events:
            lyric_event_rows.append(lyric_events)
    melody_line = _pick_melody_line(melody_candidates)
    melody_events = _melody_events_from_line(melody_line)
    return FT3TextRecord(
        melody_line,
        dedup_lyrics,
        melody_events=melody_events,
        lyric_event_rows=lyric_event_rows,
        editorial_text=[],
        structured_rows=[],
        parse_mode="ascii",
    )


def refine_ft3_raw_text_record(record: FT3TextRecord, chunk: bytes) -> FT3TextRecord:
    if record.parse_mode != "structured" or not record.structured_rows:
        return record
    tail = chunk[32:] if len(chunk) > 32 else chunk
    positioned_tokens_by_row = _structured_positioned_lyric_rows(tail)
    if not positioned_tokens_by_row:
        return record
    three_verse_rows = _reconstruct_three_verse_raw_rows(
        positioned_tokens_by_row,
        melody_event_count=len(record.melody_events),
    )
    if three_verse_rows:
        return _record_with_verse_rows(record, three_verse_rows)
    verse_rows = _structured_lyric_rows_from_positioned_rows(
        positioned_tokens_by_row,
        prefer_cluster=True,
    )
    if not verse_rows:
        return record
    verse_rows = _coalesce_raw_multi_verse_rows(
        verse_rows,
        melody_event_count=len(record.melody_events),
    )
    return _record_with_verse_rows(record, verse_rows)
