"""Piece-model mapping for the canonical Petrucci score renderer."""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from fractions import Fraction

from petrucci.adapters.piece import notation_score_from_piece
from petrucci.core.model import ImportedStaff, MelodyEvent, Piece
from petrucci.core.score import NotationEvent, NotationScore, NotationStaff
from petrucci.engraving.layout.engine import ElementRole, LayoutMetrics, NotationLayoutPolicy, ScoreLayout, layout_score
from petrucci.engraving.score_typeset import ScoreTypesetOptions, ScoreTypesetResult
from petrucci.rendering.primitives.utils import bar_cells_from_chords, chord_positions, note_type_to_denom
from petrucci.terminal.api import GlyphMode, SemanticFrame, paint_score
from petrucci.terminal.canvas.framebuffer import Frame
from petrucci.terminal.canvas.screen import A_BOLD, A_DIM, A_REVERSE
from petrucci.terminal.lyrics import piece_for_lyric_display

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


@dataclass
class _TabCanvas:
    lines: list[list[str]]
    attrs: list[list[int]]
    roles: list[list[ElementRole | None]]
    element_ids: list[list[str | None]]

    @classmethod
    def from_frame(cls, frame: SemanticFrame) -> _TabCanvas:
        return cls(
            lines=[list(line) for line in frame.frame.lines],
            attrs=[list(row) for row in frame.frame.attrs],
            roles=[list(row) for row in frame.roles],
            element_ids=[list(row) for row in frame.element_ids],
        )

    def clear_rows(self, top: int, bottom: int) -> None:
        for y in range(max(0, top), min(len(self.lines), bottom + 1)):
            self.lines[y] = [" "] * len(self.lines[y])
            self.attrs[y] = [0] * len(self.attrs[y])
            self.roles[y] = [None] * len(self.roles[y])
            self.element_ids[y] = [None] * len(self.element_ids[y])

    def put(self, y: int, x: int, text: str) -> None:
        if not 0 <= y < len(self.lines):
            return
        for offset, char in enumerate(text):
            column = x + offset
            if not 0 <= column < len(self.lines[y]):
                continue
            self.lines[y][column] = char
            self.attrs[y][column] = 0
            self.roles[y][column] = ElementRole.STAFF
            self.element_ids[y][column] = "piece:tab"

    def freeze(self) -> SemanticFrame:
        return SemanticFrame(
            frame=Frame(lines=["".join(row) for row in self.lines], attrs=[tuple(row) for row in self.attrs]),
            roles=tuple(tuple(row) for row in self.roles),
            element_ids=tuple(tuple(row) for row in self.element_ids),
        )


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
    active_verse_index: int | None = None,
) -> PieceScoreView | None:
    """Render a Piece notation-focused view, or return ``None`` for tablature."""

    piece = piece_for_lyric_display(piece, settings, active_verse_index=active_verse_index)
    score_view = settings.get("scoreview", "auto")
    staff_indices = _canonical_staff_indices(piece, focused_imported_staff_index, score_view=score_view)
    if settings.get("showmelody", "on") != "on" or staff_indices == ():
        return None
    score = notation_score_from_piece(
        piece,
        staff_indices=None if staff_indices is None else staff_indices,
        include_lyrics=settings.get("showlyrics", "on") == "on",
    )
    mixed_default = _mixed_score_view(piece, focused_imported_staff_index, score_view=score_view)
    if mixed_default:
        score = _with_tablature_staff(score)
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
    focused_staff_id = _focused_staff_id(
        piece,
        focused_imported_staff_index,
        tab_is_focus=mixed_default and focused_imported_staff_index is None,
    )
    active_events = _source_events(
        piece,
        score,
        *active_position,
        preferred_staff_id=focused_staff_id,
        temporal_tab_position=playback is not None and _has_tablature(piece),
    )
    active_event = active_events[0] if active_events else None
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
    if mixed_default:
        semantic_frame = _with_tablature(
            semantic_frame,
            layout=layout,
            piece=piece,
            system_offset=system_offset,
            y_offset=y_offset,
            settings=settings,
            playback=playback,
        )
    for active_event in active_events:
        semantic_frame = _with_event_attr(
            semantic_frame,
            active_event.id,
            A_REVERSE if playback is not None else A_DIM,
        )
        if playback is not None:
            semantic_frame = _with_playback_marker(semantic_frame, active_event.id)
    result = ScoreTypesetResult(layout=layout, semantic_frame=semantic_frame)
    return PieceScoreView(result=result, cursor_display_maps=_cursor_display_maps(score, layout, system_offset))


def _has_tablature(piece: Piece) -> bool:
    return any(bar.chords or bar.notes for bar in piece.bars)


def _with_tablature_staff(score: NotationScore) -> NotationScore:
    source = score.staffs[0]
    measures = tuple(
        replace(
            measure,
            id=f"piece:tab:bar:{index}:measure",
            events=(),
            time_signature=None,
            key_signature=None,
            clef=None,
        )
        for index, measure in enumerate(source.measures)
    )
    tab = NotationStaff(id="piece:tab", label="lute", measures=measures)
    return replace(score, staffs=(*score.staffs, tab))


def _with_tablature(
    frame: SemanticFrame,
    *,
    layout: ScoreLayout,
    piece: Piece,
    system_offset: int,
    y_offset: int,
    settings: dict[str, str],
    playback: tuple[int, int] | None,
) -> SemanticFrame:
    canvas = _TabCanvas.from_frame(frame)
    origin_y = layout.systems[system_offset].rect.y + y_offset
    for system in layout.systems[system_offset:]:
        rows = next((row for row in system.staff_rows if row.staff_id == "piece:tab"), None)
        if rows is None:
            continue
        canvas.clear_rows(rows.top - origin_y, rows.bottom - origin_y)
        _draw_tab_system(
            canvas,
            system=system,
            course_top=rows.notation_top + 1 - origin_y,
            piece=piece,
            settings=settings,
            playback=playback,
        )
    return canvas.freeze()


def _draw_tab_system(
    canvas: _TabCanvas,
    *,
    system,
    course_top: int,
    piece: Piece,
    settings: dict[str, str],
    playback: tuple[int, int] | None,
) -> None:
    for bar_index, box in zip(range(system.measure_start, system.measure_end), system.measure_boxes, strict=True):
        if not 0 <= bar_index < len(piece.bars):
            continue
        _draw_tab_bar(
            canvas,
            bar=piece.bars[bar_index],
            bar_index=bar_index,
            x=box.x,
            width=box.width,
            course_top=course_top,
            settings=settings,
            playback=playback,
        )
    if system.measure_boxes:
        canvas.put(course_top + 2, max(0, system.measure_boxes[0].x - 5), "lute")


def _draw_tab_bar(
    canvas: _TabCanvas,
    *,
    bar,
    bar_index: int,
    x: int,
    width: int,
    course_top: int,
    settings: dict[str, str],
    playback: tuple[int, int] | None,
) -> None:
    inner_width = max(1, width - 2)
    cells = bar_cells_from_chords(
        bar,
        6,
        inner_width,
        4,
        settings.get("style", "french"),
        french_c_shape=settings.get("frenchc", "normal"),
        label_mode=settings.get("fretlabels", "auto"),
    )
    for course, row in enumerate(cells):
        canvas.put(course_top + course, x, "|")
        canvas.put(course_top + course, x + 1, "".join(row))
        canvas.put(course_top + course, x + width - 1, "|")
    if settings.get("showdur", "off") != "off":
        _draw_tab_durations(canvas, bar, x + 1, inner_width, course_top - 1)
    if playback is not None and playback[0] == bar_index:
        _highlight_tab_chord(
            canvas,
            bar,
            x=x + 1,
            width=inner_width,
            course_top=course_top,
            playback_column=playback[1],
        )


def _draw_tab_durations(canvas: _TabCanvas, bar, x: int, width: int, y: int) -> None:
    for position, denominator, dotted in chord_positions(bar, width, 4):
        text = f"{denominator}{'.' if dotted else ''}"
        canvas.put(y, x + position, text)


def _highlight_tab_chord(
    canvas: _TabCanvas,
    bar,
    *,
    x: int,
    width: int,
    course_top: int,
    playback_column: int,
) -> None:
    positions = chord_positions(bar, width, 4)
    if not positions:
        return
    index = min(max(0, playback_column), len(positions) - 1)
    column = x + positions[index][0]
    for course in range(6):
        y = course_top + course
        if 0 <= y < len(canvas.attrs) and 0 <= column < len(canvas.attrs[y]):
            canvas.attrs[y][column] = A_REVERSE | A_BOLD


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


def _canonical_staff_indices(
    piece: Piece,
    focused_index: int | None,
    *,
    score_view: str,
) -> tuple[int, ...] | None:
    imported = piece.imported_score
    has_tablature = _has_tablature(piece)
    if imported is None:
        return None if not has_tablature and any(bar.melody_events for bar in piece.bars) else ()
    note_indices = tuple(index for index, staff in enumerate(imported.staffs) if staff.kind == "note")
    if not note_indices:
        return ()
    if score_view == "score" or (score_view == "auto" and not has_tablature):
        return note_indices
    if score_view == "staff" and has_tablature and focused_index is None:
        return ()
    if focused_index is not None and 0 <= focused_index < len(imported.staffs):
        selected = imported.staffs[focused_index]
        note_index = _note_index_for_focus(imported.staffs, focused_index, selected)
        return (note_index,) if note_index is not None else ()
    return (note_indices[0],) if score_view == "staff" else note_indices


def _mixed_score_view(piece: Piece, focused_index: int | None, *, score_view: str) -> bool:
    if not _has_tablature(piece):
        return False
    if score_view == "score":
        return True
    return score_view == "auto" and focused_index is None


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


def _focused_staff_id(piece: Piece, focused_index: int | None, *, tab_is_focus: bool = False) -> str | None:
    if tab_is_focus:
        return "piece:tab"
    imported = piece.imported_score
    if imported is None or focused_index is None or not 0 <= focused_index < len(imported.staffs):
        return None
    selected = imported.staffs[focused_index]
    note_index = _note_index_for_focus(imported.staffs, focused_index, selected)
    return f"piece:staff:{note_index}" if note_index is not None else None


def _source_events(
    piece: Piece,
    score: NotationScore,
    bar_index: int,
    onset_index: int,
    *,
    preferred_staff_id: str | None,
    temporal_tab_position: bool = False,
) -> tuple[NotationEvent, ...]:
    staffs = sorted(score.staffs, key=lambda staff: staff.id != preferred_staff_id)
    matches: list[NotationEvent] = []
    for staff in staffs:
        staff_onset = _source_onset_index(
            piece,
            bar_index,
            onset_index,
            preferred_staff_id=staff.id,
            temporal_tab_position=temporal_tab_position,
        )
        for measure in staff.measures:
            if measure.number != bar_index + 1:
                continue
            for event in measure.events:
                match = _SOURCE_EVENT_ID.search(event.id)
                if match is not None and int(match["onset"]) == staff_onset:
                    matches.append(event)
    return tuple(matches)


def _source_onset_index(
    piece: Piece,
    bar_index: int,
    source_position: int,
    *,
    preferred_staff_id: str | None,
    temporal_tab_position: bool,
) -> int:
    imported = piece.imported_score
    if imported is None:
        return source_position
    preferred = (
        int(preferred_staff_id.rsplit(":", 1)[-1])
        if preferred_staff_id is not None and preferred_staff_id.startswith("piece:staff:")
        else None
    )
    staffs = [(index, staff) for index, staff in enumerate(imported.staffs) if staff.kind == "note"]
    staffs.sort(key=lambda item: item[0] != preferred)
    for _index, staff in staffs:
        bar = next((item for item in staff.bars if item.source_bar_index == bar_index), None)
        if bar is None or not bar.melody_events:
            continue
        if temporal_tab_position:
            mapped = _notation_onset_at_tab_attack(piece, bar_index, source_position, bar.melody_events)
            if mapped is not None:
                return mapped
        direct = next((event for event in bar.melody_events if event.onset_index == source_position), None)
        event = direct or min(
            bar.melody_events,
            key=lambda item: (abs(item.src_pos - source_position), item.onset_index),
        )
        return event.onset_index
    return source_position


def _notation_onset_at_tab_attack(
    piece: Piece,
    bar_index: int,
    chord_index: int,
    melody_events: list[MelodyEvent],
) -> int | None:
    if not 0 <= bar_index < len(piece.bars):
        return None
    chords = piece.bars[bar_index].chords
    if not chords or not melody_events:
        return None
    target = sum((_written_duration(chord.note_type, chord.dotted) for chord in chords[:chord_index]), Fraction())
    voice = min(event.voice for event in melody_events)
    ordered = sorted(
        (event for event in melody_events if event.voice == voice),
        key=lambda event: event.onset_index,
    )
    onset = Fraction()
    for event in ordered:
        end = onset + _written_duration(event.note_type, event.dotted)
        if target < end:
            return event.onset_index
        onset = end
    return ordered[-1].onset_index if ordered else None


def _written_duration(note_type: int | None, dotted: bool) -> Fraction:
    denominator = note_type_to_denom(note_type or 4) or 4
    duration = Fraction(1, denominator)
    return duration * Fraction(3, 2) if dotted else duration


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
