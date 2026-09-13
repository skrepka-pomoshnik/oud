from __future__ import annotations

from fractions import Fraction

from petrucci import (
    ElementRole,
    FlowEvent,
    FlowMeasure,
    GlyphMode,
    ScoreTypesetOptions,
    TimeSignature,
    adapt_flow_measures,
    layout_score,
    typeset_score,
)


def test_breve_note_engraves_without_tied_wholes_stem_or_flag() -> None:
    flow = adapt_flow_measures(
        (
            FlowMeasure(
                "breve-measure",
                (FlowEvent("breve-note", Fraction(), Fraction(4), (60, 127)),),
                time_signature=TimeSignature(4, 2),
            ),
        ),
    )

    layout = layout_score(flow.score)
    elements = layout.elements_for("breve-note")
    roles = {element.key.role for element in elements}
    notehead = next(element for element in elements if element.key.role is ElementRole.NOTEHEAD)
    result = typeset_score(
        flow.score,
        options=ScoreTypesetOptions(width=40, height=20, glyph_mode=GlyphMode.SAFE),
    )

    assert flow.score.staffs[0].measures[0].events[0].duration == Fraction(2)
    assert notehead.value == "breve"
    assert ElementRole.STEM not in roles
    assert ElementRole.FLAG not in roles
    assert result.cells_for("breve-note")
    assert result.layout.document_height > 20
    assert not flow.score.staffs[0].spans


def test_dotted_breve_rest_keeps_distinct_semantics_when_clipped() -> None:
    flow = adapt_flow_measures(
        (
            FlowMeasure(
                "dotted-breve-measure",
                (FlowEvent("dotted-breve-rest", Fraction(), Fraction(6)),),
                time_signature=TimeSignature(6, 2),
                irregular=True,
            ),
        ),
    )

    result = typeset_score(
        flow.score,
        options=ScoreTypesetOptions(width=20, height=16, glyph_mode=GlyphMode.SAFE),
    )
    elements = result.layout.elements_for("dotted-breve-rest")
    rest = next(element for element in elements if element.key.role is ElementRole.REST)
    dots = tuple(element for element in elements if element.key.role is ElementRole.DOT)

    assert rest.value == "breve"
    assert len(dots) == 1 and dots[0].value == "1"
    assert result.cells_for("dotted-breve-rest")
