"""Standard-notation measurement and semantic positioning."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, replace
from fractions import Fraction
from itertools import pairwise
from typing import NoReturn

from oud.petrucci.display import display_width
from oud.petrucci.layout import (
    ElementKey,
    ElementRole,
    EventLocation,
    LayoutElement,
    LayoutError,
    LayoutMetrics,
    LayoutViewport,
    NotationLayoutPolicy,
    OnsetPosition,
    Rect,
    ScoreLayout,
    ScoreSystem,
    StaffRows,
)
from oud.petrucci.score import (
    AccidentalDisplay,
    BeamKind,
    Clef,
    EventKind,
    KeySignature,
    LyricSyllable,
    NotationEvent,
    NotationMeasure,
    NotationScore,
    NotationStaff,
    PitchStep,
    SpanKind,
    StemDirection,
    Syllabic,
    TimeSignature,
    WrittenPitch,
    duration_notation,
    iter_score_events,
)
from oud.petrucci.system_fitting import BoxSystem, MeasuredBox, fit_measured_boxes


@dataclass(frozen=True, slots=True)
class _ScoreState:
    clef: Clef
    time: TimeSignature
    key: KeySignature


@dataclass(frozen=True, slots=True)
class _OnsetGroup:
    onset: Fraction
    events: tuple[NotationEvent, ...]
    event_offsets: tuple[int, ...]
    width: int


@dataclass(frozen=True, slots=True)
class _MeasureGeometry:
    groups: tuple[_OnsetGroup, ...]
    change_width: int
    min_width: int
    natural_width: int


@dataclass(frozen=True, slots=True)
class _HorizontalPlan:
    label_width: int
    staff_x: int
    measure_x: int
    available_width: int
    systems: tuple[BoxSystem, ...]


@dataclass(frozen=True, slots=True)
class _StaffVerticalNeeds:
    top_padding: int
    bottom_padding: int
    has_slur: bool
    has_tie: bool
    has_ending: bool
    has_ornament: bool
    has_fermata: bool
    has_dynamic: bool
    has_pitch_labels: bool
    has_feedback: bool


def build_score_layout(
    score: NotationScore,
    *,
    viewport: LayoutViewport,
    metrics: LayoutMetrics,
    policy: NotationLayoutPolicy,
    feedback_event_ids: frozenset[str] = frozenset(),
) -> ScoreLayout:
    horizontal = _horizontal_plan(score, viewport=viewport, metrics=metrics, policy=policy)
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
            feedback_event_ids=feedback_event_ids,
        )
        elements, system_onsets, vertically_clipped = _system_elements(
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
        clipped = vertically_clipped or any(box.clipped for box in box_system.boxes)
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
            ),
        )
        onsets.extend(system_onsets)
        y += height + metrics.system_gap
    systems = list(_with_score_spans(score, tuple(systems), tuple(onsets)))
    document_height = max(1, y - metrics.system_gap if systems else 1)
    return ScoreLayout(
        score_id=score.id,
        width=viewport.width,
        document_height=document_height,
        event_ids=tuple(event.id for event in iter_score_events(score)),
        event_locations=_event_locations(score, tuple(systems)),
        systems=tuple(systems),
        onsets=tuple(onsets),
    )


def _event_locations(score: NotationScore, systems: tuple[ScoreSystem, ...]) -> tuple[EventLocation, ...]:
    system_by_measure = {
        measure_index: system.index
        for system in systems
        for measure_index in range(system.measure_start, system.measure_end)
    }
    return tuple(
        EventLocation(event.id, staff.id, measure.id, system_by_measure[measure_index])
        for staff in score.staffs
        for measure_index, measure in enumerate(staff.measures)
        for event in measure.events
    )


def _horizontal_plan(
    score: NotationScore,
    *,
    viewport: LayoutViewport,
    metrics: LayoutMetrics,
    policy: NotationLayoutPolicy,
) -> _HorizontalPlan:
    labels = [display_width(staff.label or "") for staff in score.staffs]
    label_width = min(12, max(labels, default=0))
    if label_width:
        label_width += 1
    staff_x = metrics.left_padding + label_width
    prefix_width = max(metrics.system_prefix_width, 8 + _maximum_key_signature_width(score))
    measure_x = staff_x + prefix_width
    available = viewport.width - measure_x - metrics.right_padding
    if available < metrics.min_measure_width:
        message = (
            f"viewport width {viewport.width} leaves {available} columns for measures; "
            f"at least {metrics.min_measure_width} are required"
        )
        raise LayoutError(message)
    boxes = _measure_boxes(score, metrics=metrics, policy=policy)
    systems = fit_measured_boxes(
        boxes,
        available_width=available,
        gap=metrics.measure_gap,
        justify=policy.justify,
        max_stretch_per_box=metrics.max_measure_stretch,
    )
    return _HorizontalPlan(label_width, staff_x, measure_x, available, systems)


def _measure_boxes(
    score: NotationScore,
    *,
    metrics: LayoutMetrics,
    policy: NotationLayoutPolicy,
) -> tuple[MeasuredBox, ...]:
    boxes: list[MeasuredBox] = []
    for index in range(len(score.staffs[0].measures)):
        geometries = [_measure_geometry(staff, index, metrics=metrics, policy=policy) for staff in score.staffs]
        boxes.append(
            MeasuredBox(
                id=_slot_id(index),
                min_width=max(geometry.min_width for geometry in geometries),
                natural_width=max(geometry.natural_width for geometry in geometries),
                stretch_weight=max(1, *(len(geometry.groups) for geometry in geometries)),
                break_after=any(staff.measures[index].forced_break_after for staff in score.staffs),
            ),
        )
    return tuple(boxes)


def _measure_geometry(
    staff: NotationStaff,
    index: int,
    *,
    metrics: LayoutMetrics,
    policy: NotationLayoutPolicy,
) -> _MeasureGeometry:
    measure = staff.measures[index]
    lyrics = _lyrics_by_event(staff.lyrics) if policy.show_lyrics else {}
    visible_accidentals = _visible_accidentals(staff, index)
    groups = _onset_groups(
        measure,
        lyrics=lyrics,
        visible_accidentals=visible_accidentals,
        clef=_state_at(staff, index).clef,
        policy=policy,
    )
    change_width = _measure_change_width(staff, index)
    token_width = sum(group.width for group in groups)
    natural_gaps = sum(
        _natural_onset_gap(groups[pos].onset, groups[pos + 1].onset, metrics.event_gap)
        for pos in range(max(0, len(groups) - 1))
    )
    min_gaps = metrics.event_gap * max(0, len(groups) - 1)
    fixed = 2 + change_width
    min_width = max(metrics.min_measure_width, fixed + token_width + min_gaps)
    natural_width = max(min_width, fixed + token_width + natural_gaps)
    return _MeasureGeometry(groups, change_width, min_width, natural_width)


def _onset_groups(
    measure: NotationMeasure,
    *,
    lyrics: dict[str, tuple[LyricSyllable, ...]],
    visible_accidentals: dict[str, frozenset[WrittenPitch]],
    clef: Clef,
    policy: NotationLayoutPolicy,
) -> tuple[_OnsetGroup, ...]:
    by_onset: dict[Fraction, list[NotationEvent]] = {}
    for event in measure.events:
        by_onset.setdefault(event.onset, []).append(event)
    groups: list[_OnsetGroup] = []
    for onset in sorted(by_onset):
        events = tuple(sorted(by_onset[onset], key=lambda event: (event.voice, event.id)))
        event_widths = tuple(
            max(
                _event_width(
                    event,
                    accidental_pitches=visible_accidentals.get(event.id, frozenset()),
                    show_pitch_labels=policy.show_pitch_labels,
                ),
                max((display_width(lyric.text) for lyric in lyrics.get(event.id, ())), default=0),
            )
            for event in events
        )
        lane_widths = (
            tuple(
                _event_lane_width(event, width, show_stems=policy.show_stems)
                for event, width in zip(events, event_widths, strict=True)
            )
            if len(events) > 1
            else event_widths
        )
        event_offsets = _event_collision_offsets(
            events,
            lane_widths,
            lyrics=lyrics,
            clef=clef,
            policy=policy,
        )
        width = max(
            (offset + event_width for offset, event_width in zip(event_offsets, lane_widths, strict=True)),
            default=1,
        )
        groups.append(_OnsetGroup(onset=onset, events=events, event_offsets=event_offsets, width=max(1, width)))
    return tuple(groups)


def _event_collision_offsets(
    events: tuple[NotationEvent, ...],
    widths: tuple[int, ...],
    *,
    lyrics: dict[str, tuple[LyricSyllable, ...]],
    clef: Clef,
    policy: NotationLayoutPolicy,
) -> tuple[int, ...]:
    lanes: list[list[NotationEvent]] = []
    lane_widths: list[int] = []
    assignments: list[int] = []
    for event, width in zip(events, widths, strict=True):
        lane_index = next(
            (
                index
                for index, lane in enumerate(lanes)
                if all(not _events_collide(event, other, lyrics=lyrics, clef=clef, policy=policy) for other in lane)
            ),
            len(lanes),
        )
        if lane_index == len(lanes):
            lanes.append([event])
            lane_widths.append(width)
        else:
            lanes[lane_index].append(event)
            lane_widths[lane_index] = max(lane_widths[lane_index], width)
        assignments.append(lane_index)
    lane_offsets: list[int] = []
    cursor = 0
    for width in lane_widths:
        lane_offsets.append(cursor)
        cursor += width + 1
    return tuple(lane_offsets[index] for index in assignments)


def _events_collide(
    left: NotationEvent,
    right: NotationEvent,
    *,
    lyrics: dict[str, tuple[LyricSyllable, ...]],
    clef: Clef,
    policy: NotationLayoutPolicy,
) -> bool:
    if left.kind is EventKind.REST or right.kind is EventKind.REST:
        return True
    if policy.show_pitch_labels or (left.dynamic and right.dynamic):
        return True
    left_verses = {lyric.verse for lyric in lyrics.get(left.id, ())}
    right_verses = {lyric.verse for lyric in lyrics.get(right.id, ())}
    if left_verses.intersection(right_verses):
        return True
    left_positions = [_staff_position(pitch, clef=clef) for pitch in left.pitches]
    right_positions = [_staff_position(pitch, clef=clef) for pitch in right.pitches]
    if any(abs(left_pos - right_pos) <= 1 for left_pos in left_positions for right_pos in right_positions):
        return True
    return policy.show_stems and _events_have_colliding_stems(left, right, left_positions, right_positions)


def _events_have_colliding_stems(
    left: NotationEvent,
    right: NotationEvent,
    left_positions: list[int],
    right_positions: list[int],
) -> bool:
    left_denominator, _left_dots = _event_notation(left)
    right_denominator, _right_dots = _event_notation(right)
    if left_denominator <= 1 or right_denominator <= 1:
        return False
    return _stem_up(left, left_positions) == _stem_up(right, right_positions)


def _event_width(
    event: NotationEvent,
    *,
    accidental_pitches: frozenset[WrittenPitch],
    show_pitch_labels: bool,
) -> int:
    _denominator, dots = _event_notation(event)
    if event.kind is EventKind.REST:
        notation_width = 1 + dots
    else:
        accidental = max(
            (_accidental_width(pitch) for pitch in event.pitches if pitch in accidental_pitches),
            default=0,
        )
        chord_offset = 1 if _chord_has_second(event.pitches) else 0
        editorial_width = 2 if event.editorial_brackets else 0
        notation_width = accidental + editorial_width + 1 + chord_offset + dots
    pitch_label_width = display_width(_event_pitch_label(event)) if show_pitch_labels else 0
    return max(notation_width, display_width(event.dynamic or ""), pitch_label_width)


def _event_lane_width(event: NotationEvent, width: int, *, show_stems: bool) -> int:
    if not show_stems or event.kind is EventKind.REST:
        return width
    denominator, _dots = _event_notation(event)
    if denominator <= 1:
        return width
    return max(width, 3 if denominator >= 8 and event.beam is BeamKind.NONE else 2)


def _natural_onset_gap(left: Fraction, right: Fraction, base: int) -> int:
    quarter_delta = (right - left) * 4
    if quarter_delta >= 4:
        return base + 3
    if quarter_delta >= 2:
        return base + 2
    if quarter_delta >= 1:
        return base + 1
    return base


def _measure_change_width(staff: NotationStaff, index: int) -> int:
    if index == 0:
        return 0
    measure = staff.measures[index]
    previous = _state_at(staff, index - 1)
    width = 0
    if measure.clef is not None and measure.clef != previous.clef:
        width += 3
    if measure.key_signature is not None and measure.key_signature != previous.key:
        width += max(1, abs(measure.key_signature.fifths)) + 1
    if measure.time_signature is not None and measure.time_signature != previous.time:
        width += 4
    return width


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
    feedback_event_ids: frozenset[str],
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
            feedback_event_ids=feedback_event_ids,
            show_stems=policy.show_stems,
            show_pitch_labels=policy.show_pitch_labels,
            reserve_feedback_lane=policy.reserve_feedback_lane,
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
    slur_rows = (cursor,) if needs.has_slur else ()
    cursor += len(slur_rows)
    ornament_row = cursor if needs.has_ornament else None
    cursor += int(ornament_row is not None)
    fermata_row = cursor if needs.has_fermata else None
    cursor += int(fermata_row is not None)
    notation_top = cursor
    step = metrics.staff_line_gap + 1
    first_line = notation_top + needs.top_padding
    line_rows = (
        first_line,
        first_line + step,
        first_line + (2 * step),
        first_line + (3 * step),
        first_line + (4 * step),
    )
    notation_bottom = line_rows[-1] + needs.bottom_padding
    cursor = notation_bottom
    tie_rows = (cursor + 1,) if needs.has_tie else ()
    cursor += len(tie_rows)
    dynamic_row = cursor + 1 if needs.has_dynamic else None
    cursor += int(dynamic_row is not None)
    pitch_label_row = cursor + 1 if needs.has_pitch_labels else None
    cursor += int(pitch_label_row is not None)
    feedback_row = cursor + 1 if needs.has_feedback else None
    cursor += int(feedback_row is not None)
    lyric_start = cursor + max(1, metrics.lyric_gap)
    lyric_rows = tuple(lyric_start + index for index in range(verse_count))
    bottom = lyric_rows[-1] if lyric_rows else cursor
    return StaffRows(
        staff_id=staff_id,
        top=top,
        measure_number_row=measure_number_row,
        ending_row=ending_row,
        slur_rows=slur_rows,
        ornament_row=ornament_row,
        fermata_row=fermata_row,
        notation_top=notation_top,
        line_rows=line_rows,
        notation_bottom=notation_bottom,
        tie_rows=tie_rows,
        dynamic_row=dynamic_row,
        pitch_label_row=pitch_label_row,
        feedback_row=feedback_row,
        lyric_rows=lyric_rows,
        bottom=bottom,
    )


def _system_staff_needs(
    staff: NotationStaff,
    *,
    measure_start: int,
    measure_end: int,
    metrics: LayoutMetrics,
    feedback_event_ids: frozenset[str],
    show_stems: bool,
    show_pitch_labels: bool,
    reserve_feedback_lane: bool,
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
    span_kinds = _system_span_kinds(staff, measure_start=measure_start, measure_end=measure_end)
    return _StaffVerticalNeeds(
        top_padding=max(metrics.staff_top_padding, -upper),
        bottom_padding=max(metrics.staff_bottom_padding, lower - line_bottom),
        has_slur=SpanKind.SLUR in span_kinds,
        has_tie=SpanKind.TIE in span_kinds,
        has_ending=any(measure.ending_numbers for measure in staff.measures[measure_start:measure_end]),
        has_ornament=any(
            event.ornament for measure in staff.measures[measure_start:measure_end] for event in measure.events
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
        has_feedback=reserve_feedback_lane
        or any(
            event.id in feedback_event_ids
            for measure in staff.measures[measure_start:measure_end]
            for event in measure.events
        ),
    )


def _system_span_kinds(staff: NotationStaff, *, measure_start: int, measure_end: int) -> set[SpanKind]:
    event_measures = {
        event.id: measure_index for measure_index, measure in enumerate(staff.measures) for event in measure.events
    }
    kinds: set[SpanKind] = set()
    for span in staff.spans:
        start = event_measures[span.start_event_id]
        end = event_measures[span.end_event_id]
        if min(start, end) < measure_end and max(start, end) >= measure_start:
            kinds.add(span.kind)
    return kinds


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
    denominator, _dots = _event_notation(event)
    if show_stems and denominator > 1:
        if _stem_up(event, positions):
            upper -= 3
        else:
            lower += 3
    if event.tuplet is not None:
        upper -= 2
    return upper, lower


def _system_verse_count(staff: NotationStaff, start: int, end: int) -> int:
    event_ids = {event.id for measure in staff.measures[start:end] for event in measure.events}
    verses = [lyric.verse for lyric in staff.lyrics if lyric.event_id in event_ids]
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
) -> tuple[tuple[LayoutElement, ...], tuple[OnsetPosition, ...], bool]:
    elements: list[LayoutElement] = []
    onsets: list[OnsetPosition] = []
    clipped = False
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
        for placed in box_system.boxes:
            measure_index = _slot_index(placed.id)
            measure = staff.measures[measure_index]
            measure_x = horizontal.measure_x + placed.x
            measure_elements, measure_onsets, measure_clipped = _layout_measure(
                staff,
                measure,
                measure_index=measure_index,
                system_index=system_index,
                system_start=measure_start,
                x=measure_x,
                width=placed.width,
                rows=staff_rows,
                lyrics=lyrics,
                metrics=metrics,
                policy=policy,
            )
            elements.extend(measure_elements)
            onsets.extend(measure_onsets)
            clipped = clipped or measure_clipped or placed.clipped
    return tuple(elements), tuple(onsets), clipped


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
    elements.extend(
        [
            LayoutElement(
                ElementKey(staff.id, ElementRole.CLEF, system_start),
                Rect(staff_x + 1, rows.line_rows[2] - 1),
                state.clef.value,
            ),
            LayoutElement(
                ElementKey(staff.id, ElementRole.TIME_SIGNATURE, system_start),
                Rect(staff_x + 4 + abs(state.key.fifths), rows.line_rows[2] - 1, 3, 2),
                f"{state.time.beats}/{state.time.beat_unit}",
            ),
        ],
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
    measure_index: int,
    system_index: int,
    system_start: int,
    x: int,
    width: int,
    rows: StaffRows,
    lyrics: dict[str, tuple[LyricSyllable, ...]],
    metrics: LayoutMetrics,
    policy: NotationLayoutPolicy,
) -> tuple[tuple[LayoutElement, ...], tuple[OnsetPosition, ...], bool]:
    geometry = _measure_geometry(staff, measure_index, metrics=metrics, policy=policy)
    active_clef = _state_at(staff, measure_index).clef
    visible_accidentals = _visible_accidentals(staff, measure_index)
    change_elements, event_left = _change_elements(
        staff,
        measure,
        measure_index=measure_index,
        system_start=system_start,
        x=x + 1,
        rows=rows,
    )
    group_xs, clipped = _group_positions(
        geometry.groups,
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
    onsets: list[OnsetPosition] = []
    event_xs: dict[str, int] = {}
    for group, group_x in zip(geometry.groups, group_xs, strict=False):
        for event, event_offset in zip(group.events, group.event_offsets, strict=True):
            event_x = group_x + event_offset
            event_elements, event_clipped = _event_elements(
                event,
                x=event_x,
                rows=rows,
                clef=active_clef,
                accidental_pitches=visible_accidentals.get(event.id, frozenset()),
                policy=policy,
            )
            elements.extend(event_elements)
            onsets.append(OnsetPosition(event.id, staff.id, measure.id, system_index, group_x))
            event_xs[event.id] = event_x
            clipped = clipped or event_clipped
            if policy.show_lyrics:
                elements.extend(_lyric_elements(lyrics.get(event.id, ()), x=event_x, rows=rows))
    if policy.show_stems:
        elements.extend(_beam_elements(measure.events, elements))
    if policy.show_lyrics:
        elements.extend(_lyric_connector_elements(lyrics, event_xs=event_xs, rows=rows))
    bar_x = x + width - 1
    if policy.show_barlines:
        elements.append(
            LayoutElement(
                ElementKey(measure.id, ElementRole.BARLINE),
                Rect(bar_x, rows.line_rows[0], 1, rows.line_rows[-1] - rows.line_rows[0] + 1),
                measure.barline.value,
            ),
        )
    if clipped:
        elements.append(
            LayoutElement(
                ElementKey(measure.id, ElementRole.CLIP_MARKER),
                Rect(max(x, bar_x - 1), rows.line_rows[0]),
                "right",
            ),
        )
    return tuple(elements), tuple(onsets), clipped


def _change_elements(
    staff: NotationStaff,
    measure: NotationMeasure,
    *,
    measure_index: int,
    system_start: int,
    x: int,
    rows: StaffRows,
) -> tuple[tuple[LayoutElement, ...], int]:
    if measure_index == system_start:
        return (), x
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
        elements.append(
            LayoutElement(
                ElementKey(measure.id, ElementRole.TIME_SIGNATURE),
                Rect(cursor, rows.line_rows[2] - 1, 3, 2),
                f"{measure.time_signature.beats}/{measure.time_signature.beat_unit}",
            ),
        )
        cursor += 4
    return tuple(elements), cursor


def _group_positions(
    groups: tuple[_OnsetGroup, ...],
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
            break
        positions.append(cursor)
        if cursor + group.width - 1 > right:
            clipped = True
        cursor += group.width
        if index < len(gaps):
            cursor += gaps[index]
    return tuple(positions), clipped or len(positions) != len(groups)


def _spread_gap_slack(gaps: list[int], slack: int) -> None:
    index = 0
    cap = 4 * len(gaps)
    remaining = min(slack, cap)
    while remaining > 0:
        gaps[index] += 1
        remaining -= 1
        index = (index + 1) % len(gaps)


def _event_elements(
    event: NotationEvent,
    *,
    x: int,
    rows: StaffRows,
    clef: Clef,
    accidental_pitches: frozenset[WrittenPitch],
    policy: NotationLayoutPolicy,
) -> tuple[tuple[LayoutElement, ...], bool]:
    denominator, dots = _event_notation(event)
    if event.kind is EventKind.REST:
        elements = _rest_elements(event, x=x, rows=rows, denominator=denominator, dots=dots)
        clipped = False
    else:
        elements, clipped = _note_elements(
            event,
            x=x,
            rows=rows,
            clef=clef,
            denominator=denominator,
            dots=dots,
            accidental_pitches=accidental_pitches,
            show_stems=policy.show_stems,
        )
        if policy.show_pitch_labels:
            if rows.pitch_label_row is None:
                _layout_fail(f"event {event.id!r} requires an unallocated pitch-label row")
            label = _event_pitch_label(event)
            elements = (
                *elements,
                LayoutElement(
                    ElementKey(event.id, ElementRole.PITCH_LABEL),
                    Rect(x, rows.pitch_label_row, max(1, display_width(label))),
                    label,
                ),
            )
    if event.dynamic:
        if rows.dynamic_row is None:
            _layout_fail(f"event {event.id!r} requires an unallocated dynamic row")
        elements = (
            *elements,
            LayoutElement(
                ElementKey(event.id, ElementRole.DYNAMIC),
                Rect(x, rows.dynamic_row, max(1, display_width(event.dynamic))),
                event.dynamic,
            ),
        )
    if event.fermata:
        if rows.fermata_row is None:
            _layout_fail(f"event {event.id!r} requires an unallocated fermata row")
        elements = (
            *elements,
            LayoutElement(ElementKey(event.id, ElementRole.FERMATA), Rect(x, rows.fermata_row)),
        )
    if event.ornament is not None:
        if rows.ornament_row is None:
            _layout_fail(f"event {event.id!r} requires an unallocated ornament row")
        elements = (
            *elements,
            LayoutElement(
                ElementKey(event.id, ElementRole.ORNAMENT),
                Rect(x, rows.ornament_row),
                event.ornament.value,
            ),
        )
    return elements, clipped


def _rest_elements(
    event: NotationEvent,
    *,
    x: int,
    rows: StaffRows,
    denominator: int,
    dots: int,
) -> tuple[LayoutElement, ...]:
    middle = rows.line_rows[2]
    elements = [
        LayoutElement(ElementKey(event.id, ElementRole.REST), Rect(x, middle), str(denominator)),
    ]
    if dots:
        elements.append(LayoutElement(ElementKey(event.id, ElementRole.DOT), Rect(x + 1, middle, dots), str(dots)))
    return tuple(elements)


def _note_elements(
    event: NotationEvent,
    *,
    x: int,
    rows: StaffRows,
    clef: Clef,
    denominator: int,
    dots: int,
    accidental_pitches: frozenset[WrittenPitch],
    show_stems: bool,
) -> tuple[tuple[LayoutElement, ...], bool]:
    pitches = sorted(event.pitches, key=_diatonic_number)
    positions = [_staff_position(pitch, clef=clef) for pitch in pitches]
    offsets = _chord_offsets(positions)
    elements: list[LayoutElement] = []
    clipped = False
    head_points: list[tuple[int, int]] = []
    for index, (pitch, position, offset) in enumerate(zip(pitches, positions, offsets, strict=True)):
        raw_y = rows.line_rows[-1] - position
        y = min(rows.notation_bottom, max(rows.notation_top, raw_y))
        clipped = clipped or y != raw_y
        show_accidental = pitch in accidental_pitches
        accidental_width = _accidental_width(pitch) if show_accidental else 0
        bracket_offset = 1 if event.editorial_brackets else 0
        head_x = x + offset + accidental_width + bracket_offset
        head_points.append((head_x, y))
        elements.extend(
            _pitch_elements(
                event,
                pitch,
                pitch_index=index,
                head_x=head_x,
                y=y,
                position=position,
                rows=rows,
                denominator=denominator,
                dots=dots,
                show_accidental=show_accidental,
                editorial_brackets=event.editorial_brackets,
            )
        )
    stems = (
        _stem_elements(event, head_points=head_points, positions=positions, rows=rows, denominator=denominator)
        if show_stems
        else ()
    )
    elements.extend(stems)
    if denominator >= 8 and event.beam is BeamKind.NONE and stems:
        elements.extend(_flag_elements(event, stem=stems[0], denominator=denominator, rows=rows))
    if event.tuplet is not None and head_points:
        tuplet_y = max(rows.notation_top, min(y for _x, y in head_points) - 2)
        elements.append(
            LayoutElement(
                ElementKey(event.id, ElementRole.TUPLET),
                Rect(x, tuplet_y, 3),
                f"{event.tuplet.actual}:{event.tuplet.normal}",
            ),
        )
    return tuple(elements), clipped


def _event_pitch_label(event: NotationEvent) -> str:
    return "/".join(_written_pitch_label(pitch) for pitch in event.pitches)


def _written_pitch_label(pitch: WrittenPitch) -> str:
    accidental = {-2: "bb", -1: "b", 0: "", 1: "#", 2: "##"}[pitch.alter]
    return f"{pitch.step.value}{accidental}{pitch.octave}"


def _pitch_elements(
    event: NotationEvent,
    pitch: WrittenPitch,
    *,
    pitch_index: int,
    head_x: int,
    y: int,
    position: int,
    rows: StaffRows,
    denominator: int,
    dots: int,
    show_accidental: bool,
    editorial_brackets: bool,
) -> tuple[LayoutElement, ...]:
    elements = [
        LayoutElement(
            ElementKey(event.id, ElementRole.NOTEHEAD, pitch_index),
            Rect(head_x, y),
            str(denominator),
        ),
    ]
    if editorial_brackets:
        elements.extend(
            (
                LayoutElement(
                    ElementKey(event.id, ElementRole.EDITORIAL_BRACKET, pitch_index * 2),
                    Rect(head_x - 1, y),
                    "[",
                ),
                LayoutElement(
                    ElementKey(event.id, ElementRole.EDITORIAL_BRACKET, pitch_index * 2 + 1),
                    Rect(head_x + 1, y),
                    "]",
                ),
            ),
        )
    if show_accidental:
        accidental_width = _accidental_width(pitch)
        bracket_offset = 1 if editorial_brackets else 0
        elements.append(
            LayoutElement(
                ElementKey(event.id, ElementRole.ACCIDENTAL, pitch_index),
                Rect(max(0, head_x - bracket_offset - accidental_width), y, accidental_width),
                (f"{pitch.alter}:courtesy" if pitch.accidental is AccidentalDisplay.COURTESY else str(pitch.alter)),
            ),
        )
    if dots:
        dot_offset = 2 if editorial_brackets else 1
        elements.append(
            LayoutElement(
                ElementKey(event.id, ElementRole.DOT, pitch_index),
                Rect(head_x + dot_offset, y, dots),
                str(dots),
            ),
        )
    elements.extend(_ledger_elements(event.id, pitch_index=pitch_index, x=head_x, position=position, rows=rows))
    return tuple(elements)


def _accidental_width(pitch: WrittenPitch) -> int:
    return max(1, abs(pitch.alter)) + (2 if pitch.accidental is AccidentalDisplay.COURTESY else 0)


def _ledger_elements(
    event_id: str,
    *,
    pitch_index: int,
    x: int,
    position: int,
    rows: StaffRows,
) -> tuple[LayoutElement, ...]:
    ledger_positions: Iterable[int]
    if position < 0:
        ledger_positions = range(-2, position - 1, -2)
    elif position > 8:
        ledger_positions = range(10, position + 1, 2)
    else:
        ledger_positions = ()
    elements: list[LayoutElement] = []
    for ledger_index, ledger_position in enumerate(ledger_positions):
        y = rows.line_rows[-1] - ledger_position
        if rows.notation_top <= y <= rows.notation_bottom:
            key_index = (pitch_index * 16) + ledger_index
            elements.append(
                LayoutElement(
                    ElementKey(event_id, ElementRole.LEDGER_LINE, key_index),
                    Rect(max(0, x - 1), y, 3),
                ),
            )
    return tuple(elements)


def _stem_elements(
    event: NotationEvent,
    *,
    head_points: list[tuple[int, int]],
    positions: list[int],
    rows: StaffRows,
    denominator: int,
) -> tuple[LayoutElement, ...]:
    if not head_points or denominator <= 1:
        return ()
    up = _stem_up(event, positions)
    if up:
        anchor_x, anchor_y = max(head_points, key=lambda point: point[1])
        end_y = max(rows.notation_top, min(y for _x, y in head_points) - 3)
        stem_x = anchor_x + 1
    else:
        anchor_x, anchor_y = min(head_points, key=lambda point: point[1])
        end_y = min(rows.notation_bottom, max(y for _x, y in head_points) + 3)
        stem_x = max(0, anchor_x - 1)
    top = min(anchor_y, end_y)
    height = abs(anchor_y - end_y) + 1
    return (
        LayoutElement(
            ElementKey(event.id, ElementRole.STEM),
            Rect(stem_x, top, 1, height),
            "up" if up else "down",
        ),
    )


def _flag_elements(
    event: NotationEvent,
    *,
    stem: LayoutElement,
    denominator: int,
    rows: StaffRows,
) -> tuple[LayoutElement, ...]:
    up = stem.value == "up"
    count = _flag_count(denominator)
    elements: list[LayoutElement] = []
    for index in range(count):
        y = stem.rect.y + index if up else stem.rect.bottom - index
        y = min(rows.notation_bottom, max(rows.notation_top, y))
        x = stem.rect.x if up else max(0, stem.rect.x - 1)
        elements.append(
            LayoutElement(
                ElementKey(event.id, ElementRole.FLAG, index),
                Rect(x, y, 2),
                "up" if up else "down",
            ),
        )
    return tuple(elements)


def _beam_elements(
    events: tuple[NotationEvent, ...],
    elements: list[LayoutElement],
) -> tuple[LayoutElement, ...]:
    stems = {element.key.source_id: element for element in elements if element.key.role is ElementRole.STEM}
    beams: list[LayoutElement] = []
    for group in _beam_groups(events):
        group_stems = [stems[event.id] for event in group if event.id in stems]
        if len(group_stems) >= 2:
            beams.extend(_complete_beam_elements(group, group_stems))
        elif len(group_stems) == 1 and group[0].beam is not BeamKind.NONE:
            beams.extend(_partial_beam_elements(group[0], group_stems[0]))
    return tuple(beams)


def _beam_groups(events: tuple[NotationEvent, ...]) -> tuple[tuple[NotationEvent, ...], ...]:
    groups: list[tuple[NotationEvent, ...]] = []
    voices = sorted({event.voice for event in events})
    for voice in voices:
        active: list[NotationEvent] = []
        ordered = sorted((event for event in events if event.voice == voice), key=lambda event: (event.onset, event.id))
        for event in ordered:
            if event.beam is BeamKind.START:
                if active:
                    groups.append(tuple(active))
                active = [event]
            elif event.beam is BeamKind.CONTINUE and active:
                active.append(event)
            elif event.beam is BeamKind.END and active:
                active.append(event)
                groups.append(tuple(active))
                active = []
            elif event.beam in {BeamKind.PARTIAL_FORWARD, BeamKind.PARTIAL_BACKWARD}:
                groups.append((event,))
        if active:
            groups.append(tuple(active))
    return tuple(groups)


def _complete_beam_elements(
    events: tuple[NotationEvent, ...],
    stems: list[LayoutElement],
) -> tuple[LayoutElement, ...]:
    up = stems[0].value == "up"
    start_x = min(stem.rect.x for stem in stems)
    end_x = max(stem.rect.x for stem in stems)
    beam_y = min(stem.rect.y for stem in stems) if up else max(stem.rect.bottom for stem in stems)
    count = min(_flag_count_for_event(event) for event in events)
    source_id = events[0].id
    return tuple(
        LayoutElement(
            ElementKey(source_id, ElementRole.BEAM, index),
            Rect(start_x, beam_y + (index if up else -index), max(1, end_x - start_x + 1)),
            str(count),
        )
        for index in range(count)
    )


def _partial_beam_elements(event: NotationEvent, stem: LayoutElement) -> tuple[LayoutElement, ...]:
    forward = event.beam in {BeamKind.START, BeamKind.CONTINUE, BeamKind.PARTIAL_FORWARD}
    start_x = stem.rect.x if forward else max(0, stem.rect.x - 2)
    up = stem.value == "up"
    y = stem.rect.y if up else stem.rect.bottom
    return tuple(
        LayoutElement(
            ElementKey(event.id, ElementRole.BEAM, index),
            Rect(start_x, y + (index if up else -index), 3),
            "partial",
        )
        for index in range(_flag_count_for_event(event))
    )


def _flag_count_for_event(event: NotationEvent) -> int:
    denominator, _dots = _event_notation(event)
    return _flag_count(denominator)


def _event_notation(event: NotationEvent) -> tuple[int, int]:
    written_duration = event.duration
    if event.tuplet is not None:
        written_duration *= Fraction(event.tuplet.actual, event.tuplet.normal)
    notation = duration_notation(written_duration)
    if notation is None:
        _layout_fail(f"event {event.id!r} has an unsupported written duration {written_duration}")
    return notation


def _layout_fail(message: str) -> NoReturn:
    raise LayoutError(message)


def _flag_count(denominator: int) -> int:
    return max(1, denominator.bit_length() - 3)


def _stem_up(event: NotationEvent, positions: list[int]) -> bool:
    if event.stem is StemDirection.UP:
        return True
    if event.stem is StemDirection.DOWN:
        return False
    return (sum(positions) / max(1, len(positions))) < 4


def _lyric_elements(
    lyrics: tuple[LyricSyllable, ...],
    *,
    x: int,
    rows: StaffRows,
) -> tuple[LayoutElement, ...]:
    elements: list[LayoutElement] = []
    for lyric in lyrics:
        if lyric.verse >= len(rows.lyric_rows):
            continue
        width = max(1, display_width(lyric.text))
        elements.append(
            LayoutElement(
                ElementKey(lyric.id, ElementRole.LYRIC),
                Rect(x, rows.lyric_rows[lyric.verse], width),
                lyric.text,
            ),
        )
        if lyric.extender:
            elements.append(
                LayoutElement(
                    ElementKey(lyric.id, ElementRole.LYRIC_EXTENDER),
                    Rect(x + width, rows.lyric_rows[lyric.verse], 2),
                ),
            )
    return tuple(elements)


def _lyric_connector_elements(
    lyrics: dict[str, tuple[LyricSyllable, ...]],
    *,
    event_xs: dict[str, int],
    rows: StaffRows,
) -> tuple[LayoutElement, ...]:
    by_verse: dict[int, list[tuple[int, LyricSyllable]]] = {}
    for event_id, event_lyrics in lyrics.items():
        if event_id not in event_xs:
            continue
        for lyric in event_lyrics:
            by_verse.setdefault(lyric.verse, []).append((event_xs[event_id], lyric))
    elements: list[LayoutElement] = []
    for verse, values in by_verse.items():
        ordered = sorted(values, key=lambda item: (item[0], item[1].id))
        for (x, lyric), (next_x, _next_lyric) in pairwise(ordered):
            if lyric.syllabic not in {Syllabic.BEGIN, Syllabic.MIDDLE}:
                continue
            right = x + display_width(lyric.text)
            if next_x - right < 2 or verse >= len(rows.lyric_rows):
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
) -> tuple[tuple[int, LayoutElement], ...]:
    role = ElementRole.TIE if kind is SpanKind.TIE else ElementRole.SLUR
    segments: list[tuple[int, LayoutElement]] = []
    segment_index = 0
    for system_index in range(start.system_index, end.system_index + 1):
        system = systems[system_index]
        left, right = _staff_horizontal_bounds(system, staff_id)
        segment_left = start.x + 1 if system_index == start.system_index else left
        segment_right = end.x - 1 if system_index == end.system_index else right
        if segment_right < segment_left:
            continue
        y = _span_row(system, staff_id=staff_id, role=role)
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


def _span_row(system: ScoreSystem, *, staff_id: str, role: ElementRole) -> int:
    rows = next(row for row in system.staff_rows if row.staff_id == staff_id)
    if role is ElementRole.SLUR:
        if not rows.slur_rows:
            _layout_fail(f"staff {staff_id!r} requires an unallocated slur row")
        return rows.slur_rows[0]
    if not rows.tie_rows:
        _layout_fail(f"staff {staff_id!r} requires an unallocated tie row")
    return rows.tie_rows[0]


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


def _state_at(staff: NotationStaff, measure_index: int) -> _ScoreState:
    clef = staff.clef
    time = TimeSignature()
    key = KeySignature()
    for measure in staff.measures[: measure_index + 1]:
        clef = measure.clef or clef
        time = measure.time_signature or time
        key = measure.key_signature or key
    return _ScoreState(clef=clef, time=time, key=key)


def _visible_accidentals(staff: NotationStaff, measure_index: int) -> dict[str, frozenset[WrittenPitch]]:
    defaults = _key_signature_alters(_state_at(staff, measure_index).key)
    active: dict[tuple[PitchStep, int], int] = {}
    visible: dict[str, frozenset[WrittenPitch]] = {}
    events = sorted(staff.measures[measure_index].events, key=lambda event: (event.onset, event.voice, event.id))
    for event in events:
        event_visible: set[WrittenPitch] = set()
        for pitch in sorted(event.pitches, key=_diatonic_number):
            key = (pitch.step, pitch.octave)
            current = active.get(key, defaults.get(pitch.step, 0))
            if pitch.accidental is not AccidentalDisplay.AUTO or pitch.alter != current:
                event_visible.add(pitch)
            active[key] = pitch.alter
        visible[event.id] = frozenset(event_visible)
    return visible


def _key_signature_alters(key: KeySignature) -> dict[PitchStep, int]:
    order = (
        (PitchStep.F, PitchStep.C, PitchStep.G, PitchStep.D, PitchStep.A, PitchStep.E, PitchStep.B)
        if key.fifths >= 0
        else (PitchStep.B, PitchStep.E, PitchStep.A, PitchStep.D, PitchStep.G, PitchStep.C, PitchStep.F)
    )
    alter = 1 if key.fifths >= 0 else -1
    return dict.fromkeys(order[: abs(key.fifths)], alter)


def _maximum_key_signature_width(score: NotationScore) -> int:
    return max(
        (
            abs(_state_at(staff, measure_index).key.fifths)
            for staff in score.staffs
            for measure_index in range(len(staff.measures))
        ),
        default=0,
    )


def _key_signature_elements(
    source_id: str,
    *,
    fifths: int,
    clef: Clef,
    x: int,
    rows: StaffRows,
    index_offset: int = 0,
) -> tuple[LayoutElement, ...]:
    if fifths == 0:
        return ()
    positions = _key_signature_positions(clef=clef, sharp=fifths > 0)
    value = "sharp" if fifths > 0 else "flat"
    return tuple(
        LayoutElement(
            ElementKey(source_id, ElementRole.KEY_SIGNATURE, index_offset + index),
            Rect(x + index, rows.line_rows[-1] - position),
            value,
        )
        for index, position in enumerate(positions[: abs(fifths)])
    )


def _key_signature_positions(*, clef: Clef, sharp: bool) -> tuple[int, ...]:
    treble = (8, 5, 9, 6, 3, 7, 4) if sharp else (4, 7, 3, 6, 2, 5, 1)
    if clef is Clef.TREBLE:
        return treble
    return tuple(position - 2 for position in treble)


def _staff_position(pitch: WrittenPitch, *, clef: Clef) -> int:
    bottom = WrittenPitch(PitchStep.E, 4) if clef is Clef.TREBLE else WrittenPitch(PitchStep.G, 2)
    return _diatonic_number(pitch) - _diatonic_number(bottom)


def _diatonic_number(pitch: WrittenPitch) -> int:
    steps = {
        PitchStep.C: 0,
        PitchStep.D: 1,
        PitchStep.E: 2,
        PitchStep.F: 3,
        PitchStep.G: 4,
        PitchStep.A: 5,
        PitchStep.B: 6,
    }
    return (pitch.octave * 7) + steps[pitch.step]


def _chord_has_second(pitches: tuple[WrittenPitch, ...]) -> bool:
    positions = sorted(_diatonic_number(pitch) for pitch in pitches)
    return any(right - left == 1 for left, right in pairwise(positions))


def _chord_offsets(positions: list[int]) -> tuple[int, ...]:
    offsets: list[int] = []
    previous: int | None = None
    previous_offset = 0
    for position in positions:
        offset = 1 - previous_offset if previous is not None and position - previous == 1 else 0
        offsets.append(offset)
        previous = position
        previous_offset = offset
    return tuple(offsets)


def _slot_id(index: int) -> str:
    return f"measure-slot:{index}"


def _slot_index(value: str) -> int:
    return int(value.rsplit(":", 1)[1])
