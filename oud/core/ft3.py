from __future__ import annotations

import gzip
import re
from dataclasses import replace
from pathlib import Path
from statistics import median

from oud.core.ft3_extras import decode_ft3_extras
from oud.core.ft3_text import (
    FT3TextRecord,
    decode_ft3_vocal_events,
    is_ft3_text_record,
    parse_ft3_text_record,
)
from oud.core.model import (
    Bar,
    Chord,
    ImportedBarContent,
    ImportedScore,
    ImportedStaff,
    MelodyEvent,
    Note,
    Piece,
)


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
    difficulty_value = _annotation_lookup(annotations, "difficulty")
    ensemble_value = _annotation_lookup(annotations, "ensemble")
    instrumentation_value = _annotation_lookup(annotations, "instrumentation")
    part_value = _annotation_lookup(annotations, "part")
    source_value = _annotation_lookup(normalized, "source")
    editor_value = _annotation_lookup(annotations, "editor")
    comment_value = _annotation_lookup(annotations, "comment")
    publisher_value = _annotation_lookup(annotations, "publisher/library")
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


def at_next_note(s: int, f: int) -> bool:
    on_fret = 0x30 <= f <= 0x3E
    # French tab frets are letter-coded across a wider alphabet range, not just a..f.
    on_diapason = 0x61 <= f <= 0x7A
    on_string = 0x02 <= s <= 0x08
    return on_string and (on_fret or on_diapason)


def parse_bar(bar_data: bytes) -> Bar:  # noqa: PLR0912, C901
    bar = Bar()
    bar.time_sig = parse_time_signature(bar_data)
    _parse_bar_markers(bar_data, bar)
    ptr = 32

    while ptr + 9 <= len(bar_data):
        if not at_next_note(bar_data[ptr + 4], bar_data[ptr + 5]):
            ptr += 1
            continue

        note_type = bar_data[ptr] + 2
        if note_type_to_denominator(note_type) is None:
            # Ignore false-positive chord headers found while scanning body bytes.
            # Valid FT3 rhythmic note types map to known denominators.
            ptr += 1
            continue
        dotted = bool(bar_data[ptr + 1] & 0x10)
        grid = None
        if bar_data[ptr + 1] & 0x02:
            grid = "start"
        elif bar_data[ptr + 1] & 0x04:
            grid = "mid"
        elif bar_data[ptr + 1] & 0x08:
            grid = "end"
        chord = Chord(note_type=note_type, dotted=dotted, grid=grid)
        ptr += 4

        while ptr + 5 <= len(bar_data) and at_next_note(bar_data[ptr], bar_data[ptr + 1]):
            string = None
            fret = None

            if bar_data[ptr] < 8:
                string = bar_data[ptr] - 1
                fret_byte = bar_data[ptr + 1]
                fret = fret_byte - 0x61 if 0x61 <= fret_byte <= 0x7A else fret_byte - 0x30
            elif bar_data[ptr] == 8:
                flag = bar_data[ptr + 4]
                if flag == 0x00:
                    fret_byte = bar_data[ptr + 1]
                    if 0x61 <= fret_byte <= 0x7A:
                        string = 7
                        fret = fret_byte - 0x61
                elif flag & 0x20:
                    course_byte = bar_data[ptr + 1]
                    if 0x30 <= course_byte <= 0x39:
                        string = course_byte - 0x30 + 7
                        fret = 0
                elif flag & 0x48 == 0x48:
                    fret_byte = bar_data[ptr + 1]
                    if 0x61 <= fret_byte <= 0x7A:
                        string = 8
                        fret = fret_byte - 0x61

            if string is not None and fret is not None:
                extras = (bar_data[ptr + 3] << 8) | bar_data[ptr + 2]
                decoded = decode_ft3_extras(extras)
                note = Note(
                    string=string,
                    fret=fret,
                    raw_pos=ptr,
                    right_fingering=decoded.right_fingering,
                    left_fingering=decoded.left_fingering,
                    right_ornament=decoded.right_ornament,
                    left_ornament=decoded.left_ornament,
                    ft3_extras=extras if extras else None,
                    ft3_extra_residual=decoded.residual,
                )
                bar.notes.append(note)
                chord.notes.append(note)

            ptr += 5

        if chord.notes:
            bar.chords.append(chord)

    return bar


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

    if (b0 & 0x80) or (b1 & 0x01):
        bar.barline = "||"


def _ft3_text_import_warning(records: list[FT3TextRecord]) -> str | None:
    if not records:
        return None
    ascii_fallback = any(record.parse_mode == "ascii" for record in records)
    has_lyrics = any(record.lyric_event_rows or record.lyrics for record in records)
    has_melody = any(record.melody_events or record.melody_grid for record in records)
    has_editorial = any(record.editorial_text for record in records)
    if ascii_fallback:
        return "FT3 vocal text imported via raw fallback; lyric alignment may be approximate."
    if has_lyrics and not has_melody:
        return (
            "FT3 lyrics parsed from structured text records; "
            "melody lane is inferred from tablature."
        )
    if has_lyrics or has_melody:
        return (
            "FT3 vocal text parsed from structured records; "
            "some vocal details may still be omitted."
        )
    if has_editorial:
        return "FT3 editorial text parsed from structured records."
    return None


def _record_has_content(record: FT3TextRecord) -> bool:
    return bool(
        record.melody_grid
        or record.lyrics
        or record.melody_events
        or record.lyric_event_rows
        or record.editorial_text
        or record.structured_rows,
    )


def _merge_text_record_into_bar(bar: Bar, record: FT3TextRecord) -> None:
    if record.melody_grid:
        bar.melody_grid = record.melody_grid
    if record.melody_events:
        bar.melody_events = list(record.melody_events)
    if record.lyrics:
        bar.lyrics = list(record.lyrics)
    if record.lyric_event_rows:
        bar.lyric_event_rows = [list(row) for row in record.lyric_event_rows]
    if record.editorial_text:
        bar.editorial_text.extend(text for text in record.editorial_text if text)
    if record.structured_rows:
        bar.structured_text_rows.extend(record.structured_rows)
    _finalize_explicit_vocal_melody(bar)


def _classify_unknown_score_chunk(chunk: bytes, bar: Bar) -> str | None:
    if bar.chords or bar.notes:
        return None
    raw_kind: str | None = None
    if bar.time_sig or bar.barline or bar.repeat:
        raw_kind = "barline-raw"
    elif len(chunk) > 32:
        payload = chunk[32:]
        nonzero = sum(1 for b in payload if b)
        controls = sum(1 for b in payload if 0 < b < 32 and b not in (9, 10, 13))
        if nonzero >= 12 or controls >= 4:
            if b"{\\rtf" in payload or b"\\fonttbl" in payload:
                raw_kind = "comment-rtf-raw"
            else:
                note_staff_markers = (b"\x01\x32", b"\x01\x33", b"\x01\x34", b"\x01\x35")
                has_note_staff_markers = any(marker in payload for marker in note_staff_markers)
                has_text = b"\r\n" in payload and any(
                    (0x41 <= b <= 0x5A) or (0x61 <= b <= 0x7A) for b in payload
                )
                if has_note_staff_markers and has_text:
                    raw_kind = "note-lyric-raw"
                elif has_note_staff_markers:
                    raw_kind = "note-staff-raw"
                elif has_text:
                    raw_kind = "text-score-raw"
                else:
                    raw_kind = "unknown"
    return raw_kind


def _decode_raw_score_record(raw_kind: str, chunk: bytes) -> FT3TextRecord | None:
    if raw_kind not in {"note-staff-raw", "note-lyric-raw"}:
        return None
    payload = chunk[32:] if len(chunk) > 32 else chunk
    record = parse_ft3_text_record(bytes(32) + payload)
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
    )


def _import_decoded_bar_text_layers(
    *,
    note_staff: ImportedStaff,
    lyric_staff: ImportedStaff,
    comment_staff: ImportedStaff,
    unknown_staff: ImportedStaff,
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
    if bar.editorial_text:
        comment_staff.bars.append(
            replace(
                base,
                editorial_text=list(bar.editorial_text),
                text_rows=[row for row in bar.structured_text_rows if row.kind == "editorial"],
            ),
        )
    unknown_text_rows = [row for row in bar.structured_text_rows if row.kind == "unknown"]
    meta_text_rows = [row for row in bar.structured_text_rows if row.kind in {"font", "control"}]
    if unknown_text_rows:
        unknown_staff.bars.append(
            replace(base, text_rows=unknown_text_rows + meta_text_rows, raw_kind="structured-text"),
        )


def _append_raw_imported_bar(
    *,
    note_staff: ImportedStaff,
    lyric_staff: ImportedStaff,
    barline_staff: ImportedStaff,
    unknown_staff: ImportedStaff,
    bar_index: int,
    raw_size: int,
    raw_kind: str,
    source_bar: Bar,
    decoded: FT3TextRecord | None,
) -> None:
    base = _imported_bar_base(bar_index, source_bar)
    if raw_kind == "barline-raw":
        barline_staff.bars.append(replace(base, raw_kind=raw_kind, raw_size=raw_size))
        return
    if decoded is not None and decoded.melody_events:
        note_staff.bars.append(
            replace(
                base,
                melody_events=list(decoded.melody_events),
                text_rows=[row for row in decoded.structured_rows if row.kind == "vocal"],
                raw_kind=raw_kind,
                raw_size=raw_size,
            ),
        )
    if (
        raw_kind == "note-lyric-raw"
        and decoded is not None
        and (decoded.lyrics or decoded.lyric_event_rows)
    ):
        lyric_staff.bars.append(
            replace(
                base,
                lyrics=list(decoded.lyrics),
                lyric_event_rows=[list(row) for row in decoded.lyric_event_rows],
                text_rows=[row for row in decoded.structured_rows if row.kind == "lyrics"],
                raw_kind=raw_kind,
                raw_size=raw_size,
            ),
        )
        return
    if decoded is not None and raw_kind in {"note-staff-raw", "note-lyric-raw"}:
        return
    unknown_staff.bars.append(replace(base, raw_kind=raw_kind, raw_size=raw_size))


def _build_imported_score(
    piece: Piece,
    *,
    unknown_bar_chunks: list[tuple[int, int, str, bytes]],
) -> ImportedScore | None:
    note_staff = ImportedStaff(kind="note")
    lyric_staff = ImportedStaff(kind="lyrics")
    comment_staff = ImportedStaff(kind="comment")
    barline_staff = ImportedStaff(kind="barline")
    unknown_staff = ImportedStaff(kind="unknown")

    for bar_index, bar in enumerate(piece.bars):
        _import_decoded_bar_text_layers(
            note_staff=note_staff,
            lyric_staff=lyric_staff,
            comment_staff=comment_staff,
            unknown_staff=unknown_staff,
            bar_index=bar_index,
            bar=bar,
        )

    for bar_index, raw_size, raw_kind, chunk in unknown_bar_chunks:
        source_bar = piece.bars[bar_index] if 0 <= bar_index < len(piece.bars) else Bar()
        decoded = _decode_raw_score_record(raw_kind, chunk)
        _append_raw_imported_bar(
            note_staff=note_staff,
            lyric_staff=lyric_staff,
            barline_staff=barline_staff,
            unknown_staff=unknown_staff,
            bar_index=bar_index,
            raw_size=raw_size,
            raw_kind=raw_kind,
            source_bar=source_bar,
            decoded=decoded,
        )
    staffs = [
        staff
        for staff in (note_staff, lyric_staff, comment_staff, barline_staff, unknown_staff)
        if staff.bars
    ]
    if not staffs:
        return None
    return ImportedScore(source_format="ft3", staffs=staffs)


def load_ft3(path: str) -> Piece:  # noqa: C901, PLR0912
    data = read_ft3(path)

    blocks, metadata_blob = _extract_cpiece_blocks(data)
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

    raw_chunks = re.split(b"\x03\x80", data)
    parsed_text_records: list[FT3TextRecord] = []
    bar_chunks = raw_chunks
    bar_text_records: list[list[FT3TextRecord]] = []
    parsed_bars: list[Bar] = []
    unknown_bar_chunks: list[tuple[int, int, str, bytes]] = []
    body_start = data.find(b"CBar")
    if body_start >= 0:
        body_chunks = re.split(b"\x03\x80", data[body_start + 4 :])
        # Always parse bars from the CBar body stream so CPiece/metadata bytes
        # cannot pollute bar 1 (common in duet-score files).
        bar_chunks = []
        bar_text_records = []
        leading_records: list[FT3TextRecord] = []
        for chunk in body_chunks:
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
        if raw_kind := _classify_unknown_score_chunk(chunk, bar):
            unknown_bar_chunks.append((bar_index, len(chunk), raw_kind, chunk))
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
    piece.imported_score = _build_imported_score(piece, unknown_bar_chunks=unknown_bar_chunks)
    if parsed_text_records:
        warning = _ft3_text_import_warning(parsed_text_records)
        if warning:
            piece.import_warnings.append(warning)
    if (
        piece.imported_score is not None
        and any(staff.kind == "unknown" for staff in piece.imported_score.staffs)
        and not any(bar.chords for bar in piece.bars)
    ):
        piece.import_warnings.append(
            "FT3 contains non-tab score data that is not decoded yet; imported as unknown staves.",
        )
    annotations = _parse_section_annotations(metadata_blob)
    _apply_annotations(piece, annotations)
    for bar in piece.bars:
        _normalize_vocal_event_accidentals(bar, key=piece.key)
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


_MAJOR_KEY_SIGNATURES = {
    "C": 0,
    "G": 1,
    "D": 2,
    "A": 3,
    "E": 4,
    "B": 5,
    "F#": 6,
    "C#": 7,
    "F": -1,
    "Bb": -2,
    "Eb": -3,
    "Ab": -4,
    "Db": -5,
    "Gb": -6,
    "Cb": -7,
}
_MINOR_KEY_SIGNATURES = {
    "A": 0,
    "E": 1,
    "B": 2,
    "F#": 3,
    "C#": 4,
    "G#": 5,
    "D#": 6,
    "A#": 7,
    "D": -1,
    "G": -2,
    "C": -3,
    "F": -4,
    "Bb": -5,
    "Eb": -6,
    "Ab": -7,
}
_KEY_SHARP_ORDER = ("f", "c", "g", "d", "a", "e", "b")
_KEY_FLAT_ORDER = ("b", "e", "a", "d", "g", "c", "f")


def _normalized_key_signature_name(value: str | None) -> tuple[str, str] | None:
    if not value:
        return None
    text = value.strip()
    if not text:
        return None
    compact = re.sub(r"\s+", "", text)
    match = re.fullmatch(r"([A-Ga-g])([#b]?)(M|m)?", compact)
    if match:
        tonic = f"{match.group(1).upper()}{match.group(2)}"
        mode = "minor" if match.group(3) == "m" else "major"
        return tonic, mode
    match = re.fullmatch(r"([A-Ga-g])([#b]?)\s*(maj(?:or)?|min(?:or)?)", text, re.I)
    if match:
        tonic = f"{match.group(1).upper()}{match.group(2)}"
        mode = "minor" if match.group(3).lower().startswith("min") else "major"
        return tonic, mode
    return None


def _key_signature_accidentals(key: str | None) -> dict[str, str]:
    parsed = _normalized_key_signature_name(key)
    if parsed is None:
        return {}
    tonic, mode = parsed
    count = (
        _MINOR_KEY_SIGNATURES.get(tonic) if mode == "minor" else _MAJOR_KEY_SIGNATURES.get(tonic)
    )
    if count is None or count == 0:
        return {}
    if count > 0:
        return dict.fromkeys(_KEY_SHARP_ORDER[:count], "#")
    return dict.fromkeys(_KEY_FLAT_ORDER[:-count], "b")


def _normalize_vocal_event_accidentals(bar: Bar, *, key: str | None) -> None:
    defaults = _key_signature_accidentals(key)
    if not defaults:
        return
    normalized: list[MelodyEvent] = []
    for event in getattr(bar, "melody_events", None) or []:
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
            accidental = ""
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


def _sum_matches_meter(sum_quarter_beats: float, meter: str) -> bool:
    target = {
        "O": 1.5,
        "3/4": 1.5,
        "6/8": 1.5,
        "C|": 2.0,
        "C": 4.0,
        "4/4": 4.0,
        "2/2": 2.0,
    }.get(meter)
    if target is None:
        return False
    return abs(sum_quarter_beats - target) <= 0.15


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

    def _fill_range(
        start: int,
        end: int,
        *,
        prev_meter: str | None,
        next_meter: str | None,
    ) -> None:
        for idx in range(start, end):
            bar = bars[idx]
            if bar.time_sig is not None or not bar.chords:
                continue
            total = _bar_sum_quarter_beats(bar)
            if prev_meter is None and next_meter:
                # Before the first explicit meter: keep strong sum-based guesses
                # (e.g. O for 3/4-like bars), otherwise fall back to next_meter
                # so short lead-ins still show the score meter cue.
                guessed = _infer_meter_from_sum(total)
                if guessed:
                    bar.time_sig = guessed
                    continue
                bar.time_sig = next_meter
                continue
            if prev_meter and _sum_matches_meter(total, prev_meter):
                bar.time_sig = prev_meter
                continue
            if next_meter and _sum_matches_meter(total, next_meter):
                bar.time_sig = next_meter
                continue
            guessed = _infer_meter_from_sum(total)
            if guessed:
                bar.time_sig = guessed

    first = explicit[0]
    _fill_range(0, first, prev_meter=None, next_meter=bars[first].time_sig)
    for pos, idx in enumerate(explicit[:-1]):
        nxt = explicit[pos + 1]
        _fill_range(idx + 1, nxt, prev_meter=bars[idx].time_sig, next_meter=bars[nxt].time_sig)
    last = explicit[-1]
    _fill_range(last + 1, len(bars), prev_meter=bars[last].time_sig, next_meter=None)


def parse_time_signature(bar_data: bytes) -> str | None:
    if len(bar_data) < 10:
        return None
    time_signature = bar_data[0] & 0x7F
    if time_signature == 0x01:
        return "C"
    if time_signature == 0x02:
        return "C|"
    if time_signature == 0x03:
        return "O"
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
