"""Consumer regressions: musical time anchors noteheads, including accidentals."""

from fractions import Fraction

import pytest

from petrucci import (
    ElementRole,
    FlowEvent,
    NotationLayoutPolicy,
    TimelineProjectionRequest,
    adapt_flow_events,
    layout_score_proportional,
)


@pytest.mark.parametrize("midi", [60, 61, 63, 66, 68, 70])
def test_proportional_noteheads_remain_at_the_requested_onset(midi: int) -> None:
    score = adapt_flow_events((FlowEvent("note", Fraction(), Fraction(1), (midi,)),)).score
    layout = layout_score_proportional(
        score,
        TimelineProjectionRequest(Fraction(-1, 4), Fraction(32), 80, preamble_width=16),
        policy=NotationLayoutPolicy(show_title=False),
    )
    onset = layout.onset_for("note")
    assert onset is not None
    heads = [element for element in layout.elements_for("note") if element.key.role is ElementRole.NOTEHEAD]
    assert heads and all(head.rect.x == onset.x for head in heads)
    staff_lines = [element for element in layout.elements if element.key.role is ElementRole.STAFF]
    expected_right = 78
    assert staff_lines and all(element.rect.x + element.rect.width >= expected_right for element in staff_lines)


def test_clipped_measure_does_not_invent_a_barline_or_hide_its_last_head() -> None:
    score = adapt_flow_events((FlowEvent("edge", Fraction(7, 2), Fraction(1, 2), (60,)),)).score
    layout = layout_score_proportional(
        score,
        TimelineProjectionRequest(Fraction(), Fraction(16), 32, preamble_width=16),
        policy=NotationLayoutPolicy(show_title=False, show_stems=False, show_pitch_labels=False),
    )
    assert not any(element.key.role is ElementRole.BARLINE for element in layout.elements)
    heads = [element for element in layout.elements_for("edge") if element.key.role is ElementRole.NOTEHEAD]
    onset = layout.onset_for("edge")
    assert onset is not None
    assert heads and heads[0].rect.x == onset.x
