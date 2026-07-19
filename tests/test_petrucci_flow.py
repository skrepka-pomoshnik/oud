from __future__ import annotations

from fractions import Fraction
from typing import cast

import pytest

from petrucci import (
    ElementRole,
    FlowAdapterError,
    FlowEvent,
    FlowScoreOptions,
    GlyphMode,
    LayoutViewport,
    ScoreTypesetOptions,
    Syllabic,
    TimeSignature,
    adapt_flow_events,
    layout_collisions,
    layout_score,
    typeset_layout,
)


def test_flow_adapter_splits_measure_crossing_note_and_adds_tie() -> None:
    flow = adapt_flow_events(
        (
            FlowEvent(
                "held-c",
                Fraction(5),
                Fraction(3),
                (60,),
                lyric="hold",
                syllabic=Syllabic.SINGLE,
            ),
        ),
        options=FlowScoreOptions(time_signature=TimeSignature(6, 8)),
    )

    staff = flow.score.staffs[0]
    first, second = (measure.events[0] for measure in staff.measures)
    assert (first.onset, first.duration) == (Fraction(5, 8), Fraction(1, 8))
    assert (second.onset, second.duration) == (Fraction(0), Fraction(1, 4))
    assert flow.notation_ids_for("held-c") == ("held-c", "held-c#petrucci-segment-2")
    assert flow.active_notation_event_ids(Fraction(6)) == ("held-c#petrucci-segment-2",)
    assert [(span.start_event_id, span.end_event_id) for span in staff.spans] == [(first.id, second.id)]
    assert staff.lyrics[0].event_id == first.id


def test_flow_identity_handles_overlaps_and_expands_source_values() -> None:
    flow = adapt_flow_events(
        (
            FlowEvent("lower", Fraction(0), Fraction(2), (48,), voice=1),
            FlowEvent("upper", Fraction(1), Fraction(1), (72,), voice=0),
            FlowEvent("rest", Fraction(2), Fraction(1)),
        )
    )

    assert flow.active_event_ids(Fraction(3, 2)) == ("lower", "upper")
    assert flow.active_event_ids(Fraction(2)) == ("rest",)
    caller_value = object()
    assert flow.expand_values({"lower": caller_value}) == {"lower": caller_value}
    with pytest.raises(FlowAdapterError, match="unknown event IDs: missing"):
        flow.expand_values({"missing": caller_value})


@pytest.mark.parametrize("width", (40, 80))
def test_flow_render_preserves_semantics_at_supported_widths(width: int) -> None:
    flow = adapt_flow_events(
        (
            FlowEvent("first-c", Fraction(0), Fraction(1), (60,), lyric="same"),
            FlowEvent("second-c", Fraction(1), Fraction(1), (60,), lyric="pitch"),
            FlowEvent("rest", Fraction(2), Fraction(1)),
            FlowEvent("chord", Fraction(3), Fraction(1), (64, 67)),
            FlowEvent("next-system", Fraction(4), Fraction(2), (69,)),
        ),
        options=FlowScoreOptions(title="Trainer", staff_label="Voice"),
    )
    layout = layout_score(flow.score, viewport=LayoutViewport(width=width, height=18))
    canonical = {event.id: event for measure in flow.score.staffs[0].measures for event in measure.events}
    assert canonical["first-c"].pitches[0].midi == 60
    assert canonical["second-c"].duration == Fraction(1, 4)
    assert canonical["rest"].pitches == ()
    assert len(canonical["chord"].pitches) == 2
    active_id = flow.notation_ids_for("next-system")[0]
    active_location = layout.location_for(active_id)
    assert active_location is not None
    result = typeset_layout(
        layout,
        options=ScoreTypesetOptions(
            width=width,
            height=18,
            system_offset=active_location.system_index,
            glyph_mode=GlyphMode.SAFE,
        ),
    )

    assert layout_collisions(result.layout) == ()
    assert result.cells_for(active_id)
    roles = {
        result.semantic_frame.roles[y][x] for event_id in result.layout.event_ids for y, x in result.cells_for(event_id)
    }
    assert ElementRole.NOTEHEAD in roles


def test_flow_adapter_rejects_invalid_or_ambiguous_identity() -> None:
    with pytest.raises(FlowAdapterError, match="must be unique"):
        adapt_flow_events(
            (
                FlowEvent("same", Fraction(0), Fraction(1), (60,)),
                FlowEvent("same", Fraction(1), Fraction(1), (62,)),
            )
        )
    with pytest.raises(FlowAdapterError, match="reserved marker"):
        FlowEvent("bad#petrucci-segment-2", Fraction(0), Fraction(1), (60,))
    with pytest.raises(FlowAdapterError, match="invalid flow score identity"):
        adapt_flow_events(
            (FlowEvent("same-as-score", Fraction(0), Fraction(1), (60,)),),
            options=FlowScoreOptions(score_id="same-as-score"),
        )
    with pytest.raises(FlowAdapterError, match="must be a Fraction"):
        FlowEvent("float-time", cast(Fraction, 0.0), Fraction(1), (60,))
