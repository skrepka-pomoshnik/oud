from __future__ import annotations

import re
from pathlib import Path

from oud.importers._ft3_duration import (
    _apply_legacy_duration_fix,
    _bar_uses_raw_vocal_fallback,
    _fill_missing_time_signatures,
    _normalize_vocal_event_accidentals,
    build_durations,
)
from oud.importers._ft3_metadata import (
    _apply_annotations,
    _apply_preamble_notes,
    _extract_cpiece_blocks,
    _extract_ft3_preamble_notes,
    _parse_footnote_parts,
    _parse_section_annotations,
    _strip_rtf,
    extract_text,
    read_ft3,
)
from oud.importers._ft3_score import (
    _BodyEntry,
    _build_imported_score,
    _classify_unknown_score_chunk,
    _decode_raw_score_record,
    _ensemble_staff_labels,
    _has_structural_score_marker,
    _ImportedScoreChunk,
    _is_tab_bar,
    _map_body_with_tab,
    _map_score_only_body,
    _merge_text_record_into_bar,
    _parallel_note_tab_plan,
    _parse_score_text_record,
    _record_has_content,
)
from oud.importers._ft3_tab import (
    _apply_embedded_sections,
    parse_bar,
)
from oud.importers._ft3_text import (
    FT3TextRecord,
    is_ft3_text_record,
)
from petrucci.model import (
    Bar,
    Piece,
)


class FT3FormatError(ValueError):
    def __init__(self) -> None:
        super().__init__("FT3 input is missing the CPiece document marker")


__all__ = ["FT3FormatError", "build_durations", "load_ft3"]


def _read_valid_ft3(path: str) -> bytes:
    data = read_ft3(path)
    if b"CPiece" not in data:
        raise FT3FormatError
    return data


def load_ft3(path: str) -> Piece:  # noqa: C901, PLR0912
    data = _read_valid_ft3(path)

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
    text_record_cache: dict[bytes, FT3TextRecord] = {}
    body_start = data.find(b"CBar")
    if body_start >= 0:
        body_chunks = re.split(b"\x03\x80", data[body_start + 4 :])
        body_entries: list[_BodyEntry] = []
        for chunk in body_chunks:
            parsed = parse_bar(chunk)
            raw_kind = _classify_unknown_score_chunk(
                chunk,
                parsed,
                text_record_cache=text_record_cache,
            )
            kind = "other"
            if raw_kind in {"note-staff-raw", "note-lyric-raw"}:
                kind = "raw"
            elif _is_tab_bar(parsed):
                kind = "tab"
            elif raw_kind is not None:
                kind = "raw"
            body_entries.append(_BodyEntry(kind, chunk, parsed, raw_kind))
        if any(entry.kind == "tab" for entry in body_entries):
            parallel_plan = _parallel_note_tab_plan(body_entries, annotations)
            if parallel_plan is not None:
                tab_entries, mapped_score_entries, imported_staff_labels = parallel_plan
            else:
                tab_entries, mapped_score_entries = _map_body_with_tab(
                    body_entries,
                    text_record_cache=text_record_cache,
                )
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
                    _ImportedScoreChunk(
                        target_index,
                        mapped.staff_index,
                        len(chunk),
                        raw_kind,
                        chunk,
                        mapped.voice_index,
                    ),
                )
                decoded = _decode_raw_score_record(
                    raw_kind,
                    chunk,
                    voice_index=mapped.voice_index,
                    text_record_cache=text_record_cache,
                )
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
                        mapped.voice_index,
                    ),
                )
                decoded = _decode_raw_score_record(
                    raw_kind,
                    mapped.entry.chunk,
                    voice_index=mapped.voice_index,
                    text_record_cache=text_record_cache,
                )
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
                    record = _parse_score_text_record(chunk, text_record_cache=text_record_cache)
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
        if not _is_tab_bar(bar) and (
            raw_kind := _classify_unknown_score_chunk(
                chunk,
                bar,
                text_record_cache=text_record_cache,
            )
        ):
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
        text_record_cache=text_record_cache,
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
