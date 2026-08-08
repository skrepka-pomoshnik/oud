"""Piece-model mapping for the canonical Petrucci score renderer."""

from __future__ import annotations

import re
from dataclasses import dataclass, replace

from petrucci.framebuffer import Frame
from petrucci.layout import ElementRole, LayoutMetrics, NotationLayoutPolicy, ScoreLayout, layout_score
from petrucci.model import ImportedStaff, Piece
from petrucci.piece_adapter import notation_score_from_piece
from petrucci.score import NotationEvent, NotationScore
from petrucci.score_typeset import ScoreTypesetOptions, ScoreTypesetResult
from petrucci.screen import A_BOLD, A_DIM, A_REVERSE
from petrucci.terminal import GlyphMode, SemanticFrame, paint_score

_SOURCE_EVENT_ID = re.compile(r":bar:(?P<bar>\d+):event:(?P<onset>\d+):(?P<voice>\d+)$")

_TERMINAL_SCORE_METRICS = LayoutMetrics(
    left_padding=0,
    right_padding=0,
    system_prefix_width=8,
    min_measure_width=6,
    event_gap=2,
    max_measure_stretch=3,
    staff_line_gap=1,
    staff_gap=0,
    system_gap=0,
)


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
        show_measure_numbers=False,
        show_lyrics=settings.get("showlyrics", "on") == "on",
        show_stems=settings.get("showdur", "off") != "off",
    )
    base_options = ScoreTypesetOptions(
        width=max(1, width),
        height=max(1, height),
        glyph_mode=GlyphMode.SAFE,
        metrics=_TERMINAL_SCORE_METRICS,
        policy=policy,
    )
    layout = layout_score(score, viewport=base_options.viewport, metrics=base_options.metrics, policy=policy)
    active_position = playback or cursor
    focused_staff_id = _focused_staff_id(piece, focused_imported_staff_index)
    active_event = _source_event(
        score,
        *active_position,
        preferred_staff_id=focused_staff_id,
    )
    system_offset = _system_offset(layout, score, bar_offset=bar_offset, active_event=active_event)
    y_offset = _vertical_offset(
        layout,
        system_offset=system_offset,
        focused_staff_id=focused_staff_id,
        height=base_options.height,
    )
    options = ScoreTypesetOptions(
        width=base_options.width,
        height=base_options.height,
        system_offset=system_offset,
        y_offset=y_offset,
        glyph_mode=base_options.glyph_mode,
        metrics=base_options.metrics,
        policy=policy,
    )
    semantic_frame = paint_score(
        layout,
        viewport=options.viewport,
        glyph_mode=options.glyph_mode,
    )
    semantic_frame = _without_partial_staffs(
        semantic_frame,
        layout,
        system_offset=system_offset,
        y_offset=y_offset,
        focused_staff_id=focused_staff_id,
    )
    if active_event is not None:
        semantic_frame = _with_event_attr(
            semantic_frame,
            active_event.id,
            A_REVERSE if playback is not None else A_DIM,
        )
        if playback is not None:
            semantic_frame = _with_playback_marker(semantic_frame, active_event.id)
    result = ScoreTypesetResult(layout=layout, semantic_frame=semantic_frame)
    return PieceScoreView(result=result, cursor_display_maps=_cursor_display_maps(score, layout, system_offset))


def _with_event_attr(frame: SemanticFrame, event_id: str, attr: int) -> SemanticFrame:
    attrs = [list(row) for row in frame.frame.attrs]
    for row, column in frame.cells_for(event_id):
        attrs[row][column] = attr
    painted = Frame(lines=list(frame.frame.lines), attrs=[tuple(row) for row in attrs])
    return replace(frame, frame=painted)


def _with_playback_marker(frame: SemanticFrame, event_id: str) -> SemanticFrame:
    event_cells = [
        (row, column)
        for row, column in frame.cells_for(event_id)
        if frame.roles[row][column] in {ElementRole.NOTEHEAD, ElementRole.REST}
    ]
    if not event_cells:
        return frame
    note_row, note_column = min(event_cells)
    marker_row = max(0, note_row - 1)
    lines = [list(line) for line in frame.frame.lines]
    attrs = [list(row) for row in frame.frame.attrs]
    roles = [list(row) for row in frame.roles]
    element_ids = [list(row) for row in frame.element_ids]
    lines[marker_row][note_column] = "^"
    attrs[marker_row][note_column] = A_REVERSE | A_BOLD
    roles[marker_row][note_column] = ElementRole.CLIP_MARKER
    element_ids[marker_row][note_column] = event_id
    return SemanticFrame(
        frame=Frame(lines=["".join(line) for line in lines], attrs=[tuple(row) for row in attrs]),
        roles=tuple(tuple(row) for row in roles),
        element_ids=tuple(tuple(row) for row in element_ids),
    )


def _without_partial_staffs(
    frame: SemanticFrame,
    layout: ScoreLayout,
    *,
    system_offset: int,
    y_offset: int,
    focused_staff_id: str | None,
) -> SemanticFrame:
    system = layout.systems[system_offset]
    if len(system.staff_rows) < 2:
        return frame
    viewport_top = system.rect.y + y_offset
    viewport_bottom = viewport_top + len(frame.lines) - 1
    partial = [
        rows
        for rows in system.staff_rows
        if (rows.top < viewport_top or rows.bottom > viewport_bottom) and rows.staff_id != focused_staff_id
    ]
    if not partial:
        return frame
    lines = [list(line) for line in frame.frame.lines]
    attrs = [list(row) for row in frame.frame.attrs]
    roles = [list(row) for row in frame.roles]
    element_ids = [list(row) for row in frame.element_ids]
    for rows in partial:
        start = max(0, rows.top - viewport_top)
        end = min(len(lines), rows.bottom - viewport_top + 1)
        for row in range(start, end):
            lines[row] = [" "] * len(lines[row])
            attrs[row] = [0] * len(attrs[row])
            roles[row] = [None] * len(roles[row])
            element_ids[row] = [None] * len(element_ids[row])
    return SemanticFrame(
        frame=Frame(lines=["".join(line) for line in lines], attrs=[tuple(row) for row in attrs]),
        roles=tuple(tuple(row) for row in roles),
        element_ids=tuple(tuple(row) for row in element_ids),
    )


def _canonical_staff_indices(piece: Piece, focused_index: int | None) -> tuple[int, ...] | None:
    imported = piece.imported_score
    has_tablature = any(bar.chords or bar.notes for bar in piece.bars)
    if imported is None:
        return None if not has_tablature and any(bar.melody_events for bar in piece.bars) else ()
    note_indices = tuple(index for index, staff in enumerate(imported.staffs) if staff.kind == "note")
    if not note_indices:
        return ()
    if not has_tablature:
        return note_indices
    if focused_index is not None and 0 <= focused_index < len(imported.staffs):
        selected = imported.staffs[focused_index]
        note_index = _note_index_for_focus(imported.staffs, focused_index, selected)
        return (note_index,) if note_index is not None else ()
    return ()


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


def _focused_staff_id(piece: Piece, focused_index: int | None) -> str | None:
    imported = piece.imported_score
    if imported is None or focused_index is None or not 0 <= focused_index < len(imported.staffs):
        return None
    selected = imported.staffs[focused_index]
    note_index = _note_index_for_focus(imported.staffs, focused_index, selected)
    return f"piece:staff:{note_index}" if note_index is not None else None


def _source_event(
    score: NotationScore,
    bar_index: int,
    onset_index: int,
    *,
    preferred_staff_id: str | None,
) -> NotationEvent | None:
    staffs = sorted(score.staffs, key=lambda staff: staff.id != preferred_staff_id)
    for staff in staffs:
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


def _vertical_offset(
    layout: ScoreLayout,
    *,
    system_offset: int,
    focused_staff_id: str | None,
    height: int,
) -> int:
    system = layout.systems[system_offset]
    focused = next((rows for rows in system.staff_rows if rows.staff_id == focused_staff_id), None)
    best_offset = 0
    best_count = -1
    for viewport_top in (system.rect.y, *(rows.top for rows in system.staff_rows)):
        viewport_bottom = viewport_top + height - 1
        if focused is not None and not (viewport_top <= focused.top and focused.bottom <= viewport_bottom):
            continue
        complete_count = sum(viewport_top <= rows.top and rows.bottom <= viewport_bottom for rows in system.staff_rows)
        if complete_count > best_count:
            best_count = complete_count
            best_offset = viewport_top - system.rect.y
    if best_count >= 0:
        return best_offset
    if focused is None:
        return 0
    return max(0, focused.bottom - (system.rect.y + height - 1))


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
