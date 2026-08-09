from fractions import Fraction

from oud.exports.lilypond.voices.vocal import _append_imported_melody_bar
from petrucci.core.model import ImportedBarContent, ImportedScore, ImportedStaff, MelodyEvent, Piece
from petrucci.adapters.piece import notation_score_from_piece
from petrucci.core.score import SpanKind, StemDirection
from petrucci.engraving.score_typeset import ScoreTypesetOptions, typeset_score
from petrucci.terminal.api import GlyphMode


def _extended_piece() -> Piece:
    bar = ImportedBarContent(
        source_bar_index=0,
        proportion=(3, 2),
        melody_events=[
            MelodyEvent("c4", 0, note_type=4, voice=0, harmonic=True, fingering="1"),
            MelodyEvent("e4", 0, note_type=4, voice=1),
            MelodyEvent("d4", 1, note_type=4, voice=0, glissando_from_previous=True),
        ],
    )
    return Piece(imported_score=ImportedScore("ft3", [ImportedStaff("note", "Cantus", [bar])]))


def test_imported_notation_extensions_survive_canonical_layout() -> None:
    score = notation_score_from_piece(_extended_piece())
    measure = score.staffs[0].measures[0]
    upper, lower, target = measure.events

    assert upper.onset == lower.onset == Fraction(0)
    assert upper.stem is StemDirection.UP
    assert lower.stem is StemDirection.DOWN
    assert upper.harmonic and upper.fingering == "1"
    assert measure.proportion is not None
    assert (measure.proportion.numerator, measure.proportion.denominator) == (3, 2)
    assert any(span.kind is SpanKind.GLISSANDO and span.end_event_id == target.id for span in score.staffs[0].spans)

    result = typeset_score(
        score,
        options=ScoreTypesetOptions(width=72, height=24, glyph_mode=GlyphMode.SAFE),
    )
    assert "3:2" in result.text
    assert "H1" in result.text
    assert "/" in result.text


def test_imported_notation_extensions_emit_lilypond_tokens() -> None:
    piece = _extended_piece()
    assert piece.imported_score is not None
    bar = piece.imported_score.staffs[0].bars[0]
    body: list[str] = []

    _append_imported_melody_bar(body, bar, None)

    text = "\n".join(body)
    assert r"\scaleDurations 2/3 {" in text
    assert r"\flageolet" in text
    assert "-1" in text
    assert r"\glissando" in text
