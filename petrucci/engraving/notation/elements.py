from __future__ import annotations

from collections.abc import Iterable
from fractions import Fraction
from typing import NoReturn

from petrucci.core.score import (
    AccidentalDisplay,
    BeamKind,
    Clef,
    EventKind,
    LyricSyllable,
    NotationEvent,
    StemDirection,
    WrittenPitch,
    duration_notation,
)
from petrucci.engraving.layout.engine import (
    ElementKey,
    ElementRole,
    LayoutElement,
    LayoutError,
    NotationLayoutPolicy,
    Rect,
    StaffRows,
)
from petrucci.engraving.notation.state import _chord_offsets, _diatonic_number, _staff_position
from petrucci.terminal.display import display_width

_BEAM_LANE_HEIGHT = 3


def _unplaced_event_markers(
    events: tuple[NotationEvent, ...],
    *,
    right: int,
    rows: StaffRows,
    clef: Clef,
) -> tuple[LayoutElement, ...]:
    markers: list[LayoutElement] = []
    for index, event in enumerate(events):
        marker_x = max(0, right - index)
        y = _event_marker_y(event, rows=rows, clef=clef)
        markers.append(
            LayoutElement(
                ElementKey(event.id, ElementRole.CLIP_MARKER, 2048 + index),
                Rect(marker_x, y),
                "right",
            ),
        )
    return tuple(markers)


def _event_marker_y(event: NotationEvent, *, rows: StaffRows, clef: Clef | None = None) -> int:
    if event.kind is EventKind.REST or clef is None:
        return rows.line_rows[2]
    position = _staff_position(event.pitches[0], clef=clef)
    return min(rows.notation_bottom, max(rows.notation_top, rows.line_rows[-1] - position))


def _event_elements(
    event: NotationEvent,
    *,
    x: int,
    rows: StaffRows,
    clef: Clef,
    accidental_pitches: frozenset[WrittenPitch],
    policy: NotationLayoutPolicy,
    stem_up_override: bool | None,
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
            stem_up_override=stem_up_override,
        )
    presentation = _event_presentation_elements(
        event,
        x=x,
        rows=rows,
        show_pitch_labels=policy.show_pitch_labels,
    )
    return (*elements, *presentation), clipped


def _event_presentation_elements(
    event: NotationEvent,
    *,
    x: int,
    rows: StaffRows,
    show_pitch_labels: bool,
) -> tuple[LayoutElement, ...]:
    return (
        *_pitch_label_elements(event, x=x, rows=rows, show=show_pitch_labels),
        *_event_cue_elements(event, x=x, rows=rows),
        *_event_mark_elements(event, x=x, rows=rows),
    )


def _pitch_label_elements(
    event: NotationEvent,
    *,
    x: int,
    rows: StaffRows,
    show: bool,
) -> tuple[LayoutElement, ...]:
    if not show or event.kind is not EventKind.NOTE:
        return ()
    if rows.pitch_label_row is None:
        _layout_fail(f"event {event.id!r} requires an unallocated pitch-label row")
    label = _event_pitch_label(event)
    return (
        LayoutElement(
            ElementKey(event.id, ElementRole.PITCH_LABEL),
            Rect(x, rows.pitch_label_row, max(1, display_width(label))),
            label,
        ),
    )


def _event_cue_elements(
    event: NotationEvent,
    *,
    x: int,
    rows: StaffRows,
) -> tuple[LayoutElement, ...]:
    elements: list[LayoutElement] = []
    if event.grace:
        if rows.grace_row is None:
            _layout_fail(f"event {event.id!r} requires an unallocated grace row")
        elements.append(
            LayoutElement(ElementKey(event.id, ElementRole.GRACE), Rect(x, rows.grace_row), "grace"),
        )
    return tuple(elements)


def _event_mark_elements(
    event: NotationEvent,
    *,
    x: int,
    rows: StaffRows,
) -> tuple[LayoutElement, ...]:
    return (
        *_dynamic_elements(event, x=x, rows=rows),
        *_fermata_elements(event, x=x, rows=rows),
        *_ornament_elements(event, x=x, rows=rows),
        *_technique_elements(event, x=x, rows=rows),
    )


def _dynamic_elements(event: NotationEvent, *, x: int, rows: StaffRows) -> tuple[LayoutElement, ...]:
    if event.dynamic:
        if rows.dynamic_row is None:
            _layout_fail(f"event {event.id!r} requires an unallocated dynamic row")
        return (
            LayoutElement(
                ElementKey(event.id, ElementRole.DYNAMIC),
                Rect(x, rows.dynamic_row, max(1, display_width(event.dynamic))),
                event.dynamic,
            ),
        )
    return ()


def _fermata_elements(event: NotationEvent, *, x: int, rows: StaffRows) -> tuple[LayoutElement, ...]:
    if event.fermata:
        if rows.fermata_row is None:
            _layout_fail(f"event {event.id!r} requires an unallocated fermata row")
        return (LayoutElement(ElementKey(event.id, ElementRole.FERMATA), Rect(x, rows.fermata_row)),)
    return ()


def _ornament_elements(event: NotationEvent, *, x: int, rows: StaffRows) -> tuple[LayoutElement, ...]:
    if event.ornament is not None:
        if rows.ornament_row is None:
            _layout_fail(f"event {event.id!r} requires an unallocated ornament row")
        return (
            LayoutElement(
                ElementKey(event.id, ElementRole.ORNAMENT),
                Rect(x, rows.ornament_row),
                event.ornament.value,
            ),
        )
    return ()


def _technique_elements(event: NotationEvent, *, x: int, rows: StaffRows) -> tuple[LayoutElement, ...]:
    elements: list[LayoutElement] = []
    mark_x = x + int(event.ornament is not None)
    if event.harmonic:
        if rows.ornament_row is None:
            _layout_fail(f"event {event.id!r} requires an unallocated ornament row")
        elements.append(
            LayoutElement(ElementKey(event.id, ElementRole.HARMONIC), Rect(mark_x, rows.ornament_row), "H"),
        )
        mark_x += 1
    if event.fingering is not None:
        if rows.ornament_row is None:
            _layout_fail(f"event {event.id!r} requires an unallocated ornament row")
        elements.append(
            LayoutElement(
                ElementKey(event.id, ElementRole.FINGERING),
                Rect(mark_x, rows.ornament_row, max(1, display_width(event.fingering))),
                event.fingering,
            ),
        )
    return tuple(elements)


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
    stem_up_override: bool | None,
) -> tuple[tuple[LayoutElement, ...], bool]:
    pitches = sorted(event.pitches, key=_diatonic_number)
    positions = [_staff_position(pitch, clef=clef) for pitch in pitches]
    offsets = _chord_offsets(positions)
    elements: list[LayoutElement] = []
    clipped = False
    head_points: list[tuple[int, int]] = []
    pitch_points: list[tuple[WrittenPitch, int, int, int, bool, bool]] = []
    for pitch, position, offset in zip(pitches, positions, offsets, strict=True):
        raw_y = rows.line_rows[-1] - position
        y = min(rows.notation_bottom, max(rows.notation_top, raw_y))
        pitch_clipped = y != raw_y
        clipped = clipped or pitch_clipped
        show_accidental = pitch in accidental_pitches
        accidental_width = _accidental_width(pitch) if show_accidental else 0
        bracket_offset = 1 if event.editorial_brackets else 0
        head_x = x + offset + accidental_width + bracket_offset
        head_points.append((head_x, y))
        pitch_points.append((pitch, position, head_x, y, show_accidental, pitch_clipped))
    dot_x = max((head_x for head_x, _y in head_points), default=x) + (2 if event.editorial_brackets else 1)
    for index, (pitch, position, head_x, y, show_accidental, pitch_clipped) in enumerate(pitch_points):
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
                dot_x=dot_x,
                show_accidental=show_accidental,
                editorial_brackets=event.editorial_brackets,
            )
        )
        if pitch_clipped:
            elements.append(
                LayoutElement(
                    ElementKey(event.id, ElementRole.CLIP_MARKER, index),
                    Rect(head_x, y),
                    "above" if y == rows.notation_top else "below",
                ),
            )
    stems = (
        _stem_elements(
            event,
            head_points=head_points,
            positions=positions,
            rows=rows,
            denominator=denominator,
            up_override=stem_up_override,
        )
        if show_stems
        else ()
    )
    elements.extend(stems)
    if denominator >= 8 and event.beam is BeamKind.NONE and stems:
        elements.extend(_flag_elements(event, stem=stems[0], denominator=denominator, rows=rows))
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
    dot_x: int,
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
        elements.append(
            LayoutElement(
                ElementKey(event.id, ElementRole.DOT, pitch_index),
                Rect(dot_x, y, dots),
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
    up_override: bool | None,
) -> tuple[LayoutElement, ...]:
    if not head_points or denominator <= 1:
        return ()
    up = _stem_up(event, positions) if up_override is None else up_override
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
    *,
    lanes: dict[str, tuple[bool, int]],
    rows: StaffRows,
    left: int,
    right: int,
) -> tuple[LayoutElement, ...]:
    stems = {element.key.source_id: element for element in elements if element.key.role is ElementRole.STEM}
    beams: list[LayoutElement] = []
    for group in _beam_groups(events):
        group_stems = [stems[event.id] for event in group if event.id in stems]
        if not group_stems:
            continue
        up, lane = lanes[group[0].id]
        beam_y = (
            rows.notation_top + (lane * _BEAM_LANE_HEIGHT) if up else rows.notation_bottom - (lane * _BEAM_LANE_HEIGHT)
        )
        beams.extend(_beam_stem_extensions(group_stems, up=up, beam_y=beam_y))
        if len(group_stems) >= 2:
            beams.extend(_complete_beam_elements(group, group_stems, up=up, beam_y=beam_y))
        elif group[0].beam is not BeamKind.NONE:
            beams.extend(
                _partial_beam_elements(group[0], group_stems[0], up=up, beam_y=beam_y, left=left, right=right),
            )
    return tuple(beams)


def _beam_stem_extensions(
    stems: list[LayoutElement],
    *,
    up: bool,
    beam_y: int,
) -> tuple[LayoutElement, ...]:
    extensions: list[LayoutElement] = []
    for stem in stems:
        top = min(beam_y, stem.rect.y)
        bottom = max(beam_y, stem.rect.bottom)
        extensions.append(
            LayoutElement(
                ElementKey(stem.key.source_id, ElementRole.STEM, 1),
                Rect(stem.rect.x, top, 1, bottom - top + 1),
                "up" if up else "down",
            ),
        )
    return tuple(extensions)


def _events_by_voice(events: tuple[NotationEvent, ...]) -> tuple[tuple[NotationEvent, ...], ...]:
    voices = sorted({event.voice for event in events})
    return tuple(
        tuple(sorted((event for event in events if event.voice == voice), key=lambda event: (event.onset, event.id)))
        for voice in voices
    )


def _beam_groups(events: tuple[NotationEvent, ...]) -> tuple[tuple[NotationEvent, ...], ...]:
    groups: list[tuple[NotationEvent, ...]] = []
    for voice_events in _events_by_voice(events):
        groups.extend(_voice_beam_groups(voice_events))
    return tuple(groups)


def _voice_beam_groups(events: tuple[NotationEvent, ...]) -> tuple[tuple[NotationEvent, ...], ...]:
    groups: list[tuple[NotationEvent, ...]] = []
    active: list[NotationEvent] = []
    for event in events:
        if event.beam is BeamKind.START:
            _flush_beam_group(groups, active)
            active = [event]
        elif event.beam is BeamKind.CONTINUE and active:
            active.append(event)
        elif event.beam is BeamKind.END and active:
            groups.append((*active, event))
            active = []
        elif event.beam in {BeamKind.PARTIAL_FORWARD, BeamKind.PARTIAL_BACKWARD}:
            groups.append((event,))
    _flush_beam_group(groups, active)
    return tuple(groups)


def _flush_beam_group(groups: list[tuple[NotationEvent, ...]], active: list[NotationEvent]) -> None:
    if active:
        groups.append(tuple(active))


def _complete_beam_elements(
    events: tuple[NotationEvent, ...],
    stems: list[LayoutElement],
    *,
    up: bool,
    beam_y: int,
) -> tuple[LayoutElement, ...]:
    start_x = min(stem.rect.x for stem in stems)
    end_x = max(stem.rect.x for stem in stems)
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


def _partial_beam_elements(
    event: NotationEvent,
    stem: LayoutElement,
    *,
    up: bool,
    beam_y: int,
    left: int,
    right: int,
) -> tuple[LayoutElement, ...]:
    forward = event.beam in {BeamKind.START, BeamKind.CONTINUE, BeamKind.PARTIAL_FORWARD}
    start_x = stem.rect.x if forward else max(left, stem.rect.x - 2)
    end_x = min(right, stem.rect.x + 2) if forward else stem.rect.x
    return tuple(
        LayoutElement(
            ElementKey(event.id, ElementRole.BEAM, index),
            Rect(start_x, beam_y + (index if up else -index), max(1, end_x - start_x + 1)),
            "partial",
        )
        for index in range(_flag_count_for_event(event))
    )


def _tuplet_elements(
    events: tuple[NotationEvent, ...],
    event_xs: dict[str, int],
    *,
    rows: StaffRows,
    right: int,
) -> tuple[LayoutElement, ...]:
    groups = _tuplet_groups(events)
    if not groups:
        return ()
    if not rows.tuplet_rows:
        _layout_fail("tuplet events require an unallocated tuplet row")
    elements: list[LayoutElement] = []
    for group in groups:
        first = group[0]
        ratio = first.tuplet
        if ratio is None or first.id not in event_xs:
            continue
        left = event_xs[first.id]
        last_x = event_xs.get(group[-1].id, left)
        natural_right = max(left + 2, last_x)
        elements.append(
            LayoutElement(
                ElementKey(first.id, ElementRole.TUPLET),
                Rect(left, rows.tuplet_rows[0], max(1, min(right, natural_right) - left + 1)),
                f"{ratio.actual}:{ratio.normal}",
            ),
        )
    return tuple(elements)


def _tuplet_groups(events: tuple[NotationEvent, ...]) -> tuple[tuple[NotationEvent, ...], ...]:
    groups: list[tuple[NotationEvent, ...]] = []
    for voice_events in _events_by_voice(events):
        groups.extend(_voice_tuplet_groups(voice_events))
    return tuple(groups)


def _voice_tuplet_groups(events: tuple[NotationEvent, ...]) -> tuple[tuple[NotationEvent, ...], ...]:
    groups: list[tuple[NotationEvent, ...]] = []
    active: list[NotationEvent] = []
    for event in events:
        if event.tuplet is None:
            if active:
                groups.append(tuple(active))
                active = []
        elif active and event.tuplet == active[-1].tuplet:
            active.append(event)
        else:
            if active:
                groups.append(tuple(active))
            active = [event]
    if active:
        groups.append(tuple(active))
    return tuple(groups)


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
    right: int,
    rows: StaffRows,
) -> tuple[LayoutElement, ...]:
    elements: list[LayoutElement] = []
    for lyric in lyrics:
        if lyric.verse >= len(rows.lyric_rows):
            continue
        if x > right:
            elements.append(
                LayoutElement(
                    ElementKey(lyric.id, ElementRole.CLIP_MARKER),
                    Rect(right, rows.lyric_rows[lyric.verse]),
                    "right",
                ),
            )
            continue
        natural_width = max(1, display_width(lyric.text))
        width = max(1, min(natural_width, right - x + 1))
        lyric_x = x
        elements.append(
            LayoutElement(
                ElementKey(lyric.id, ElementRole.LYRIC),
                Rect(lyric_x, rows.lyric_rows[lyric.verse], width),
                lyric.text,
            ),
        )
        if natural_width > width:
            elements.append(
                LayoutElement(
                    ElementKey(lyric.id, ElementRole.CLIP_MARKER),
                    Rect(right, rows.lyric_rows[lyric.verse]),
                    "right",
                ),
            )
        if lyric.extender:
            extender_x = min(right, lyric_x + width)
            elements.append(
                LayoutElement(
                    ElementKey(lyric.id, ElementRole.LYRIC_EXTENDER),
                    Rect(extender_x, rows.lyric_rows[lyric.verse], max(1, min(2, right - extender_x + 1))),
                ),
            )
    return tuple(elements)
