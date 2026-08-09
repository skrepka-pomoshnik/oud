from __future__ import annotations

from petrucci import (
    Bar,
    GlyphMode,
    MelodyEvent,
    Piece,
    ScoreTypesetOptions,
    notation_score_from_piece,
    typeset_score,
)


def test_melody_source_identity_survives_projection_and_typesetting() -> None:
    source_id = "source:folio-7:sign-12"
    piece = Piece(
        bars=[Bar(melody_events=[MelodyEvent("c4", 0, note_type=4, source_id=source_id)])],
    )

    score = notation_score_from_piece(piece)
    result = typeset_score(
        score,
        options=ScoreTypesetOptions(width=48, height=18, glyph_mode=GlyphMode.SAFE),
    )

    event = score.staffs[0].measures[0].events[0]
    assert event.id == source_id
    cells = result.cells_for(source_id)
    assert cells
    assert {result.semantic_frame.element_ids[y][x] for y, x in cells} == {source_id}
