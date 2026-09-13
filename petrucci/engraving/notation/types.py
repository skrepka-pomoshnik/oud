from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from petrucci.core.music.projection import TimelineProjection
from petrucci.core.score import Clef, KeySignature, LyricSyllable, NotationEvent, TimeSignature, WrittenPitch
from petrucci.engraving.layout.engine import LayoutElement, NotationLayoutPolicy, OnsetPosition, StaffRows
from petrucci.engraving.layout.fitting import BoxSystem


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
class _SharedOnsetGroup:
    onset: Fraction
    width: int


@dataclass(frozen=True, slots=True)
class _SharedMeasureGeometry:
    groups: tuple[_SharedOnsetGroup, ...]
    change_width: int
    min_width: int
    natural_width: int


@dataclass(frozen=True, slots=True)
class _MeasureEventContext:
    staff_id: str
    measure_id: str
    system_index: int
    rows: StaffRows
    clef: Clef
    visible_accidentals: dict[str, frozenset[WrittenPitch]]
    lyrics: dict[str, tuple[LyricSyllable, ...]]
    content_left: int
    content_right: int
    policy: NotationLayoutPolicy
    beam_lanes: dict[str, tuple[bool, int]]
    preserve_anchor: bool = False


@dataclass(frozen=True, slots=True)
class _PositionedMeasureEvents:
    elements: tuple[LayoutElement, ...]
    onsets: tuple[OnsetPosition, ...]
    event_xs: dict[str, int]
    clipped_event_ids: frozenset[str]


@dataclass(frozen=True, slots=True)
class _HorizontalPlan:
    label_width: int
    staff_x: int
    measure_x: int
    available_width: int
    systems: tuple[BoxSystem, ...]
    measure_geometries: tuple[_SharedMeasureGeometry, ...]
    projection: TimelineProjection | None = None


@dataclass(frozen=True, slots=True)
class _StaffVerticalNeeds:
    top_padding: int
    bottom_padding: int
    upper_beam_depth: int
    lower_beam_depth: int
    slur_lanes: int
    tie_lanes: int
    has_tuplet: bool
    has_grace: bool
    has_ending: bool
    has_ornament: bool
    has_fermata: bool
    has_dynamic: bool
    has_pitch_labels: bool
