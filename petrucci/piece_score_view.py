"""Piece-model mapping for the canonical Petrucci score renderer."""

from __future__ import annotations

import re
from dataclasses import dataclass, replace

from petrucci.framebuffer import Frame
from petrucci.layout import NotationLayoutPolicy, layout_score
from petrucci.model import ImportedStaff, Piece
from petrucci.piece_adapter import notation_score_from_piece
from petrucci.score import NotationEvent, NotationScore
from petrucci.score_typeset import ScoreTypesetOptions, ScoreTypesetResult
from petrucci.screen import A_DIM, A_REVERSE
from petrucci.terminal import GlyphMode, SemanticFrame, paint_score

_SOURCE_EVENT_ID = re.compile(r":bar:(?P<bar>\d+):event:(?P<onset>\d+):(?P<voice>\d+)$")


@dataclass(frozen=True, slots=True)
class PieceScoreView:
    result: ScoreTypesetResult
    cursor_display_maps: dict[int, list[int]]


def typeset_piece_score_view(
    piece: Piece,
    *,
    width: int,
    height: int,
    bar_offset: int,
    cursor: tuple[int, int],
    playback: tuple[int, int] | None,
    settings: dict[str, str],
    focused_imported_staff_index: int | None = None,
) -> PieceScoreView | None:
    """Render a Piece notation-focused view, or return ``None`` for tablature."""

    staff_indices = _canonical_staff_indices(piece, focused_imported_staff_index)
    if settings.get("showmelody", "on") != "on" or staff_indices == ():
        return None
    score = notation_score_from_piece(
        piece,
        staff_indices=None if staff_indices is None else staff_indices,
        include_lyrics=settings.get("showlyrics", "on") == "on",
    )
    policy = NotationLayoutPolicy(
        justify=settings.get("justify", "smart") != "packed",
        show_lyrics=settings.get("showlyrics", "on") == "on",
        show_stems=settings.get("showdur", "off") != "off" or settings.get("flagredundant", "on") == "on",
    )
    base_options = ScoreTypesetOptions(
        width=max(1, width),
        height=max(1, height),
        glyph_mode=GlyphMode.SAFE,
        policy=policy,
    )
    layout = layout_score(score, viewport=base_options.viewport, metrics=base_options.metrics, policy=policy)
    active_position = playback or cursor
    active_event = _source_event(score, *active_position)
    system_offset = _system_offset(layout, score, bar_offset=bar_offset, active_event=active_event)
    options = ScoreTypesetOptions(
        width=base_options.width,
        height=base_options.height,
        system_offset=system_offset,
        glyph_mode=base_options.glyph_mode,
        metrics=base_options.metrics,
        policy=policy,
    )
    semantic_frame = paint_score(
        layout,
        viewport=options.viewport,
        glyph_mode=options.glyph_mode,
    )
    if active_event is not None:
        semantic_frame = _with_event_attr(
            semantic_frame,
            active_event.id,
            A_REVERSE if playback is not None else A_DIM,
        )
    result = ScoreTypesetResult(layout=layout, semantic_frame=semantic_frame)
    return PieceScoreView(result=result, cursor_display_maps=_cursor_display_maps(score, layout, system_offset))


def _with_event_attr(frame: SemanticFrame, event_id: str, attr: int) -> SemanticFrame:
    attrs = [list(row) for row in frame.frame.attrs]
    for row, column in frame.cells_for(event_id):
        attrs[row][column] = attr
    painted = Frame(lines=list(frame.frame.lines), attrs=[tuple(row) for row in attrs])
    return replace(frame, frame=painted)


def _canonical_staff_indices(piece: Piece, focused_index: int | None) -> tuple[int, ...] | None:
    imported = piece.imported_score
    has_tablature = any(bar.chords or bar.notes for bar in piece.bars)
    if imported is None:
        return None if not has_tablature and any(bar.melody_events for bar in piece.bars) else ()
    if focused_index is not None and 0 <= focused_index < len(imported.staffs):
        selected = imported.staffs[focused_index]
        note_index = _note_index_for_focus(imported.staffs, focused_index, selected)
        return (note_index,) if note_index is not None else ()
    note_indices = tuple(index for index, staff in enumerate(imported.staffs) if staff.kind == "note")
    if not note_indices or has_tablature:
        return ()
    return note_indices


def _note_index_for_focus(staffs: list[ImportedStaff], index: int, selected: ImportedStaff) -> int | None:
    if selected.kind == "note":
        return index
    if selected.kind != "lyrics":
        return None
    labeled = next(
        (
            staff_index
            for staff_index, staff in enumerate(staffs)
            if staff.kind == "note" and staff.label == selected.label
        ),
        None,
    )
    if labeled is not None:
        return labeled
    note_indices = [staff_index for staff_index, staff in enumerate(staffs) if staff.kind == "note"]
    return note_indices[0] if len(note_indices) == 1 else None


def _source_event(score: NotationScore, bar_index: int, onset_index: int) -> NotationEvent | None:
    for staff in score.staffs:
        for measure in staff.measures:
            if measure.number != bar_index + 1:
                continue
            for event in measure.events:
                match = _SOURCE_EVENT_ID.search(event.id)
                if match is not None and int(match["onset"]) == onset_index:
                    return event
    return None


def _system_offset(layout, score: NotationScore, *, bar_offset: int, active_event: NotationEvent | None) -> int:
    if active_event is not None:
        location = layout.location_for(active_event.id)
        if location is not None:
            return location.system_index
    measure_index = next(
        (index for index, measure in enumerate(score.staffs[0].measures) if measure.number >= max(0, bar_offset) + 1),
        max(0, len(score.staffs[0].measures) - 1),
    )
    return next(
        (system.index for system in layout.systems if system.measure_start <= measure_index < system.measure_end),
        max(0, len(layout.systems) - 1),
    )


def _cursor_display_maps(
    score: NotationScore,
    layout,
    system_offset: int,
) -> dict[int, list[int]]:
    maps: dict[int, list[int]] = {}
    visible_systems = {system.index for system in layout.systems[system_offset:]}
    for staff in score.staffs:
        for measure in staff.measures:
            for event in measure.events:
                match = _SOURCE_EVENT_ID.search(event.id)
                onset = layout.onset_for(event.id)
                location = layout.location_for(event.id)
                if match is None or onset is None or location is None or location.system_index not in visible_systems:
                    continue
                bar_index = int(match["bar"])
                onset_index = int(match["onset"])
                mapping = maps.setdefault(bar_index, [])
                if len(mapping) <= onset_index:
                    mapping.extend([onset.x] * (onset_index + 1 - len(mapping)))
                mapping[onset_index] = onset.x
    return maps


__all__ = ["PieceScoreView", "typeset_piece_score_view"]
