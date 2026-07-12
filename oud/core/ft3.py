from __future__ import annotations

import gzip
import re
from dataclasses import dataclass, replace
from pathlib import Path
from statistics import median

from oud.core.ft3_extras import decode_ft3_extras
from oud.core.ft3_text import (
    FT3TextRecord,
    decode_ft3_annotation_group,
    decode_ft3_vocal_events,
    is_ft3_text_record,
    parse_ft3_text_record,
    refine_ft3_raw_text_record,
)
from oud.petrucci.key_signature import key_signature_accidentals
from oud.petrucci.model import (
    Bar,
    Chord,
    ImportedBarContent,
    ImportedScore,
    ImportedSourceRecord,
    ImportedStaff,
    ImportedTextRow,
    LyricEvent,
    MelodyEvent,
    Note,
    Piece,
)


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


@dataclass(frozen=True)
class _ImportedScoreChunk:
    bar_index: int
    staff_index: int
    raw_size: int
    record_kind: str
    chunk: bytes


_SOURCE_RECORD_KINDS = {
    "annotation-group-raw": "annotation-group",
    "barline-raw": "barline",
    "comment-rtf-raw": "comment",
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


def _map_body_with_tab(entries: list[_BodyEntry]) -> tuple[list[_BodyEntry], list[_MappedScoreEntry]]:
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
                and (decoded := _decode_raw_score_record(raw_entry.score_kind, raw_entry.chunk))
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


def _map_score_only_body(
    entries: list[_BodyEntry],
    annotations: dict[str, str],
) -> tuple[int, list[_MappedScoreEntry], list[str]] | None:
    if not entries or any(entry.kind != "raw" for entry in entries):
        return None
    labels = list(reversed(_ensemble_staff_labels(annotations)))
    if not labels or len(entries) % len(labels):
        return None
    bar_count = len(entries) // len(labels)
    mapped = [_MappedScoreEntry(index % bar_count, index // bar_count, entry) for index, entry in enumerate(entries)]
    return bar_count, mapped, labels


def _strip_rtf(text: str) -> str:
    if "\\rtf" not in text:
        return text.strip()
    cleaned = re.sub(r"{\\fonttbl.*?}", " ", text, flags=re.S)
    cleaned = re.sub(r"{\\colortbl.*?}", " ", cleaned, flags=re.S)
    cleaned = re.sub(r"\\'[0-9a-fA-F]{2}", "", cleaned)
    cleaned = re.sub(r"\\[a-zA-Z]+-?\d* ?", "", cleaned)
    cleaned = re.sub(r"\\[{}]", "", cleaned)
    cleaned = cleaned.replace("{", " ").replace("}", " ")
    cleaned = re.sub(r"[\x00-\x1f]+", " ", cleaned)
    cleaned = cleaned.replace("~", " ")
    cleaned = re.sub(r"\\+", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def _embedded_rtf_blocks(data: bytes) -> list[str]:
    blocks: list[str] = []
    index = 0
    while True:
        start = data.find(b"{\\rtf", index)
        if start < 0:
            return blocks
        end = _find_matching_brace(data, start, len(data))
        if end is None:
            return blocks
        text = _strip_rtf(data[start : end + 1].decode("latin1", errors="ignore"))
        if text:
            blocks.append(text)
        index = end + 1


def _embedded_plain_text(data: bytes) -> list[str]:
    texts: list[str] = []
    scan_data = bytearray(data)
    rtf_index = 0
    while True:
        start = data.find(b"{\\rtf", rtf_index)
        if start < 0:
            break
        end = _find_matching_brace(data, start, len(data))
        if end is None:
            break
        scan_data[start : end + 1] = bytes(end + 1 - start)
        rtf_index = end + 1
    index = 32
    while index < len(scan_data):
        size = scan_data[index]
        end = index + 1 + size
        if 8 <= size <= 160 and end <= len(scan_data):
            raw = scan_data[index + 1 : end]
            if all(32 <= value <= 126 for value in raw):
                text = raw.decode("latin1").strip()
                alpha = sum(char.isalpha() for char in text)
                if alpha >= 4 and "\\rtf" not in text and text not in texts:
                    texts.append(text)
                index = end
                continue
        index += 1
    return texts


def read_ft3(path: str) -> bytes:
    with Path(path).open("rb") as f:
        magic = f.read(2)
        f.seek(0)

        if magic == b"\x1f\x8b":
            with gzip.open(path, "rb") as gz:
                return gz.read()

        return f.read()


def extract_text(data: bytes, marker: bytes) -> tuple[str | None, int | None]:
    pos = data.find(marker)
    if pos == -1:
        return None, None
    pos += len(marker)
    if marker == b"CPiece":
        start = data.find(b"{\\rtf", pos)
        if start != -1:
            end = data.find(b"}\r\n~", start)
            if end != -1:
                raw = data[start : end + 1]
                text = raw.decode("utf-8", errors="ignore")
                return text, end + 1
        if pos + 4 <= len(data):
            length = int.from_bytes(data[pos : pos + 4], "little")
            if 0 < length <= len(data) - (pos + 4):
                raw = data[pos + 4 : pos + 4 + length]
                start = raw.find(b"{")
                if start != -1:
                    raw = raw[start:]
                text = raw.decode("utf-8", errors="ignore")
                return text, pos + 4 + length
    length = data[pos]
    text = data[pos + 1 : pos + 1 + length].decode("utf-8", errors="ignore")
    return text, pos + 1 + length


def _find_matching_brace(data: bytes, start: int, stop: int) -> int | None:
    depth = 0
    idx = start
    while idx < stop:
        byte = data[idx]
        if byte == ord("{"):
            depth += 1
        elif byte == ord("}"):
            depth -= 1
            if depth == 0:
                return idx
        idx += 1
    return None


def _extract_cpiece_blocks(data: bytes) -> tuple[list[str], str]:
    cpiece = data.find(b"CPiece")
    if cpiece == -1:
        return [], ""
    cbar = data.find(b"CBar", cpiece + 6)
    stop = cbar if cbar != -1 else min(len(data), cpiece + 8192)
    blocks: list[str] = []
    index = cpiece + 6
    while True:
        start = data.find(b"{\\rtf", index, stop)
        if start == -1:
            break
        end = _find_matching_brace(data, start, stop)
        if end is None:
            break
        block = data[start : end + 1].decode("utf-8", errors="ignore")
        blocks.append(_strip_rtf(block))
        index = end + 1
    metadata_blob = ""
    if index < stop:
        raw = data[index:stop]
        metadata_blob = raw.decode("latin1", errors="ignore")
    return blocks, metadata_blob


def _extract_ft3_preamble_notes(data: bytes) -> list[str]:
    cpiece = data.find(b"CPiece")
    if cpiece <= 0:
        return []
    preamble = data[:cpiece]
    printable = "".join(chr(byte) if 32 <= byte <= 126 else " " for byte in preamble)
    printable = re.sub(r"\s+", " ", printable)
    pattern = re.compile(
        r"([A-Z][A-Za-z][A-Za-z0-9 ,.'()/-]{8,}?"
        r"Encoded and edited by [A-Z][A-Za-z .'-]{1,80}\.)",
    )
    matches = [match.group(1).strip() for match in pattern.finditer(printable)]
    deduped: list[str] = []
    seen: set[str] = set()
    for text in matches:
        cleaned = re.sub(r"^[^A-Za-z]+", "", text).strip()
        cleaned = re.sub(r"\s+", " ", cleaned)
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        deduped.append(cleaned)
    return deduped


def _parse_section_annotations(text: str) -> dict[str, str]:
    annotations: dict[str, str] = {}
    for raw_line in text.replace("\x00", "\n").splitlines():
        line = re.sub(r"[\x00-\x1f]+", " ", raw_line).strip()
        if not line:
            continue
        line = re.sub(r"^[^A-Za-z]+", "", line)
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = re.sub(r"\s+", " ", key.strip().lower())
        value = value.strip()
        if not key or not value:
            continue
        annotations[key] = value
    return annotations


def _annotation_lookup(annotations: dict[str, str], name: str) -> str | None:
    name_l = name.strip().lower()
    if name_l in annotations:
        return annotations[name_l]
    short = name_l[:3]
    for key, value in annotations.items():
        if key[:3] == short:
            return value
        if key.endswith(name_l):
            return value
        if key.endswith(short):
            return value
    return None


def _parse_footnote_parts(footnote: str | None) -> tuple[str | None, str | None, str | None]:
    if not footnote:
        return None, None, None
    parts = [part.strip() for part in re.split(r"\s{2,}", footnote.strip(), maxsplit=2)]
    source = parts[0] if len(parts) >= 1 and parts[0] else None
    editor = parts[1] if len(parts) >= 2 and parts[1] else None
    comment = parts[2] if len(parts) >= 3 and parts[2] else None
    return source, editor, comment


def _canonicalize_metadata_fields(annotations: dict[str, str]) -> dict[str, str]:
    normalized = dict(annotations)
    con_value = _annotation_lookup(annotations, "con")
    source_value = _annotation_lookup(annotations, "source")
    if con_value:
        if source_value:
            if con_value not in source_value:
                normalized["source"] = f"{source_value} {con_value}".strip()
        else:
            normalized["source"] = con_value
    return normalized


def _apply_annotations(piece: Piece, annotations: dict[str, str]) -> None:
    normalized = _canonicalize_metadata_fields(annotations)
    key_value = _annotation_lookup(annotations, "key")
    type_value = _annotation_lookup(annotations, "type")
    style_value = _annotation_lookup(annotations, "style")
    tuning_value = _annotation_lookup(annotations, "tuning")
    difficulty_value = _annotation_lookup(annotations, "difficulty")
    ensemble_value = _annotation_lookup(annotations, "ensemble")
    instrumentation_value = _annotation_lookup(annotations, "instrumentation")
    part_value = _annotation_lookup(annotations, "part")
    source_value = _annotation_lookup(normalized, "source")
    editor_value = _annotation_lookup(annotations, "editor")
    comment_value = _annotation_lookup(annotations, "comment")
    publisher_value = _annotation_lookup(annotations, "publisher/library") or _annotation_lookup(annotations, "library")
    volume_value = _annotation_lookup(annotations, "volume")
    page_value = _annotation_lookup(annotations, "page")
    piece_value = _annotation_lookup(annotations, "piece")
    subtitle_value = _annotation_lookup(annotations, "subtitle")
    composer_value = _annotation_lookup(annotations, "composer")
    arranger_value = _annotation_lookup(annotations, "arranger")
    author_value = _annotation_lookup(annotations, "author")
    footnote_value = _annotation_lookup(annotations, "footnote")

    if piece_value:
        piece.title = piece_value
    if subtitle_value:
        piece.subtitle = subtitle_value
    if composer_value:
        piece.composer = composer_value
    if arranger_value:
        piece.arranger = arranger_value
    if author_value:
        piece.author = author_value
    if footnote_value:
        piece.footnote = footnote_value

    piece.key = key_value
    piece.piece_type = type_value
    piece.style = style_value
    piece.tuning = tuning_value
    piece.difficulty = difficulty_value
    piece.ensemble = ensemble_value
    piece.instrumentation = instrumentation_value
    piece.part = part_value
    piece.source = source_value
    piece.editor = editor_value
    piece.comment = comment_value
    piece.publisher = publisher_value
    piece.volume = volume_value
    piece.page = page_value
    piece.section_annotations = annotations
    piece.raw_metadata = annotations


def _apply_preamble_notes(piece: Piece, notes: list[str]) -> None:
    if not notes:
        return
    piece.notes = list(notes)
    primary = notes[0]
    match = re.match(
        r"(?P<source>.+?),\s*f\.\s*(?P<page>[A-Za-z0-9]+)\.\s*"
        r"Encoded and edited by (?P<editor>.+?)\.$",
        primary,
    )
    if match is None:
        return
    if piece.source is None:
        piece.source = match.group("source").strip()
    if piece.page is None:
        piece.page = match.group("page").strip()
    if piece.editor is None:
        piece.editor = match.group("editor").strip()


def at_next_note(s: int, f: int) -> bool:
    on_fret = 0x30 <= f <= 0x3E
    # French tab frets are letter-coded across a wider alphabet range, not just a..f.
    on_diapason = 0x61 <= f <= 0x7A
    on_string = 0x02 <= s <= 0x08
    return on_string and (on_fret or on_diapason)


def _decode_ft3_note_position(
    string_byte: int,
    fret_byte: int,
    note_flag: int,
) -> tuple[int, int] | None:
    if string_byte < 8:
        fret = fret_byte - 0x61 if 0x61 <= fret_byte <= 0x7A else fret_byte - 0x30
        return string_byte - 1, fret

    if string_byte != 0x08:
        return None

    if note_flag == 0x00 and 0x61 <= fret_byte <= 0x7A:
        return 7, fret_byte - 0x61
    if (note_flag & 0x20) and 0x30 <= fret_byte <= 0x39:
        return fret_byte - 0x30 + 7, 0
    if (note_flag & 0x48) == 0x48 and 0x61 <= fret_byte <= 0x7A:
        return 8, fret_byte - 0x61
    return None


_STANDARD_STAFF_MARKERS = {bytes((0x01, row)) for row in range(0x31, 0x36)}
_DYNAMIC_TEXT = {"ppp", "pp", "p", "mp", "mf", "f", "ff", "fff"}


def _is_standard_staff_record(data: bytes) -> bool:
    return len(data) >= 32 and data[30:32] in _STANDARD_STAFF_MARKERS


def _is_embedded_score_text_record(data: bytes) -> bool:
    if len(data) < 32 or data[30:32] != b"\x90\x01":
        return False
    alpha = sum((0x41 <= value <= 0x5A) or (0x61 <= value <= 0x7A) for value in data[32:])
    return is_ft3_text_record(data) or alpha >= 24


def _leading_tab_text_object(data: bytes) -> tuple[str, int] | None:
    if len(data) < 44 or data[30:32] != b"\x00\x00" or data[32:36] != b"\x01\x00\x00\x00":
        return None
    text_size = data[41]
    end = 44 + text_size
    if end > len(data):
        return None
    text = data[42 : 42 + text_size].decode("latin1", errors="replace").strip()
    return text, end


def _prepare_tab_body(data: bytes, bar: Bar) -> tuple[int, int] | None:
    if _is_standard_staff_record(data) or _is_embedded_score_text_record(data):
        return None
    object_count = int.from_bytes(data[28:30], "little") + 1 if len(data) >= 30 else 0
    if object_count > 128:
        return None
    ptr = 32
    text_object = _leading_tab_text_object(data)
    if text_object is None:
        return ptr, object_count
    text, ptr = text_object
    lowered = text.lower().rstrip(".")
    if lowered in _DYNAMIC_TEXT:
        bar.dynamic = lowered
    elif text and any(char.isalnum() for char in text):
        bar.editorial_text.append(text)
    return ptr, max(0, object_count - 1)


def _grid_kind(flags: int) -> str | None:
    if flags & 0x02:
        return "start"
    if flags & 0x04:
        return "mid"
    if flags & 0x08:
        return "end"
    return None


def _append_ft3_note(bar: Bar, chord: Chord, data: bytes, ptr: int) -> None:
    decoded_position = _decode_ft3_note_position(data[ptr], data[ptr + 1], data[ptr + 4])
    if decoded_position is None:
        return
    string, fret = decoded_position
    extras = (data[ptr + 3] << 8) | data[ptr + 2]
    decoded = decode_ft3_extras(extras)
    note = Note(
        string=string,
        fret=fret,
        raw_pos=ptr,
        barre=decoded.barre,
        right_fingering=decoded.right_fingering,
        left_fingering=decoded.left_fingering,
        right_ornament=decoded.right_ornament,
        left_ornament=decoded.left_ornament,
        arpeggio=decoded.arpeggio,
        ft3_extras=extras if extras else None,
        ft3_extra_residual=decoded.residual,
    )
    bar.notes.append(note)
    chord.notes.append(note)


def _parse_tab_chords(bar_data: bytes, bar: Bar, ptr: int, object_count: int) -> None:

    while ptr + 9 <= len(bar_data):
        if len(bar.chords) >= object_count:
            break
        if not at_next_note(bar_data[ptr + 4], bar_data[ptr + 5]):
            ptr += 1
            continue

        note_type = bar_data[ptr] + 2
        if note_type_to_denominator(note_type) is None:
            # Ignore false-positive chord headers found while scanning body bytes.
            # Valid FT3 rhythmic note types map to known denominators.
            ptr += 1
            continue
        flags = bar_data[ptr + 1]
        chord = Chord(note_type=note_type, dotted=bool(flags & 0x10), grid=_grid_kind(flags))
        item_count = int.from_bytes(bar_data[ptr - 2 : ptr], "little") if ptr >= 2 else 0
        # Minimal hand-built fixtures predate the decoded item-count field.
        note_count = max(0, item_count - 1) if item_count else 128
        ptr += 4

        while note_count and ptr + 5 <= len(bar_data) and at_next_note(bar_data[ptr], bar_data[ptr + 1]):
            _append_ft3_note(bar, chord, bar_data, ptr)
            ptr += 5
            note_count -= 1

        if chord.notes:
            bar.chords.append(chord)


def parse_bar(bar_data: bytes) -> Bar:
    bar = Bar()
    bar.time_sig = parse_time_signature(bar_data)
    _parse_bar_markers(bar_data, bar)
    body_plan = _prepare_tab_body(bar_data, bar)
    if body_plan is not None:
        _parse_tab_chords(bar_data, bar, *body_plan)
        for text in _embedded_plain_text(bar_data):
            if text not in bar.editorial_text:
                bar.editorial_text.append(text)
    return bar


def _apply_embedded_sections(chunks: list[bytes], bars: list[Bar]) -> None:
    for index, chunk in enumerate(chunks[:-1]):
        titles = _embedded_rtf_blocks(chunk)
        if not titles:
            continue
        bars[index].system_break = True
        target = bars[index + 1]
        target.page_break_before = True
        target.section_title = titles[0]
        target.section_subtitle = titles[1] if len(titles) > 1 else None


def _parse_bar_markers(bar_data: bytes, bar: Bar) -> None:
    if len(bar_data) < 2:
        return
    b0 = bar_data[0]
    b1 = bar_data[1]

    # Corpus-based FT3 header hints (conservative):
    # - byte1 bit 0x10 marks left repeat dots
    # - byte0 upper-nibble bit 0x10 marks right repeat dots
    # - byte0 bit 0x80 and/or byte1 bit 0x01 mark an explicit closing/double barline
    # - byte1 bit 0x02 appears on a few bars alongside explicit closers and likely
    #   indicates right repeat dots; decode it as such only for structural repeat marks.
    left_repeat = bool(b1 & 0x10)
    right_repeat = bool((b0 & 0x10) or (b1 & 0x02))

    if left_repeat and right_repeat:
        bar.repeat = ":|:"
    elif left_repeat:
        bar.repeat = ".:"
    elif right_repeat:
        bar.repeat = ":."

    bar.ending_numbers = tuple(number for bit, number in ((0x20, 1), (0x40, 2)) if b0 & bit)

    if (b0 & 0x80) or (b1 & 0x01):
        bar.barline = "||"


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
    return [
        MelodyEvent(
            text=event.text,
            onset_index=event.onset_index + offset,
            src_pos=event.src_pos,
            note_type=event.note_type,
            dotted=event.dotted,
            accidental_flags=event.accidental_flags,
            is_rest=event.is_rest,
            beam=event.beam,
            fermata=event.fermata,
        )
        for event in events
    ]


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
    return not (len(words) == 1 and len(words[0]) == 1 and words[0].lower() not in {"i", "a", "o"})


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


def _score_record_kind(chunk: bytes) -> str | None:
    if _is_standard_staff_record(chunk):
        decoded = parse_ft3_text_record(chunk)
        return "note-lyric-raw" if decoded.lyrics or decoded.lyric_event_rows else "note-staff-raw"
    if _is_embedded_score_text_record(chunk):
        decoded = parse_ft3_text_record(chunk)
        return "note-lyric-raw" if decoded.lyrics or decoded.lyric_event_rows else "text-score-raw"
    return None


def _has_structural_score_marker(bar: Bar) -> bool:
    return bool(bar.time_sig or bar.barline or bar.repeat or bar.ending_numbers)


def _classify_score_payload(chunk: bytes) -> str | None:
    payload = chunk[32:]
    note_staff_markers = tuple(bytes((0x01, row)) for row in range(0x31, 0x36))
    marker_region = chunk[28:]
    has_note_staff_markers = any(marker in marker_region for marker in note_staff_markers)
    is_score_settings = chunk[2:7] == b"\x00\x11\x00\x00\xff" and b"\r\n" not in payload
    if is_score_settings and not has_note_staff_markers:
        return "score-settings-raw"
    object_index = int.from_bytes(chunk[28:30], "little") if len(chunk) >= 30 else 0
    if object_index > 128 and chunk[30:32] == b"\x02\x00":
        return "annotation-group-raw"
    nonzero = sum(1 for value in payload if value)
    controls = sum(1 for value in payload if 0 < value < 32 and value not in (9, 10, 13))
    if nonzero < 12 and controls < 4:
        return None
    if b"{\\rtf" in payload or b"\\fonttbl" in payload:
        return "comment-rtf-raw"
    has_text = b"\r\n" in payload and any((0x41 <= value <= 0x5A) or (0x61 <= value <= 0x7A) for value in payload)
    if has_note_staff_markers:
        return "note-lyric-raw" if has_text else "note-staff-raw"
    return "text-score-raw" if has_text else "unknown"


def _classify_unknown_score_chunk(chunk: bytes, bar: Bar) -> str | None:
    if score_kind := _score_record_kind(chunk):
        return score_kind
    if _has_structural_score_marker(bar):
        return "barline-raw"
    if bar.chords or bar.notes:
        return None
    return _classify_score_payload(chunk) if len(chunk) > 32 else None


def _decode_raw_score_record(raw_kind: str, chunk: bytes) -> FT3TextRecord | None:
    if raw_kind == "annotation-group-raw":
        return decode_ft3_annotation_group(chunk)
    if raw_kind not in {"barline-raw", "note-staff-raw", "note-lyric-raw", "text-score-raw"}:
        return None
    payload = chunk[32:] if len(chunk) > 32 else chunk
    record = parse_ft3_text_record(bytes(32) + payload)
    if raw_kind in {"barline-raw", "note-lyric-raw", "text-score-raw"} and record.parse_mode != "structured":
        record = refine_ft3_raw_text_record(record, bytes(32) + payload)
    if record and _record_has_content(record):
        return record
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


def _imported_bar_base(bar_index: int, bar: Bar) -> ImportedBarContent:
    return ImportedBarContent(
        source_bar_index=bar_index,
        time_sig=bar.time_sig,
        barline=bar.barline,
        repeat=bar.repeat,
        ending_numbers=bar.ending_numbers,
        system_break=bar.system_break,
        dynamic=bar.dynamic,
        fermata=bar.fermata,
    )


def _import_decoded_bar_text_layers(
    *,
    note_staff: ImportedStaff,
    lyric_staff: ImportedStaff,
    comment_staff: ImportedStaff,
    bar_index: int,
    bar: Bar,
) -> None:
    base = _imported_bar_base(bar_index, bar)
    if bar.melody_grid or bar.melody_events:
        note_staff.bars.append(
            replace(
                base,
                melody_grid=bar.melody_grid,
                melody_events=list(bar.melody_events),
                text_rows=[row for row in bar.structured_text_rows if row.kind == "vocal"],
            ),
        )
    if bar.lyrics or bar.lyric_event_rows:
        lyric_staff.bars.append(
            replace(
                base,
                lyrics=list(bar.lyrics),
                lyric_event_rows=[list(row) for row in bar.lyric_event_rows],
                text_rows=[row for row in bar.structured_text_rows if row.kind == "lyrics"],
            ),
        )
    editorial_text_rows = [row for row in bar.structured_text_rows if row.kind == "editorial"]
    unknown_text_rows = [row for row in bar.structured_text_rows if row.kind == "unknown"]
    meta_text_rows = [row for row in bar.structured_text_rows if row.kind in {"font", "control"}]
    if bar.editorial_text or unknown_text_rows:
        comment_staff.bars.append(
            replace(
                base,
                editorial_text=list(bar.editorial_text) + [row.text for row in unknown_text_rows if row.text],
                text_rows=editorial_text_rows + unknown_text_rows + meta_text_rows,
            ),
        )


def _decoded_comment_content(decoded: FT3TextRecord | None) -> tuple[list[str], list[ImportedTextRow]] | None:
    if decoded is None:
        return None
    text_rows = [row for row in decoded.structured_rows if row.kind in {"editorial", "unknown"}]
    meta_rows = [row for row in decoded.structured_rows if row.kind in {"font", "control"}]
    if decoded.editorial_text or text_rows or meta_rows:
        editorial = list(decoded.editorial_text) + [row.text for row in text_rows if row.text]
        return editorial, text_rows + meta_rows
    return None


def _decoded_note_content(
    base: ImportedBarContent,
    decoded: FT3TextRecord | None,
) -> ImportedBarContent:
    events = list(decoded.melody_events) if decoded is not None else []
    event_bar = Bar(time_sig=base.time_sig, melody_events=events)
    _finalize_explicit_vocal_melody(event_bar)
    return replace(
        base,
        melody_grid=decoded.melody_grid if decoded is not None else None,
        melody_events=event_bar.melody_events,
        text_rows=[row for row in decoded.structured_rows if row.kind == "vocal"] if decoded is not None else [],
        fermata=base.fermata or any(event.fermata for event in event_bar.melody_events),
    )


def _append_raw_imported_bar(
    *,
    note_staff: ImportedStaff,
    lyric_staff: ImportedStaff,
    comment_staff: ImportedStaff,
    barline_staff: ImportedStaff,
    layout_staff: ImportedStaff,
    unknown_staff: ImportedStaff,
    bar_index: int,
    raw_kind: str,
    source_bar: Bar,
    decoded: FT3TextRecord | None,
) -> None:
    base = _imported_bar_base(bar_index, source_bar)
    if raw_kind == "score-settings-raw":
        layout_staff.bars.append(base)
        return
    if raw_kind == "barline-raw":
        barline_staff.bars.append(base)
    if raw_kind in {"note-staff-raw", "note-lyric-raw"} or (decoded is not None and decoded.melody_events):
        note_staff.bars.append(_decoded_note_content(base, decoded))
    if (
        raw_kind in {"barline-raw", "note-lyric-raw", "text-score-raw"}
        and decoded is not None
        and (decoded.lyrics or decoded.lyric_event_rows)
    ):
        lyric_staff.bars.append(
            replace(
                base,
                lyrics=list(decoded.lyrics),
                lyric_event_rows=[list(row) for row in decoded.lyric_event_rows],
                text_rows=[row for row in decoded.structured_rows if row.kind == "lyrics"],
            ),
        )
    if comment_content := _decoded_comment_content(decoded):
        editorial_text, text_rows = comment_content
        comment_staff.bars.append(
            replace(
                base,
                editorial_text=editorial_text,
                text_rows=text_rows,
            ),
        )
        if raw_kind == "annotation-group-raw":
            return
    if raw_kind in {"comment-rtf-raw", "annotation-group-raw"} or (raw_kind == "text-score-raw" and decoded is None):
        comment_staff.bars.append(base)
        return
    raw_text_kinds = {"barline-raw", "note-staff-raw", "note-lyric-raw", "text-score-raw"}
    if raw_kind in {"note-staff-raw", "note-lyric-raw"} or (decoded is not None and raw_kind in raw_text_kinds):
        return
    unknown_staff.bars.append(base)


def _build_imported_score(
    piece: Piece,
    *,
    imported_chunks: list[_ImportedScoreChunk],
    staff_labels: list[str],
) -> ImportedScore | None:
    note_staffs: dict[int, ImportedStaff] = {}
    lyric_staffs: dict[int, ImportedStaff] = {}
    comment_staff = ImportedStaff(kind="comment")
    barline_staff = ImportedStaff(kind="barline")
    layout_staff = ImportedStaff(kind="layout")
    unknown_staff = ImportedStaff(kind="unknown")

    if not imported_chunks:
        note_staffs[0] = ImportedStaff(kind="note")
        lyric_staffs[0] = ImportedStaff(kind="lyrics")
        for bar_index, bar in enumerate(piece.bars):
            _import_decoded_bar_text_layers(
                note_staff=note_staffs[0],
                lyric_staff=lyric_staffs[0],
                comment_staff=comment_staff,
                bar_index=bar_index,
                bar=bar,
            )

    for imported in imported_chunks:
        label = staff_labels[imported.staff_index] if imported.staff_index < len(staff_labels) else None
        note_staff = note_staffs.setdefault(imported.staff_index, ImportedStaff(kind="note", label=label))
        lyric_staff = lyric_staffs.setdefault(imported.staff_index, ImportedStaff(kind="lyrics", label=label))
        source_bar = piece.bars[imported.bar_index] if 0 <= imported.bar_index < len(piece.bars) else Bar()
        decoded = _decode_raw_score_record(imported.record_kind, imported.chunk)
        _append_raw_imported_bar(
            note_staff=note_staff,
            lyric_staff=lyric_staff,
            comment_staff=comment_staff,
            barline_staff=barline_staff,
            layout_staff=layout_staff,
            unknown_staff=unknown_staff,
            bar_index=imported.bar_index,
            raw_kind=imported.record_kind,
            source_bar=source_bar,
            decoded=decoded,
        )
    ordered = [*note_staffs.values(), *lyric_staffs.values()]
    ordered.extend((comment_staff, barline_staff, layout_staff, unknown_staff))
    staffs = [staff for staff in ordered if staff.bars]
    if not staffs:
        return None
    source_records = [
        ImportedSourceRecord(
            source_bar_index=imported.bar_index,
            source_staff_index=imported.staff_index,
            kind=_SOURCE_RECORD_KINDS.get(imported.record_kind, imported.record_kind),
            size=imported.raw_size,
        )
        for imported in imported_chunks
    ]
    return ImportedScore(source_format="ft3", staffs=staffs, source_records=source_records)


def load_ft3(path: str) -> Piece:  # noqa: C901, PLR0912
    data = read_ft3(path)

    blocks, metadata_blob = _extract_cpiece_blocks(data)
    preamble_notes = _extract_ft3_preamble_notes(data)
    title = blocks[0] if len(blocks) >= 1 else None
    subtitle = blocks[1] if len(blocks) >= 2 else None
    composer = blocks[2] if len(blocks) >= 3 else None
    footnote = blocks[3] if len(blocks) >= 4 else None
    if not title:
        title, _pos = extract_text(data, b"CPiece")
        if title:
            title = _strip_rtf(title)
    if not title:
        title = Path(path).stem.replace("_", " ")
    author = None
    annotations = _parse_section_annotations(metadata_blob)

    raw_chunks = re.split(b"\x03\x80", data)
    parsed_text_records: list[FT3TextRecord] = []
    bar_chunks = raw_chunks
    bar_text_records: list[list[FT3TextRecord]] = []
    parsed_bars: list[Bar] = []
    imported_chunks: list[_ImportedScoreChunk] = []
    imported_staff_labels: list[str] = []
    parallel_meta_bars: list[tuple[int, Bar]] = []
    body_start = data.find(b"CBar")
    if body_start >= 0:
        body_chunks = re.split(b"\x03\x80", data[body_start + 4 :])
        body_entries: list[_BodyEntry] = []
        for chunk in body_chunks:
            parsed = parse_bar(chunk)
            raw_kind = _classify_unknown_score_chunk(chunk, parsed)
            kind = "other"
            if _is_tab_bar(parsed):
                kind = "tab"
            elif raw_kind is not None:
                kind = "raw"
            body_entries.append(_BodyEntry(kind, chunk, parsed, raw_kind))
        if any(entry.kind == "tab" for entry in body_entries):
            tab_entries, mapped_score_entries = _map_body_with_tab(body_entries)
            max_staff_index = max((mapped.staff_index for mapped in mapped_score_entries), default=-1)
            ensemble_labels = _ensemble_staff_labels(annotations)
            imported_staff_labels = list(reversed(ensemble_labels[-max_staff_index - 1 :]))
            bar_chunks = [entry.chunk for entry in tab_entries]
            bar_text_records = [[] for _ in tab_entries]
            for mapped in mapped_score_entries:
                target_index = mapped.bar_index
                chunk = mapped.entry.chunk
                parsed = mapped.entry.parsed
                raw_kind = mapped.entry.score_kind
                if raw_kind is None:
                    continue
                imported_chunks.append(
                    _ImportedScoreChunk(target_index, mapped.staff_index, len(chunk), raw_kind, chunk),
                )
                decoded = _decode_raw_score_record(raw_kind, chunk)
                if decoded is not None and _record_has_content(decoded):
                    parsed_text_records.append(decoded)
                    bar_text_records[target_index].append(decoded)
                if parsed.time_sig or parsed.barline or parsed.repeat or parsed.system_break:
                    parallel_meta_bars.append((target_index, parsed))
        elif score_plan := _map_score_only_body(body_entries, annotations):
            bar_count, mapped_score_entries, imported_staff_labels = score_plan
            parsed_bars = [Bar() for _ in range(bar_count)]
            bar_chunks = []
            bar_text_records = [[] for _ in range(bar_count)]
            for mapped in mapped_score_entries:
                raw_kind = mapped.entry.score_kind
                if raw_kind is None:
                    continue
                imported_chunks.append(
                    _ImportedScoreChunk(
                        mapped.bar_index,
                        mapped.staff_index,
                        len(mapped.entry.chunk),
                        raw_kind,
                        mapped.entry.chunk,
                    ),
                )
                decoded = _decode_raw_score_record(raw_kind, mapped.entry.chunk)
                if mapped.staff_index == 0 and decoded is not None and _record_has_content(decoded):
                    parsed_text_records.append(decoded)
                    bar_text_records[mapped.bar_index].append(decoded)
                if mapped.staff_index == 0 and _has_structural_score_marker(mapped.entry.parsed):
                    parallel_meta_bars.append((mapped.bar_index, mapped.entry.parsed))
        else:
            # Always parse bars from the CBar body stream so CPiece/metadata bytes
            # cannot pollute bar 1 (common in duet-score files).
            bar_chunks = []
            bar_text_records = []
            leading_records: list[FT3TextRecord] = []
            for entry in body_entries:
                chunk = entry.chunk
                if is_ft3_text_record(chunk):
                    record = parse_ft3_text_record(chunk)
                    if not _record_has_content(record):
                        continue
                    parsed_text_records.append(record)
                    if bar_chunks:
                        bar_text_records[-1].append(record)
                    else:
                        leading_records.append(record)
                    continue
                bar_chunks.append(chunk)
                attached: list[FT3TextRecord] = []
                if leading_records:
                    attached.append(leading_records.pop(0))
                bar_text_records.append(attached)
    for bar_index, chunk in enumerate(bar_chunks):
        bar = parse_bar(chunk)
        parsed_bars.append(bar)
        if not _is_tab_bar(bar) and (raw_kind := _classify_unknown_score_chunk(chunk, bar)):
            imported_chunks.append(_ImportedScoreChunk(bar_index, 0, len(chunk), raw_kind, chunk))
    if bar_chunks:
        _apply_embedded_sections(bar_chunks, parsed_bars)
    for bar_index, meta_bar in parallel_meta_bars:
        if 0 <= bar_index < len(parsed_bars):
            target = parsed_bars[bar_index]
            if target.time_sig is None:
                target.time_sig = meta_bar.time_sig
            if target.barline is None:
                target.barline = meta_bar.barline
            if target.repeat is None:
                target.repeat = meta_bar.repeat
            if not target.ending_numbers:
                target.ending_numbers = meta_bar.ending_numbers
            target.system_break = target.system_break or meta_bar.system_break
    bars = parsed_bars
    _apply_legacy_duration_fix(bars)
    _fill_missing_time_signatures(bars)
    max_string = 0
    for bar in bars:
        for note in bar.notes:
            max_string = max(max_string, note.string)
    strings = max(6, max_string) if max_string else 6
    piece = Piece(
        title=title,
        subtitle=subtitle,
        author=author,
        composer=composer,
        footnote=footnote,
        bars=bars,
        strings=strings,
    )
    if bar_text_records:
        for bar, records in zip(piece.bars, bar_text_records, strict=False):
            for record in records:
                _merge_text_record_into_bar(bar, record)
    piece.imported_score = _build_imported_score(
        piece,
        imported_chunks=imported_chunks,
        staff_labels=imported_staff_labels,
    )
    if piece.imported_score is not None and any(staff.kind == "unknown" for staff in piece.imported_score.staffs):
        piece.import_warnings.append(
            "FT3 contains non-tab score data that is not decoded yet; imported as unknown staves.",
        )
    _apply_annotations(piece, annotations)
    _apply_preamble_notes(piece, preamble_notes)
    for bar in piece.bars:
        _normalize_vocal_event_accidentals(
            bar,
            key=piece.key,
            raw_fallback=_bar_uses_raw_vocal_fallback(bar),
        )
    source, editor, comment = _parse_footnote_parts(piece.footnote)
    piece.footnote_source = source
    piece.footnote_editor = editor
    piece.footnote_comment = comment
    if piece.source is None:
        piece.source = source
    if piece.editor is None:
        piece.editor = editor
    if piece.comment is None:
        piece.comment = comment
    return piece


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
    return MelodyEvent(
        text=event.text,
        onset_index=event.onset_index,
        src_pos=event.src_pos,
        note_type=note_type,
        dotted=dotted,
        accidental_flags=event.accidental_flags,
        is_rest=event.is_rest,
        beam=event.beam,
        fermata=event.fermata,
    )


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


def _normalize_vocal_event_accidentals(
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
        normalized.append(
            MelodyEvent(
                text=f"{name}{accidental}{octave}",
                onset_index=event.onset_index,
                src_pos=event.src_pos,
                note_type=event.note_type,
                dotted=event.dotted,
                accidental_flags=event.accidental_flags,
                is_rest=event.is_rest,
                beam=event.beam,
                fermata=event.fermata,
            ),
        )
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


def _fill_missing_time_signatures(bars: list[Bar]) -> None:
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
    time_signature = bar_data[0] & 0x7F
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
