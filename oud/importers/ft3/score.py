from __future__ import annotations

import re
from dataclasses import dataclass, replace

from oud.importers.ft3.musical.duration import (
    _finalize_explicit_vocal_melody,
)
from oud.importers.ft3.musical.tab import (
    _DYNAMIC_TEXT,
    _is_embedded_score_text_record,
    _is_standard_staff_record,
)
from oud.importers.ft3.text.codec import (
    FT3TextRecord,
    decode_ft3_annotation_group,
    decode_ft3_note_record,
    decode_ft3_vocal_events,
    ft3_note_record_group_count,
    parse_ft3_text_record,
    refine_ft3_raw_text_record,
)
from petrucci.core.model import (
    Bar,
    ImportedTextRow,
    LyricEvent,
    MelodyEvent,
)

_MATRIX_COORDINATES = frozenset(b"0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ")
_SCORE_ANNOTATION_FONTS = frozenset(("arial", "times new roman"))


def _is_tab_bar(bar: Bar) -> bool:
    return bool(bar.chords or bar.notes)


def _parallel_mixed_score_prefix_count(kinds: list[str]) -> int | None:
    first_tab = next((idx for idx, kind in enumerate(kinds) if kind == "tab"), -1)
    if first_tab <= 0:
        return None
    prefix = kinds[:first_tab]
    suffix = kinds[first_tab:]
    if any(kind != "raw" for kind in prefix):
        return None
    if not suffix or any(kind != "tab" for kind in suffix):
        return None
    if len(prefix) != len(suffix):
        return None
    return len(prefix)


def _parallel_raw_bar_targets(raw_kinds: list[str], *, bar_count: int) -> list[int]:
    if bar_count <= 0:
        return []
    targets: list[int] = []
    bar_index = 0
    for raw_kind in raw_kinds:
        target_index = min(bar_index, bar_count - 1)
        targets.append(target_index)
        if raw_kind:
            bar_index += 1
    return targets


@dataclass(frozen=True)
class _BodyEntry:
    kind: str
    chunk: bytes
    parsed: Bar
    score_kind: str | None


@dataclass(frozen=True)
class _MappedScoreEntry:
    bar_index: int
    staff_index: int
    entry: _BodyEntry
    voice_index: int = 0


@dataclass(frozen=True)
class _ImportedScoreChunk:
    bar_index: int
    staff_index: int
    raw_size: int
    record_kind: str
    chunk: bytes
    voice_index: int = 0


_SOURCE_RECORD_KINDS = {
    "annotation-group-raw": "annotation-group",
    "barline-raw": "barline",
    "comment-rtf-raw": "comment",
    "layout-raw": "layout",
    "note-lyric-raw": "note-lyrics",
    "note-staff-raw": "note",
    "score-settings-raw": "score-terminator",
    "text-score-raw": "text",
    "unknown": "unknown",
}


def _entry_run_end(entries: list[_BodyEntry], start: int, kind: str) -> int:
    end = start
    while end < len(entries) and entries[end].kind == kind:
        end += 1
    return end


def _map_body_with_tab(
    entries: list[_BodyEntry],
    *,
    text_record_cache: dict[bytes, FT3TextRecord],
) -> tuple[list[_BodyEntry], list[_MappedScoreEntry]]:
    tab_entries: list[_BodyEntry] = []
    score_entries: list[_MappedScoreEntry] = []
    index = 0
    while index < len(entries):
        entry = entries[index]
        if entry.kind == "tab":
            end = _entry_run_end(entries, index, "tab")
            tab_entries.extend(entries[index:end])
            index = end
            continue
        if entry.kind != "raw":
            index += 1
            continue

        raw_end = _entry_run_end(entries, index, "raw")
        tab_end = _entry_run_end(entries, raw_end, "tab")
        raw_run = entries[index:raw_end]
        tab_run = entries[raw_end:tab_end]
        parallel_score = any(
            _is_standard_staff_record(raw_entry.chunk)
            or bool(
                raw_entry.score_kind
                and (
                    decoded := _decode_raw_score_record(
                        raw_entry.score_kind,
                        raw_entry.chunk,
                        text_record_cache=text_record_cache,
                    )
                )
                and decoded.melody_events
            )
            for raw_entry in raw_run
        )
        if parallel_score and tab_run and len(raw_run) % len(tab_run) == 0:
            bar_offset = len(tab_entries)
            for raw_index, raw_entry in enumerate(raw_run):
                score_entries.append(
                    _MappedScoreEntry(
                        bar_index=bar_offset + (raw_index % len(tab_run)),
                        staff_index=raw_index // len(tab_run),
                        entry=raw_entry,
                    ),
                )
            tab_entries.extend(tab_run)
            index = tab_end
            continue

        anchors_next_bar = tab_end > raw_end and all(
            raw_entry.score_kind == "annotation-group-raw" for raw_entry in raw_run
        )
        target = len(tab_entries) if anchors_next_bar else max(0, len(tab_entries) - 1)
        score_entries.extend(_MappedScoreEntry(target, 0, raw_entry) for raw_entry in raw_run)
        index = raw_end
    return tab_entries, score_entries


def _ensemble_staff_labels(annotations: dict[str, str]) -> list[str]:
    ensemble = annotations.get("ensemble", "")
    return [part.split(":", 1)[0].strip() for part in ensemble.split(",") if part.strip()]


def _notation_staff_labels(annotations: dict[str, str]) -> list[str]:
    labels = [
        label for label in reversed(_ensemble_staff_labels(annotations)) if not _is_tablature_instrument_label(label)
    ]
    selected = annotations.get("part", "").strip()
    if not selected or selected.lower() == "score":
        return labels
    selected_labels = {part.strip().lower() for part in selected.split(",") if part.strip()}
    matched = [label for label in labels if label.lower() in selected_labels]
    return matched or labels


def _is_tablature_instrument_label(label: str) -> bool:
    normalized = label.lower()
    if "viol" in normalized:
        return False
    return "course" in normalized or any(
        instrument in normalized for instrument in ("archlute", "guitar", "lute", "theorbo", "vihuela")
    )


def _is_note_score_entry(entry: _BodyEntry) -> bool:
    return entry.score_kind in {"note-staff-raw", "note-lyric-raw"}


def _parallel_note_tab_plan(
    entries: list[_BodyEntry],
    annotations: dict[str, str],
) -> tuple[list[_BodyEntry], list[_MappedScoreEntry], list[str]] | None:
    tab_start = len(entries)
    while tab_start > 0 and entries[tab_start - 1].kind == "tab":
        tab_start -= 1
    tab_entries = entries[tab_start:]
    prefix = entries[:tab_start]
    if not prefix or not tab_entries:
        return None
    note_entries = [entry for entry in prefix if _is_note_score_entry(entry)]
    if not note_entries or len(note_entries) % len(tab_entries):
        return None
    if any(not _is_note_score_entry(entry) and not _is_parallel_score_padding(entry) for entry in prefix):
        return None

    labels = _notation_staff_labels(annotations)
    lane_count = len(note_entries) // len(tab_entries)
    if not labels or lane_count % len(labels):
        return None
    voices_per_staff = lane_count // len(labels)
    mapped: list[_MappedScoreEntry] = []
    for lane_index in range(lane_count):
        start = lane_index * len(tab_entries)
        lane = note_entries[start : start + len(tab_entries)]
        staff_index = lane_index // voices_per_staff
        voice_index = lane_index % voices_per_staff
        mapped.extend(
            _MappedScoreEntry(bar_index, staff_index, entry, voice_index) for bar_index, entry in enumerate(lane)
        )
    mapped.extend(_parallel_padding_mappings(prefix, len(tab_entries), voices_per_staff))
    return tab_entries, mapped, labels


_FT3_SCORE_HEADER_SIZE = 32
_FT3_SCORE_MAX_OBJECT_INDEX = 128
_FT3_SCORE_OBJECT_HEADER_SIZE = 30
_FT3_SCORE_MIN_NONZERO_PAYLOAD = 12
_FT3_SCORE_MAX_CONTROL_BYTES = 4
_FT3_SCORE_UPPER_LETTER_MIN = 0x41
_FT3_SCORE_UPPER_LETTER_MAX = 0x5A
_FT3_SCORE_LOWER_LETTER_MIN = 0x61
_FT3_SCORE_LOWER_LETTER_MAX = 0x7A
_FT3_SCORE_LAYOUT_LENGTH = 74
_FT3_SCORE_EXERCISE_LAYOUT_LENGTH = 97
_FT3_SCORE_PARENTHESES_LAYOUT_LENGTH = 95
_FT3_SCORE_FIXED_TAB_LENGTH = 64
_FT3_SCORE_EMPTY_STAFF_LENGTH = 62
_FT3_SCORE_HEADING_MIN_LENGTH = 40
_FT3_SCORE_MIN_NOTE_GROUPS = 2
_FT3_SCORE_MIN_LYRIC_ROWS = 8
_FT3_SCORE_MIN_MATRIX_COLUMNS = 2
_FT3_SCORE_MIN_CONTROL_FRAGMENT_ROWS = 4
_FT3_SCORE_MAX_CONTROL_FRAGMENT_TEXT = 2
_FT3_SCORE_CONTROL_BYTE_LIMIT = 0x20
_FT3_SCORE_MIN_POSITIONED_ROWS = 3


def _is_parallel_score_padding(entry: _BodyEntry) -> bool:
    return entry.score_kind in {"layout-raw", "barline-raw"} or (
        entry.kind == "other" and len(entry.chunk) <= _FT3_SCORE_HEADER_SIZE
    )


def _parallel_padding_mappings(
    entries: list[_BodyEntry],
    bar_count: int,
    voices_per_staff: int,
) -> list[_MappedScoreEntry]:
    mapped: list[_MappedScoreEntry] = []
    note_index = 0
    for entry in entries:
        if _is_note_score_entry(entry):
            note_index += 1
            continue
        if entry.score_kind is None:
            continue
        preceding = max(0, note_index - 1)
        lane_index, bar_index = divmod(preceding, bar_count)
        mapped.append(
            _MappedScoreEntry(bar_index, lane_index // voices_per_staff, entry, lane_index % voices_per_staff),
        )
    return mapped


def _map_score_only_body(
    entries: list[_BodyEntry],
    annotations: dict[str, str],
) -> tuple[int, list[_MappedScoreEntry], list[str]] | None:
    if not entries or any(entry.kind != "raw" for entry in entries):
        return None
    if single_staff := _map_single_staff_score_only_body(entries, annotations):
        return single_staff
    labels = list(reversed(_ensemble_staff_labels(annotations)))
    if not labels or len(entries) % len(labels):
        return None
    bar_count = len(entries) // len(labels)
    mapped = [_MappedScoreEntry(index % bar_count, index // bar_count, entry) for index, entry in enumerate(entries)]
    return bar_count, mapped, labels


def _map_single_staff_score_only_body(
    entries: list[_BodyEntry],
    annotations: dict[str, str],
) -> tuple[int, list[_MappedScoreEntry], list[str]] | None:
    labels = _notation_staff_labels(annotations)
    supported = {"note-staff-raw", "note-lyric-raw", "layout-raw", "barline-raw", "text-score-raw"}
    selected_part = annotations.get("part", "").strip()
    has_layout = any(entry.score_kind == "layout-raw" for entry in entries)
    if not selected_part or selected_part.lower() == "score" or not has_layout:
        return None
    if len(labels) != 1 or any(entry.score_kind not in supported for entry in entries):
        return None
    note_count = sum(_is_note_score_entry(entry) for entry in entries)
    if not note_count:
        return None
    mapped: list[_MappedScoreEntry] = []
    bar_index = 0
    for entry in entries:
        target = bar_index if _is_note_score_entry(entry) else max(0, bar_index - 1)
        mapped.append(_MappedScoreEntry(target, 0, entry))
        if _is_note_score_entry(entry):
            bar_index += 1
    return note_count, mapped, labels


def _record_has_content(record: FT3TextRecord) -> bool:
    return bool(
        record.melody_grid
        or record.lyrics
        or record.melody_events
        or record.lyric_event_rows
        or record.editorial_text
        or record.structured_rows,
    )


def _next_melody_onset(events: list[MelodyEvent]) -> int:
    return max((event.onset_index for event in events), default=-1) + 1


def _next_lyric_onset(rows: list[list[LyricEvent]]) -> int:
    return max(
        (max((event.onset_index for event in row), default=-1) + 1 for row in rows),
        default=0,
    )


def _append_text_rows(existing: list[str], incoming: list[str]) -> list[str]:
    merged = list(existing)
    for idx, text in enumerate(incoming):
        if not text:
            continue
        while len(merged) <= idx:
            merged.append("")
        merged[idx] = f"{merged[idx]} {text}".strip() if merged[idx] else text
    return merged


def _shift_melody_events(events: list[MelodyEvent], offset: int) -> list[MelodyEvent]:
    if offset <= 0:
        return list(events)
    return [replace(event, onset_index=event.onset_index + offset) for event in events]


def _shift_lyric_rows(
    rows: list[list[LyricEvent]],
    offset: int,
) -> list[list[LyricEvent]]:
    if offset <= 0:
        return [list(row) for row in rows]
    return [
        [
            LyricEvent(
                text=event.text,
                onset_index=event.onset_index + offset,
                verse=event.verse,
                syllabic=event.syllabic,
                src_pos=event.src_pos,
                extender=event.extender,
            )
            for event in row
        ]
        for row in rows
    ]


def _merge_melody_record_into_bar(
    bar: Bar,
    *,
    melody_grid: str | None,
    melody_events: list[MelodyEvent],
) -> None:
    if melody_grid:
        bar.melody_grid = bar.melody_grid or melody_grid
    if not melody_events:
        return
    incoming = list(melody_events)
    if bar.melody_events and min((event.onset_index for event in incoming), default=0) == 0:
        incoming = _shift_melody_events(incoming, _next_melody_onset(bar.melody_events))
    bar.melody_events.extend(incoming)
    bar.fermata = bar.fermata or any(event.fermata for event in incoming)


def _merge_lyric_record_into_bar(
    bar: Bar,
    *,
    lyrics: list[str],
    lyric_event_rows: list[list[LyricEvent]],
) -> None:
    if lyrics:
        filtered_lines = [line for line in lyrics if _is_meaningful_lyric_line(line)]
        if filtered_lines:
            bar.lyrics = _append_text_rows(bar.lyrics, filtered_lines)
    if not lyric_event_rows:
        return
    incoming_rows = [list(row) for row in lyric_event_rows]
    if bar.lyric_event_rows and any(row for row in incoming_rows):
        lyric_offset = _next_melody_onset(bar.melody_events) or _next_lyric_onset(
            bar.lyric_event_rows,
        )
        incoming_rows = _shift_lyric_rows(incoming_rows, lyric_offset)
    while len(bar.lyric_event_rows) < len(incoming_rows):
        bar.lyric_event_rows.append([])
    for idx, row in enumerate(incoming_rows):
        bar.lyric_event_rows[idx].extend(row)


def _is_meaningful_lyric_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if set(stripped) <= {"_", "-", " "}:
        return False
    words = re.findall(r"[A-Za-z][A-Za-z'-]*", stripped)
    if not words:
        return False
    return not all(len(word) == 1 and word.lower() not in {"i", "a", "o"} for word in words)


def _merge_text_record_into_bar(bar: Bar, record: FT3TextRecord) -> None:
    _merge_melody_record_into_bar(
        bar,
        melody_grid=record.melody_grid,
        melody_events=list(record.melody_events),
    )
    _merge_lyric_record_into_bar(
        bar,
        lyrics=list(record.lyrics),
        lyric_event_rows=[list(row) for row in record.lyric_event_rows],
    )
    for text in record.editorial_text:
        normalized = text.lower().rstrip(".")
        if normalized in _DYNAMIC_TEXT and bar.dynamic is None:
            bar.dynamic = normalized
        elif text:
            bar.editorial_text.append(text)
    if record.structured_rows:
        bar.structured_text_rows.extend(record.structured_rows)
    _finalize_explicit_vocal_melody(bar)


def _parse_score_text_record(
    chunk: bytes,
    *,
    text_record_cache: dict[bytes, FT3TextRecord] | None,
) -> FT3TextRecord:
    payload = chunk[_FT3_SCORE_HEADER_SIZE:] if len(chunk) > _FT3_SCORE_HEADER_SIZE else chunk
    normalized = bytes(32) + payload
    if text_record_cache is not None and payload in text_record_cache:
        return text_record_cache[payload]
    decoded = parse_ft3_text_record(normalized)
    annotations = _plain_score_annotations(normalized)
    if _use_plain_score_annotation(decoded, annotations):
        rows = [
            ImportedTextRow(row_index=index, kind="editorial", text=text, tokens=text.split())
            for index, text in enumerate(annotations)
        ]
        decoded = replace(
            decoded,
            lyrics=[],
            lyric_event_rows=[],
            editorial_text=annotations,
            structured_rows=rows,
            parse_mode="structured",
        )
    if text_record_cache is not None:
        text_record_cache[payload] = decoded
    return decoded


def _use_plain_score_annotation(decoded: FT3TextRecord, annotations: list[str]) -> bool:
    if len(annotations) != 1 or decoded.melody_grid or decoded.melody_events or decoded.lyric_event_rows:
        return False
    if not decoded.lyrics:
        return True
    annotation = annotations[0].lower()
    return all(annotation in lyric.lower() for lyric in decoded.lyrics)


def _plain_score_annotations(chunk: bytes) -> list[str]:
    annotations: list[str] = []
    for raw in re.findall(rb"[\x20-\x7e]{4,}", chunk):
        text = raw.decode("cp1252", errors="replace").strip()
        text = re.sub(r"^[^A-Za-z]+", "", text).strip()
        normalized = text.lower().rstrip(".")
        if not text or not any(char.isalpha() for char in text):
            continue
        if normalized in _SCORE_ANNOTATION_FONTS or re.fullmatch(r"c[><=][0-9:;<=>?@a-z]+", normalized):
            continue
        if text not in annotations:
            annotations.append(text)
    return annotations


def _score_record_kind(
    chunk: bytes,
    *,
    text_record_cache: dict[bytes, FT3TextRecord] | None = None,
) -> str | None:
    container_kind = "layout-raw" if _is_tab_layout_record(chunk) else None
    if container_kind is None and _is_fixed_empty_tab_record(chunk):
        container_kind = "barline-raw"
    if container_kind is not None:
        return container_kind
    if _tab_heading_texts(chunk):
        return "text-score-raw"
    if _is_standard_staff_record(chunk):
        decoded = _parse_score_text_record(chunk, text_record_cache=text_record_cache)
        return "note-lyric-raw" if decoded.lyrics or decoded.lyric_event_rows else "note-staff-raw"
    if _is_empty_standard_staff_record(chunk):
        return "note-staff-raw"
    if _is_embedded_score_text_record(chunk):
        decoded = _parse_score_text_record(chunk, text_record_cache=text_record_cache)
        return "note-lyric-raw" if decoded.lyrics or decoded.lyric_event_rows else "text-score-raw"
    return None


def _decoded_note_record_kind(
    chunk: bytes,
    *,
    text_record_cache: dict[bytes, FT3TextRecord] | None = None,
) -> str:
    decoded = _parse_score_text_record(chunk, text_record_cache=text_record_cache)
    return "note-lyric-raw" if decoded.lyrics or decoded.lyric_event_rows else "note-staff-raw"


def _has_structural_score_marker(bar: Bar) -> bool:
    return bool(bar.time_sig or bar.barline or bar.repeat or bar.ending_numbers)


def _classify_score_payload(chunk: bytes) -> str | None:
    payload = chunk[32:]
    note_staff_markers = tuple(bytes((0x01, row)) for row in range(0x30, 0x36))
    marker_region = chunk[28:]
    has_note_staff_markers = any(marker in marker_region for marker in note_staff_markers)
    is_score_settings = chunk[2:7] == b"\x00\x11\x00\x00\xff" and b"\r\n" not in payload
    if is_score_settings and not has_note_staff_markers:
        return "score-settings-raw"
    object_index = int.from_bytes(chunk[28:30], "little") if len(chunk) >= _FT3_SCORE_OBJECT_HEADER_SIZE else 0
    if object_index > _FT3_SCORE_MAX_OBJECT_INDEX and chunk[30:_FT3_SCORE_HEADER_SIZE] == b"\x02\x00":
        return "annotation-group-raw"
    nonzero = sum(1 for value in payload if value)
    controls = sum(1 for value in payload if 0 < value < _FT3_SCORE_CONTROL_BYTE_LIMIT and value not in (9, 10, 13))
    if nonzero < _FT3_SCORE_MIN_NONZERO_PAYLOAD and controls < _FT3_SCORE_MAX_CONTROL_BYTES:
        return None
    if b"{\\rtf" in payload or b"\\fonttbl" in payload:
        return "comment-rtf-raw"
    has_text = b"\r\n" in payload and any(
        (_FT3_SCORE_UPPER_LETTER_MIN <= value <= _FT3_SCORE_UPPER_LETTER_MAX)
        or (_FT3_SCORE_LOWER_LETTER_MIN <= value <= _FT3_SCORE_LOWER_LETTER_MAX)
        for value in payload
    )
    if has_note_staff_markers:
        return "note-lyric-raw" if has_text else "note-staff-raw"
    return "text-score-raw" if has_text else "unknown"


def _is_tab_layout_record(chunk: bytes) -> bool:
    fixed_layout = _is_fixed_empty_tab_record(chunk) and chunk[4:7] == b"\x00\x00\xff"
    # A later FT3 layout variant carries three placement tuples and no objects.
    placement_layout = (
        len(chunk) == _FT3_SCORE_LAYOUT_LENGTH
        and chunk[2:7] == b"\x04\x11\x00\x00\xff"
        and chunk[28:32] == b"\x00\x00\x03\x03"
        and chunk[-18:-16] == b"\x02\x00"
        and chunk[-16:] == b"\x00" * 16
    )
    compact_placement_layout = (
        len(chunk) in {59, 117}
        and chunk[2:7] == b"\x04\x11\x00\x00\xff"
        and chunk[28:33] == b"\x00\x00\x00\x02\x00"
        and chunk[-16:] == bytes(16)
    )
    exercise_layout = (
        len(chunk) == _FT3_SCORE_EXERCISE_LAYOUT_LENGTH
        and chunk[2:7] == b"\x04\x11\x00\x00\xff"
        and chunk[8:10] == b"\x7e\x80"
        and chunk[-20:] == bytes(20)
    )
    parenthesized_layout = (
        len(chunk) == _FT3_SCORE_PARENTHESES_LAYOUT_LENGTH
        and chunk[2:7] == b"\x04\x11\x00\x00\xff"
        and b"(   )" in chunk
        and chunk[-8:] == bytes(8)
    )
    padding_layout = chunk == b"\x00\x00\x04\x11\x00\x00\xff\x00"
    return (
        fixed_layout
        or placement_layout
        or compact_placement_layout
        or exercise_layout
        or parenthesized_layout
        or padding_layout
    )


def _is_fixed_empty_tab_record(chunk: bytes) -> bool:
    return (
        len(chunk) == _FT3_SCORE_FIXED_TAB_LENGTH
        and chunk[2:4] == b"\x04\x11"
        and chunk[6] in {0xF4, 0xFF}
        and chunk[28:32] == b"\x00\x00\x01\x00"
        and chunk[32] in {0x01, 0x03}
        and chunk[33:38] == b"\x00\x00\x00\x02\x00"
    )


def _is_empty_standard_staff_record(chunk: bytes) -> bool:
    return (
        len(chunk) == _FT3_SCORE_EMPTY_STAFF_LENGTH
        and chunk[2:7] == b"\x04\x11\x00\x00\xff"
        and chunk[28:33] == b"\x00\x00\x00\x02\x00"
        and chunk[41:54] == b"\x02\x00" + bytes(10) + b"\x01"
    )


def _tab_heading_texts(chunk: bytes) -> list[str]:
    if (
        len(chunk) < _FT3_SCORE_HEADING_MIN_LENGTH
        or chunk[2:7] != b"\x04\x11\x78\x00\x00"
        or chunk[32:36] != b"\x01\x00\x00\x00"
    ):
        return []
    cursor = 36
    values: list[str] = []
    while cursor + 3 <= len(chunk) and chunk[cursor : cursor + 2] == b"\x01\x00":
        size = chunk[cursor + 2]
        start = cursor + 3
        end = start + size
        if end > len(chunk):
            break
        if size == 0:
            cursor = end
            continue
        text = chunk[start:end].decode("latin1", errors="replace").replace("\x00", "").strip()
        if text and any(char.isalnum() for char in text):
            values.append(text)
        cursor = end
    return [value for value in values if value.lower().rstrip(".") not in _SCORE_ANNOTATION_FONTS]


def _decode_tab_heading(chunk: bytes) -> FT3TextRecord | None:
    headings = _tab_heading_texts(chunk)
    if not headings:
        return None
    return FT3TextRecord(
        melody_grid=None,
        lyrics=[],
        melody_events=[],
        lyric_event_rows=[],
        editorial_text=headings,
        structured_rows=[],
        parse_mode="structured",
    )


def _classify_unknown_score_chunk(
    chunk: bytes,
    bar: Bar,
    *,
    text_record_cache: dict[bytes, FT3TextRecord] | None = None,
) -> str | None:
    note_group_count = ft3_note_record_group_count(chunk)
    if note_group_count and (not _is_tab_bar(bar) or note_group_count >= _FT3_SCORE_MIN_NOTE_GROUPS):
        return _decoded_note_record_kind(chunk, text_record_cache=text_record_cache)
    if score_kind := _score_record_kind(chunk, text_record_cache=text_record_cache):
        if (
            _is_embedded_score_text_record(chunk)
            and bar.chords
            and all(note.ft3_extra_residual is None for note in bar.notes)
        ):
            return None
        return score_kind
    if bar.chords or bar.notes:
        return None
    if _has_structural_score_marker(bar):
        return "barline-raw"
    payload_kind = _classify_score_payload(chunk) if len(chunk) > _FT3_SCORE_HEADER_SIZE else None
    return "text-score-raw" if payload_kind == "unknown" and _plain_score_annotations(chunk) else payload_kind


def _decode_raw_text_record(
    raw_kind: str,
    chunk: bytes,
    *,
    text_record_cache: dict[bytes, FT3TextRecord] | None,
) -> tuple[FT3TextRecord, bytes]:
    payload = chunk[_FT3_SCORE_HEADER_SIZE:] if len(chunk) > _FT3_SCORE_HEADER_SIZE else chunk
    normalized_chunk = bytes(_FT3_SCORE_HEADER_SIZE) + payload
    record = _parse_score_text_record(normalized_chunk, text_record_cache=text_record_cache)
    raw_text_kinds = {"barline-raw", "note-lyric-raw", "text-score-raw"}
    if raw_kind in raw_text_kinds and record.parse_mode != "structured":
        record = refine_ft3_raw_text_record(record, normalized_chunk)
    return record, payload


def _prefer_decoded_note_events(
    record: FT3TextRecord,
    raw_kind: str,
    chunk: bytes,
    payload: bytes,
    *,
    voice_index: int | None,
) -> FT3TextRecord:
    note_events = decode_ft3_note_record(chunk, voice=voice_index)
    legacy_events = decode_ft3_vocal_events(payload)
    preferred_events = legacy_events if len(legacy_events) > len(note_events) else note_events
    if preferred_events:
        return replace(record, melody_events=preferred_events)
    if raw_kind in {"barline-raw", "note-staff-raw", "note-lyric-raw"}:
        return _demote_heuristic_melody(record)
    return record


def _fallback_vocal_record(payload: bytes) -> FT3TextRecord | None:
    melody_events = decode_ft3_vocal_events(payload)
    if not melody_events:
        return None
    return FT3TextRecord(
        melody_grid=None,
        lyrics=[],
        melody_events=melody_events,
        lyric_event_rows=[],
        editorial_text=[],
        structured_rows=[],
        parse_mode="structured",
    )


def _decode_raw_score_record(
    raw_kind: str,
    chunk: bytes,
    *,
    voice_index: int | None = None,
    text_record_cache: dict[bytes, FT3TextRecord] | None = None,
) -> FT3TextRecord | None:
    if raw_kind == "annotation-group-raw":
        return decode_ft3_annotation_group(chunk)
    if raw_kind == "text-score-raw" and (heading := _decode_tab_heading(chunk)) is not None:
        return heading
    if raw_kind not in {"barline-raw", "note-staff-raw", "note-lyric-raw", "text-score-raw"}:
        return None
    record, payload = _decode_raw_text_record(
        raw_kind,
        chunk,
        text_record_cache=text_record_cache,
    )
    record = _prefer_decoded_note_events(
        record,
        raw_kind,
        chunk,
        payload,
        voice_index=voice_index,
    )
    if record and _record_has_content(record):
        return record
    return _fallback_vocal_record(payload)


def _demote_heuristic_melody(record: FT3TextRecord) -> FT3TextRecord:
    rows = list(record.structured_rows)
    if record.melody_grid:
        rows.append(
            ImportedTextRow(
                row_index=len(rows),
                kind="control",
                text=record.melody_grid,
                tokens=record.melody_grid.split(),
            ),
        )
    return replace(record, melody_grid=None, melody_events=[], structured_rows=rows)


