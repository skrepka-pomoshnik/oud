from __future__ import annotations

from fractions import Fraction

import pytest

from petrucci import (
    DurationBase,
    EventKind,
    FlowEvent,
    FlowMeasure,
    LayoutViewport,
    NotationEvent,
    NotationMeasure,
    NotationScore,
    NotationSpan,
    NotationStaff,
    ScoreValidationError,
    SpanKind,
    TimeSignature,
    adapt_flow_measures,
    layout_score,
    pitch_from_midi,
    score_measure_boundaries,
    spell_duration,
)
from petrucci.engraving.layout.engine import ElementRole
from petrucci.terminal.api import SemanticFrame
from petrucci.terminal.canvas.framebuffer import Frame


def _note(event_id: str, onset: Fraction, midi: int = 60, duration: Fraction = Fraction(1, 4)) -> NotationEvent:
    return NotationEvent(event_id, onset, duration, EventKind.NOTE, (pitch_from_midi(midi),))


def test_explicit_pickup_duration_defines_the_canonical_timeline() -> None:
    flow = adapt_flow_measures(
        (
            FlowMeasure(
                "pickup", (FlowEvent("pickup-note", Fraction(), Fraction(1), (60,)),), beat_capacity=Fraction(1)
            ),
            FlowMeasure("full", (FlowEvent("full-note", Fraction(), Fraction(1), (62,)),)),
        ),
    )

    pickup, full = score_measure_boundaries(flow.score)
    assert (pickup.start, pickup.duration, pickup.end) == (Fraction(), Fraction(1, 4), Fraction(1, 4))
    assert (full.start, full.duration) == (Fraction(1, 4), Fraction(1))
    assert flow.score.staffs[0].measures[0].duration == Fraction(1, 4)


def test_explicit_duration_validates_irregular_measures_and_aligned_staffs() -> None:
    with pytest.raises(ScoreValidationError, match="capacity 1/4"):
        NotationScore(
            "overflow",
            (
                NotationStaff(
                    "staff",
                    (
                        NotationMeasure(
                            "pickup", 0, (_note("late", Fraction(1, 4)),), irregular=True, duration=Fraction(1, 4)
                        ),
                    ),
                ),
            ),
        )

    with pytest.raises(ScoreValidationError, match="matching measure durations"):
        NotationScore(
            "unaligned",
            (
                NotationStaff("upper", (NotationMeasure("upper-m", 1, duration=Fraction(1, 4)),)),
                NotationStaff("lower", (NotationMeasure("lower-m", 1, duration=Fraction(1, 2)),)),
            ),
        )


def test_written_duration_spelling_supports_breve_and_dotted_breve() -> None:
    spelling = spell_duration(Fraction(2))
    assert spelling is not None and (spelling.base, spelling.dots) == (DurationBase.BREVE, 0)
    dotted = spell_duration(Fraction(3))
    assert dotted is not None and (dotted.base, dotted.dots) == (DurationBase.BREVE, 1)
    assert spell_duration(Fraction(1, 3)) is None


def test_all_staffs_share_exact_onset_anchors() -> None:
    upper = NotationStaff(
        "upper",
        (NotationMeasure("upper-m", 1, (_note("upper-a", Fraction()), _note("upper-c", Fraction(1, 2)))),),
    )
    lower = NotationStaff(
        "lower",
        (
            NotationMeasure(
                "lower-m",
                1,
                (
                    _note("lower-a", Fraction(), 48),
                    _note("lower-b", Fraction(1, 4), 50),
                    _note("lower-c", Fraction(1, 2), 52),
                ),
            ),
        ),
    )

    layout = layout_score(NotationScore("aligned", (upper, lower)), viewport=LayoutViewport(width=80))

    positions = tuple(layout.onset_for(event_id) for event_id in ("upper-a", "lower-a", "upper-c", "lower-c"))
    assert all(position is not None for position in positions)
    xs = {position.event_id: position.x for position in positions if position is not None}
    assert xs["upper-a"] == xs["lower-a"]
    assert xs["upper-c"] == xs["lower-c"]
    assert layout.measure_boundaries[0].duration == Fraction(1)


def test_span_geometry_survives_a_clipped_endpoint() -> None:
    events = tuple(
        _note(f"event-{index}", Fraction(index, 16), 60 + (index % 5), Fraction(1, 16)) for index in range(12)
    )
    staff = NotationStaff(
        "staff",
        (NotationMeasure("measure", 1, events),),
        spans=(NotationSpan("tie", SpanKind.TIE, events[0].id, events[-1].id),),
    )

    layout = layout_score(NotationScore("clipped-span", (staff,)), viewport=LayoutViewport(width=24))

    assert layout.onset_for(events[-1].id) is not None
    assert events[-1].id in layout.systems[0].clipped_event_ids
    assert layout.elements_for("tie")
    assert all(element.continuation for element in layout.elements_for("tie"))


def test_staff_state_and_semantic_cells_are_preindexed() -> None:
    staff = NotationStaff(
        "staff",
        (
            NotationMeasure("first", 1, time_signature=TimeSignature(3, 4)),
            NotationMeasure("second", 2),
        ),
    )
    assert staff.measure_state(1)[1] == TimeSignature(3, 4)

    frame = SemanticFrame(
        Frame(lines=["ab"], attrs=[(0, 0)]),
        ((ElementRole.NOTEHEAD, ElementRole.STEM),),
        (("note", "note"),),
    )
    assert frame.cells_for_many(("note", "missing")) == {"note": ((0, 0), (0, 1)), "missing": ()}
