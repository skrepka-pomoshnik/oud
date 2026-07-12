from __future__ import annotations

from dataclasses import replace

from oud.petrucci.model import Bar, ImportedBarContent, ImportedStaff, Piece


def _bars_by_source(staff: ImportedStaff | None) -> dict[int, ImportedBarContent]:
    if staff is None:
        return {}
    return {bar.source_bar_index: bar for bar in staff.bars}


def _matching_staff(piece: Piece, *, kind: str, label: str | None) -> ImportedStaff | None:
    if piece.imported_score is None:
        return None
    candidates = [staff for staff in piece.imported_score.staffs if staff.kind == kind]
    if label is not None:
        matched = next((staff for staff in candidates if staff.label == label), None)
        if matched is not None:
            return matched
    return candidates[0] if len(candidates) == 1 else None


def _project_bar(
    base: Bar,
    *,
    note: ImportedBarContent | None,
    lyrics: ImportedBarContent | None,
    comment: ImportedBarContent | None,
) -> Bar:
    projected = replace(base)
    projected.melody_grid = note.melody_grid if note is not None else None
    projected.melody_events = list(note.melody_events) if note is not None else []
    projected.lyrics = list(lyrics.lyrics) if lyrics is not None else []
    projected.lyric_event_rows = [list(row) for row in lyrics.lyric_event_rows] if lyrics is not None else []
    if comment is not None:
        projected.editorial_text = list(comment.editorial_text)
        projected.structured_text_rows = list(comment.text_rows)
    structure = note or lyrics or comment
    if structure is not None:
        projected.time_sig = structure.time_sig or projected.time_sig
        projected.barline = structure.barline or projected.barline
        projected.repeat = structure.repeat or projected.repeat
        projected.ending_numbers = structure.ending_numbers or projected.ending_numbers
        projected.system_break = structure.system_break or projected.system_break
        projected.dynamic = structure.dynamic or projected.dynamic
        projected.fermata = structure.fermata or projected.fermata
    return projected


def project_imported_staff(piece: Piece, staff_index: int | None) -> Piece:
    if staff_index is None or piece.imported_score is None:
        return piece
    if not 0 <= staff_index < len(piece.imported_score.staffs):
        return piece
    selected = piece.imported_score.staffs[staff_index]
    if selected.kind not in {"note", "lyrics", "comment"}:
        return piece

    note_staff = selected if selected.kind == "note" else _matching_staff(piece, kind="note", label=selected.label)
    lyric_staff = selected if selected.kind == "lyrics" else _matching_staff(piece, kind="lyrics", label=selected.label)
    comment_staff = selected if selected.kind == "comment" else None
    note_bars = _bars_by_source(note_staff)
    lyric_bars = _bars_by_source(lyric_staff)
    comment_bars = _bars_by_source(comment_staff)
    source_indices = {*note_bars, *lyric_bars, *comment_bars}
    bar_count = max(len(piece.bars), max(source_indices, default=-1) + 1)
    bars = [
        _project_bar(
            piece.bars[index] if index < len(piece.bars) else Bar(),
            note=note_bars.get(index),
            lyrics=lyric_bars.get(index),
            comment=comment_bars.get(index),
        )
        for index in range(bar_count)
    ]
    return replace(piece, bars=bars)
