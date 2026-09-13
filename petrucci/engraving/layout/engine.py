"""Backend-neutral contracts for Petrucci score layout."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from enum import StrEnum
from functools import lru_cache
from typing import NoReturn

from petrucci.core.music.projection import ProjectionCollision, TimelineProjectionRequest
from petrucci.core.music.timeline import MeasureBoundary
from petrucci.core.score import NotationScore
from petrucci.engraving.layout.fitting import BoxSystem, MeasuredBox, PlacedBox, fit_measured_boxes


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
    EDITORIAL_BRACKET = "editorial-bracket"
    REST = "rest"
    ACCIDENTAL = "accidental"
    DOT = "dot"
    STEM = "stem"
    FLAG = "flag"
    BEAM = "beam"
    LEDGER_LINE = "ledger-line"
    TIE = "tie"
    SLUR = "slur"
    GLISSANDO = "glissando"
    TUPLET = "tuplet"
    GRACE = "grace"
    FERMATA = "fermata"
    ORNAMENT = "ornament"
    HARMONIC = "harmonic"
    FINGERING = "fingering"
    PROPORTION = "proportion"
    DYNAMIC = "dynamic"
    PITCH_LABEL = "pitch-label"
    PITCH_CUE = "pitch-cue"
    LYRIC = "lyric"
    LYRIC_LINE = "lyric-line"
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
class LayoutCollision:
    left: ElementKey
    right: ElementKey
    x: int
    y: int


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
    tuplet_rows: tuple[int, ...]
    grace_row: int | None
    ornament_row: int | None
    fermata_row: int | None
    notation_top: int
    line_rows: tuple[int, int, int, int, int]
    notation_bottom: int
    tie_rows: tuple[int, ...]
    dynamic_row: int | None
    pitch_label_row: int | None
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
            *self.tuplet_rows,
            *((self.grace_row,) if self.grace_row is not None else ()),
            *((self.ornament_row,) if self.ornament_row is not None else ()),
            *((self.fermata_row,) if self.fermata_row is not None else ()),
        )
        if any(not self.top <= row < self.notation_top for row in above):
            _fail("staff upper lanes must precede notation")
        below = (
            *self.tie_rows,
            *((self.dynamic_row,) if self.dynamic_row is not None else ()),
            *((self.pitch_label_row,) if self.pitch_label_row is not None else ()),
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
    clipped_event_ids: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class LayoutViewport:
    width: int = 80
    height: int = 24
    system_offset: int = 0
    x_offset: int = 0
    y_offset: int = 0

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            _fail("layout viewport dimensions must be positive")
        if self.system_offset < 0:
            _fail("layout system offset must be non-negative")
        if self.x_offset < 0:
            _fail("layout horizontal offset must be non-negative")
        if self.y_offset < 0:
            _fail("layout vertical offset must be non-negative")


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
    """Display policy; hidden time signatures retain their layout reservation."""

    justify: bool = True
    justify_last_system: bool = False
    show_title: bool = True
    show_measure_numbers: bool = True
    show_lyrics: bool = True
    show_stems: bool = True
    show_barlines: bool = True
    show_pitch_labels: bool = False
    show_time_signature: bool = True


@dataclass(frozen=True, slots=True)
class ScoreLayout:
    score_id: str
    width: int
    document_height: int
    event_ids: tuple[str, ...]
    event_locations: tuple[EventLocation, ...]
    systems: tuple[ScoreSystem, ...]
    onsets: tuple[OnsetPosition, ...]
    measure_boundaries: tuple[MeasureBoundary, ...] = ()
    timeline_collisions: tuple[ProjectionCollision, ...] = ()

    def __post_init__(self) -> None:
        _validate_layout_references(self)
        _validate_layout_bounds(self)
        _validate_clipped_event_ids(self)

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


def _validate_layout_references(layout: ScoreLayout) -> None:
    if len(set(layout.event_ids)) != len(layout.event_ids):
        _fail("score layout event IDs must be unique")
    if any(position.event_id not in layout.event_ids for position in layout.onsets):
        _fail("score layout onsets must reference known event IDs")
    location_ids = tuple(location.event_id for location in layout.event_locations)
    if location_ids != layout.event_ids:
        _fail("score layout locations must match canonical event IDs in order")
    if any(not 0 <= location.system_index < len(layout.systems) for location in layout.event_locations):
        _fail("score layout locations must reference known systems")


def _validate_layout_bounds(layout: ScoreLayout) -> None:
    if any(element.rect.right >= layout.width for element in layout.elements):
        _fail("score layout elements must stay within the document width")
    if any(element.rect.bottom >= layout.document_height for element in layout.elements):
        _fail("score layout elements must stay within the document height")


def _validate_clipped_event_ids(layout: ScoreLayout) -> None:
    known_ids = set(layout.event_ids)
    if any(event_id not in known_ids for system in layout.systems for event_id in system.clipped_event_ids):
        _fail("clipped event IDs must reference canonical events")


def layout_score(
    score: NotationScore,
    *,
    viewport: LayoutViewport | None = None,
    metrics: LayoutMetrics | None = None,
    policy: NotationLayoutPolicy | None = None,
) -> ScoreLayout:
    """Lay out a canonical score without choosing terminal glyphs or styles."""

    active_viewport = viewport or LayoutViewport()
    geometry_viewport = LayoutViewport(width=active_viewport.width, height=1)
    return _cached_layout_score(
        score,
        geometry_viewport,
        metrics or LayoutMetrics(),
        policy or NotationLayoutPolicy(),
    )


def layout_score_proportional(
    score: NotationScore,
    request: TimelineProjectionRequest,
    *,
    metrics: LayoutMetrics | None = None,
    policy: NotationLayoutPolicy | None = None,
) -> ScoreLayout:
    """Lay out one fixed-scale timeline viewport without rhythmic respacing."""

    return _cached_proportional_layout_score(
        score,
        request,
        metrics or LayoutMetrics(),
        policy or NotationLayoutPolicy(),
    )


def clear_layout_cache() -> None:
    """Clear immutable score layouts, primarily for bounded host lifecycle use."""

    _cached_layout_score.cache_clear()
    _cached_proportional_layout_score.cache_clear()


@dataclass(slots=True)
class _CollisionScan:
    occupied: dict[tuple[int, int], list[LayoutElement]]
    seen: set[tuple[ElementKey, ElementKey, int, int]]
    collisions: list[LayoutCollision]

    def record(self, element: LayoutElement, x: int, y: int) -> None:
        for other in self.occupied.get((x, y), ()):
            if not _illegal_pair(other, element):
                continue
            key = (other.key, element.key, x, y)
            if key not in self.seen:
                self.seen.add(key)
                self.collisions.append(LayoutCollision(other.key, element.key, x, y))
        self.occupied.setdefault((x, y), []).append(element)


def layout_collisions(layout: ScoreLayout) -> tuple[LayoutCollision, ...]:
    """Return illegal cross-source overlaps between positioned score elements."""

    scan = _CollisionScan({}, set(), [])
    for element in layout.elements:
        if element.key.role not in _COLLISION_ROLES:
            continue
        for x, y in _element_cells(element):
            scan.record(element, x, y)
    return tuple(scan.collisions)


def _element_cells(element: LayoutElement) -> Iterator[tuple[int, int]]:
    for y in range(element.rect.y, element.rect.bottom + 1):
        for x in range(element.rect.x, element.rect.right + 1):
            yield x, y


@lru_cache(maxsize=64)
def _cached_layout_score(
    score: NotationScore,
    viewport: LayoutViewport,
    metrics: LayoutMetrics,
    policy: NotationLayoutPolicy,
) -> ScoreLayout:
    from petrucci.engraving.notation.layout import build_score_layout  # noqa: PLC0415

    return build_score_layout(
        score,
        viewport=viewport,
        metrics=metrics,
        policy=policy,
    )


@lru_cache(maxsize=64)
def _cached_proportional_layout_score(
    score: NotationScore,
    request: TimelineProjectionRequest,
    metrics: LayoutMetrics,
    policy: NotationLayoutPolicy,
) -> ScoreLayout:
    from petrucci.engraving.notation.layout import build_score_layout  # noqa: PLC0415

    return build_score_layout(
        score,
        viewport=LayoutViewport(width=request.width, height=1),
        metrics=metrics,
        policy=policy,
        projection_request=request,
    )


def _fail(message: str) -> NoReturn:
    raise LayoutError(message)


_COLLISION_ROLES = frozenset(
    {
        ElementRole.NOTEHEAD,
        ElementRole.EDITORIAL_BRACKET,
        ElementRole.REST,
        ElementRole.ACCIDENTAL,
        ElementRole.DOT,
        ElementRole.STEM,
        ElementRole.FLAG,
        ElementRole.BEAM,
        ElementRole.TIE,
        ElementRole.SLUR,
        ElementRole.TUPLET,
        ElementRole.GRACE,
        ElementRole.FERMATA,
        ElementRole.ORNAMENT,
        ElementRole.DYNAMIC,
        ElementRole.PITCH_LABEL,
        ElementRole.LYRIC,
        ElementRole.LYRIC_LINE,
        ElementRole.LYRIC_HYPHEN,
        ElementRole.LYRIC_EXTENDER,
    },
)


def _illegal_pair(left: LayoutElement, right: LayoutElement) -> bool:
    if left.key.source_id == right.key.source_id:
        return False
    return {left.key.role, right.key.role} != {ElementRole.BEAM, ElementRole.STEM}


__all__ = [
    "BoxSystem",
    "ElementKey",
    "ElementRole",
    "EventLocation",
    "LayoutCollision",
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
    "layout_collisions",
    "layout_score",
]
