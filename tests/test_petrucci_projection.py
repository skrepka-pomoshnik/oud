from __future__ import annotations

from fractions import Fraction
from itertools import pairwise

import pytest

from petrucci import (
    Clef,
    EventKind,
    NotationEvent,
    NotationMeasure,
    NotationScore,
    NotationSpan,
    NotationStaff,
    PitchStep,
    ProjectionError,
    ProjectionRounding,
    SpanKind,
    TimelineProjectionRequest,
    WrittenPitch,
    continuous_staff_position,
    pitch_from_midi,
    project_continuous_pitch,
    project_timeline,
    project_written_pitch,
    round_projection,
    written_staff_position,
)


def _note(
    event_id: str,
    onset: Fraction,
    pitch: int,
    *,
    voice: int = 0,
    duration: Fraction = Fraction(1, 4),
) -> NotationEvent:
    return NotationEvent(
        event_id,
        onset,
        duration,
        EventKind.NOTE,
        (WrittenPitch(PitchStep.C, pitch),),
        voice=voice,
    )


def _projection_score() -> NotationScore:
    first = _note("first", Fraction(), 4)
    close = _note("close", Fraction(1, 16), 4, duration=Fraction(1, 16))
    simultaneous = _note("simultaneous", Fraction(), 5, voice=1)
    last = _note("last", Fraction(5, 8), 4, duration=Fraction(1, 8))
    return NotationScore(
        "projection-score",
        (
            NotationStaff(
                "staff",
                (
                    NotationMeasure("pickup", 0, (first, close, simultaneous), irregular=True, duration=Fraction(1, 4)),
                    NotationMeasure("second", 1, (last,), clef=Clef.BASS, duration=Fraction(3, 4)),
                ),
                spans=(NotationSpan("span", SpanKind.SLUR, first.id, last.id),),
            ),
        ),
    )


def test_timeline_projection_preserves_exact_scale_identity_and_clipping() -> None:
    request = TimelineProjectionRequest(Fraction(1, 4), Fraction(8), width=6, preamble_width=1)
    projection = project_timeline(_projection_score(), request)

    assert [(item.start, item.end) for item in projection.measures] == [
        (Fraction(), Fraction(1, 4)),
        (Fraction(1, 4), Fraction(1)),
    ]
    first = projection.event_for("first")
    last = projection.event_for("last")
    assert first is not None and (first.x_start, first.column_start, first.clipped_left) == (Fraction(-1), -1, True)
    assert last is not None and (last.x_start, last.column_start, last.clipped_right) == (Fraction(6), 6, True)
    span = projection.spans[0]
    assert (span.source_id, span.clipped_left, span.clipped_right, span.visible) == ("span", True, True, True)


def test_projection_reports_quantization_collisions_without_moving_events() -> None:
    projection = project_timeline(
        _projection_score(),
        TimelineProjectionRequest(Fraction(), Fraction(1), width=8),
    )

    assert [(item.source_id, item.x_start) for item in projection.events[:3]] == [
        ("first", Fraction()),
        ("close", Fraction(1, 16)),
        ("simultaneous", Fraction()),
    ]
    assert len(projection.collisions) == 1
    assert projection.collisions[0].event_ids == ("close", "first", "simultaneous")


def test_projection_rounding_is_explicit_for_positive_and_negative_halves() -> None:
    assert round_projection(Fraction(3, 2), ProjectionRounding.FLOOR) == 1
    assert round_projection(Fraction(3, 2), ProjectionRounding.CEILING) == 2
    assert round_projection(Fraction(3, 2), ProjectionRounding.NEAREST) == 2
    assert round_projection(Fraction(-3, 2), ProjectionRounding.NEAREST) == -2


def test_written_and_continuous_pitch_projection_tracks_active_clef_and_viewport() -> None:
    score = _projection_score()
    sharp_c = WrittenPitch(PitchStep.C, 4, 1)
    assert written_staff_position(sharp_c, Clef.TREBLE) == -2
    assert continuous_staff_position(Fraction(61), Clef.TREBLE) == Fraction(-3, 2)

    written = project_written_pitch(score, "staff", Fraction(1, 8), sharp_c, bottom_row=10, viewport_y_offset=2)
    assert (written.clef, written.staff_position, written.row, written.rounded_row) == (
        Clef.TREBLE,
        Fraction(-2),
        Fraction(10),
        10,
    )
    measured = project_continuous_pitch(score, "staff", Fraction(1, 2), Fraction(42), bottom_row=12)
    assert measured.clef is Clef.BASS
    assert measured.staff_position == Fraction(-1, 2)
    assert measured.row == Fraction(25, 2)


@pytest.mark.parametrize("clef", [Clef.TREBLE, Clef.BASS])
def test_continuous_projection_preserves_exact_natural_intervals(clef: Clef) -> None:
    natural_classes = (0, 2, 4, 5, 7, 9, 11, 12)
    for octave in range(9):
        for lower, upper in pairwise(natural_classes):
            midi = (octave + 1) * 12 + lower
            written = written_staff_position(pitch_from_midi(midi), clef)
            for fraction in (Fraction(), Fraction(1, 7), Fraction(1, 2), Fraction(6, 7), Fraction(1)):
                assert (
                    continuous_staff_position(Fraction(midi) + fraction * (upper - lower), clef) == written + fraction
                )
    with pytest.raises(ProjectionError, match="outside the supported projection range"):
        continuous_staff_position(Fraction(1000), clef)


def test_pitch_projection_rejects_unknown_staff_and_out_of_range_time() -> None:
    score = _projection_score()
    with pytest.raises(ProjectionError, match="unknown projection staff"):
        project_continuous_pitch(score, "missing", Fraction(), Fraction(60), bottom_row=8)
    with pytest.raises(ProjectionError, match="outside the score timeline"):
        project_continuous_pitch(score, "staff", Fraction(2), Fraction(60), bottom_row=8)
