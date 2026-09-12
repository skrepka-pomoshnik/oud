"""Source-neutral timed-event adaptation for live score consumers."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from enum import StrEnum
from fractions import Fraction
from itertools import pairwise
from typing import NoReturn, TypeVar

from petrucci.core.score import (
    BeamKind,
    Clef,
    EventKind,
    KeySignature,
    LyricSyllable,
    NotationEvent,
    NotationMeasure,
    NotationScore,
    NotationSpan,
    NotationStaff,
    ScoreValidationError,
    SpanKind,
    Syllabic,
    TimeSignature,
    WrittenPitch,
    duration_notation,
    pitch_from_midi,
)

_GENERATED_MARKER = "#petrucci-"
_SEGMENT_MARKER = f"{_GENERATED_MARKER}segment-"
_T = TypeVar("_T")


class FlowAdapterError(ValueError):
    """Raised when a timed event cannot be represented without guessing."""


class FlowBeamPolicy(StrEnum):
    """Automatic beam behavior for adapted flow events."""

    NONE = "none"
    METER = "meter"


@dataclass(frozen=True, slots=True)
class FlowEvent:
    """A caller-owned event timed in units of the active meter beat."""

    id: str
    onset: Fraction
    duration: Fraction
    midi_pitches: tuple[int, ...] = ()
    voice: int = 0
    lyric: str | None = None
    syllabic: Syllabic = Syllabic.SINGLE
    written_pitches: tuple[WrittenPitch, ...] = ()
    beam: BeamKind | None = None

    def __post_init__(self) -> None:
        _validate_flow_event_identity(self)
        _validate_flow_event_timing(self)
        _validate_flow_event_content(self)


@dataclass(frozen=True, slots=True)
class FlowMeasure:
    """An explicit measure whose event times use its active meter beat."""

    id: str
    events: tuple[FlowEvent, ...]
    time_signature: TimeSignature | None = None
    beat_capacity: Fraction | None = None
    number: int | None = None
    key_signature: KeySignature | None = None
    clef: Clef | None = None
    irregular: bool = False

    def __post_init__(self) -> None:
        _validate_flow_measure_identity(self)
        _validate_flow_measure_timing(self)
        _validate_flow_measure_state(self)


@dataclass(frozen=True, slots=True)
class FlowScoreOptions:
    score_id: str = "flow-score"
    staff_id: str = "flow-staff"
    measure_id_prefix: str = "flow-measure"
    time_signature: TimeSignature = field(default_factory=TimeSignature)
    title: str | None = None
    staff_label: str | None = None
    beam_policy: FlowBeamPolicy = FlowBeamPolicy.NONE
    key_signature: KeySignature | None = None
    clef: Clef = Clef.TREBLE

    def __post_init__(self) -> None:
        for label, value in (
            ("score ID", self.score_id),
            ("staff ID", self.staff_id),
            ("measure ID prefix", self.measure_id_prefix),
        ):
            if not isinstance(value, str) or not value:
                _fail(f"flow {label} must be a non-empty string")
        if not isinstance(self.time_signature, TimeSignature):
            _fail("flow time signature must be a TimeSignature")
        if not isinstance(self.beam_policy, FlowBeamPolicy):
            _fail("flow beam policy must be a FlowBeamPolicy")
        if self.key_signature is not None and not isinstance(self.key_signature, KeySignature):
            _fail("flow key signature must be a KeySignature")
        if not isinstance(self.clef, Clef):
            _fail("flow clef must be a Clef")


@dataclass(frozen=True, slots=True)
class FlowSegmentMap:
    notation_event_id: str
    onset: Fraction
    duration: Fraction


@dataclass(frozen=True, slots=True)
class FlowEventMap:
    source_event_id: str
    onset: Fraction
    duration: Fraction
    notation_event_ids: tuple[str, ...]
    segments: tuple[FlowSegmentMap, ...] = ()


@dataclass(frozen=True, slots=True)
class FlowScore:
    """Canonical score plus stable source-to-segment identity."""

    score: NotationScore
    events: tuple[FlowEventMap, ...]
    measure_capacity: Fraction | None
    measure_capacities: tuple[Fraction, ...] = ()

    def notation_ids_for(self, source_event_id: str) -> tuple[str, ...]:
        mapping = next((item for item in self.events if item.source_event_id == source_event_id), None)
        return mapping.notation_event_ids if mapping is not None else ()

    def active_event_ids(self, position: Fraction) -> tuple[str, ...]:
        _validate_fraction(position, "flow position", allow_zero=True)
        return tuple(
            item.source_event_id for item in self.events if item.onset <= position < item.onset + item.duration
        )

    def active_notation_event_ids(self, position: Fraction) -> tuple[str, ...]:
        """Return the visible segment IDs active at an exact flow position."""

        _validate_fraction(position, "flow position", allow_zero=True)
        return tuple(
            segment.notation_event_id
            for item in self.events
            for segment in item.segments
            if segment.onset <= position < segment.onset + segment.duration
        )

    def expand_values(self, values: Mapping[str, _T]) -> dict[str, _T]:
        """Expand caller values from source IDs to every split notation segment."""

        unknown = set(values) - {item.source_event_id for item in self.events}
        if unknown:
            _fail(f"flow values reference unknown event IDs: {', '.join(sorted(unknown))}")
        return {
            notation_id: values[item.source_event_id]
            for item in self.events
            if item.source_event_id in values
            for notation_id in item.notation_event_ids
        }


def adapt_flow_events(
    events: tuple[FlowEvent, ...],
    *,
    options: FlowScoreOptions | None = None,
) -> FlowScore:
    """Split exact timed events at fixed-meter boundaries and build a canonical score."""

    _validate_event_sequence(events)
    active = options or FlowScoreOptions()
    measure_capacity = Fraction(active.time_signature.beats)
    measure_count = max(_measure_count(event, measure_capacity) for event in events)
    measures, spans, lyrics, mappings = _flow_parts(events, active, measure_count, measure_capacity)
    split_ids = {item.source_event_id for item in mappings if len(item.notation_event_ids) > 1}
    notation_measures = tuple(
        NotationMeasure(
            id=f"{active.measure_id_prefix}:{index + 1}",
            number=index + 1,
            events=_apply_meter_beams(
                tuple(sorted(measure, key=lambda item: (item.onset, item.voice, item.id))),
                active.time_signature,
                active.beam_policy,
                split_ids,
                {event.id for event in events if event.beam is not None},
            ),
            time_signature=active.time_signature if index == 0 else None,
            key_signature=active.key_signature if index == 0 else None,
        )
        for index, measure in enumerate(measures)
    )
    score = _build_score(notation_measures, spans, lyrics, active)
    return FlowScore(
        score,
        tuple(mappings),
        measure_capacity,
        tuple(measure_capacity for _ in notation_measures),
    )


def adapt_flow_measures(
    measures: tuple[FlowMeasure, ...],
    *,
    options: FlowScoreOptions | None = None,
) -> FlowScore:
    """Build a score from explicit measure boundaries, pickups, and state changes."""

    _validate_flow_measures(measures)
    active = options or FlowScoreOptions()
    meter = active.time_signature
    timeline = Fraction(0)
    notation_measures: list[NotationMeasure] = []
    spans: list[NotationSpan] = []
    lyrics: list[LyricSyllable] = []
    mappings: list[FlowEventMap] = []
    capacities: list[Fraction] = []
    for index, measure in enumerate(measures):
        meter = measure.time_signature or meter
        notation, measure_mappings, measure_lyrics, capacity = _adapt_explicit_measure(
            measure,
            index=index,
            meter=meter,
            timeline=timeline,
            options=active,
        )
        notation_measures.append(notation)
        mappings.extend(measure_mappings)
        lyrics.extend(measure_lyrics)
        capacities.append(capacity)
        timeline += capacity
    score = _build_score(tuple(notation_measures), spans, lyrics, active)
    uniform_capacity = capacities[0] if len(set(capacities)) == 1 else None
    return FlowScore(score, tuple(mappings), uniform_capacity, tuple(capacities))


def _adapt_explicit_measure(
    measure: FlowMeasure,
    *,
    index: int,
    meter: TimeSignature,
    timeline: Fraction,
    options: FlowScoreOptions,
) -> tuple[NotationMeasure, list[FlowEventMap], list[LyricSyllable], Fraction]:
    capacity = measure.beat_capacity or Fraction(meter.beats)
    events, mappings, lyrics = _explicit_measure_events(measure, meter, timeline, capacity)
    events = list(
        _apply_meter_beams(
            tuple(sorted(events, key=lambda item: (item.onset, item.voice, item.id))),
            meter,
            options.beam_policy,
            set(),
            {event.id for event in measure.events if event.beam is not None},
        )
    )
    notation = NotationMeasure(
        id=measure.id,
        number=index + 1 if measure.number is None else measure.number,
        events=tuple(events),
        time_signature=_explicit_time_signature(measure, options, index),
        key_signature=(measure.key_signature or options.key_signature) if index == 0 else measure.key_signature,
        clef=measure.clef,
        irregular=measure.irregular or capacity != meter.beats,
    )
    return notation, mappings, lyrics, capacity


def _explicit_measure_events(
    measure: FlowMeasure,
    meter: TimeSignature,
    timeline: Fraction,
    capacity: Fraction,
) -> tuple[list[NotationEvent], list[FlowEventMap], list[LyricSyllable]]:
    notation_events: list[NotationEvent] = []
    mappings: list[FlowEventMap] = []
    lyrics: list[LyricSyllable] = []
    for event in measure.events:
        if event.onset + event.duration > capacity:
            _fail(f"flow event {event.id!r} crosses explicit measure {measure.id!r}")
        notation_events.append(_notation_event(event, event.id, event.onset, event.duration, meter.beat_unit))
        segment = FlowSegmentMap(event.id, timeline + event.onset, event.duration)
        mappings.append(FlowEventMap(event.id, segment.onset, event.duration, (event.id,), (segment,)))
        if event.lyric is not None:
            lyrics.append(_event_lyric(event, event.id))
    return notation_events, mappings, lyrics


def _explicit_time_signature(
    measure: FlowMeasure,
    options: FlowScoreOptions,
    index: int,
) -> TimeSignature | None:
    if index == 0:
        return measure.time_signature or options.time_signature
    return measure.time_signature


def _build_score(
    measures: tuple[NotationMeasure, ...],
    spans: list[NotationSpan],
    lyrics: list[LyricSyllable],
    options: FlowScoreOptions,
) -> NotationScore:
    try:
        return NotationScore(
            id=options.score_id,
            title=options.title,
            staffs=(
                NotationStaff(
                    options.staff_id,
                    measures,
                    clef=options.clef,
                    label=options.staff_label,
                    lyrics=tuple(lyrics),
                    spans=tuple(spans),
                ),
            ),
        )
    except ScoreValidationError as exc:
        _fail(f"invalid flow score identity or timing: {exc}")


def _measure_count(event: FlowEvent, capacity: Fraction) -> int:
    end = event.onset + event.duration
    quotient, remainder = divmod(end, capacity)
    return int(quotient + bool(remainder))


def _flow_parts(
    events: tuple[FlowEvent, ...],
    options: FlowScoreOptions,
    measure_count: int,
    measure_capacity: Fraction,
) -> tuple[list[list[NotationEvent]], list[NotationSpan], list[LyricSyllable], list[FlowEventMap]]:
    measures: list[list[NotationEvent]] = [[] for _ in range(measure_count)]
    spans: list[NotationSpan] = []
    lyrics: list[LyricSyllable] = []
    mappings: list[FlowEventMap] = []
    for event in events:
        segments = _event_segments(event, measure_capacity, options.time_signature.beat_unit)
        for measure_index, notation_event, _segment in segments:
            measures[measure_index].append(notation_event)
        segment_maps = tuple(segment for _, _, segment in segments)
        notation_ids = tuple(segment.notation_event_id for segment in segment_maps)
        spans.extend(_segment_ties(event, notation_ids))
        if event.lyric is not None:
            lyrics.append(_event_lyric(event, notation_ids[0]))
        mappings.append(FlowEventMap(event.id, event.onset, event.duration, notation_ids, segment_maps))
    return measures, spans, lyrics, mappings


def _event_lyric(event: FlowEvent, notation_event_id: str) -> LyricSyllable:
    return LyricSyllable(
        f"{event.id}{_GENERATED_MARKER}lyric",
        notation_event_id,
        event.lyric or "",
        syllabic=event.syllabic,
    )


def _event_segments(
    event: FlowEvent,
    capacity: Fraction,
    beat_unit: int,
) -> tuple[tuple[int, NotationEvent, FlowSegmentMap], ...]:
    first_segment_capacity = capacity - event.onset % capacity
    if event.duration > first_segment_capacity and event.beam not in {None, BeamKind.NONE}:
        _fail(f"flow event {event.id!r} with an explicit beam group cannot cross a measure boundary")
    segments: list[tuple[int, NotationEvent, FlowSegmentMap]] = []
    cursor = event.onset
    remaining = event.duration
    while remaining:
        measure_index = int(cursor // capacity)
        local_onset = cursor % capacity
        segment_duration = min(remaining, capacity - local_onset)
        segment_index = len(segments)
        segment_id = event.id if segment_index == 0 else f"{event.id}{_SEGMENT_MARKER}{segment_index + 1}"
        notation = _notation_event(event, segment_id, local_onset, segment_duration, beat_unit)
        segments.append((measure_index, notation, FlowSegmentMap(segment_id, cursor, segment_duration)))
        cursor += segment_duration
        remaining -= segment_duration
    return tuple(segments)


def _notation_event(
    event: FlowEvent,
    event_id: str,
    onset: Fraction,
    duration: Fraction,
    beat_unit: int,
) -> NotationEvent:
    pitches = event.written_pitches or tuple(pitch_from_midi(midi) for midi in event.midi_pitches)
    return NotationEvent(
        id=event_id,
        onset=onset / beat_unit,
        duration=duration / beat_unit,
        kind=EventKind.NOTE if pitches else EventKind.REST,
        pitches=pitches,
        voice=event.voice,
        beam=BeamKind.NONE if event.beam is None else event.beam,
    )


def _segment_ties(event: FlowEvent, notation_ids: tuple[str, ...]) -> tuple[NotationSpan, ...]:
    if not event.midi_pitches and not event.written_pitches:
        return ()
    return tuple(
        NotationSpan(f"{event.id}{_GENERATED_MARKER}tie-{index}", SpanKind.TIE, start, end)
        for index, (start, end) in enumerate(pairwise(notation_ids), start=1)
    )


def _apply_meter_beams(
    events: tuple[NotationEvent, ...],
    meter: TimeSignature,
    policy: FlowBeamPolicy,
    split_ids: set[str],
    explicit_beam_ids: set[str],
) -> tuple[NotationEvent, ...]:
    if policy is FlowBeamPolicy.NONE:
        return events
    compound_beat_unit_threshold = 8
    compound_beat_count = 3
    group_duration = Fraction(
        compound_beat_count
        if meter.beat_unit >= compound_beat_unit_threshold and meter.beats % compound_beat_count == 0
        else 1,
        meter.beat_unit,
    )
    replacements: dict[str, BeamKind] = {}
    for voice in sorted({event.voice for event in events}):
        for run in _beam_runs(events, voice, group_duration, split_ids | explicit_beam_ids):
            minimum_beam_run_events = 2
            if len(run) < minimum_beam_run_events:
                continue
            replacements[run[0].id] = BeamKind.START
            replacements[run[-1].id] = BeamKind.END
            for event in run[1:-1]:
                replacements[event.id] = BeamKind.CONTINUE
    return tuple(replace(event, beam=replacements.get(event.id, event.beam)) for event in events)


def _beam_runs(
    events: tuple[NotationEvent, ...],
    voice: int,
    group_duration: Fraction,
    excluded_ids: set[str],
) -> list[list[NotationEvent]]:
    candidates = [
        event
        for event in events
        if event.voice == voice
        and _beamable(event)
        and event.id not in excluded_ids
        and _SEGMENT_MARKER not in event.id
    ]
    runs: list[list[NotationEvent]] = []
    for event in candidates:
        bucket = event.onset // group_duration
        if not runs or not _continues_beam_run(runs[-1][-1], event, bucket, group_duration):
            runs.append([event])
        else:
            runs[-1].append(event)
    return runs


def _continues_beam_run(
    previous: NotationEvent,
    event: NotationEvent,
    bucket: int,
    group_duration: Fraction,
) -> bool:
    return (
        previous.onset + previous.duration == event.onset
        and previous.onset // group_duration == bucket
        and event.onset + event.duration <= (bucket + 1) * group_duration
    )


def _beamable(event: NotationEvent) -> bool:
    notation = duration_notation(event.duration)
    minimum_beamable_denominator = 8
    return event.kind is EventKind.NOTE and notation is not None and notation[0] >= minimum_beamable_denominator


def _validate_event_sequence(events: tuple[FlowEvent, ...]) -> None:
    if not events:
        _fail("cannot adapt an empty flow event sequence")
    if any(not isinstance(event, FlowEvent) for event in events):
        _fail("flow events must contain FlowEvent values")
    source_ids = tuple(event.id for event in events)
    if len(set(source_ids)) != len(source_ids):
        _fail("flow event IDs must be unique")


def _validate_flow_event_identity(event: FlowEvent) -> None:
    if not isinstance(event.id, str) or not event.id:
        _fail("flow event ID must be a non-empty string")
    if _GENERATED_MARKER in event.id:
        _fail(f"flow event ID cannot contain reserved marker {_GENERATED_MARKER!r}")


def _validate_flow_event_timing(event: FlowEvent) -> None:
    _validate_fraction(event.onset, "flow event onset", allow_zero=True)
    _validate_fraction(event.duration, "flow event duration", allow_zero=False)
    if event.voice < 0:
        _fail("flow event voice must be non-negative")


def _validate_flow_event_content(event: FlowEvent) -> None:
    if event.midi_pitches and event.written_pitches:
        _fail(f"flow event {event.id!r} cannot contain both MIDI and written pitches")
    _validate_midi_pitches(event)
    _validate_written_pitches(event)
    if event.lyric is not None and not event.lyric:
        _fail("flow event lyric must be non-empty when present")
    if not isinstance(event.syllabic, Syllabic):
        _fail("flow event syllabic value must be a Syllabic")
    if event.beam is not None and not isinstance(event.beam, BeamKind):
        _fail("flow event beam must be a BeamKind or None")


def _validate_midi_pitches(event: FlowEvent) -> None:
    if len(set(event.midi_pitches)) != len(event.midi_pitches):
        _fail(f"flow event {event.id!r} contains a duplicate MIDI pitch")
    midi_min = 0
    midi_max = 127
    if any(not isinstance(midi, int) or not midi_min <= midi <= midi_max for midi in event.midi_pitches):
        _fail("flow event MIDI pitches must be integers between 0 and 127")


def _validate_written_pitches(event: FlowEvent) -> None:
    if any(not isinstance(pitch, WrittenPitch) for pitch in event.written_pitches):
        _fail("flow event written pitches must be WrittenPitch values")
    if len(set(event.written_pitches)) != len(event.written_pitches):
        _fail(f"flow event {event.id!r} contains a duplicate written pitch")


def _validate_flow_measure_identity(measure: FlowMeasure) -> None:
    if not isinstance(measure.id, str) or not measure.id:
        _fail("flow measure ID must be a non-empty string")
    if _GENERATED_MARKER in measure.id:
        _fail(f"flow measure ID cannot contain reserved marker {_GENERATED_MARKER!r}")
    if any(not isinstance(event, FlowEvent) for event in measure.events):
        _fail("flow measure events must contain FlowEvent values")


def _validate_flow_measure_timing(measure: FlowMeasure) -> None:
    if measure.beat_capacity is not None:
        _validate_fraction(measure.beat_capacity, "flow measure beat capacity", allow_zero=False)
    if measure.number is not None and measure.number < 0:
        _fail("flow measure number must be non-negative")


def _validate_flow_measure_state(measure: FlowMeasure) -> None:
    if measure.time_signature is not None and not isinstance(measure.time_signature, TimeSignature):
        _fail("flow measure time signature must be a TimeSignature")
    if measure.key_signature is not None and not isinstance(measure.key_signature, KeySignature):
        _fail("flow measure key signature must be a KeySignature")
    if measure.clef is not None and not isinstance(measure.clef, Clef):
        _fail("flow measure clef must be a Clef")
    if not isinstance(measure.irregular, bool):
        _fail("flow measure irregular must be a bool")


def _validate_flow_measures(measures: tuple[FlowMeasure, ...]) -> None:
    if not measures:
        _fail("cannot adapt an empty flow measure sequence")
    if any(not isinstance(measure, FlowMeasure) for measure in measures):
        _fail("flow measures must contain FlowMeasure values")
    if len({measure.id for measure in measures}) != len(measures):
        _fail("flow measure IDs must be unique")
    all_events = tuple(event for measure in measures for event in measure.events)
    if all_events:
        _validate_event_sequence(all_events)


def _validate_fraction(value: Fraction, label: str, *, allow_zero: bool) -> None:
    if not isinstance(value, Fraction):
        _fail(f"{label} must be a Fraction")
    if value < 0 or (not allow_zero and value == 0):
        qualifier = "non-negative" if allow_zero else "positive"
        _fail(f"{label} must be {qualifier}")


def _fail(message: str) -> NoReturn:
    raise FlowAdapterError(message)


__all__ = [
    "FlowAdapterError",
    "FlowBeamPolicy",
    "FlowEvent",
    "FlowEventMap",
    "FlowMeasure",
    "FlowScore",
    "FlowScoreOptions",
    "FlowSegmentMap",
    "adapt_flow_events",
    "adapt_flow_measures",
]
