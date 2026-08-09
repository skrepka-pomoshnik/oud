"""Transient semantic pitch cues painted without changing score layout."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import NoReturn

from petrucci.core.score import NotationMeasure, NotationScore, NotationStaff, WrittenPitch
from petrucci.engraving.layout.engine import ElementRole, LayoutViewport, OnsetPosition, ScoreLayout, StaffRows
from petrucci.engraving.notation.state import _staff_position, _state_at
from petrucci.terminal.api import GlyphMode, SemanticFrame
from petrucci.terminal.canvas.framebuffer import overlay_frame
from petrucci.terminal.canvas.screen import A_DIM


class PitchCueError(ValueError):
    """Raised when a pitch cue has no deterministic score-layout anchor."""


@dataclass(frozen=True, slots=True)
class PitchCue:
    """A transient pitch anchored to an event or an exact measure onset."""

    id: str
    pitch: WrittenPitch
    event_id: str | None = None
    staff_id: str | None = None
    measure_id: str | None = None
    onset: Fraction | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.id, str) or not self.id:
            _fail("pitch cue ID must be a non-empty string")
        if not isinstance(self.pitch, WrittenPitch):
            _fail("pitch cue pitch must be a WrittenPitch")
        event_anchor = self.event_id is not None
        onset_values = (self.staff_id, self.measure_id, self.onset)
        onset_anchor = all(value is not None for value in onset_values)
        if event_anchor == onset_anchor or (not onset_anchor and any(value is not None for value in onset_values)):
            _fail("pitch cue must use exactly one complete event or onset anchor")
        if self.onset is not None and (not isinstance(self.onset, Fraction) or self.onset < 0):
            _fail("pitch cue onset must be a non-negative Fraction")


def paint_pitch_cues(
    semantic_frame: SemanticFrame,
    *,
    score: NotationScore,
    layout: ScoreLayout,
    cues: tuple[PitchCue, ...],
    viewport: LayoutViewport,
    glyph_mode: GlyphMode,
) -> SemanticFrame:
    """Overlay semantic cue cells while preserving the supplied layout."""

    _validate_cue_request(score, layout, cues)
    if not cues or not layout.systems:
        return semantic_frame
    cells = _visible_cue_cells(score, layout, cues, viewport)
    glyph = "x" if glyph_mode is GlyphMode.SAFE else "◇"
    frame = overlay_frame(semantic_frame.frame, [(y, x, glyph, A_DIM) for _cue, y, x in cells])
    roles = [list(row) for row in semantic_frame.roles]
    element_ids = [list(row) for row in semantic_frame.element_ids]
    for cue, y, x in cells:
        roles[y][x] = ElementRole.PITCH_CUE
        element_ids[y][x] = cue.id
    return SemanticFrame(
        frame=frame,
        roles=tuple(tuple(row) for row in roles),
        element_ids=tuple(tuple(row) for row in element_ids),
    )


def _validate_cue_request(score: NotationScore, layout: ScoreLayout, cues: tuple[PitchCue, ...]) -> None:
    if score.id != layout.score_id:
        _fail("pitch cue score and layout IDs must match")
    if any(not isinstance(cue, PitchCue) for cue in cues):
        _fail("pitch cues must contain PitchCue values")
    cue_ids = tuple(cue.id for cue in cues)
    if len(set(cue_ids)) != len(cue_ids):
        _fail("pitch cue IDs must be unique")
    if set(cue_ids) & set(layout.event_ids):
        _fail("pitch cue IDs must not collide with score event IDs")


def _visible_cue_cells(
    score: NotationScore,
    layout: ScoreLayout,
    cues: tuple[PitchCue, ...],
    viewport: LayoutViewport,
) -> list[tuple[PitchCue, int, int]]:
    scroll_y = layout.systems[viewport.system_offset].rect.y + viewport.y_offset
    cells: list[tuple[PitchCue, int, int]] = []
    for cue in cues:
        staff, measure_index, anchor = _resolve_anchor(cue, score, layout)
        rows = _staff_rows(layout.systems[anchor.system_index].staff_rows, staff.id)
        clef = _state_at(staff, measure_index).clef
        y = rows.line_rows[-1] - _staff_position(cue.pitch, clef=clef) - scroll_y
        x = anchor.x - viewport.x_offset
        if 0 <= y < viewport.height and 0 <= x < viewport.width:
            cells.append((cue, y, x))
    return cells


def _resolve_anchor(
    cue: PitchCue,
    score: NotationScore,
    layout: ScoreLayout,
) -> tuple[NotationStaff, int, OnsetPosition]:
    if cue.event_id is not None:
        location = layout.location_for(cue.event_id)
        anchor = layout.onset_for(cue.event_id)
        if location is None or anchor is None:
            _fail(f"pitch cue {cue.id!r} references unknown event {cue.event_id!r}")
        staff = _staff(score, location.staff_id)
        measure_index, measure = _measure(staff, location.measure_id)
        return staff, measure_index, anchor
    staff = _staff(score, cue.staff_id or "")
    measure_index, measure = _measure(staff, cue.measure_id or "")
    candidates = tuple(event for event in measure.events if event.onset == cue.onset)
    if not candidates:
        _fail(f"pitch cue {cue.id!r} onset does not match an event")
    event = min(candidates, key=lambda item: (item.voice, item.id))
    anchor = layout.onset_for(event.id)
    if anchor is None:
        _fail(f"pitch cue {cue.id!r} event has no layout onset")
    return staff, measure_index, anchor


def _staff(score: NotationScore, staff_id: str) -> NotationStaff:
    staff = next((item for item in score.staffs if item.id == staff_id), None)
    if staff is None:
        _fail(f"pitch cue references unknown staff {staff_id!r}")
    return staff


def _measure(staff: NotationStaff, measure_id: str) -> tuple[int, NotationMeasure]:
    found = next(((index, item) for index, item in enumerate(staff.measures) if item.id == measure_id), None)
    if found is None:
        _fail(f"pitch cue references unknown measure {measure_id!r}")
    return found


def _staff_rows(rows: tuple[StaffRows, ...], staff_id: str) -> StaffRows:
    found = next((item for item in rows if item.staff_id == staff_id), None)
    if found is None:
        _fail(f"pitch cue layout has no rows for staff {staff_id!r}")
    return found


def _fail(message: str) -> NoReturn:
    raise PitchCueError(message)


__all__ = ["PitchCue", "PitchCueError", "paint_pitch_cues"]
