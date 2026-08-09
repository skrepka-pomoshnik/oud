from __future__ import annotations

import re
from dataclasses import replace

from oud.importers.ft3.text.rows import _events_from_lyric_tokens, _filtered_structured_lyric_tokens
from petrucci.core.model import ImportedBarContent, ImportedStaff, Piece

_FINAL_VERSE_CODA = re.compile(r"\bCoda at end only\.", re.IGNORECASE)


def _final_verse_cue(bar: ImportedBarContent) -> str | None:
    for row in bar.text_rows:
        if match := _FINAL_VERSE_CODA.search(row.text):
            return match.group(0)
    return None


def _source_phrase_tokens(bar: ImportedBarContent) -> list[str]:
    candidates = [_filtered_structured_lyric_tokens(row.tokens) for row in bar.text_rows]
    return max(candidates, key=len, default=[])


def _align_bar_to_final_verse(
    bar: ImportedBarContent,
    verse_count: int,
    note_onsets: tuple[int, ...],
    source_tokens: list[str],
) -> None:
    final_index = verse_count - 1
    final_row = [
        replace(
            event,
            verse=final_index,
            onset_index=note_onsets[index] if index < len(note_onsets) else event.onset_index,
        )
        for index, event in enumerate(_events_from_lyric_tokens(source_tokens, verse=final_index))
    ]
    bar.lyric_event_rows = [[] for _ in range(final_index)] + [final_row]
    final_text = " ".join(source_tokens)
    bar.lyrics = [""] * final_index + [final_text]


def _register_editorial_cue(piece: Piece, source_bar_index: int, cue: str) -> None:
    if 0 <= source_bar_index < len(piece.bars) and cue not in piece.bars[source_bar_index].editorial_text:
        piece.bars[source_bar_index].editorial_text.append(cue)
    imported = piece.imported_score
    if imported is None:
        return
    comment_staff = next((staff for staff in imported.staffs if staff.kind == "comment"), None)
    if comment_staff is None:
        comment_staff = ImportedStaff(kind="comment")
        imported.staffs.append(comment_staff)
    comment_bar = next((bar for bar in comment_staff.bars if bar.source_bar_index == source_bar_index), None)
    if comment_bar is None:
        comment_bar = ImportedBarContent(source_bar_index=source_bar_index)
        comment_staff.bars.append(comment_bar)
    if cue not in comment_bar.editorial_text:
        comment_bar.editorial_text.append(cue)


def _note_onsets_by_bar(piece: Piece, lyric_staff: ImportedStaff) -> dict[int, tuple[int, ...]]:
    if piece.imported_score is None:
        return {}
    note_staffs = [staff for staff in piece.imported_score.staffs if staff.kind == "note"]
    note_staff = next((staff for staff in note_staffs if staff.label == lyric_staff.label), None)
    if note_staff is None and note_staffs:
        note_staff = note_staffs[0]
    if note_staff is None:
        return {}
    return {
        bar.source_bar_index: tuple(event.onset_index for event in bar.melody_events if not event.is_rest)
        for bar in note_staff.bars
    }


def _align_staff_final_verse_coda(piece: Piece, staff: ImportedStaff) -> None:
    verse_count = 1
    final_verse_only = False
    note_onsets = _note_onsets_by_bar(piece, staff)
    for bar in sorted(staff.bars, key=lambda item: item.source_bar_index):
        cue = _final_verse_cue(bar)
        if cue is not None:
            final_verse_only = True
            _register_editorial_cue(piece, bar.source_bar_index, cue)
        if not final_verse_only:
            verse_count = max(verse_count, len(bar.lyric_event_rows))
        source_tokens = _source_phrase_tokens(bar)
        if final_verse_only and verse_count > 1 and bar.lyric_event_rows and source_tokens:
            _align_bar_to_final_verse(
                bar,
                verse_count,
                note_onsets.get(bar.source_bar_index, ()),
                source_tokens,
            )


def apply_ft3_lyric_scopes(piece: Piece) -> None:
    """Interpret explicit FT3 stanza-scope cues without rewriting source text rows."""
    imported = piece.imported_score
    if imported is None:
        return
    lyric_staffs = [staff for staff in imported.staffs if staff.kind == "lyrics"]
    for staff in lyric_staffs:
        _align_staff_final_verse_coda(piece, staff)
    if len(lyric_staffs) != 1:
        return
    for imported_bar in lyric_staffs[0].bars:
        index = imported_bar.source_bar_index
        if 0 <= index < len(piece.bars):
            piece.bars[index].lyrics = list(imported_bar.lyrics)
            piece.bars[index].lyric_event_rows = [list(row) for row in imported_bar.lyric_event_rows]
