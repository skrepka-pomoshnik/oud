from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from oud.importers.ft3.metadata import (
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
from oud.importers.ft3.musical.duration import (
    _apply_legacy_duration_fix,
    _bar_uses_raw_vocal_fallback,
    _fill_missing_time_signatures,
    _normalize_vocal_event_accidentals,
    build_durations,
)
from oud.importers.ft3.musical.lyric_scope import apply_ft3_lyric_scopes
from oud.importers.ft3.musical.tab import (
    _apply_embedded_sections,
    parse_bar,
)
from oud.importers.ft3.score import (
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
    _MappedScoreEntry,
    _merge_text_record_into_bar,
    _parallel_note_tab_plan,
    _parse_score_text_record,
    _record_has_content,
)
from oud.importers.ft3.source_profiles import apply_ft3_source_tuning
from oud.importers.ft3.text.codec import (
    FT3TextRecord,
    is_ft3_text_record,
)
from petrucci.core.model import (
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


@dataclass(frozen=True, slots=True)
class _DocumentMetadata:
    title: str
    subtitle: str | None
    composer: str | None
    footnote: str | None
    annotations: dict[str, str]
    preamble_notes: list[str]


@dataclass(slots=True)
class _BodyState:
    bar_chunks: list[bytes]
    bar_text_records: list[list[FT3TextRecord]]
    parsed_bars: list[Bar]
    imported_chunks: list[_ImportedScoreChunk]
    imported_staff_labels: list[str]
    parallel_meta_bars: list[tuple[int, Bar]]
    text_record_cache: dict[bytes, FT3TextRecord]


def _document_metadata(data: bytes, path: str) -> _DocumentMetadata:
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
    return _DocumentMetadata(
        title,
        subtitle,
        composer,
        footnote,
        _parse_section_annotations(metadata_blob),
        preamble_notes,
    )


def _classify_body_entries(data: bytes, state: _BodyState) -> list[_BodyEntry]:
    body_start = data.find(b"CBar")
    if body_start < 0:
        return []
    entries: list[_BodyEntry] = []
    for chunk in re.split(b"\x03\x80", data[body_start + 4 :]):
        parsed = parse_bar(chunk)
        raw_kind = _classify_unknown_score_chunk(
            chunk,
            parsed,
            text_record_cache=state.text_record_cache,
        )
        kind = "other"
        if raw_kind in {"note-staff-raw", "note-lyric-raw"}:
            kind = "raw"
        elif _is_tab_bar(parsed):
            kind = "tab"
        elif raw_kind is not None:
            kind = "raw"
        entries.append(_BodyEntry(kind, chunk, parsed, raw_kind))
    return entries


def _decode_tab_body(
    entries: list[_BodyEntry],
    annotations: dict[str, str],
    state: _BodyState,
) -> None:
    parallel_plan = _parallel_note_tab_plan(entries, annotations)
    if parallel_plan is not None:
        tab_entries, mapped_entries, state.imported_staff_labels = parallel_plan
    else:
        tab_entries, mapped_entries = _map_body_with_tab(entries, text_record_cache=state.text_record_cache)
        max_staff = max((mapped.staff_index for mapped in mapped_entries), default=-1)
        labels = _ensemble_staff_labels(annotations)
        state.imported_staff_labels = list(reversed(labels[-max_staff - 1 :]))
    state.bar_chunks = [entry.chunk for entry in tab_entries]
    state.bar_text_records = [[] for _ in tab_entries]
    for mapped in mapped_entries:
        raw_kind = mapped.entry.score_kind
        if raw_kind is None:
            continue
        chunk = mapped.entry.chunk
        state.imported_chunks.append(
            _ImportedScoreChunk(
                mapped.bar_index,
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
            text_record_cache=state.text_record_cache,
        )
        if decoded is not None and _record_has_content(decoded):
            state.bar_text_records[mapped.bar_index].append(decoded)
        parsed = mapped.entry.parsed
        if parsed.time_sig or parsed.barline or parsed.repeat or parsed.system_break:
            state.parallel_meta_bars.append((mapped.bar_index, parsed))


def _decode_score_only_body(
    score_plan: tuple[int, list[_MappedScoreEntry], list[str]],
    state: _BodyState,
) -> None:
    bar_count, mapped_entries, state.imported_staff_labels = score_plan
    state.parsed_bars = [Bar() for _ in range(bar_count)]
    state.bar_chunks = []
    state.bar_text_records = [[] for _ in range(bar_count)]
    for mapped in mapped_entries:
        raw_kind = mapped.entry.score_kind
        if raw_kind is None:
            continue
        chunk = mapped.entry.chunk
        state.imported_chunks.append(
            _ImportedScoreChunk(
                mapped.bar_index,
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
            text_record_cache=state.text_record_cache,
        )
        if mapped.staff_index == 0 and decoded is not None and _record_has_content(decoded):
            state.bar_text_records[mapped.bar_index].append(decoded)
        if mapped.staff_index == 0 and _has_structural_score_marker(mapped.entry.parsed):
            state.parallel_meta_bars.append((mapped.bar_index, mapped.entry.parsed))


def _decode_sequential_body(entries: list[_BodyEntry], state: _BodyState) -> None:
    state.bar_chunks = []
    state.bar_text_records = []
    leading_records: list[FT3TextRecord] = []
    for entry in entries:
        chunk = entry.chunk
        if is_ft3_text_record(chunk):
            record = _parse_score_text_record(chunk, text_record_cache=state.text_record_cache)
            if not _record_has_content(record):
                continue
            if state.bar_chunks:
                state.bar_text_records[-1].append(record)
            else:
                leading_records.append(record)
            continue
        state.bar_chunks.append(chunk)
        attached = [leading_records.pop(0)] if leading_records else []
        state.bar_text_records.append(attached)


def _decode_body(data: bytes, annotations: dict[str, str]) -> _BodyState:
    state = _BodyState(re.split(b"\x03\x80", data), [], [], [], [], [], {})
    entries = _classify_body_entries(data, state)
    if not entries:
        return state
    if any(entry.kind == "tab" for entry in entries):
        _decode_tab_body(entries, annotations, state)
    elif score_plan := _map_score_only_body(entries, annotations):
        _decode_score_only_body(score_plan, state)
    else:
        _decode_sequential_body(entries, state)
    return state


def _parse_body_bars(state: _BodyState) -> None:
    for bar_index, chunk in enumerate(state.bar_chunks):
        bar = parse_bar(chunk)
        state.parsed_bars.append(bar)
        if not _is_tab_bar(bar) and (
            raw_kind := _classify_unknown_score_chunk(
                chunk,
                bar,
                text_record_cache=state.text_record_cache,
            )
        ):
            state.imported_chunks.append(_ImportedScoreChunk(bar_index, 0, len(chunk), raw_kind, chunk))
    if state.bar_chunks:
        _apply_embedded_sections(state.bar_chunks, state.parsed_bars)


def _merge_meta_bar(target: Bar, source: Bar) -> None:
    if target.time_sig is None:
        target.time_sig = source.time_sig
    if target.barline is None:
        target.barline = source.barline
    if target.repeat is None:
        target.repeat = source.repeat
    if not target.ending_numbers:
        target.ending_numbers = source.ending_numbers
    target.system_break = target.system_break or source.system_break


def _merge_parallel_metadata(state: _BodyState) -> None:
    for bar_index, meta_bar in state.parallel_meta_bars:
        if 0 <= bar_index < len(state.parsed_bars):
            _merge_meta_bar(state.parsed_bars[bar_index], meta_bar)


def _string_count(bars: list[Bar]) -> int:
    max_string = 0
    for bar in bars:
        for note in bar.notes:
            max_string = max(max_string, note.string)
    return max(6, max_string) if max_string else 6


def _merge_bar_text(piece: Piece, records_by_bar: list[list[FT3TextRecord]]) -> None:
    for bar, records in zip(piece.bars, records_by_bar, strict=False):
        for record in records:
            _merge_text_record_into_bar(bar, record)


def _finalize_piece(piece: Piece, metadata: _DocumentMetadata, state: _BodyState) -> Piece:
    _merge_bar_text(piece, state.bar_text_records)
    piece.imported_score = _build_imported_score(
        piece,
        imported_chunks=state.imported_chunks,
        staff_labels=state.imported_staff_labels,
        text_record_cache=state.text_record_cache,
    )
    apply_ft3_lyric_scopes(piece)
    if piece.imported_score is not None and any(staff.kind == "unknown" for staff in piece.imported_score.staffs):
        piece.import_warnings.append(
            "FT3 contains non-tab score data that is not decoded yet; imported as unknown staves.",
        )
    _apply_annotations(piece, metadata.annotations)
    apply_ft3_source_tuning(piece)
    _apply_preamble_notes(piece, metadata.preamble_notes)
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
    piece.source = piece.source or source
    piece.editor = piece.editor or editor
    piece.comment = piece.comment or comment
    return piece


def load_ft3(path: str) -> Piece:
    data = _read_valid_ft3(path)
    metadata = _document_metadata(data, path)
    state = _decode_body(data, metadata.annotations)
    _parse_body_bars(state)
    _merge_parallel_metadata(state)
    _apply_legacy_duration_fix(state.parsed_bars)
    _fill_missing_time_signatures(state.parsed_bars)
    piece = Piece(
        title=metadata.title,
        subtitle=metadata.subtitle,
        author=None,
        composer=metadata.composer,
        footnote=metadata.footnote,
        bars=state.parsed_bars,
        strings=_string_count(state.parsed_bars),
    )
    return _finalize_piece(piece, metadata, state)
