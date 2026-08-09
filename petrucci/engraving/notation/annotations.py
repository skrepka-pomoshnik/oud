from __future__ import annotations

from dataclasses import replace
from itertools import pairwise

from petrucci.terminal.display import display_width
from petrucci.engraving.layout.engine import (
    ElementKey,
    ElementRole,
    LayoutElement,
    NotationLayoutPolicy,
    OnsetPosition,
    Rect,
    ScoreSystem,
    StaffRows,
)
from petrucci.engraving.notation.elements import _layout_fail
from petrucci.core.score import LyricLine, LyricSyllable, NotationScore, NotationStaff, SpanKind, Syllabic


def _span_lane_map(staff: NotationStaff, *, kinds: frozenset[SpanKind]) -> dict[str, int]:
    event_order = {
        event.id: index for index, event in enumerate(event for measure in staff.measures for event in measure.events)
    }
    spans = sorted(
        (span for span in staff.spans if span.kind in kinds),
        key=lambda span: (event_order[span.start_event_id], event_order[span.end_event_id], span.id),
    )
    lane_ends: list[int] = []
    lanes: dict[str, int] = {}
    for span in spans:
        start = event_order[span.start_event_id]
        end = event_order[span.end_event_id]
        lane = next((index for index, lane_end in enumerate(lane_ends) if lane_end < start), len(lane_ends))
        if lane == len(lane_ends):
            lane_ends.append(end)
        else:
            lane_ends[lane] = end
        lanes[span.id] = lane
    return lanes


def _lyric_line_elements(
    lines: tuple[LyricLine, ...],
    *,
    x: int,
    right: int,
    rows: StaffRows,
) -> tuple[LayoutElement, ...]:
    elements: list[LayoutElement] = []
    for line in lines:
        if line.verse >= len(rows.lyric_rows):
            continue
        natural_width = display_width(line.text)
        width = max(1, min(natural_width, right - min(x, right) + 1))
        line_x = min(x, right)
        elements.append(
            LayoutElement(
                ElementKey(line.id, ElementRole.LYRIC_LINE),
                Rect(line_x, rows.lyric_rows[line.verse], width),
                line.text,
            ),
        )
        if x > right or natural_width > width:
            elements.append(
                LayoutElement(
                    ElementKey(line.id, ElementRole.CLIP_MARKER),
                    Rect(right, rows.lyric_rows[line.verse]),
                    "right",
                ),
            )
    return tuple(elements)


def _lyric_connector_elements(
    lyrics: dict[str, tuple[LyricSyllable, ...]],
    *,
    event_xs: dict[str, int],
    rows: StaffRows,
) -> tuple[LayoutElement, ...]:
    by_verse = _visible_lyrics_by_verse(lyrics, event_xs=event_xs)
    return tuple(
        element for verse, values in by_verse.items() for element in _verse_hyphen_elements(verse, values, rows=rows)
    )


def _visible_lyrics_by_verse(
    lyrics: dict[str, tuple[LyricSyllable, ...]],
    *,
    event_xs: dict[str, int],
) -> dict[int, list[tuple[int, LyricSyllable]]]:
    by_verse: dict[int, list[tuple[int, LyricSyllable]]] = {}
    for event_id, event_lyrics in lyrics.items():
        if event_id not in event_xs:
            continue
        for lyric in event_lyrics:
            by_verse.setdefault(lyric.verse, []).append((event_xs[event_id], lyric))
    return by_verse


def _verse_hyphen_elements(
    verse: int,
    values: list[tuple[int, LyricSyllable]],
    *,
    rows: StaffRows,
) -> tuple[LayoutElement, ...]:
    if verse >= len(rows.lyric_rows):
        return ()
    elements: list[LayoutElement] = []
    ordered = sorted(values, key=lambda item: (item[0], item[1].id))
    for (x, lyric), (next_x, _next_lyric) in pairwise(ordered):
        if lyric.syllabic not in {Syllabic.BEGIN, Syllabic.MIDDLE}:
            continue
        right = x + display_width(lyric.text)
        if next_x - right < 2:
            continue
        hyphen_x = right + ((next_x - right) // 2)
        elements.append(
            LayoutElement(
                ElementKey(lyric.id, ElementRole.LYRIC_HYPHEN),
                Rect(hyphen_x, rows.lyric_rows[verse]),
            ),
        )
    return tuple(elements)


def _with_score_spans(
    score: NotationScore,
    systems: tuple[ScoreSystem, ...],
    onsets: tuple[OnsetPosition, ...],
) -> tuple[ScoreSystem, ...]:
    onset_map = {onset.event_id: onset for onset in onsets}
    extra: dict[int, list[LayoutElement]] = {}
    for staff in score.staffs:
        lane_maps = {
            SpanKind.TIE: _span_lane_map(staff, kinds=frozenset({SpanKind.TIE})),
            SpanKind.SLUR: _span_lane_map(staff, kinds=frozenset({SpanKind.SLUR, SpanKind.GLISSANDO})),
        }
        lane_maps[SpanKind.GLISSANDO] = lane_maps[SpanKind.SLUR]
        for span in staff.spans:
            start = onset_map.get(span.start_event_id)
            end = onset_map.get(span.end_event_id)
            if start is None or end is None:
                continue
            for system_index, element in _span_segments(
                span_id=span.id,
                kind=span.kind,
                staff_id=staff.id,
                start=start,
                end=end,
                systems=systems,
                lane=lane_maps[span.kind][span.id],
            ):
                extra.setdefault(system_index, []).append(element)
    return tuple(replace(system, elements=(*system.elements, *extra.get(system.index, ()))) for system in systems)


def _span_segments(
    *,
    span_id: str,
    kind: SpanKind,
    staff_id: str,
    start: OnsetPosition,
    end: OnsetPosition,
    systems: tuple[ScoreSystem, ...],
    lane: int,
) -> tuple[tuple[int, LayoutElement], ...]:
    role = {
        SpanKind.TIE: ElementRole.TIE,
        SpanKind.SLUR: ElementRole.SLUR,
        SpanKind.GLISSANDO: ElementRole.GLISSANDO,
    }[kind]
    segments: list[tuple[int, LayoutElement]] = []
    segment_index = 0
    for system_index in range(start.system_index, end.system_index + 1):
        system = systems[system_index]
        left, right = _staff_horizontal_bounds(system, staff_id)
        segment_left = start.x + 1 if system_index == start.system_index else left
        segment_right = end.x - 1 if system_index == end.system_index else right
        if segment_right < segment_left:
            continue
        y = _span_row(system, staff_id=staff_id, role=role, lane=lane)
        segment_value = _span_segment_value(
            system_index=system_index,
            start_system=start.system_index,
            end_system=end.system_index,
        )
        segments.append(
            (
                system_index,
                LayoutElement(
                    ElementKey(span_id, role, segment_index),
                    Rect(segment_left, y, segment_right - segment_left + 1),
                    segment_value,
                    continuation=start.system_index != end.system_index,
                ),
            ),
        )
        segment_index += 1
    return tuple(segments)


def _span_segment_value(*, system_index: int, start_system: int, end_system: int) -> str:
    if start_system == end_system:
        return "complete"
    if system_index == start_system:
        return "start"
    if system_index == end_system:
        return "end"
    return "continue"


def _staff_horizontal_bounds(system: ScoreSystem, staff_id: str) -> tuple[int, int]:
    lines = [
        element.rect
        for element in system.elements
        if element.key.source_id == staff_id and element.key.role is ElementRole.STAFF
    ]
    return min(rect.x for rect in lines), max(rect.right for rect in lines)


def _span_row(system: ScoreSystem, *, staff_id: str, role: ElementRole, lane: int) -> int:
    rows = next(row for row in system.staff_rows if row.staff_id == staff_id)
    if role in {ElementRole.SLUR, ElementRole.GLISSANDO}:
        if not rows.slur_rows:
            _layout_fail(f"staff {staff_id!r} requires an unallocated slur row")
        if lane >= len(rows.slur_rows):
            _layout_fail(f"staff {staff_id!r} requires slur lane {lane}")
        return rows.slur_rows[lane]
    if not rows.tie_rows:
        _layout_fail(f"staff {staff_id!r} requires an unallocated tie row")
    if lane >= len(rows.tie_rows):
        _layout_fail(f"staff {staff_id!r} requires tie lane {lane}")
    return rows.tie_rows[lane]


def _preamble_height(score: NotationScore, policy: NotationLayoutPolicy) -> int:
    if not policy.show_title:
        return 0
    return 2 if score.title or score.composer else 0


def _preamble_elements(
    score: NotationScore,
    width: int,
    policy: NotationLayoutPolicy,
) -> tuple[LayoutElement, ...]:
    if not policy.show_title:
        return ()
    elements: list[LayoutElement] = []
    if score.title:
        title_width = min(width, max(1, display_width(score.title)))
        title_x = max(0, (width - title_width) // 2)
        elements.append(
            LayoutElement(ElementKey(score.id, ElementRole.TITLE), Rect(title_x, 0, title_width), score.title)
        )
    if score.composer:
        composer_width = min(width, max(1, display_width(score.composer)))
        composer_x = max(0, width - composer_width)
        elements.append(
            LayoutElement(
                ElementKey(score.id, ElementRole.COMPOSER),
                Rect(composer_x, 1, composer_width),
                score.composer,
            ),
        )
    return tuple(elements)


def _lyrics_by_event(lyrics: tuple[LyricSyllable, ...]) -> dict[str, tuple[LyricSyllable, ...]]:
    grouped: dict[str, list[LyricSyllable]] = {}
    for lyric in lyrics:
        grouped.setdefault(lyric.event_id, []).append(lyric)
    return {
        event_id: tuple(sorted(values, key=lambda lyric: (lyric.verse, lyric.id)))
        for event_id, values in grouped.items()
    }


def _lyric_lines_by_measure(lines: tuple[LyricLine, ...]) -> dict[str, tuple[LyricLine, ...]]:
    grouped: dict[str, list[LyricLine]] = {}
    for line in lines:
        grouped.setdefault(line.measure_id, []).append(line)
    return {
        measure_id: tuple(sorted(values, key=lambda line: (line.verse, line.id)))
        for measure_id, values in grouped.items()
    }
