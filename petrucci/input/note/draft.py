"""Mutable transaction draft for Petrucci's immutable notation score."""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from petrucci.core.score import (
    LyricSyllable,
    NotationEvent,
    NotationMeasure,
    NotationScore,
    NotationSpan,
    NotationStaff,
)
from petrucci.input.note.types import NoteInputError, ScorePosition


@dataclass(slots=True)
class DraftMeasure:
    source: NotationMeasure
    events: list[NotationEvent] = field(default_factory=list)


@dataclass(slots=True)
class DraftStaff:
    source: NotationStaff
    measures: list[DraftMeasure] = field(default_factory=list)
    lyrics: list[LyricSyllable] = field(default_factory=list)
    spans: list[NotationSpan] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class EventLocation:
    staff: DraftStaff
    measure: DraftMeasure
    staff_index: int
    measure_index: int
    event_index: int

    @property
    def event(self) -> NotationEvent:
        return self.measure.events[self.event_index]


@dataclass(slots=True)
class ScoreDraft:
    source: NotationScore
    staffs: list[DraftStaff]
    used_ids: set[str]
    staff_indices: dict[str, int]
    measure_owners: dict[str, tuple[int, int]]
    event_owners: dict[str, tuple[int, int]]

    @classmethod
    def from_score(cls, score: NotationScore) -> ScoreDraft:
        staffs = [
            DraftStaff(
                source=staff,
                measures=[DraftMeasure(measure, list(measure.events)) for measure in staff.measures],
                lyrics=list(staff.lyrics),
                spans=list(staff.spans),
            )
            for staff in score.staffs
        ]
        staff_indices = {staff.source.id: index for index, staff in enumerate(staffs)}
        measure_owners = {
            measure.source.id: (staff_index, measure_index)
            for staff_index, staff in enumerate(staffs)
            for measure_index, measure in enumerate(staff.measures)
        }
        event_owners = {
            event.id: (staff_index, measure_index)
            for staff_index, staff in enumerate(staffs)
            for measure_index, measure in enumerate(staff.measures)
            for event in measure.events
        }
        return cls(score, staffs, _score_ids(score), staff_indices, measure_owners, event_owners)

    def position(self, position: ScorePosition) -> tuple[DraftStaff, DraftMeasure]:
        staff_index = self.staff_indices.get(position.staff_id)
        if staff_index is None:
            raise NoteInputError("unknown-staff", f"unknown staff {position.staff_id!r}")
        owner = self.measure_owners.get(position.measure_id)
        if owner is None or owner[0] != staff_index:
            raise NoteInputError(
                "unknown-measure",
                f"staff {position.staff_id!r} has no measure {position.measure_id!r}",
            )
        return self.staffs[staff_index], self.staffs[staff_index].measures[owner[1]]

    def event(self, event_id: str) -> EventLocation:
        owner = self.event_owners.get(event_id)
        if owner is None:
            raise NoteInputError("unknown-event", f"unknown event {event_id!r}")
        staff_index, measure_index = owner
        staff = self.staffs[staff_index]
        measure = staff.measures[measure_index]
        event_index = next(index for index, event in enumerate(measure.events) if event.id == event_id)
        return EventLocation(staff, measure, staff_index, measure_index, event_index)

    def span(self, span_id: str) -> tuple[DraftStaff, int]:
        for staff in self.staffs:
            for index, span in enumerate(staff.spans):
                if span.id == span_id:
                    return staff, index
        raise NoteInputError("unknown-span", f"unknown span {span_id!r}")

    def lyric(self, lyric_id: str) -> tuple[DraftStaff, int]:
        for staff in self.staffs:
            for index, lyric in enumerate(staff.lyrics):
                if lyric.id == lyric_id:
                    return staff, index
        raise NoteInputError("unknown-lyric", f"unknown lyric {lyric_id!r}")

    def reserve_id(self, requested: str | None, *, prefix: str) -> str:
        if requested is not None:
            if not requested.strip():
                raise NoteInputError("invalid-id", "element ID must be non-empty")
            if requested in self.used_ids:
                raise NoteInputError("duplicate-id", f"duplicate score element ID {requested!r}")
            self.used_ids.add(requested)
            return requested
        index = 1
        while f"input-{prefix}-{index}" in self.used_ids:
            index += 1
        generated = f"input-{prefix}-{index}"
        self.used_ids.add(generated)
        return generated

    def insert_event(self, measure: DraftMeasure, event: NotationEvent) -> None:
        index = len(measure.events)
        key = (event.onset, event.voice)
        for candidate_index, candidate in enumerate(measure.events):
            if (candidate.onset, candidate.voice) > key:
                index = candidate_index
                break
        measure.events.insert(index, event)
        self.event_owners[event.id] = self.measure_owners[measure.source.id]

    def delete_event(self, location: EventLocation) -> None:
        del self.event_owners[location.event.id]
        del location.measure.events[location.event_index]

    def commit(self) -> NotationScore:
        staffs = []
        for staff in self.staffs:
            measures = tuple(replace(measure.source, events=tuple(measure.events)) for measure in staff.measures)
            staffs.append(
                replace(
                    staff.source,
                    measures=measures,
                    lyrics=tuple(staff.lyrics),
                    spans=tuple(staff.spans),
                ),
            )
        return replace(self.source, staffs=tuple(staffs))


def ensure_event_position(location: EventLocation, position: ScorePosition) -> None:
    event = location.event
    if location.staff.source.id != position.staff_id or location.measure.source.id != position.measure_id:
        raise NoteInputError("position-mismatch", f"event {event.id!r} is not at the requested staff and measure")
    if event.onset != position.onset or event.voice != position.voice:
        raise NoteInputError("position-mismatch", f"event {event.id!r} is not at the requested onset and voice")


def events_at(measure: DraftMeasure, position: ScorePosition) -> list[NotationEvent]:
    return [event for event in measure.events if event.onset == position.onset and event.voice == position.voice]


def previous_events(location: EventLocation) -> list[NotationEvent]:
    events: list[NotationEvent] = []
    for measure_index, measure in enumerate(location.staff.measures):
        if measure_index > location.measure_index:
            break
        for event_index, event in enumerate(measure.events):
            if measure_index == location.measure_index and event_index >= location.event_index:
                break
            events.append(event)
    return events


def remove_event_spans(location: EventLocation, event_id: str) -> tuple[NotationSpan, ...]:
    staff = location.staff
    removed = tuple(span for span in staff.spans if event_id in {span.start_event_id, span.end_event_id})
    staff.spans[:] = [span for span in staff.spans if event_id not in {span.start_event_id, span.end_event_id}]
    return removed


def remove_event_attachments(
    location: EventLocation,
    event_id: str,
) -> tuple[tuple[NotationSpan, ...], tuple[LyricSyllable, ...]]:
    staff = location.staff
    removed_spans = remove_event_spans(location, event_id)
    removed_lyrics = tuple(lyric for lyric in staff.lyrics if lyric.event_id == event_id)
    staff.lyrics[:] = [lyric for lyric in staff.lyrics if lyric.event_id != event_id]
    return removed_spans, removed_lyrics


def _score_ids(score: NotationScore) -> set[str]:
    ids = {score.id}
    for staff in score.staffs:
        ids.add(staff.id)
        ids.update(measure.id for measure in staff.measures)
        ids.update(event.id for measure in staff.measures for event in measure.events)
        ids.update(lyric.id for lyric in staff.lyrics)
        ids.update(span.id for span in staff.spans)
        ids.update(line.id for line in staff.lyric_lines)
    return ids
