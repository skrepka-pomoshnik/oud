"""Standard-notation measurement and semantic positioning."""

from __future__ import annotations

from dataclasses import replace

from petrucci.core.music.projection import ProjectedInterval, TimelineProjection, TimelineProjectionRequest
from petrucci.core.music.timeline import score_measure_boundaries
from petrucci.core.score import (
    Clef,
    EventKind,
    LyricLine,
    LyricSyllable,
    NotationEvent,
    NotationMeasure,
    NotationScore,
    NotationStaff,
    SpanKind,
    StemDirection,
    iter_score_events,
)
from petrucci.engraving.layout.engine import (
    ElementKey,
    ElementRole,
    EventLocation,
    LayoutElement,
    LayoutMetrics,
    LayoutViewport,
    NotationLayoutPolicy,
    OnsetPosition,
    Rect,
    ScoreLayout,
    ScoreSystem,
    StaffRows,
)
from petrucci.engraving.layout.fitting import BoxSystem
from petrucci.engraving.notation.annotations import (
    _lyric_connector_elements,
    _lyric_line_elements,
    _lyric_lines_by_measure,
    _lyrics_by_event,
    _preamble_elements,
    _preamble_height,
    _span_lane_map,
    _with_score_spans,
)
from petrucci.engraving.notation.elements import (
    _beam_elements,
    _beam_groups,
    _event_elements,
    _event_marker_y,
    _event_notation,
    _layout_fail,
    _lyric_elements,
    _stem_up,
    _tuplet_elements,
    _unplaced_event_markers,
)
from petrucci.engraving.notation.horizontal import _horizontal_plan, _measure_geometry, _natural_onset_gap
from petrucci.engraving.notation.state import (
    _key_signature_elements,
    _slot_index,
    _staff_position,
    _state_at,
    _visible_accidentals,
)
from petrucci.engraving.notation.types import (
    _HorizontalPlan,
    _MeasureEventContext,
    _OnsetGroup,
    _PositionedMeasureEvents,
    _SharedMeasureGeometry,
    _SharedOnsetGroup,
    _StaffVerticalNeeds,
)

_BEAM_LANE_HEIGHT = 3


def build_score_layout(
    score: NotationScore,
    *,
    viewport: LayoutViewport,
    metrics: LayoutMetrics,
    policy: NotationLayoutPolicy,
    projection_request: TimelineProjectionRequest | None = None,
) -> ScoreLayout:
    horizontal = _horizontal_plan(
        score,
        viewport=viewport,
        metrics=metrics,
        policy=policy,
        projection_request=projection_request,
    )
    systems: list[ScoreSystem] = []
    onsets: list[OnsetPosition] = []
    y = 0
    for index, box_system in enumerate(horizontal.systems):
        preamble_height = _preamble_height(score, policy) if index == 0 else 0
        measure_start, measure_end = _system_measure_range(box_system)
        rows, system_height = _allocate_system_rows(
            score,
            measure_start=measure_start,
            measure_end=measure_end,
            top=y + preamble_height,
            metrics=metrics,
            policy=policy,
        )
        elements, system_onsets, clipped_event_ids = _system_elements(
            score,
            system_index=index,
            box_system=box_system,
            rows=rows,
            horizontal=horizontal,
            metrics=metrics,
            policy=policy,
        )
        if index == 0:
            elements = (*_preamble_elements(score, viewport.width, policy), *elements)
        height = preamble_height + system_height
        clipped = bool(clipped_event_ids) or any(box.clipped for box in box_system.boxes)
        systems.append(
            ScoreSystem(
                index=index,
                measure_start=measure_start,
                measure_end=measure_end,
                rect=Rect(0, y, viewport.width, height),
                measure_boxes=box_system.boxes,
                staff_rows=rows,
                elements=elements,
                clipped=clipped,
                clipped_event_ids=clipped_event_ids,
            ),
        )
        onsets.extend(system_onsets)
        y += height + metrics.system_gap
    if horizontal.projection is not None:
        onsets = list(_complete_projected_onsets(score, tuple(onsets), horizontal.projection))
        clipped = _projected_clipped_ids(horizontal.projection)
        systems[0] = replace(
            systems[0],
            clipped=systems[0].clipped or bool(clipped),
            clipped_event_ids=tuple(sorted({*systems[0].clipped_event_ids, *clipped})),
        )
    systems = list(_with_score_spans(score, tuple(systems), tuple(onsets)))
    document_height = max(1, y - metrics.system_gap if systems else 1)
    return ScoreLayout(
        score_id=score.id,
        width=viewport.width,
        document_height=document_height,
        event_ids=tuple(event.id for event in iter_score_events(score)),
        event_locations=_event_locations(score, tuple(systems), fallback_system=0 if horizontal.projection else None),
        systems=tuple(systems),
        onsets=tuple(onsets),
        measure_boundaries=score_measure_boundaries(score),
        timeline_collisions=horizontal.projection.collisions if horizontal.projection is not None else (),
    )


def _event_locations(
    score: NotationScore,
    systems: tuple[ScoreSystem, ...],
    *,
    fallback_system: int | None = None,
) -> tuple[EventLocation, ...]:
    system_by_measure = {
        measure_index: system.index
        for system in systems
        for measure_index in range(system.measure_start, system.measure_end)
    }
    return tuple(
        EventLocation(
            event.id,
            staff.id,
            measure.id,
            _event_system_index(system_by_measure, measure_index, fallback_system),
        )
        for staff in score.staffs
        for measure_index, measure in enumerate(staff.measures)
        for event in measure.events
    )


def _event_system_index(system_by_measure: dict[int, int], measure_index: int, fallback: int | None) -> int:
    system_index = system_by_measure.get(measure_index, fallback)
    if system_index is None:
        _layout_fail(f"measure slot {measure_index} is missing from score systems")
    return system_index


def _complete_projected_onsets(
    score: NotationScore,
    onsets: tuple[OnsetPosition, ...],
    projection: TimelineProjection,
) -> tuple[OnsetPosition, ...]:
    known = {onset.event_id for onset in onsets}
    projected = {event.source_id: event for event in projection.events}
    extra = tuple(
        OnsetPosition(event.id, staff.id, measure.id, 0, projected[event.id].column_start)
        for staff in score.staffs
        for measure in staff.measures
        for event in measure.events
        if event.id not in known
    )
    return (*onsets, *extra)


def _projected_clipped_ids(projection: TimelineProjection) -> tuple[str, ...]:
    request = projection.request
    return tuple(
        event.source_id
        for event in projection.events
        if not request.preamble_width <= event.column_start < request.width
    )


def _system_measure_range(system: BoxSystem) -> tuple[int, int]:
    indexes = [_slot_index(box.id) for box in system.boxes]
    return min(indexes), max(indexes) + 1


def _allocate_system_rows(
    score: NotationScore,
    *,
    measure_start: int,
    measure_end: int,
    top: int,
    metrics: LayoutMetrics,
    policy: NotationLayoutPolicy,
) -> tuple[tuple[StaffRows, ...], int]:
    rows: list[StaffRows] = []
    current_top = top
    for staff in score.staffs:
        verse_count = _system_verse_count(staff, measure_start, measure_end) if policy.show_lyrics else 0
        needs = _system_staff_needs(
            staff,
            measure_start=measure_start,
            measure_end=measure_end,
            metrics=metrics,
            show_stems=policy.show_stems,
            show_pitch_labels=policy.show_pitch_labels,
        )
        allocated = _staff_rows(
            staff.id,
            top=current_top,
            verse_count=verse_count,
            needs=needs,
            metrics=metrics,
            policy=policy,
        )
        rows.append(allocated)
        current_top = allocated.bottom + 1 + metrics.staff_gap
    bottom = rows[-1].bottom if rows else top
    return tuple(rows), bottom - top + 1


def _staff_rows(
    staff_id: str,
    *,
    top: int,
    verse_count: int,
    needs: _StaffVerticalNeeds,
    metrics: LayoutMetrics,
    policy: NotationLayoutPolicy,
) -> StaffRows:
    cursor = top
    measure_number_row = cursor if policy.show_measure_numbers else None
    cursor += int(measure_number_row is not None)
    ending_row = cursor if needs.has_ending else None
    cursor += int(ending_row is not None)
    slur_rows = tuple(range(cursor, cursor + needs.slur_lanes))
    cursor += len(slur_rows)
    tuplet_rows = (cursor,) if needs.has_tuplet else ()
    cursor += len(tuplet_rows)
    grace_row = cursor if needs.has_grace else None
    cursor += int(grace_row is not None)
    ornament_row = cursor if needs.has_ornament else None
    cursor += int(ornament_row is not None)
    fermata_row = cursor if needs.has_fermata else None
    cursor += int(fermata_row is not None)
    notation_top = cursor
    step = metrics.staff_line_gap + 1
    first_line = notation_top + needs.top_padding + needs.upper_beam_depth
    line_rows = (
        first_line,
        first_line + step,
        first_line + (2 * step),
        first_line + (3 * step),
        first_line + (4 * step),
    )
    notation_bottom = line_rows[-1] + needs.bottom_padding + needs.lower_beam_depth
    cursor = notation_bottom
    tie_rows = tuple(range(cursor + 1, cursor + 1 + needs.tie_lanes))
    cursor += len(tie_rows)
    dynamic_row = cursor + 1 if needs.has_dynamic else None
    cursor += int(dynamic_row is not None)
    pitch_label_row = cursor + 1 if needs.has_pitch_labels else None
    cursor += int(pitch_label_row is not None)
    lyric_start = cursor + max(1, metrics.lyric_gap)
    lyric_rows = tuple(lyric_start + index for index in range(verse_count))
    bottom = lyric_rows[-1] if lyric_rows else cursor
    return StaffRows(
        staff_id=staff_id,
        top=top,
        measure_number_row=measure_number_row,
        ending_row=ending_row,
        slur_rows=slur_rows,
        tuplet_rows=tuplet_rows,
        grace_row=grace_row,
        ornament_row=ornament_row,
        fermata_row=fermata_row,
        notation_top=notation_top,
        line_rows=line_rows,
        notation_bottom=notation_bottom,
        tie_rows=tie_rows,
        dynamic_row=dynamic_row,
        pitch_label_row=pitch_label_row,
        lyric_rows=lyric_rows,
        bottom=bottom,
    )


def _system_staff_needs(
    staff: NotationStaff,
    *,
    measure_start: int,
    measure_end: int,
    metrics: LayoutMetrics,
    show_stems: bool,
    show_pitch_labels: bool,
) -> _StaffVerticalNeeds:
    line_bottom = 4 * (metrics.staff_line_gap + 1)
    upper = 0
    lower = line_bottom
    for measure_index in range(measure_start, measure_end):
        clef = _state_at(staff, measure_index).clef
        for event in staff.measures[measure_index].events:
            event_upper, event_lower = _event_vertical_extent(
                event,
                clef=clef,
                line_bottom=line_bottom,
                show_stems=show_stems,
            )
            upper = min(upper, event_upper)
            lower = max(lower, event_lower)
    beam_depths = [
        _beam_depths(measure.events, clef=_state_at(staff, measure_index).clef)
        for measure_index, measure in enumerate(
            staff.measures[measure_start:measure_end],
            start=measure_start,
        )
    ]
    return _StaffVerticalNeeds(
        top_padding=max(metrics.staff_top_padding, -upper),
        bottom_padding=max(metrics.staff_bottom_padding, lower - line_bottom),
        upper_beam_depth=max((upper_depth for upper_depth, _lower_depth in beam_depths), default=0),
        lower_beam_depth=max((lower_depth for _upper_depth, lower_depth in beam_depths), default=0),
        slur_lanes=_system_span_lane_count(
            staff,
            kinds=frozenset({SpanKind.SLUR, SpanKind.GLISSANDO}),
            measure_start=measure_start,
            measure_end=measure_end,
        ),
        tie_lanes=_system_span_lane_count(
            staff,
            kinds=frozenset({SpanKind.TIE}),
            measure_start=measure_start,
            measure_end=measure_end,
        ),
        has_tuplet=any(
            event.tuplet is not None
            for measure in staff.measures[measure_start:measure_end]
            for event in measure.events
        ),
        has_grace=any(event.grace for measure in staff.measures[measure_start:measure_end] for event in measure.events),
        has_ending=any(measure.ending_numbers for measure in staff.measures[measure_start:measure_end]),
        has_ornament=any(
            event.ornament or event.harmonic or event.fingering
            for measure in staff.measures[measure_start:measure_end]
            for event in measure.events
        ),
        has_fermata=any(
            event.fermata for measure in staff.measures[measure_start:measure_end] for event in measure.events
        ),
        has_dynamic=any(
            event.dynamic for measure in staff.measures[measure_start:measure_end] for event in measure.events
        ),
        has_pitch_labels=show_pitch_labels
        and any(
            event.kind is EventKind.NOTE
            for measure in staff.measures[measure_start:measure_end]
            for event in measure.events
        ),
    )


def _system_span_lane_count(
    staff: NotationStaff,
    *,
    kinds: frozenset[SpanKind],
    measure_start: int,
    measure_end: int,
) -> int:
    event_measures = {
        event.id: measure_index for measure_index, measure in enumerate(staff.measures) for event in measure.events
    }
    lanes = _span_lane_map(staff, kinds=kinds)
    return max(
        (
            lanes[span.id] + 1
            for span in staff.spans
            if span.kind in kinds
            if event_measures[span.start_event_id] < measure_end and event_measures[span.end_event_id] >= measure_start
        ),
        default=0,
    )


def _beam_depths(events: tuple[NotationEvent, ...], *, clef: Clef) -> tuple[int, int]:
    lanes = _beam_lane_map(events, clef=clef)
    upper = {lane for up, lane in lanes.values() if up}
    lower = {lane for up, lane in lanes.values() if not up}
    return len(upper) * _BEAM_LANE_HEIGHT, len(lower) * _BEAM_LANE_HEIGHT


def _beam_lane_map(events: tuple[NotationEvent, ...], *, clef: Clef) -> dict[str, tuple[bool, int]]:
    groups = _beam_groups(events)
    directions = [(group, _beam_group_up(group, clef=clef)) for group in groups]
    upper_voices = sorted({group[0].voice for group, up in directions if up})
    lower_voices = sorted({group[0].voice for group, up in directions if not up})
    lane_by_direction = {
        True: {voice: lane for lane, voice in enumerate(upper_voices)},
        False: {voice: lane for lane, voice in enumerate(lower_voices)},
    }
    return {event.id: (up, lane_by_direction[up][group[0].voice]) for group, up in directions for event in group}


def _beam_group_up(events: tuple[NotationEvent, ...], *, clef: Clef) -> bool:
    explicit = {event.stem for event in events if event.stem is not StemDirection.AUTO}
    if len(explicit) > 1:
        ids = ", ".join(event.id for event in events)
        _layout_fail(f"beam group has conflicting explicit stem directions: {ids}")
    if explicit:
        return explicit.pop() is StemDirection.UP
    positions = [
        _staff_position(pitch, clef=clef) for event in events if event.kind is EventKind.NOTE for pitch in event.pitches
    ]
    staff_center_position = 4
    return (sum(positions) / max(1, len(positions))) < staff_center_position


def _event_vertical_extent(
    event: NotationEvent,
    *,
    clef: Clef,
    line_bottom: int,
    show_stems: bool,
) -> tuple[int, int]:
    if event.kind is EventKind.REST:
        middle = line_bottom // 2
        return middle, middle
    positions = [_staff_position(pitch, clef=clef) for pitch in event.pitches]
    points = [line_bottom - position for position in positions]
    upper = min(points)
    lower = max(points)
    denominator = _event_notation(event).denominator
    if show_stems and denominator is not None and denominator > 1:
        if _stem_up(event, positions):
            upper -= 3
        else:
            lower += 3
    return upper, lower


def _system_verse_count(staff: NotationStaff, start: int, end: int) -> int:
    event_ids = {event.id for measure in staff.measures[start:end] for event in measure.events}
    measure_ids = {measure.id for measure in staff.measures[start:end]}
    verses = [lyric.verse for lyric in staff.lyrics if lyric.event_id in event_ids]
    verses.extend(line.verse for line in staff.lyric_lines if line.measure_id in measure_ids)
    return max(verses, default=-1) + 1


def _system_elements(
    score: NotationScore,
    *,
    system_index: int,
    box_system: BoxSystem,
    rows: tuple[StaffRows, ...],
    horizontal: _HorizontalPlan,
    metrics: LayoutMetrics,
    policy: NotationLayoutPolicy,
) -> tuple[tuple[LayoutElement, ...], tuple[OnsetPosition, ...], tuple[str, ...]]:
    elements: list[LayoutElement] = []
    onsets: list[OnsetPosition] = []
    clipped_event_ids: set[str] = set()
    measure_start, _measure_end = _system_measure_range(box_system)
    system_right = horizontal.measure_x + box_system.width
    for staff_index, staff in enumerate(score.staffs):
        staff_rows = rows[staff_index]
        elements.extend(
            _staff_base_elements(
                staff,
                rows=staff_rows,
                system_start=measure_start,
                staff_x=horizontal.staff_x,
                measure_x=horizontal.measure_x,
                system_right=system_right,
                label_width=horizontal.label_width,
                policy=policy,
            ),
        )
        lyrics = _lyrics_by_event(staff.lyrics) if policy.show_lyrics else {}
        lyric_lines = _lyric_lines_by_measure(staff.lyric_lines) if policy.show_lyrics else {}
        for placed in box_system.boxes:
            measure_index = _slot_index(placed.id)
            measure = staff.measures[measure_index]
            measure_x = horizontal.measure_x + placed.x
            measure_elements, measure_onsets, measure_clipped_event_ids = _layout_measure(
                staff,
                measure,
                shared_geometry=horizontal.measure_geometries[measure_index],
                measure_index=measure_index,
                system_index=system_index,
                system_start=measure_start,
                x=measure_x,
                width=placed.width,
                rows=staff_rows,
                lyrics=lyrics,
                lyric_lines=lyric_lines.get(measure.id, ()),
                metrics=metrics,
                policy=policy,
                projection=horizontal.projection,
            )
            elements.extend(measure_elements)
            onsets.extend(measure_onsets)
            clipped_event_ids.update(measure_clipped_event_ids)
    return tuple(elements), tuple(onsets), tuple(sorted(clipped_event_ids))


def _staff_base_elements(
    staff: NotationStaff,
    *,
    rows: StaffRows,
    system_start: int,
    staff_x: int,
    measure_x: int,
    system_right: int,
    label_width: int,
    policy: NotationLayoutPolicy,
) -> tuple[LayoutElement, ...]:
    state = _state_at(staff, system_start)
    elements = [
        LayoutElement(
            ElementKey(staff.id, ElementRole.STAFF, (system_start * 5) + line_index),
            Rect(staff_x, line_y, max(1, system_right - staff_x)),
        )
        for line_index, line_y in enumerate(rows.line_rows)
    ]
    elements.append(
        LayoutElement(
            ElementKey(staff.id, ElementRole.CLEF, system_start),
            Rect(staff_x + 1, rows.line_rows[2] - 1),
            state.clef.value,
        ),
    )
    if policy.show_time_signature:
        elements.append(
            LayoutElement(
                ElementKey(staff.id, ElementRole.TIME_SIGNATURE, system_start),
                Rect(staff_x + 4 + abs(state.key.fifths), rows.line_rows[2] - 1, 3, 2),
                f"{state.time.beats}/{state.time.beat_unit}",
            ),
        )
    elements.extend(
        _key_signature_elements(
            staff.id,
            fifths=state.key.fifths,
            clef=state.clef,
            x=staff_x + 3,
            rows=rows,
            index_offset=system_start * 7,
        ),
    )
    if staff.label and label_width:
        elements.append(
            LayoutElement(
                ElementKey(staff.id, ElementRole.STAFF_LABEL, system_start),
                Rect(0, rows.line_rows[2], label_width),
                staff.label,
            ),
        )
    if policy.show_measure_numbers:
        measure = staff.measures[system_start]
        if rows.measure_number_row is None:
            _layout_fail("measure-number policy requires an allocated row")
        elements.append(
            LayoutElement(
                ElementKey(measure.id, ElementRole.MEASURE_NUMBER),
                Rect(measure_x, rows.measure_number_row),
                str(measure.number),
            ),
        )
    return tuple(elements)


def _layout_measure(
    staff: NotationStaff,
    measure: NotationMeasure,
    *,
    shared_geometry: _SharedMeasureGeometry,
    measure_index: int,
    system_index: int,
    system_start: int,
    x: int,
    width: int,
    rows: StaffRows,
    lyrics: dict[str, tuple[LyricSyllable, ...]],
    lyric_lines: tuple[LyricLine, ...],
    metrics: LayoutMetrics,
    policy: NotationLayoutPolicy,
    projection: TimelineProjection | None,
) -> tuple[tuple[LayoutElement, ...], tuple[OnsetPosition, ...], tuple[str, ...]]:
    geometry = _measure_geometry(staff, measure_index, metrics=metrics, policy=policy)
    active_clef = _state_at(staff, measure_index).clef
    visible_accidentals = _visible_accidentals(staff, measure_index)
    change_elements, _local_event_left = _change_elements(
        staff,
        measure,
        measure_index=measure_index,
        system_start=system_start,
        x=x + 1,
        rows=rows,
        show_time_signature=policy.show_time_signature,
    )
    event_left = x + 1 + shared_geometry.change_width
    group_xs, horizontally_clipped = _measure_group_positions(
        geometry.groups,
        shared_geometry,
        projection=projection,
        left=event_left,
        right=x + width - 2,
        base_gap=metrics.event_gap,
    )
    elements = list(change_elements)
    if measure.ending_numbers:
        if rows.ending_row is None:
            _layout_fail(f"measure {measure.id!r} requires an unallocated ending row")
        elements.append(
            LayoutElement(
                ElementKey(measure.id, ElementRole.ENDING),
                Rect(x, rows.ending_row, width),
                ",".join(str(number) for number in measure.ending_numbers),
            ),
        )
    content_right = x + width - 2
    beam_lanes = _beam_lane_map(measure.events, clef=active_clef) if policy.show_stems else {}
    positioned = _position_measure_events(
        geometry.groups,
        group_xs,
        context=_MeasureEventContext(
            staff_id=staff.id,
            measure_id=measure.id,
            system_index=system_index,
            rows=rows,
            clef=active_clef,
            visible_accidentals=visible_accidentals,
            lyrics=lyrics,
            content_left=x if projection is not None else event_left,
            content_right=content_right,
            policy=policy,
            beam_lanes=beam_lanes,
            preserve_anchor=projection is not None,
        ),
    )
    elements.extend(positioned.elements)
    if policy.show_stems:
        elements.extend(
            _beam_elements(
                measure.events,
                elements,
                lanes=beam_lanes,
                rows=rows,
                left=event_left,
                right=content_right,
            ),
        )
    elements.extend(_tuplet_elements(measure.events, positioned.event_xs, rows=rows, right=content_right))
    if policy.show_lyrics:
        elements.extend(_lyric_line_elements(lyric_lines, x=event_left, right=content_right, rows=rows))
        elements.extend(_lyric_connector_elements(lyrics, event_xs=positioned.event_xs, rows=rows))
    bar_x = x + width - 1
    if policy.show_barlines:
        elements.append(
            LayoutElement(
                ElementKey(measure.id, ElementRole.BARLINE),
                Rect(bar_x, rows.line_rows[0], 1, rows.line_rows[-1] - rows.line_rows[0] + 1),
                measure.barline.value,
            ),
        )
    if horizontally_clipped and not positioned.clipped_event_ids:
        elements.append(
            LayoutElement(
                ElementKey(measure.id, ElementRole.CLIP_MARKER),
                Rect(max(x, bar_x - 1), rows.line_rows[0]),
                "right",
            ),
        )
    return tuple(elements), positioned.onsets, tuple(sorted(positioned.clipped_event_ids))


def _position_measure_events(
    groups: tuple[_OnsetGroup, ...],
    group_xs: tuple[int, ...],
    *,
    context: _MeasureEventContext,
) -> _PositionedMeasureEvents:
    elements: list[LayoutElement] = []
    onsets: list[OnsetPosition] = []
    event_xs: dict[str, int] = {}
    clipped_event_ids: set[str] = set()
    for group_index, group in enumerate(groups):
        if group_index >= len(group_xs):
            clipped_event_ids.update(event.id for event in group.events)
            elements.extend(
                _unplaced_event_markers(
                    group.events,
                    right=context.content_right,
                    rows=context.rows,
                    clef=context.clef,
                ),
            )
            continue
        group_x = group_xs[group_index]
        for event, event_offset in zip(group.events, group.event_offsets, strict=True):
            event_x = group_x if context.preserve_anchor else group_x + event_offset
            if event_x < context.content_left:
                onsets.append(
                    OnsetPosition(event.id, context.staff_id, context.measure_id, context.system_index, group_x),
                )
                event_xs[event.id] = context.content_left
                clipped_event_ids.add(event.id)
                elements.append(
                    LayoutElement(
                        ElementKey(event.id, ElementRole.CLIP_MARKER, 1024),
                        Rect(context.content_left, _event_marker_y(event, rows=context.rows)),
                        "left",
                    ),
                )
                continue
            event_elements, event_clipped = _event_elements(
                event,
                x=event_x,
                rows=context.rows,
                clef=context.clef,
                accidental_pitches=context.visible_accidentals.get(event.id, frozenset()),
                policy=context.policy,
                stem_up_override=context.beam_lanes.get(event.id, (None, 0))[0],
            )
            bounded_elements, bounded_clipped = _bound_event_elements(
                event,
                event_elements,
                right=context.content_right,
                rows=context.rows,
                marker_x=min(event_x, context.content_right),
            )
            elements.extend(bounded_elements)
            onsets.append(
                OnsetPosition(event.id, context.staff_id, context.measure_id, context.system_index, group_x),
            )
            event_xs[event.id] = min(event_x, context.content_right)
            if event_clipped or bounded_clipped:
                clipped_event_ids.add(event.id)
            if context.policy.show_lyrics:
                elements.extend(
                    _lyric_elements(
                        context.lyrics.get(event.id, ()),
                        x=event_x,
                        right=context.content_right,
                        rows=context.rows,
                    ),
                )
    return _PositionedMeasureEvents(
        tuple(elements),
        tuple(onsets),
        event_xs,
        frozenset(clipped_event_ids),
    )


def _measure_group_positions(
    groups: tuple[_OnsetGroup, ...],
    shared_geometry: _SharedMeasureGeometry,
    *,
    projection: TimelineProjection | None,
    left: int,
    right: int,
    base_gap: int,
) -> tuple[tuple[int, ...], bool]:
    if projection is not None:
        positions = tuple(_projected_event(projection, group.events[0].id).column_start for group in groups)
        return positions, any(position < left or position > right for position in positions)
    shared_xs, clipped = _group_positions(shared_geometry.groups, left=left, right=right, base_gap=base_gap)
    shared_by_onset = dict(zip((group.onset for group in shared_geometry.groups), shared_xs, strict=True))
    return tuple(shared_by_onset[group.onset] for group in groups), clipped


def _projected_event(projection: TimelineProjection, event_id: str) -> ProjectedInterval:
    event = projection.event_for(event_id)
    if event is None:
        _layout_fail(f"projection is missing canonical event {event_id!r}")
    return event


def _change_elements(
    staff: NotationStaff,
    measure: NotationMeasure,
    *,
    measure_index: int,
    system_start: int,
    x: int,
    rows: StaffRows,
    show_time_signature: bool,
) -> tuple[tuple[LayoutElement, ...], int]:
    if measure_index == system_start:
        return _proportion_elements(measure, x=x, rows=rows)
    previous = _state_at(staff, measure_index - 1)
    elements: list[LayoutElement] = []
    cursor = x
    if measure.clef is not None and measure.clef != previous.clef:
        elements.append(
            LayoutElement(
                ElementKey(measure.id, ElementRole.CLEF), Rect(cursor, rows.line_rows[2] - 1), measure.clef.value
            )
        )
        cursor += 3
    if measure.key_signature is not None and measure.key_signature != previous.key:
        elements.extend(
            _key_signature_elements(
                measure.id,
                fifths=measure.key_signature.fifths,
                clef=measure.clef or previous.clef,
                x=cursor,
                rows=rows,
            ),
        )
        cursor += max(1, abs(measure.key_signature.fifths)) + 1
    if measure.time_signature is not None and measure.time_signature != previous.time:
        if show_time_signature:
            elements.append(
                LayoutElement(
                    ElementKey(measure.id, ElementRole.TIME_SIGNATURE),
                    Rect(cursor, rows.line_rows[2] - 1, 3, 2),
                    f"{measure.time_signature.beats}/{measure.time_signature.beat_unit}",
                ),
            )
        cursor += 4
    proportion, cursor = _proportion_elements(measure, x=cursor, rows=rows)
    elements.extend(proportion)
    return tuple(elements), cursor


def _proportion_elements(
    measure: NotationMeasure,
    *,
    x: int,
    rows: StaffRows,
) -> tuple[tuple[LayoutElement, ...], int]:
    if measure.proportion is None:
        return (), x
    value = f"{measure.proportion.numerator}:{measure.proportion.denominator}"
    element = LayoutElement(
        ElementKey(measure.id, ElementRole.PROPORTION),
        Rect(x, rows.line_rows[2] - 1, len(value)),
        value,
    )
    return (element,), x + len(value) + 1


def _group_positions(
    groups: tuple[_OnsetGroup, ...] | tuple[_SharedOnsetGroup, ...],
    *,
    left: int,
    right: int,
    base_gap: int,
) -> tuple[tuple[int, ...], bool]:
    if not groups:
        return (), False
    gaps = [
        _natural_onset_gap(groups[index].onset, groups[index + 1].onset, base_gap) for index in range(len(groups) - 1)
    ]
    content_width = sum(group.width for group in groups) + sum(gaps)
    available = max(1, right - left + 1)
    if content_width < available and gaps:
        _spread_gap_slack(gaps, available - content_width)
    positions: list[int] = []
    cursor = left
    clipped = False
    for index, group in enumerate(groups):
        if cursor > right:
            clipped = True
        positions.append(cursor)
        if cursor + group.width - 1 > right:
            clipped = True
        cursor += group.width
        if index < len(gaps):
            cursor += gaps[index]
    return tuple(positions), clipped


def _spread_gap_slack(gaps: list[int], slack: int) -> None:
    index = 0
    cap = 4 * len(gaps)
    remaining = min(slack, cap)
    while remaining > 0:
        gaps[index] += 1
        remaining -= 1
        index = (index + 1) % len(gaps)


def _bound_event_elements(
    event: NotationEvent,
    elements: tuple[LayoutElement, ...],
    *,
    right: int,
    rows: StaffRows,
    marker_x: int,
) -> tuple[tuple[LayoutElement, ...], bool]:
    bounded: list[LayoutElement] = []
    clipped = False
    for element in elements:
        if element.rect.x > right:
            clipped = True
            continue
        if element.rect.right > right:
            clipped = True
            bounded.append(replace(element, rect=replace(element.rect, width=right - element.rect.x + 1)))
        else:
            bounded.append(element)
    if clipped:
        y = _event_marker_y(event, rows=rows)
        bounded.append(
            LayoutElement(
                ElementKey(event.id, ElementRole.CLIP_MARKER, 1024),
                Rect(max(0, min(marker_x, right)), y),
                "right",
            ),
        )
    return tuple(bounded), clipped
