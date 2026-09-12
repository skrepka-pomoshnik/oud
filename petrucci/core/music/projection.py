"""Exact source-neutral projection from musical time into a fixed viewport."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from fractions import Fraction
from typing import NoReturn

from petrucci.core.music.timeline import score_measure_boundaries
from petrucci.core.score import NotationScore


class ProjectionError(ValueError):
    """Raised when an exact projection request is invalid."""


class ProjectionRounding(StrEnum):
    FLOOR = "floor"
    NEAREST = "nearest"
    CEILING = "ceiling"


@dataclass(frozen=True, slots=True)
class TimelineProjectionRequest:
    """Viewport mapping in whole-note units and terminal columns."""

    origin: Fraction
    columns_per_whole: Fraction
    width: int
    preamble_width: int = 0
    rounding: ProjectionRounding = ProjectionRounding.NEAREST

    def __post_init__(self) -> None:
        _validate_fraction(self.origin, "projection origin")
        _validate_fraction(self.columns_per_whole, "projection scale")
        if self.columns_per_whole <= 0:
            _fail("projection scale must be positive")
        if self.width <= 0:
            _fail("projection width must be positive")
        if not 0 <= self.preamble_width < self.width:
            _fail("projection preamble width must fit inside the viewport")
        if not isinstance(self.rounding, ProjectionRounding):
            _fail("projection rounding must be a ProjectionRounding")

    def x_at(self, time: Fraction) -> Fraction:
        """Return the exact viewport x coordinate for canonical musical time."""

        _validate_fraction(time, "projection time")
        return Fraction(self.preamble_width) + ((time - self.origin) * self.columns_per_whole)

    def column_at(self, time: Fraction) -> int:
        return round_projection(self.x_at(time), self.rounding)


@dataclass(frozen=True, slots=True)
class ProjectedInterval:
    source_id: str
    staff_id: str | None
    measure_id: str | None
    start: Fraction
    end: Fraction
    x_start: Fraction
    x_end: Fraction
    column_start: int
    column_end: int
    clipped_left: bool
    clipped_right: bool
    visible: bool


@dataclass(frozen=True, slots=True)
class ProjectionCollision:
    staff_id: str
    column: int
    event_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class TimelineProjection:
    request: TimelineProjectionRequest
    measures: tuple[ProjectedInterval, ...]
    events: tuple[ProjectedInterval, ...]
    spans: tuple[ProjectedInterval, ...]
    collisions: tuple[ProjectionCollision, ...]

    def event_for(self, event_id: str) -> ProjectedInterval | None:
        return next((event for event in self.events if event.source_id == event_id), None)


def project_timeline(score: NotationScore, request: TimelineProjectionRequest) -> TimelineProjection:
    """Project canonical score identity without changing the requested time scale."""

    boundaries = score_measure_boundaries(score)
    measures = tuple(
        _project_interval(
            source_id=boundary.measure_id,
            staff_id=None,
            measure_id=boundary.measure_id,
            start=boundary.start,
            end=boundary.end,
            request=request,
        )
        for boundary in boundaries
    )
    events: list[ProjectedInterval] = []
    event_times: dict[str, Fraction] = {}
    for staff in score.staffs:
        for boundary, measure in zip(boundaries, staff.measures, strict=True):
            for event in measure.events:
                start = boundary.start + event.onset
                events.append(
                    _project_interval(
                        source_id=event.id,
                        staff_id=staff.id,
                        measure_id=measure.id,
                        start=start,
                        end=start + event.duration,
                        request=request,
                    ),
                )
                event_times[event.id] = start
    spans = tuple(
        _project_interval(
            source_id=span.id,
            staff_id=staff.id,
            measure_id=None,
            start=event_times[span.start_event_id],
            end=event_times[span.end_event_id],
            request=request,
        )
        for staff in score.staffs
        for span in staff.spans
    )
    return TimelineProjection(request, measures, tuple(events), spans, _projection_collisions(events, request))


def round_projection(value: Fraction, rounding: ProjectionRounding) -> int:
    """Round an exact projected coordinate using the requested deterministic rule."""

    if rounding is ProjectionRounding.FLOOR:
        return value.numerator // value.denominator
    if rounding is ProjectionRounding.CEILING:
        return -((-value.numerator) // value.denominator)
    half = Fraction(1, 2)
    if value >= 0:
        rounded = value + half
        return rounded.numerator // rounded.denominator
    rounded = -value + half
    return -(rounded.numerator // rounded.denominator)


def _project_interval(
    source_id: str,
    *,
    staff_id: str | None,
    measure_id: str | None,
    start: Fraction,
    end: Fraction,
    request: TimelineProjectionRequest,
) -> ProjectedInterval:
    x_start = request.x_at(start)
    x_end = request.x_at(end)
    column_start = round_projection(x_start, request.rounding)
    column_end = round_projection(x_end, request.rounding)
    return ProjectedInterval(
        source_id,
        staff_id,
        measure_id,
        start,
        end,
        x_start,
        x_end,
        column_start,
        column_end,
        column_start < request.preamble_width,
        column_end >= request.width,
        column_end >= request.preamble_width and column_start < request.width,
    )


def _projection_collisions(
    events: list[ProjectedInterval],
    request: TimelineProjectionRequest,
) -> tuple[ProjectionCollision, ...]:
    cells: dict[tuple[str, int], dict[Fraction, list[str]]] = {}
    for event in events:
        if event.staff_id is None or not request.preamble_width <= event.column_start < request.width:
            continue
        cells.setdefault((event.staff_id, event.column_start), {}).setdefault(event.start, []).append(event.source_id)
    return tuple(
        ProjectionCollision(staff_id, column, tuple(sorted(event_id for ids in onsets.values() for event_id in ids)))
        for (staff_id, column), onsets in sorted(cells.items())
        if len(onsets) > 1
    )


def _validate_fraction(value: Fraction, label: str) -> None:
    if not isinstance(value, Fraction):
        _fail(f"{label} must be a Fraction")


def _fail(message: str) -> NoReturn:
    raise ProjectionError(message)
