"""Source-neutral timed-event adaptation for live score consumers."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from fractions import Fraction
from itertools import pairwise
from typing import NoReturn, TypeVar

from petrucci.score import (
    EventKind,
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
    pitch_from_midi,
)

_GENERATED_MARKER = "#petrucci-"
_SEGMENT_MARKER = f"{_GENERATED_MARKER}segment-"
_T = TypeVar("_T")


class FlowAdapterError(ValueError):
    """Raised when a timed event cannot be represented without guessing."""


@dataclass(frozen=True, slots=True)
class FlowEvent:
    """A caller-owned event timed in units of the configured meter beat."""

    id: str
    onset: Fraction
    duration: Fraction
    midi_pitches: tuple[int, ...] = ()
    voice: int = 0
    lyric: str | None = None
    syllabic: Syllabic = Syllabic.SINGLE

    def __post_init__(self) -> None:
        _validate_flow_event_identity(self)
        _validate_flow_event_timing(self)
        _validate_flow_event_content(self)


@dataclass(frozen=True, slots=True)
class FlowScoreOptions:
    score_id: str = "flow-score"
    staff_id: str = "flow-staff"
    measure_id_prefix: str = "flow-measure"
    time_signature: TimeSignature = field(default_factory=TimeSignature)
    title: str | None = None
    staff_label: str | None = None

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


@dataclass(frozen=True, slots=True)
class FlowEventMap:
    source_event_id: str
    onset: Fraction
    duration: Fraction
    notation_event_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class FlowScore:
    """Canonical score plus stable source-to-segment identity."""

    score: NotationScore
    events: tuple[FlowEventMap, ...]
    measure_capacity: Fraction

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
        active: list[str] = []
        for item in self.events:
            if not item.onset <= position < item.onset + item.duration:
                continue
            segment_index = int(position // self.measure_capacity) - int(item.onset // self.measure_capacity)
            active.append(item.notation_event_ids[segment_index])
        return tuple(active)

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
    """Split exact timed events at measure boundaries and build a canonical score."""

    if not events:
        _fail("cannot adapt an empty flow event sequence")
    if any(not isinstance(event, FlowEvent) for event in events):
        _fail("flow events must contain FlowEvent values")
    source_ids = tuple(event.id for event in events)
    if len(set(source_ids)) != len(source_ids):
        _fail("flow event IDs must be unique")
    active = options or FlowScoreOptions()
    measure_capacity = Fraction(active.time_signature.beats)
    measure_count = max(_measure_count(event, measure_capacity) for event in events)
    measures, spans, lyrics, mappings = _flow_parts(events, active, measure_count, measure_capacity)
    notation_measures = tuple(
        NotationMeasure(
            id=f"{active.measure_id_prefix}:{index + 1}",
            number=index + 1,
            events=tuple(sorted(measure, key=lambda item: (item.onset, item.voice, item.id))),
            time_signature=active.time_signature if index == 0 else None,
        )
        for index, measure in enumerate(measures)
    )
    try:
        score = NotationScore(
            id=active.score_id,
            title=active.title,
            staffs=(
                NotationStaff(
                    active.staff_id,
                    notation_measures,
                    label=active.staff_label,
                    lyrics=tuple(lyrics),
                    spans=tuple(spans),
                ),
            ),
        )
    except ScoreValidationError as exc:
        _fail(f"invalid flow score identity or timing: {exc}")
    return FlowScore(score, tuple(mappings), measure_capacity)


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
        for measure_index, notation_event in segments:
            measures[measure_index].append(notation_event)
        notation_ids = tuple(notation_event.id for _, notation_event in segments)
        spans.extend(_segment_ties(event, notation_ids))
        if event.lyric is not None:
            lyrics.append(_event_lyric(event, notation_ids[0]))
        mappings.append(FlowEventMap(event.id, event.onset, event.duration, notation_ids))
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
) -> tuple[tuple[int, NotationEvent], ...]:
    segments: list[tuple[int, NotationEvent]] = []
    cursor = event.onset
    remaining = event.duration
    while remaining:
        measure_index = int(cursor // capacity)
        local_onset = cursor % capacity
        segment_duration = min(remaining, capacity - local_onset)
        segment_index = len(segments)
        segment_id = event.id if segment_index == 0 else f"{event.id}{_SEGMENT_MARKER}{segment_index + 1}"
        segments.append(
            (
                measure_index,
                NotationEvent(
                    id=segment_id,
                    onset=local_onset / beat_unit,
                    duration=segment_duration / beat_unit,
                    kind=EventKind.NOTE if event.midi_pitches else EventKind.REST,
                    pitches=tuple(pitch_from_midi(midi) for midi in event.midi_pitches),
                    voice=event.voice,
                ),
            )
        )
        cursor += segment_duration
        remaining -= segment_duration
    return tuple(segments)


def _segment_ties(event: FlowEvent, notation_ids: tuple[str, ...]) -> tuple[NotationSpan, ...]:
    if not event.midi_pitches:
        return ()
    return tuple(
        NotationSpan(f"{event.id}{_GENERATED_MARKER}tie-{index}", SpanKind.TIE, start, end)
        for index, (start, end) in enumerate(pairwise(notation_ids), start=1)
    )


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
    if len(set(event.midi_pitches)) != len(event.midi_pitches):
        _fail(f"flow event {event.id!r} contains a duplicate MIDI pitch")
    if any(not isinstance(midi, int) or not 0 <= midi <= 127 for midi in event.midi_pitches):
        _fail("flow event MIDI pitches must be integers between 0 and 127")
    if event.lyric is not None and not event.lyric:
        _fail("flow event lyric must be non-empty when present")
    if not isinstance(event.syllabic, Syllabic):
        _fail("flow event syllabic value must be a Syllabic")


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
    "FlowEvent",
    "FlowEventMap",
    "FlowScore",
    "FlowScoreOptions",
    "adapt_flow_events",
]
