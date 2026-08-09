from __future__ import annotations

from fractions import Fraction
from pathlib import Path

import pytest

from petrucci import (
    AccidentalDisplay,
    BarlineKind,
    BeamKind,
    EventKind,
    GlyphMode,
    KeySignature,
    LyricSyllable,
    NotationEvent,
    NotationMeasure,
    NotationScore,
    NotationSpan,
    NotationStaff,
    OrnamentKind,
    PitchStep,
    ScoreTypesetOptions,
    SpanKind,
    TerminalNoteheads,
    TimeSignature,
    WrittenPitch,
    pitch_from_midi,
    typeset_score,
)
from petrucci.terminal.display import display_width
from petrucci.engraving.layout.engine import ElementRole


def _event(event_id: str, onset: int, midi: int | None, duration: Fraction = Fraction(1, 4)) -> NotationEvent:
    return NotationEvent(
        id=event_id,
        onset=Fraction(onset, 4),
        duration=duration,
        kind=EventKind.REST if midi is None else EventKind.NOTE,
        pitches=() if midi is None else (pitch_from_midi(midi),),
    )


def _score() -> NotationScore:
    first = _event("first-c", 0, 60)
    repeated = _event("second-c", 1, 60)
    rest = _event("rest", 2, None)
    final = _event("final-g", 3, 67)
    return NotationScore(
        id="terminal-score",
        title="Practice",
        composer="Petrucci",
        staffs=(
            NotationStaff(
                id="voice",
                label="Voice",
                measures=(
                    NotationMeasure(
                        "measure",
                        1,
                        (first, repeated, rest, final),
                        time_signature=TimeSignature(),
                    ),
                ),
                lyrics=(
                    LyricSyllable("lyric-first", first.id, "Sing"),
                    LyricSyllable("lyric-second", repeated.id, "wide界"),
                ),
            ),
        ),
    )


def test_typeset_score_returns_text_and_semantic_planes() -> None:
    result = typeset_score(
        _score(),
        options=ScoreTypesetOptions(width=64, height=24, glyph_mode=GlyphMode.PRETTY),
    )

    assert len(result.lines) == 24
    assert all(display_width(line) == 64 for line in result.lines)
    assert "Practice" in result.text
    assert "Sing" in result.text
    assert "wide界" in result.text
    assert result.layout.onset_for("first-c") is not None
    assert result.cells_for("first-c")
    first_cells = result.cells_for("first-c")
    assert ElementRole.NOTEHEAD in {result.semantic_frame.roles[y][x] for y, x in first_cells}
    assert len(result.semantic_frame.roles) == 24
    assert all(len(row) == 64 for row in result.semantic_frame.element_ids)


def test_repeated_pitch_ids_resolve_to_distinct_cells() -> None:
    result = typeset_score(_score(), options=ScoreTypesetOptions(width=64, height=24))

    first_cells = set(result.cells_for("first-c"))
    second_cells = set(result.cells_for("second-c"))
    rest_cells = set(result.cells_for("rest"))

    assert first_cells
    assert second_cells
    assert rest_cells
    assert first_cells.isdisjoint(second_cells)
    assert first_cells.isdisjoint(rest_cells)


def test_clipped_event_keeps_a_visible_identity_marker() -> None:
    score = _score()
    layout_only = typeset_score(
        score,
        options=ScoreTypesetOptions(width=30, height=24, glyph_mode=GlyphMode.SAFE),
    )
    clipped_id = layout_only.layout.systems[0].clipped_event_ids[0]

    result = typeset_score(score, options=ScoreTypesetOptions(width=30, height=24, glyph_mode=GlyphMode.SAFE))

    assert result.layout.systems[0].clipped
    assert result.layout.onset_for(clipped_id) is None
    assert result.layout.location_for(clipped_id) is not None
    assert result.layout.system_for_event(clipped_id) is result.layout.systems[0]
    cells = result.cells_for(clipped_id)
    assert cells
    assert any(result.semantic_frame.roles[y][x] is ElementRole.CLIP_MARKER for y, x in cells)


def test_safe_glyph_mode_keeps_structure_without_music_symbols() -> None:
    result = typeset_score(
        _score(),
        options=ScoreTypesetOptions(width=64, height=24, glyph_mode=GlyphMode.SAFE),
    )

    assert "G" in result.text
    assert "o" in result.text
    assert "-" in result.text
    assert not {"𝄞", "●", "─"}.intersection(result.text)
    assert result.layout.onset_for("final-g") is not None


def test_custom_noteheads_preserve_pretty_inventory_and_semantics() -> None:
    result = typeset_score(
        _score(),
        options=ScoreTypesetOptions(
            width=64,
            height=24,
            glyph_mode=GlyphMode.PRETTY,
            noteheads=TerminalNoteheads(filled="o", open="O"),
        ),
    )

    assert "o" in result.text
    assert "●" not in result.text
    assert "𝄞" in result.text
    assert "─" in result.text
    assert result.cells_for("first-c")


def test_custom_noteheads_reject_non_cell_glyphs() -> None:
    with pytest.raises(ValueError, match="exactly one terminal cell"):
        TerminalNoteheads(filled="oo", open="O")


def test_pretty_and_safe_modes_preserve_event_identity_and_roles() -> None:
    pretty = typeset_score(_score(), options=ScoreTypesetOptions(width=64, height=24, glyph_mode=GlyphMode.PRETTY))
    safe = typeset_score(_score(), options=ScoreTypesetOptions(width=64, height=24, glyph_mode=GlyphMode.SAFE))

    for event_id in pretty.layout.event_ids:
        assert pretty.cells_for(event_id) == safe.cells_for(event_id)
    assert pretty.semantic_frame.element_ids == safe.semantic_frame.element_ids
    assert pretty.semantic_frame.roles == safe.semantic_frame.roles


def test_safe_key_signature_paints_each_accidental_as_a_semantic_cell() -> None:
    note = _event("key-note", 0, 60)
    score = NotationScore(
        "key-score",
        (
            NotationStaff(
                "key-staff",
                (
                    NotationMeasure(
                        "key-measure",
                        1,
                        (note,),
                        key_signature=KeySignature(2),
                    ),
                ),
            ),
        ),
    )

    result = typeset_score(
        score,
        options=ScoreTypesetOptions(width=64, height=24, glyph_mode=GlyphMode.SAFE),
    )
    signature_cells = [
        (y, x)
        for y, row in enumerate(result.semantic_frame.roles)
        for x, role in enumerate(row)
        if role is ElementRole.KEY_SIGNATURE
    ]

    assert len(signature_cells) == 2
    assert result.text.count("#") == 2


def test_safe_terminal_score_matches_human_readable_snapshot() -> None:
    result = typeset_score(
        _score(),
        options=ScoreTypesetOptions(width=64, height=24, glyph_mode=GlyphMode.SAFE),
    )
    fixture = Path(__file__).parent / "fixtures" / "petrucci_score_safe.snap.txt"

    assert result.text == fixture.read_text(encoding="utf-8")


def test_semantic_frame_tracks_both_cells_of_wide_lyric_glyph() -> None:
    result = typeset_score(
        _score(),
        options=ScoreTypesetOptions(width=64, height=24),
    )

    lyric_cells = result.cells_for("lyric-second")
    assert len(lyric_cells) == display_width("wide界")
    assert all(result.semantic_frame.roles[y][x] is ElementRole.LYRIC for y, x in lyric_cells)


def test_safe_terminal_paints_flags_beams_and_tie_continuations() -> None:
    first = NotationEvent(
        "beam-start",
        Fraction(0),
        Fraction(1, 8),
        EventKind.NOTE,
        (pitch_from_midi(64),),
        beam=BeamKind.START,
    )
    second = NotationEvent(
        "beam-end",
        Fraction(1, 8),
        Fraction(1, 8),
        EventKind.NOTE,
        (pitch_from_midi(65),),
        beam=BeamKind.END,
    )
    flagged = NotationEvent(
        "flagged",
        Fraction(1, 4),
        Fraction(1, 16),
        EventKind.NOTE,
        (pitch_from_midi(67),),
    )
    tied = NotationEvent(
        "tied",
        Fraction(0),
        Fraction(1, 4),
        EventKind.NOTE,
        (pitch_from_midi(67),),
    )
    score = NotationScore(
        "marks",
        (
            NotationStaff(
                "marks-staff",
                (
                    NotationMeasure("marks-1", 1, (first, second, flagged), forced_break_after=True),
                    NotationMeasure("marks-2", 2, (tied,)),
                ),
                spans=(NotationSpan("marks-tie", SpanKind.TIE, flagged.id, tied.id),),
            ),
        ),
    )

    first_page = typeset_score(
        score,
        options=ScoreTypesetOptions(width=64, height=24, glyph_mode=GlyphMode.SAFE),
    )
    second_page = typeset_score(
        score,
        options=ScoreTypesetOptions(width=64, height=24, system_offset=1, glyph_mode=GlyphMode.SAFE),
    )

    assert "=" in first_page.text
    assert "\\" in first_page.text
    assert ">" in first_page.text
    assert "<" in second_page.text
    assert "_" in second_page.text
    assert first_page.semantic_frame.cells_for("marks-tie")
    assert second_page.semantic_frame.cells_for("marks-tie")


@pytest.mark.parametrize(
    ("barline", "glyph"),
    [
        ("repeat-start", "{"),
        ("repeat-end", "}"),
        ("repeat-both", ":"),
    ],
)
def test_safe_terminal_distinguishes_repeat_barlines(barline: str, glyph: str) -> None:
    note = NotationEvent(
        "repeat-note",
        Fraction(0),
        Fraction(1, 4),
        EventKind.NOTE,
        (pitch_from_midi(60),),
    )
    measure = NotationMeasure(
        "repeat-measure",
        1,
        (note,),
        barline=BarlineKind(barline),
    )
    score = NotationScore("repeat-score", (NotationStaff("repeat-staff", (measure,)),))

    result = typeset_score(
        score,
        options=ScoreTypesetOptions(width=48, height=20, glyph_mode=GlyphMode.SAFE),
    )
    barline_cells = [
        (y, x)
        for y, row in enumerate(result.semantic_frame.roles)
        for x, role in enumerate(row)
        if role is ElementRole.BARLINE
    ]

    assert barline_cells
    assert {result.lines[y][x] for y, x in barline_cells} == {glyph}


@pytest.mark.parametrize(
    ("glyph_mode", "expected"),
    [
        (GlyphMode.PRETTY, ("𝄾", "𝄿", "𝅀", "𝅁")),
        (GlyphMode.SAFE, ("e", "s", "t", "x")),
    ],
)
def test_terminal_distinguishes_short_rest_durations(
    glyph_mode: GlyphMode,
    expected: tuple[str, str, str, str],
) -> None:
    rests = (
        NotationEvent("rest-8", Fraction(0), Fraction(1, 8), EventKind.REST),
        NotationEvent("rest-16", Fraction(1, 8), Fraction(1, 16), EventKind.REST),
        NotationEvent("rest-32", Fraction(3, 16), Fraction(1, 32), EventKind.REST),
        NotationEvent("rest-64", Fraction(7, 32), Fraction(1, 64), EventKind.REST),
    )
    score = NotationScore(
        "rest-score",
        (NotationStaff("rest-staff", (NotationMeasure("rest-measure", 1, rests),)),),
    )

    result = typeset_score(
        score,
        options=ScoreTypesetOptions(width=64, height=20, glyph_mode=glyph_mode),
    )

    for rest, glyph in zip(rests, expected, strict=True):
        cells = [(y, x) for y, x in result.cells_for(rest.id) if result.semantic_frame.roles[y][x] is ElementRole.REST]
        assert len(cells) == 1
        y, x = cells[0]
        assert result.lines[y][x] == glyph


def test_terminal_paints_endings_ornaments_and_fermatas_in_reserved_rows() -> None:
    note = NotationEvent(
        "marked-note",
        Fraction(0),
        Fraction(1, 4),
        EventKind.NOTE,
        (pitch_from_midi(60),),
        fermata=True,
        ornament=OrnamentKind.PLUS,
    )
    score = NotationScore(
        "marked-score",
        (
            NotationStaff(
                "marked-staff",
                (NotationMeasure("marked-measure", 1, (note,), ending_numbers=(1, 2)),),
            ),
        ),
    )

    result = typeset_score(
        score,
        options=ScoreTypesetOptions(width=48, height=24, glyph_mode=GlyphMode.SAFE),
    )
    rows = result.layout.systems[0].staff_rows[0]

    assert "[1,2." in result.text
    assert "+" in result.text
    assert "^" in result.text
    assert rows.ending_row is not None
    assert rows.ornament_row is not None
    assert rows.fermata_row is not None
    assert len({rows.ending_row, rows.ornament_row, rows.fermata_row}) == 3


def test_terminal_paints_courtesy_accidental_and_editorial_brackets() -> None:
    note = NotationEvent(
        "editorial-note",
        Fraction(0),
        Fraction(1, 4),
        EventKind.NOTE,
        (WrittenPitch(PitchStep.C, 4, 0, AccidentalDisplay.COURTESY),),
        editorial_brackets=True,
    )
    score = NotationScore(
        "editorial-score",
        (NotationStaff("editorial-staff", (NotationMeasure("editorial-measure", 1, (note,)),)),),
    )

    result = typeset_score(
        score,
        options=ScoreTypesetOptions(width=48, height=18, glyph_mode=GlyphMode.SAFE),
    )

    assert "(n)[" in result.text
    assert "]" in result.text
    roles = {role for row in result.semantic_frame.roles for role in row if role is not None}
    assert ElementRole.EDITORIAL_BRACKET in roles
