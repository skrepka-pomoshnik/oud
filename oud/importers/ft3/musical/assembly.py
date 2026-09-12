from __future__ import annotations

import re
from dataclasses import replace

from oud.importers.ft3.musical.duration import _finalize_explicit_vocal_melody
from oud.importers.ft3.score import (
    _FT3_SCORE_CONTROL_BYTE_LIMIT,
    _FT3_SCORE_MAX_CONTROL_FRAGMENT_TEXT,
    _FT3_SCORE_MIN_CONTROL_FRAGMENT_ROWS,
    _FT3_SCORE_MIN_LYRIC_ROWS,
    _FT3_SCORE_MIN_MATRIX_COLUMNS,
    _MATRIX_COORDINATES,
    _SOURCE_RECORD_KINDS,
    _decode_raw_score_record,
    _ImportedScoreChunk,
    _is_meaningful_lyric_line,
)
from oud.importers.ft3.text.codec import FT3TextRecord
from petrucci.core.model import (
    Bar,
    ImportedBarContent,
    ImportedScore,
    ImportedSourceRecord,
    ImportedStaff,
    ImportedTextRow,
    LyricEvent,
    MelodyEvent,
    Piece,
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
    text_rows = [
        row
        for row in decoded.structured_rows
        if row.kind == "editorial" or (row.kind == "unknown" and len(row.text.strip()) > 1)
    ]
    meta_rows = [row for row in decoded.structured_rows if row.kind in {"font", "control"}]
    if decoded.editorial_text or text_rows or meta_rows:
        editorial = [
            cleaned
            for text in (*decoded.editorial_text, *(row.text for row in text_rows))
            if (cleaned := _clean_editorial_text(text))
        ]
        return list(dict.fromkeys(editorial)), text_rows + meta_rows
    return None


def _clean_editorial_text(text: str) -> str:
    cleaned = text.split("&", 1)[-1].strip()
    return re.sub(r"\s+(\d+)(?:\s+\1){2,}\s+.*$", "", cleaned).strip()


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


def _decoded_lyric_content(decoded: FT3TextRecord, chunk: bytes) -> tuple[list[str], list[list[LyricEvent]]]:
    matrix = _positioned_lyric_matrix(chunk, decoded.melody_events)
    if matrix is not None:
        return _restore_matrix_source_prefix(matrix, decoded)
    lyrics = [line for line in decoded.lyrics if _is_meaningful_lyric_line(line)]
    rows = [
        list(row)
        for row in decoded.lyric_event_rows
        if any(event.extender for event in row) or _is_meaningful_lyric_line(" ".join(event.text for event in row))
    ]
    return lyrics, rows


def _decoded_lyric_text_rows(decoded: FT3TextRecord) -> list[ImportedTextRow]:
    meaningful = [row for row in decoded.structured_rows if _is_meaningful_lyric_line(row.text or " ".join(row.tokens))]
    lyric_rows = [row for row in meaningful if row.kind == "lyrics"]
    return lyric_rows or [row for row in meaningful if row.kind == "vocal"]


def _restore_matrix_source_prefix(
    matrix: tuple[list[str], list[list[LyricEvent]]],
    decoded: FT3TextRecord,
) -> tuple[list[str], list[list[LyricEvent]]]:
    lyrics, rows = matrix
    if (
        len(rows) >= _FT3_SCORE_MIN_LYRIC_ROWS
        or not rows
        or not rows[0]
        or not decoded.lyric_event_rows
        or not decoded.lyric_event_rows[0]
    ):
        return matrix
    matrix_text = rows[0][0].text
    source_text = decoded.lyric_event_rows[0][0].text
    if len(source_text) != len(matrix_text) + 1 or source_text[1:] != matrix_text:
        return matrix
    repaired_rows = [list(row) for row in rows]
    repaired_rows[0][0] = replace(repaired_rows[0][0], text=source_text)
    repaired_lyrics = list(lyrics)
    _first, separator, remainder = repaired_lyrics[0].partition(" ")
    repaired_lyrics[0] = source_text + separator + remainder
    return repaired_lyrics, repaired_rows


def _positioned_lyric_matrix(
    chunk: bytes,
    melody_events: list[MelodyEvent],
) -> tuple[list[str], list[list[LyricEvent]]] | None:
    onsets = sorted({event.onset_index for event in melody_events if not event.is_rest})
    cells = _matrix_cells(chunk)
    if not onsets or not cells:
        return None
    resolved = _resolved_lyric_columns(cells, onsets)
    if resolved is None:
        return None
    lyric_onsets, columns = resolved
    rows = _transpose_lyric_columns(columns, lyric_onsets, melody_events)
    if not rows:
        return None
    lyrics = [" ".join(_matrix_source_text(cell) for cell in row) for row in zip(*columns, strict=True)]
    return lyrics, rows


def _resolved_lyric_columns(
    cells: list[bytes],
    onsets: list[int],
) -> tuple[list[int], list[list[bytes]]] | None:
    for column_count in range(len(onsets), 0, -1):
        columns = _matrix_columns(cells, column_count)
        if columns is None:
            continue
        if column_count == len(onsets) or len(columns[0]) >= _FT3_SCORE_MIN_LYRIC_ROWS:
            return onsets[:column_count], columns
    return None


def _matrix_cells(chunk: bytes) -> list[bytes]:
    parts = chunk.split(b"\r\n")
    if len(parts) < _FT3_SCORE_MIN_MATRIX_COLUMNS:
        return []
    first = re.search(rb"[\x20-\x7e\x80-\xff]+$", parts[0])
    last = re.match(rb"[\x20-\x7e\x80-\xff]+", parts[-1])
    if first is None or last is None:
        return []
    cells = [first.group(0), *parts[1:-1], last.group(0)]
    if not cells[0] or cells[0][0] not in _MATRIX_COORDINATES:
        return []
    cells[0] = cells[0][1:]
    return cells


def _matrix_columns(cells: list[bytes], column_count: int) -> list[list[bytes]] | None:
    if len(cells) == column_count:
        return [[cell] for cell in cells]
    expanded_count = len(cells) + column_count - 1
    if column_count < _FT3_SCORE_MIN_MATRIX_COLUMNS or expanded_count % column_count:
        return None
    verse_count = expanded_count // column_count
    columns: list[list[bytes]] = []
    carry: bytes | None = None
    cursor = 0
    for column_index in range(column_count):
        column = [carry] if carry is not None else []
        needed = verse_count - len(column)
        column.extend(cells[cursor : cursor + needed])
        cursor += needed
        carry = None
        if column_index < column_count - 1:
            split = _split_matrix_boundary(column[-1])
            if split is None:
                return None
            column[-1], carry = split
        columns.append(column)
    if carry is not None or cursor != len(cells) or any(len(column) != verse_count for column in columns):
        return None
    return columns


def _split_matrix_boundary(cell: bytes) -> tuple[bytes, bytes] | None:
    for marker_width in (2, 1):
        for start in range(1, len(cell) - marker_width):
            marker = cell[start : start + marker_width]
            left = cell[:start]
            right = cell[start + marker_width :]
            if _is_matrix_marker(marker) and _valid_matrix_token(left) and _valid_matrix_token(right):
                return left, right
    return None


def _is_matrix_marker(value: bytes) -> bool:
    return bool(value) and all(byte < _FT3_SCORE_CONTROL_BYTE_LIMIT or byte in _MATRIX_COORDINATES for byte in value)


def _valid_matrix_token(value: bytes) -> bool:
    text = _decode_matrix_text(value)
    return bool(text) and bool(re.match(r"[^\W\d_]", text, flags=re.UNICODE))


def _decode_matrix_text(value: bytes) -> str:
    return value.decode("cp1252", errors="replace").replace("\x00", "").strip()


def _matrix_source_text(value: bytes) -> str:
    return _decode_matrix_text(value)


def _matrix_event_text(value: bytes) -> tuple[str, str]:
    source = _matrix_source_text(value)
    starts = source.startswith("-")
    ends = source.endswith("-")
    text = source.strip("-")
    if starts and ends:
        return text, "middle"
    if starts:
        return text, "end"
    if ends:
        return text, "begin"
    return text, "single"


def _transpose_lyric_columns(
    columns: list[list[bytes]],
    onsets: list[int],
    melody_events: list[MelodyEvent],
) -> list[list[LyricEvent]]:
    source_positions = {
        onset: min(event.src_pos for event in melody_events if event.onset_index == onset) for onset in onsets
    }
    rows: list[list[LyricEvent]] = []
    for verse, values in enumerate(zip(*columns, strict=True)):
        row: list[LyricEvent] = []
        for onset, value in zip(onsets, values, strict=True):
            text, syllabic = _matrix_event_text(value)
            if text:
                row.append(
                    LyricEvent(
                        text,
                        onset,
                        verse=verse,
                        syllabic=syllabic,
                        src_pos=source_positions[onset],
                    ),
                )
        rows.append(row)
    return rows


def _append_or_merge_note_bar(staff: ImportedStaff, incoming: ImportedBarContent) -> None:
    existing = next((bar for bar in staff.bars if bar.source_bar_index == incoming.source_bar_index), None)
    if existing is None:
        staff.bars.append(incoming)
        return
    existing.melody_grid = existing.melody_grid or incoming.melody_grid
    existing.melody_events.extend(incoming.melody_events)
    existing.text_rows.extend(incoming.text_rows)
    existing.fermata = existing.fermata or incoming.fermata


def _append_raw_lyric_layer(
    lyric_staff: ImportedStaff,
    base: ImportedBarContent,
    raw_kind: str,
    chunk: bytes,
    decoded: FT3TextRecord | None,
) -> None:
    lyric_content = _decoded_lyric_content(decoded, chunk) if decoded is not None else ([], [])
    if decoded is None or raw_kind not in {"barline-raw", "note-lyric-raw", "text-score-raw"}:
        return
    if not any(lyric_content):
        return
    lyrics, lyric_event_rows = lyric_content
    lyric_staff.bars.append(
        replace(
            base,
            lyrics=lyrics,
            lyric_event_rows=lyric_event_rows,
            text_rows=_decoded_lyric_text_rows(decoded),
        ),
    )


def _append_raw_comment_layers(
    comment_staff: ImportedStaff,
    base: ImportedBarContent,
    raw_kind: str,
    decoded: FT3TextRecord | None,
) -> bool:
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
            return True
    if raw_kind in {"comment-rtf-raw", "annotation-group-raw"} or (raw_kind == "text-score-raw" and decoded is None):
        comment_staff.bars.append(base)
        return True
    return False


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
    chunk: bytes,
    source_bar: Bar,
    decoded: FT3TextRecord | None,
) -> None:
    base = _imported_bar_base(bar_index, source_bar)
    if raw_kind in {"layout-raw", "score-settings-raw"}:
        layout_staff.bars.append(base)
        return
    if raw_kind == "barline-raw":
        barline_staff.bars.append(base)
    if raw_kind in {"note-staff-raw", "note-lyric-raw"} or (
        raw_kind == "text-score-raw" and decoded is not None and decoded.melody_events
    ):
        _append_or_merge_note_bar(note_staff, _decoded_note_content(base, decoded))
    _append_raw_lyric_layer(lyric_staff, base, raw_kind, chunk, decoded)
    if _append_raw_comment_layers(comment_staff, base, raw_kind, decoded):
        return
    raw_text_kinds = {"barline-raw", "note-staff-raw", "note-lyric-raw", "text-score-raw"}
    if raw_kind == "barline-raw":
        return
    if raw_kind in {"note-staff-raw", "note-lyric-raw"} or (decoded is not None and raw_kind in raw_text_kinds):
        return
    unknown_staff.bars.append(base)


def _build_imported_score(
    piece: Piece,
    *,
    imported_chunks: list[_ImportedScoreChunk],
    staff_labels: list[str],
    text_record_cache: dict[bytes, FT3TextRecord],
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
        decoded = _decode_raw_score_record(
            imported.record_kind,
            imported.chunk,
            voice_index=imported.voice_index,
            text_record_cache=text_record_cache,
        )
        _append_raw_imported_bar(
            note_staff=note_staff,
            lyric_staff=lyric_staff,
            comment_staff=comment_staff,
            barline_staff=barline_staff,
            layout_staff=layout_staff,
            unknown_staff=unknown_staff,
            bar_index=imported.bar_index,
            raw_kind=imported.record_kind,
            chunk=imported.chunk,
            source_bar=source_bar,
            decoded=decoded,
        )
    imported_lyrics = list(lyric_staffs.values())
    if (
        len(note_staffs) > 1
        and imported_lyrics
        and all(_is_control_fragment_lyric_staff(staff) for staff in imported_lyrics)
    ):
        imported_lyrics = []
    ordered = [*note_staffs.values(), *imported_lyrics]
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
            source_voice_index=imported.voice_index,
        )
        for imported in imported_chunks
    ]
    return ImportedScore(source_format="ft3", staffs=staffs, source_records=source_records)


def _is_control_fragment_lyric_staff(staff: ImportedStaff) -> bool:
    rows = [row for bar in staff.bars for row in bar.lyric_event_rows if row]
    if len(rows) < _FT3_SCORE_MIN_CONTROL_FRAGMENT_ROWS:
        return False
    return all(len(row) == 1 and 0 < len(row[0].text.strip()) <= _FT3_SCORE_MAX_CONTROL_FRAGMENT_TEXT for row in rows)
