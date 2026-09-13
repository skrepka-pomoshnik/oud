"""Written and continuous pitch projection onto conventional staff geometry."""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
from fractions import Fraction
from typing import NoReturn

from petrucci.core.music.projection import ProjectionError, ProjectionRounding, round_projection
from petrucci.core.music.timeline import MeasureBoundary, score_measure_boundaries
from petrucci.core.score import Clef, NotationScore, NotationStaff, PitchStep, WrittenPitch

_STEP_SEMITONES = (0, 2, 4, 5, 7, 9, 11)
_STEP_INDEX = {step: index for index, step in enumerate(PitchStep)}
_MAX_PROJECTED_STAFF_POSITION = 128


@dataclass(frozen=True, slots=True)
class PitchProjection:
    staff_id: str
    measure_id: str
    measure_index: int
    time: Fraction
    clef: Clef
    staff_position: Fraction
    row: Fraction
    rounded_row: int


def written_staff_position(pitch: WrittenPitch, clef: Clef) -> int:
    """Return diatonic steps above the active staff's bottom line."""

    bottom = WrittenPitch(PitchStep.E, 4) if clef is Clef.TREBLE else WrittenPitch(PitchStep.G, 2)
    return _diatonic_number(pitch) - _diatonic_number(bottom)


def continuous_staff_position(midi: Fraction, clef: Clef) -> Fraction:
    """Interpolate exact MIDI pitch between adjacent natural staff positions."""

    if not isinstance(midi, Fraction):
        _fail("measured MIDI pitch must be a Fraction")
    octave = int(midi // 12) - 1
    pitch_class = midi % 12
    step = bisect_right(_STEP_SEMITONES, pitch_class) - 1
    lower = _STEP_SEMITONES[step]
    upper = _STEP_SEMITONES[step + 1] if step + 1 < len(_STEP_SEMITONES) else 12
    bottom = WrittenPitch(PitchStep.E, 4) if clef is Clef.TREBLE else WrittenPitch(PitchStep.G, 2)
    position = Fraction(octave * 7 + step - _diatonic_number(bottom)) + (pitch_class - lower) / (upper - lower)
    if not -_MAX_PROJECTED_STAFF_POSITION <= position <= _MAX_PROJECTED_STAFF_POSITION:
        return _fail("measured MIDI pitch is outside the supported projection range")
    return position


def project_written_pitch(
    score: NotationScore,
    staff_id: str,
    time: Fraction,
    pitch: WrittenPitch,
    *,
    bottom_row: int,
    viewport_y_offset: int = 0,
    rounding: ProjectionRounding = ProjectionRounding.NEAREST,
) -> PitchProjection:
    """Project written pitch at an arbitrary canonical timeline position."""

    staff, boundary = _staff_and_boundary(score, staff_id, time)
    clef = staff.measure_state(boundary.index)[0]
    return _pitch_projection(
        staff_id=staff_id,
        boundary=boundary,
        time=time,
        clef=clef,
        position=Fraction(written_staff_position(pitch, clef)),
        bottom_row=bottom_row,
        viewport_y_offset=viewport_y_offset,
        rounding=rounding,
    )


def project_continuous_pitch(
    score: NotationScore,
    staff_id: str,
    time: Fraction,
    midi: Fraction,
    *,
    bottom_row: int,
    viewport_y_offset: int = 0,
    rounding: ProjectionRounding = ProjectionRounding.NEAREST,
) -> PitchProjection:
    """Project measured MIDI pitch without adding assessment or tolerance policy."""

    staff, boundary = _staff_and_boundary(score, staff_id, time)
    clef = staff.measure_state(boundary.index)[0]
    return _pitch_projection(
        staff_id=staff_id,
        boundary=boundary,
        time=time,
        clef=clef,
        position=continuous_staff_position(midi, clef),
        bottom_row=bottom_row,
        viewport_y_offset=viewport_y_offset,
        rounding=rounding,
    )


def _pitch_projection(
    *,
    staff_id: str,
    boundary: MeasureBoundary,
    time: Fraction,
    clef: Clef,
    position: Fraction,
    bottom_row: int,
    viewport_y_offset: int,
    rounding: ProjectionRounding,
) -> PitchProjection:
    row = Fraction(bottom_row - viewport_y_offset) - position
    return PitchProjection(
        staff_id,
        boundary.measure_id,
        boundary.index,
        time,
        clef,
        position,
        row,
        round_projection(row, rounding),
    )


def _staff_and_boundary(
    score: NotationScore,
    staff_id: str,
    time: Fraction,
) -> tuple[NotationStaff, MeasureBoundary]:
    if not isinstance(time, Fraction):
        _fail("pitch projection time must be a Fraction")
    staff = next((candidate for candidate in score.staffs if candidate.id == staff_id), None)
    if staff is None:
        _fail(f"unknown projection staff {staff_id!r}")
    boundary = next((item for item in score_measure_boundaries(score) if item.start <= time < item.end), None)
    if boundary is None:
        _fail("pitch projection time is outside the score timeline")
    return staff, boundary


def _diatonic_number(pitch: WrittenPitch) -> int:
    return (pitch.octave * 7) + _STEP_INDEX[pitch.step]


def _fail(message: str) -> NoReturn:
    raise ProjectionError(message)
