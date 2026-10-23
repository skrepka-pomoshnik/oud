"""Octave clefs project sounding pitches without mutating the score."""

from fractions import Fraction

import pytest

from petrucci import (
    Clef,
    ElementRole,
    FlowEvent,
    FlowScoreOptions,
    GlyphMode,
    ScoreTypesetOptions,
    adapt_flow_events,
    continuous_staff_position,
    pitch_from_midi,
    typeset_score,
    written_staff_position,
)


def test_octave_clef_places_sounding_f3_at_written_f4_height() -> None:
    assert written_staff_position(pitch_from_midi(53), Clef.TREBLE_8VB) == written_staff_position(
        pitch_from_midi(65), Clef.TREBLE
    )
    assert continuous_staff_position(Fraction(107, 2), Clef.TREBLE_8VB) == continuous_staff_position(
        Fraction(131, 2), Clef.TREBLE
    )


@pytest.mark.parametrize("mode,glyph", ((GlyphMode.ASCII, "G"), (GlyphMode.PRETTY, "𝄞")))
def test_octave_clef_prints_eight_below_clef_and_preserves_sounding_midi(mode: GlyphMode, glyph: str) -> None:
    flow = adapt_flow_events(
        (FlowEvent("note", Fraction(), Fraction(1, 4), (53,)),), options=FlowScoreOptions(clef=Clef.TREBLE_8VB)
    )
    result = typeset_score(flow.score, options=ScoreTypesetOptions(width=60, height=24, glyph_mode=mode))
    row, column = next((y, line.index(glyph)) for y, line in enumerate(result.lines) if glyph in line)
    assert result.lines[row + 1][column] == "8"
    assert flow.score.staffs[0].measures[0].events[0].pitches[0].midi == 53


def test_octave_clef_braille_keeps_notehead_at_the_written_octave() -> None:
    results = []
    for midi, clef in ((53, Clef.TREBLE_8VB), (65, Clef.TREBLE)):
        flow = adapt_flow_events(
            (FlowEvent("note", Fraction(), Fraction(1, 4), (midi,)),), options=FlowScoreOptions(clef=clef)
        )
        results.append(
            typeset_score(flow.score, options=ScoreTypesetOptions(width=60, height=24, glyph_mode=GlyphMode.ADVANCED))
        )
    positions = [
        [
            (y, x)
            for y, row in enumerate(result.semantic_frame.roles)
            for x, role in enumerate(row)
            if role is ElementRole.NOTEHEAD
        ]
        for result in results
    ]
    assert positions[0] and positions[0] == positions[1]
    assert results[0].lines != results[1].lines
