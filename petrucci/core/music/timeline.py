"""Exact canonical score timeline derived from explicit measure boundaries."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from petrucci.core.score import NotationScore, TimeSignature


@dataclass(frozen=True, slots=True)
class MeasureBoundary:
    """One aligned measure interval in whole-note units."""

    measure_id: str
    index: int
    number: int
    start: Fraction
    duration: Fraction

    @property
    def end(self) -> Fraction:
        return self.start + self.duration


def score_measure_boundaries(score: NotationScore) -> tuple[MeasureBoundary, ...]:
    """Return exact shared measure intervals in canonical whole-note units."""

    meter = TimeSignature()
    start = Fraction()
    boundaries: list[MeasureBoundary] = []
    for index, measure in enumerate(score.staffs[0].measures):
        meter = measure.time_signature or meter
        duration = measure.duration or meter.duration
        boundaries.append(MeasureBoundary(measure.id, index, measure.number, start, duration))
        start += duration
    return tuple(boundaries)


def absolute_event_onset(score: NotationScore, event_id: str) -> Fraction | None:
    """Return an event onset on the canonical timeline, or ``None`` if unknown."""

    boundaries = score_measure_boundaries(score)
    for staff in score.staffs:
        for boundary, measure in zip(boundaries, staff.measures, strict=True):
            for event in measure.events:
                if event.id == event_id:
                    return boundary.start + event.onset
    return None
