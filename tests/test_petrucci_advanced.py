from __future__ import annotations

from dataclasses import replace
from fractions import Fraction
from pathlib import Path

import pytest

from petrucci import (
    BarlineKind,
    BeamKind,
    ElementRole,
    EventKind,
    GlyphMode,
    LayoutMetrics,
    LyricSyllable,
    NotationEvent,
    NotationLayoutPolicy,
    NotationMeasure,
    NotationScore,
    NotationSpan,
    NotationStaff,
    PitchCue,
    ScoreTypesetOptions,
    SpanKind,
    TerminalNoteheads,
    layout_collisions,
    pitch_from_midi,
    typeset_layout,
    typeset_score,
)
from petrucci.terminal.display import display_width
from scripts.notation_preview import example_score


def _note(
    event_id: str, onset: Fraction, duration: Fraction, midi: int, beam: BeamKind = BeamKind.NONE
) -> NotationEvent:
    return NotationEvent(event_id, onset, duration, EventKind.NOTE, (pitch_from_midi(midi),), beam=beam)


def _score(*, broken: bool = False) -> NotationScore:
    measures = (
        NotationMeasure(
            "first",
            1,
            (
                _note("e", Fraction(0), Fraction(1, 8), 64, BeamKind.START),
                _note("g", Fraction(1, 8), Fraction(1, 8), 67, BeamKind.END),
                _note("b", Fraction(1, 4), Fraction(1, 4), 71),
                _note("held", Fraction(1, 2), Fraction(1, 2), 71),
            ),
            forced_break_after=broken,
        ),
        NotationMeasure(
            "second",
            2,
            (
                _note("continued", Fraction(0), Fraction(1, 2), 71),
                _note("sharp", Fraction(1, 2), Fraction(3, 16), 78),
                NotationEvent("rest", Fraction(11, 16), Fraction(1, 16), EventKind.REST),
                _note("d", Fraction(3, 4), Fraction(1, 4), 74),
            ),
            barline=BarlineKind.FINAL,
        ),
    )
    return NotationScore(
        "advanced-score",
        (
            NotationStaff(
                "voice",
                measures,
                spans=(
                    NotationSpan("phrase", SpanKind.SLUR, "e", "b"),
                    NotationSpan("tie", SpanKind.TIE, "held", "continued"),
                ),
                lyrics=(LyricSyllable("word", "e", "Sing"), LyricSyllable("wide", "continued", "界")),
            ),
        ),
    )


@pytest.mark.parametrize("width", (48, 80))
def test_advanced_renders_music_and_keeps_visible_identity(width: int) -> None:
    options = ScoreTypesetOptions(width=width, height=32, glyph_mode=GlyphMode.ADVANCED)
    result = typeset_score(_score(), options=options)

    assert all(display_width(line) == width for line in result.lines)
    musical_roles = {
        ElementRole.NOTEHEAD,
        ElementRole.REST,
        ElementRole.CLEF,
        ElementRole.STAFF,
        ElementRole.STEM,
        ElementRole.BEAM,
        ElementRole.BARLINE,
        ElementRole.TIE,
        ElementRole.SLUR,
        ElementRole.ACCIDENTAL,
        ElementRole.TIME_SIGNATURE,
    }
    painted_roles = set()
    for y, row in enumerate(result.semantic_frame.roles):
        for x, role in enumerate(row):
            if role in musical_roles:
                assert 0x2800 <= ord(result.lines[y][x]) <= 0x28FF
                painted_roles.add(role)
    assert musical_roles <= painted_roles
    for location in result.layout.event_locations:
        page = typeset_layout(result.layout, options=replace(options, system_offset=location.system_index))
        assert page.cells_for(location.event_id)
    for span_id in ("phrase", "tie"):
        assert result.cells_for(span_id)


def test_advanced_and_ascii_share_layout_with_projected_notehead_identity() -> None:
    score = _score()
    options = ScoreTypesetOptions(width=80, height=32, glyph_mode=GlyphMode.ASCII)
    ascii_result = typeset_score(score, options=options)
    advanced = typeset_score(score, options=replace(options, glyph_mode=GlyphMode.ADVANCED))
    legacy = typeset_score(score, options=replace(options, glyph_mode=GlyphMode.SAFE))

    assert ascii_result.text == legacy.text
    assert advanced.layout is ascii_result.layout
    for event_id in advanced.layout.event_ids:
        head_columns = {
            x
            for y, x in advanced.cells_for(event_id)
            if advanced.semantic_frame.roles[y][x] in {ElementRole.NOTEHEAD, ElementRole.REST}
        }
        logical_columns = {
            element.rect.x
            for element in advanced.layout.elements_for(event_id)
            if element.key.role in {ElementRole.NOTEHEAD, ElementRole.REST}
        }
        assert logical_columns <= head_columns
        ascii_cells = {
            (y, x)
            for y, x in ascii_result.cells_for(event_id)
            if ascii_result.semantic_frame.roles[y][x] in {ElementRole.NOTEHEAD, ElementRole.REST}
        }
        assert ascii_cells
    assert len(advanced.text.splitlines()) < len(ascii_result.text.splitlines())


def test_advanced_viewport_crop_matches_full_frame_and_keeps_wide_text() -> None:
    score = _score()
    full = typeset_score(score, options=ScoreTypesetOptions(width=80, height=32, glyph_mode=GlyphMode.ADVANCED))
    cropped = typeset_layout(
        full.layout,
        options=ScoreTypesetOptions(
            width=40,
            height=12,
            layout_width=80,
            x_offset=3,
            y_offset=2,
            glyph_mode=GlyphMode.ADVANCED,
        ),
    )

    assert all(display_width(line) == 40 for line in cropped.lines)
    for y, row in enumerate(cropped.semantic_frame.element_ids):
        assert row == full.semantic_frame.element_ids[y + 2][3:43]
    assert len(full.cells_for("wide")) == 2


def test_advanced_broken_spans_custom_heads_and_event_decorations() -> None:
    score = _score(broken=True)
    options = ScoreTypesetOptions(width=64, height=24, glyph_mode=GlyphMode.ADVANCED, system_offset=1)
    result = typeset_score(score, options=options)
    custom = typeset_score(score, options=replace(options, noteheads=TerminalNoteheads(filled="x", open="O")))

    assert result.cells_for("tie")
    custom_heads = {
        (y, x) for y, x in custom.cells_for("continued") if custom.semantic_frame.roles[y][x] is ElementRole.NOTEHEAD
    }
    assert len(custom_heads) == 1
    assert custom_heads <= set(result.cells_for("continued"))
    assert "O" in custom.text and "x" in custom.text
    accepted_cells = result.cells_for("continued")
    assert all(result.semantic_frame.element_ids[y][x] == "continued" for y, x in accepted_cells)


def test_advanced_preserves_hidden_meter_spacing() -> None:
    options = ScoreTypesetOptions(width=80, height=32, glyph_mode=GlyphMode.ADVANCED)
    visible = typeset_score(_score(), options=options)
    hidden = typeset_score(_score(), options=replace(options, policy=NotationLayoutPolicy(show_time_signature=False)))

    assert visible.layout.onsets == hidden.layout.onsets
    assert not any(role is ElementRole.TIME_SIGNATURE for row in hidden.semantic_frame.roles for role in row)


def test_compact_beams_reduce_height_without_changing_written_pitch_positions() -> None:
    options = ScoreTypesetOptions(width=80, height=32, glyph_mode=GlyphMode.ADVANCED)
    normal = typeset_score(_score(), options=options)
    compact = typeset_score(_score(), options=replace(options, policy=NotationLayoutPolicy(compact_beams=True)))

    assert compact.layout.document_height < normal.layout.document_height
    assert layout_collisions(compact.layout) == ()
    beam = next(element for element in compact.layout.elements if element.key.role is ElementRole.BEAM)
    staff_rows = compact.layout.systems[0].staff_rows[0]
    assert staff_rows.line_rows[0] <= beam.rect.y <= staff_rows.line_rows[-1]
    for event_id in ("e", "g"):
        head = next(
            element for element in compact.layout.elements_for(event_id) if element.key.role is ElementRole.NOTEHEAD
        )
        assert 0 < head.rect.y - beam.rect.y <= 5


@pytest.mark.parametrize("mode", (GlyphMode.ASCII, GlyphMode.ADVANCED))
def test_standalone_preview_preserves_every_visible_note(mode: GlyphMode) -> None:
    result = typeset_score(
        example_score(),
        options=ScoreTypesetOptions(
            width=64,
            height=24,
            glyph_mode=mode,
            metrics=LayoutMetrics(event_gap=1, barline_gap=1),
            policy=NotationLayoutPolicy(show_title=False, show_measure_numbers=False, compact_beams=True),
        ),
    )
    assert len(result.layout.systems) == 1
    assert all(result.cells_for(event_id) for event_id in result.layout.event_ids)
    assert layout_collisions(result.layout) == ()


def test_complete_tie_is_near_heads_and_retains_source_endpoints() -> None:
    result = typeset_score(_score(), options=ScoreTypesetOptions(width=80, height=32, glyph_mode=GlyphMode.ADVANCED))
    tie = next(element for element in result.layout.elements if element.key.source_id == "tie")
    assert tie.anchor_ids == ("held", "continued")
    head_rows = {
        y
        for event_id in ("held", "continued")
        for y, x in result.cells_for(event_id)
        if result.semantic_frame.roles[y][x] is ElementRole.NOTEHEAD
    }
    tie_rows = {y for y, _x in result.cells_for("tie")}
    assert tie_rows
    assert min(tie_rows) >= min(head_rows)
    assert max(tie_rows) <= max(head_rows) + 2


def test_advanced_pitch_cue_uses_the_projected_head_cell() -> None:
    options = ScoreTypesetOptions(width=80, height=32, glyph_mode=GlyphMode.ADVANCED)
    original = typeset_score(_score(), options=options)
    cued = typeset_score(
        _score(),
        options=replace(options, pitch_cues=(PitchCue("cue", pitch_from_midi(71), event_id="held"),)),
    )
    cells = cued.cells_for("cue")
    assert len(cells) == 1
    y, x = cells[0]
    assert original.semantic_frame.element_ids[y][x] == "held"
    assert original.semantic_frame.roles[y][x] is ElementRole.NOTEHEAD
    assert cued.semantic_frame.roles[y][x] is ElementRole.PITCH_CUE
    assert cued.layout is original.layout


def test_standalone_braille_preview_matches_reviewed_text() -> None:
    result = typeset_score(
        example_score(),
        options=ScoreTypesetOptions(
            width=64,
            height=24,
            glyph_mode=GlyphMode.ADVANCED,
            metrics=LayoutMetrics(event_gap=1, barline_gap=1),
            policy=NotationLayoutPolicy(show_title=False, show_measure_numbers=False, compact_beams=True),
        ),
    )
    expected = Path(__file__).parent / "fixtures" / "petrucci_advanced.snap.txt"
    assert result.text == expected.read_text(encoding="utf-8")
