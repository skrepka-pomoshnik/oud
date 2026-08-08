from __future__ import annotations

from fractions import Fraction

import pytest

from petrucci import (
    ElementRole,
    FlowEvent,
    GlyphMode,
    LayoutViewport,
    PitchCue,
    PitchCueError,
    PitchStep,
    ScoreTypesetOptions,
    WrittenPitch,
    adapt_flow_events,
    layout_score,
    typeset_layout,
)


def test_pitch_cue_reuses_layout_and_exposes_semantic_cell() -> None:
    flow = adapt_flow_events((FlowEvent("target", Fraction(0), Fraction(1), (60,)),))
    layout = layout_score(flow.score, viewport=LayoutViewport(width=40, height=16))
    cue = PitchCue("heard", WrittenPitch(PitchStep.D, 4), event_id="target")

    result = typeset_layout(
        layout,
        score=flow.score,
        options=ScoreTypesetOptions(width=40, height=16, glyph_mode=GlyphMode.SAFE, pitch_cues=(cue,)),
    )

    assert result.layout is layout
    assert result.layout.event_ids == ("target",)
    assert result.cells_for("heard")
    y, x = result.cells_for("heard")[0]
    assert result.semantic_frame.roles[y][x] is ElementRole.PITCH_CUE


def test_pitch_cue_pitch_changes_row_without_relayout() -> None:
    flow = adapt_flow_events((FlowEvent("target", Fraction(0), Fraction(1), (60,)),))
    layout = layout_score(flow.score, viewport=LayoutViewport(width=40, height=16))
    low = PitchCue("low", WrittenPitch(PitchStep.C, 4), event_id="target")
    high = PitchCue("high", WrittenPitch(PitchStep.G, 4), event_id="target")
    low_options = ScoreTypesetOptions(width=40, height=16, glyph_mode=GlyphMode.SAFE, pitch_cues=(low,))
    high_options = ScoreTypesetOptions(width=40, height=16, glyph_mode=GlyphMode.SAFE, pitch_cues=(high,))

    low_result = typeset_layout(layout, score=flow.score, options=low_options)
    high_result = typeset_layout(layout, score=flow.score, options=high_options)

    assert low_result.layout is high_result.layout
    assert low_result.cells_for("low")[0][0] > high_result.cells_for("high")[0][0]


def test_pitch_cue_accepts_exact_onset_anchor() -> None:
    flow = adapt_flow_events((FlowEvent("target", Fraction(1), Fraction(1), (60,)),))
    layout = layout_score(flow.score, viewport=LayoutViewport(width=40, height=16))
    measure_id = flow.score.staffs[0].measures[0].id
    cue = PitchCue(
        "heard",
        WrittenPitch(PitchStep.E, 4),
        staff_id="flow-staff",
        measure_id=measure_id,
        onset=Fraction(1, 4),
    )

    result = typeset_layout(
        layout,
        score=flow.score,
        options=ScoreTypesetOptions(width=40, height=16, pitch_cues=(cue,)),
    )

    assert result.cells_for("heard")


def test_pitch_cues_require_score_for_cached_layout() -> None:
    flow = adapt_flow_events((FlowEvent("target", Fraction(0), Fraction(1), (60,)),))
    layout = layout_score(flow.score, viewport=LayoutViewport(width=40, height=16))
    options = ScoreTypesetOptions(
        width=40,
        height=16,
        pitch_cues=(PitchCue("heard", WrittenPitch(PitchStep.C, 4), event_id="target"),),
    )

    with pytest.raises(TypeError, match="score is required"):
        typeset_layout(layout, options=options)


def test_pitch_cue_rejects_missing_anchor() -> None:
    with pytest.raises(PitchCueError, match="exactly one"):
        PitchCue("heard", WrittenPitch(PitchStep.C, 4))
