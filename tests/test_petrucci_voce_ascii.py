from __future__ import annotations

from fractions import Fraction

import pytest

from petrucci import (
    ElementRole,
    EventKind,
    GlyphMode,
    LayoutMetrics,
    NotationEvent,
    NotationLayoutPolicy,
    NotationMeasure,
    NotationScore,
    NotationStaff,
    ScoreTypesetOptions,
    TerminalNoteheads,
    TimeSignature,
    layout_collisions,
    pitch_from_midi,
    typeset_score,
)

EVENT_IDS = (
    "voice-c",
    "voice-d",
    "voice-e",
    "voice-g",
    "voice-a",
    "voice-rest",
    "voice-final",
)
POLICY = NotationLayoutPolicy(show_title=False, show_measure_numbers=False)


def _ascii_options(width: int, system_offset: int = 0) -> ScoreTypesetOptions:
    return ScoreTypesetOptions(
        width=width,
        height=16,
        system_offset=system_offset,
        glyph_mode=GlyphMode.ASCII,
        noteheads=TerminalNoteheads(filled="*", open="o"),
        metrics=LayoutMetrics(event_gap=1, barline_gap=1),
        policy=POLICY,
    )


def _note(event_id: str, onset: Fraction, duration: Fraction, midi: int) -> NotationEvent:
    return NotationEvent(
        id=event_id,
        onset=onset,
        duration=duration,
        kind=EventKind.NOTE,
        pitches=(pitch_from_midi(midi),),
    )


def _voce_score() -> NotationScore:
    first_measure = (
        _note("voice-c", Fraction(0), Fraction(1, 4), 60),
        _note("voice-d", Fraction(1, 4), Fraction(1, 4), 62),
        _note("voice-e", Fraction(1, 2), Fraction(1, 4), 64),
        _note("voice-g", Fraction(3, 4), Fraction(1, 4), 67),
    )
    second_measure = (
        _note("voice-a", Fraction(0), Fraction(1, 2), 69),
        NotationEvent("voice-rest", Fraction(1, 2), Fraction(1, 4), EventKind.REST),
        _note("voice-final", Fraction(3, 4), Fraction(1, 4), 67),
    )
    return NotationScore(
        id="voce-like-ascii",
        title="Voce-like ASCII",
        staffs=(
            NotationStaff(
                id="voice",
                label="Voice",
                measures=(
                    NotationMeasure("measure-1", 1, first_measure, time_signature=TimeSignature()),
                    NotationMeasure("measure-2", 2, second_measure),
                ),
            ),
        ),
    )


@pytest.mark.parametrize("width", (48, 72))
def test_voce_like_score_renders_as_small_ascii_and_keeps_event_identity(width: int) -> None:
    score = _voce_score()
    result = typeset_score(
        score,
        options=_ascii_options(width),
    )

    assert result.layout.event_ids == EVENT_IDS
    assert layout_collisions(result.layout) == ()
    assert result.text
    assert result.text.isascii()
    assert all(len(line) <= width for line in result.text.splitlines())

    for location in result.layout.event_locations:
        system_result = typeset_score(
            score,
            options=_ascii_options(width, location.system_index),
        )
        assert system_result.cells_for(location.event_id)


def test_compact_ascii_distinguishes_note_values_without_pitch_label_rows() -> None:
    result = typeset_score(_voce_score(), options=_ascii_options(48))

    assert len(result.layout.systems) == 1
    assert not any(element.key.role is ElementRole.PITCH_LABEL for element in result.layout.elements)
    for event_id, expected in (("voice-c", "*"), ("voice-a", "o"), ("voice-rest", "r")):
        visible_symbols = [
            result.frame.lines[y][x]
            for y, x in result.cells_for(event_id)
            if result.semantic_frame.roles[y][x] in {ElementRole.NOTEHEAD, ElementRole.REST}
        ]
        assert visible_symbols == [expected]


def test_compact_ascii_keeps_last_stem_clear_of_each_barline() -> None:
    score = _voce_score()
    result = typeset_score(score, options=_ascii_options(48))

    for measure in score.staffs[0].measures:
        barline = next(
            element for element in result.layout.elements_for(measure.id) if element.key.role is ElementRole.BARLINE
        )
        stem = next(
            element
            for element in result.layout.elements_for(measure.events[-1].id)
            if element.key.role is ElementRole.STEM
        )
        assert barline.rect.x - stem.rect.right >= 2
