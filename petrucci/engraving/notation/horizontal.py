from __future__ import annotations

from fractions import Fraction

from petrucci.core.score import (
    BeamKind,
    Clef,
    EventKind,
    LyricSyllable,
    NotationEvent,
    NotationMeasure,
    NotationScore,
    NotationStaff,
    WrittenPitch,
)
from petrucci.engraving.layout.engine import LayoutError, LayoutMetrics, LayoutViewport, NotationLayoutPolicy
from petrucci.engraving.layout.fitting import BoxFitOptions, MeasuredBox, fit_measured_boxes
from petrucci.engraving.notation.annotations import _lyric_lines_by_measure, _lyrics_by_event
from petrucci.engraving.notation.elements import (
    _accidental_width,
    _event_notation,
    _event_pitch_label,
    _stem_up,
)
from petrucci.engraving.notation.state import (
    _chord_has_second,
    _maximum_key_signature_width,
    _slot_id,
    _staff_position,
    _state_at,
    _visible_accidentals,
)
from petrucci.engraving.notation.types import _HorizontalPlan, _MeasureGeometry, _OnsetGroup
from petrucci.terminal.display import display_width


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
        options=BoxFitOptions(
            available_width=available,
            gap=metrics.measure_gap,
            justify=policy.justify,
            justify_last_system=policy.justify_last_system,
            max_stretch_per_box=metrics.max_measure_stretch,
        ),
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
    lyric_lines = _lyric_lines_by_measure(staff.lyric_lines) if policy.show_lyrics else {}
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
    line_width = max((display_width(line.text) for line in lyric_lines.get(measure.id, ())), default=0)
    min_width = max(min_width, fixed + line_width)
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
        lane_widths = tuple(
            _event_lane_width(event, width, show_stems=policy.show_stems)
            for event, width in zip(events, event_widths, strict=True)
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
    if (
        left.kind is EventKind.REST
        or right.kind is EventKind.REST
        or policy.show_pitch_labels
        or (left.dynamic and right.dynamic)
        or (left.tuplet is not None and right.tuplet is not None)
        or (left.grace and right.grace)
    ):
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
    mark_width = int(event.ornament is not None) + int(event.harmonic) + display_width(event.fingering or "")
    return max(notation_width, display_width(event.dynamic or ""), pitch_label_width, mark_width)


def _event_lane_width(event: NotationEvent, width: int, *, show_stems: bool) -> int:
    if event.kind is EventKind.REST:
        return width
    width = max(width, 2)
    if not show_stems:
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
    measure = staff.measures[index]
    proportion_width = (
        len(f"{measure.proportion.numerator}:{measure.proportion.denominator}") + 1
        if measure.proportion is not None
        else 0
    )
    if index == 0:
        return proportion_width
    previous = _state_at(staff, index - 1)
    width = 0
    if measure.clef is not None and measure.clef != previous.clef:
        width += 3
    if measure.key_signature is not None and measure.key_signature != previous.key:
        width += max(1, abs(measure.key_signature.fifths)) + 1
    if measure.time_signature is not None and measure.time_signature != previous.time:
        width += 4
    return width + proportion_width
