from __future__ import annotations

from fractions import Fraction

import pytest

from petrucci import (
    EventKind,
    LayoutError,
    NotationEvent,
    NotationMeasure,
    NotationScore,
    NotationSpan,
    NotationStaff,
    SpanKind,
    TimelineProjectionRequest,
    TimeSignature,
    layout_collisions,
    layout_score_proportional,
    pitch_from_midi,
)


def _note(event_id: str, onset: Fraction, midi: int, duration: Fraction = Fraction(1, 16)) -> NotationEvent:
    return NotationEvent(event_id, onset, duration, EventKind.NOTE, (pitch_from_midi(midi),))


def _score() -> NotationScore:
    first = _note("first", Fraction(), 60)
    close = _note("close", Fraction(1, 16), 60)
    middle = _note("middle", Fraction(), 64)
    last = _note("last", Fraction(5, 8), 67, Fraction(1, 8))
    return NotationScore(
        "proportional",
        (
            NotationStaff(
                "staff",
                (
                    NotationMeasure("pickup", 0, (first, close), irregular=True, duration=Fraction(1, 4)),
                    NotationMeasure(
                        "body",
                        1,
                        (middle, last),
                        time_signature=TimeSignature(3, 4),
                        duration=Fraction(3, 4),
                    ),
                ),
                spans=(NotationSpan("slur", SpanKind.SLUR, first.id, last.id),),
            ),
        ),
    )


def test_proportional_layout_uses_exact_columns_without_respacing() -> None:
    layout = layout_score_proportional(
        _score(),
        TimelineProjectionRequest(Fraction(), Fraction(16), width=32, preamble_width=10),
    )

    onsets = {event_id: layout.onset_for(event_id) for event_id in ("first", "close", "middle", "last")}
    assert all(onset is not None for onset in onsets.values())
    assert {event_id: onset.x for event_id, onset in onsets.items() if onset is not None} == {
        "first": 10,
        "close": 11,
        "middle": 14,
        "last": 24,
    }
    assert [boundary.duration for boundary in layout.measure_boundaries] == [Fraction(1, 4), Fraction(3, 4)]


def test_proportional_layout_preserves_clipped_span_endpoints() -> None:
    layout = layout_score_proportional(
        _score(),
        TimelineProjectionRequest(Fraction(1, 4), Fraction(16), width=20, preamble_width=10),
    )

    first = layout.onset_for("first")
    last = layout.onset_for("last")
    assert first is not None and first.x == 6
    assert last is not None and last.x == 20
    assert {"first", "last"}.issubset(layout.systems[0].clipped_event_ids)
    spans = layout.elements_for("slur")
    assert spans and all(element.continuation for element in spans)


def test_proportional_layout_reports_collisions_instead_of_moving_time() -> None:
    layout = layout_score_proportional(
        _score(),
        TimelineProjectionRequest(Fraction(), Fraction(4), width=20, preamble_width=10),
    )

    first = layout.onset_for("first")
    close = layout.onset_for("close")
    assert first is not None and close is not None and first.x == close.x == 10
    assert layout.timeline_collisions
    assert layout.timeline_collisions[0].event_ids == ("close", "first")
    collisions = layout_collisions(layout)
    assert collisions and {collisions[0].left.source_id, collisions[0].right.source_id} == {"first", "close"}


def test_proportional_layout_requires_room_for_the_notation_preamble() -> None:
    with pytest.raises(LayoutError, match="projection preamble must be at least"):
        layout_score_proportional(
            _score(),
            TimelineProjectionRequest(Fraction(), Fraction(8), width=20, preamble_width=1),
        )
