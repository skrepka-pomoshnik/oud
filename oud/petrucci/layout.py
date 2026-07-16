"""Backend-neutral contracts for Petrucci score layout."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from functools import lru_cache
from typing import NoReturn

from oud.petrucci.score import NotationScore
from oud.petrucci.system_fitting import BoxSystem, MeasuredBox, PlacedBox, fit_measured_boxes


class LayoutError(ValueError):
    """Raised when a layout request cannot satisfy its explicit contract."""


class ElementRole(StrEnum):
    TITLE = "title"
    COMPOSER = "composer"
    STAFF = "staff"
    STAFF_LABEL = "staff-label"
    CLEF = "clef"
    KEY_SIGNATURE = "key-signature"
    TIME_SIGNATURE = "time-signature"
    MEASURE_NUMBER = "measure-number"
    ENDING = "ending"
    BARLINE = "barline"
    NOTEHEAD = "notehead"
    REST = "rest"
    ACCIDENTAL = "accidental"
    DOT = "dot"
    STEM = "stem"
    FLAG = "flag"
    BEAM = "beam"
    LEDGER_LINE = "ledger-line"
    TIE = "tie"
    SLUR = "slur"
    TUPLET = "tuplet"
    FERMATA = "fermata"
    ORNAMENT = "ornament"
    DYNAMIC = "dynamic"
    FEEDBACK = "feedback"
    LYRIC = "lyric"
    LYRIC_HYPHEN = "lyric-hyphen"
    LYRIC_EXTENDER = "lyric-extender"
    CLIP_MARKER = "clip-marker"


@dataclass(frozen=True, slots=True)
class Rect:
    x: int
    y: int
    width: int = 1
    height: int = 1

    def __post_init__(self) -> None:
        if self.x < 0 or self.y < 0:
            _fail("layout coordinates must be non-negative")
        if self.width <= 0 or self.height <= 0:
            _fail("layout rectangles must have positive dimensions")

    @property
    def right(self) -> int:
        return self.x + self.width - 1

    @property
    def bottom(self) -> int:
        return self.y + self.height - 1


@dataclass(frozen=True, slots=True)
class ElementKey:
    source_id: str
    role: ElementRole
    index: int = 0

    def __post_init__(self) -> None:
        if not self.source_id:
            _fail("layout element source ID must not be empty")
        if not isinstance(self.role, ElementRole):
            _fail("layout element role must be an ElementRole")
        if self.index < 0:
            _fail("layout element index must be non-negative")


@dataclass(frozen=True, slots=True)
class LayoutElement:
    key: ElementKey
    rect: Rect
    value: str = ""
    continuation: bool = False


@dataclass(frozen=True, slots=True)
class OnsetPosition:
    event_id: str
    staff_id: str
    measure_id: str
    system_index: int
    x: int


@dataclass(frozen=True, slots=True)
class EventLocation:
    event_id: str
    staff_id: str
    measure_id: str
    system_index: int


@dataclass(frozen=True, slots=True)
class StaffRows:
    staff_id: str
    top: int
    measure_number_row: int | None
    ending_row: int | None
    slur_rows: tuple[int, ...]
    ornament_row: int | None
    fermata_row: int | None
    notation_top: int
    line_rows: tuple[int, int, int, int, int]
    notation_bottom: int
    tie_rows: tuple[int, ...]
    dynamic_row: int | None
    feedback_row: int | None
    lyric_rows: tuple[int, ...]
    bottom: int

    def __post_init__(self) -> None:
        if tuple(sorted(self.line_rows)) != self.line_rows:
            _fail("staff line rows must be ordered")
        if not self.top <= self.notation_top <= self.line_rows[0]:
            _fail("staff notation top must precede its lines")
        if not self.line_rows[-1] <= self.notation_bottom <= self.bottom:
            _fail("staff notation bottom must follow its lines")
        above = (
            *((self.measure_number_row,) if self.measure_number_row is not None else ()),
            *((self.ending_row,) if self.ending_row is not None else ()),
            *self.slur_rows,
            *((self.ornament_row,) if self.ornament_row is not None else ()),
            *((self.fermata_row,) if self.fermata_row is not None else ()),
        )
        if any(not self.top <= row < self.notation_top for row in above):
            _fail("staff upper lanes must precede notation")
        below = (
            *self.tie_rows,
            *((self.dynamic_row,) if self.dynamic_row is not None else ()),
            *((self.feedback_row,) if self.feedback_row is not None else ()),
            *self.lyric_rows,
        )
        if any(not self.notation_bottom < row <= self.bottom for row in below):
            _fail("staff lower lanes must follow notation")
        lanes = (*above, *below)
        if len(set(lanes)) != len(lanes):
            _fail("staff presentation lanes must not overlap")


@dataclass(frozen=True, slots=True)
class ScoreSystem:
    index: int
    measure_start: int
    measure_end: int
    rect: Rect
    measure_boxes: tuple[PlacedBox, ...]
    staff_rows: tuple[StaffRows, ...]
    elements: tuple[LayoutElement, ...]
    clipped: bool = False


@dataclass(frozen=True, slots=True)
class LayoutViewport:
    width: int = 80
    height: int = 24
    system_offset: int = 0

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            _fail("layout viewport dimensions must be positive")
        if self.system_offset < 0:
            _fail("layout system offset must be non-negative")


@dataclass(frozen=True, slots=True)
class LayoutMetrics:
    left_padding: int = 1
    right_padding: int = 1
    system_prefix_width: int = 9
    min_measure_width: int = 8
    event_gap: int = 3
    measure_gap: int = 0
    max_measure_stretch: int = 6
    staff_top_padding: int = 1
    staff_line_gap: int = 1
    staff_bottom_padding: int = 1
    staff_gap: int = 2
    system_gap: int = 1
    lyric_gap: int = 1

    def __post_init__(self) -> None:
        positive = (
            self.system_prefix_width,
            self.min_measure_width,
            self.event_gap,
            self.staff_top_padding,
            self.staff_bottom_padding,
        )
        non_negative = (
            self.left_padding,
            self.right_padding,
            self.measure_gap,
            self.max_measure_stretch,
            self.staff_line_gap,
            self.staff_gap,
            self.system_gap,
            self.lyric_gap,
        )
        if any(value <= 0 for value in positive):
            _fail("positive layout metrics must be greater than zero")
        if any(value < 0 for value in non_negative):
            _fail("non-negative layout metrics must not be negative")


@dataclass(frozen=True, slots=True)
class NotationLayoutPolicy:
    justify: bool = True
    show_title: bool = True
    show_measure_numbers: bool = True
    show_lyrics: bool = True
    reserve_feedback_lane: bool = False


@dataclass(frozen=True, slots=True)
class ScoreLayout:
    score_id: str
    width: int
    document_height: int
    event_ids: tuple[str, ...]
    event_locations: tuple[EventLocation, ...]
    systems: tuple[ScoreSystem, ...]
    onsets: tuple[OnsetPosition, ...]

    def __post_init__(self) -> None:
        if len(set(self.event_ids)) != len(self.event_ids):
            _fail("score layout event IDs must be unique")
        if any(position.event_id not in self.event_ids for position in self.onsets):
            _fail("score layout onsets must reference known event IDs")
        location_ids = tuple(location.event_id for location in self.event_locations)
        if location_ids != self.event_ids:
            _fail("score layout locations must match canonical event IDs in order")
        if any(not 0 <= location.system_index < len(self.systems) for location in self.event_locations):
            _fail("score layout locations must reference known systems")

    @property
    def elements(self) -> tuple[LayoutElement, ...]:
        return tuple(element for system in self.systems for element in system.elements)

    def elements_for(self, source_id: str) -> tuple[LayoutElement, ...]:
        return tuple(element for element in self.elements if element.key.source_id == source_id)

    def onset_for(self, event_id: str) -> OnsetPosition | None:
        return next((position for position in self.onsets if position.event_id == event_id), None)

    def location_for(self, event_id: str) -> EventLocation | None:
        return next((location for location in self.event_locations if location.event_id == event_id), None)

    def system_for_event(self, event_id: str) -> ScoreSystem | None:
        location = self.location_for(event_id)
        if location is None:
            return None
        return self.systems[location.system_index]


def layout_score(
    score: NotationScore,
    *,
    viewport: LayoutViewport | None = None,
    metrics: LayoutMetrics | None = None,
    policy: NotationLayoutPolicy | None = None,
    feedback_event_ids: frozenset[str] = frozenset(),
) -> ScoreLayout:
    """Lay out a canonical score without choosing terminal glyphs or styles."""

    active_viewport = viewport or LayoutViewport()
    geometry_viewport = LayoutViewport(width=active_viewport.width, height=1)
    return _cached_layout_score(
        score,
        geometry_viewport,
        metrics or LayoutMetrics(),
        policy or NotationLayoutPolicy(),
        feedback_event_ids,
    )


def clear_layout_cache() -> None:
    """Clear immutable score layouts, primarily for bounded host lifecycle use."""

    _cached_layout_score.cache_clear()


@lru_cache(maxsize=64)
def _cached_layout_score(
    score: NotationScore,
    viewport: LayoutViewport,
    metrics: LayoutMetrics,
    policy: NotationLayoutPolicy,
    feedback_event_ids: frozenset[str],
) -> ScoreLayout:
    from oud.petrucci.notation_layout import build_score_layout  # noqa: PLC0415

    return build_score_layout(
        score,
        viewport=viewport,
        metrics=metrics,
        policy=policy,
        feedback_event_ids=feedback_event_ids,
    )


def _fail(message: str) -> NoReturn:
    raise LayoutError(message)


__all__ = [
    "BoxSystem",
    "ElementKey",
    "ElementRole",
    "EventLocation",
    "LayoutElement",
    "LayoutError",
    "LayoutMetrics",
    "LayoutViewport",
    "MeasuredBox",
    "NotationLayoutPolicy",
    "OnsetPosition",
    "PlacedBox",
    "Rect",
    "ScoreLayout",
    "ScoreSystem",
    "StaffRows",
    "clear_layout_cache",
    "fit_measured_boxes",
    "layout_score",
]
