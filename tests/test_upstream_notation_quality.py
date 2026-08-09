"""Behavioral cases derived from LilyPond 2.24.4 and MuseScore 4.6.0 tests.

The source files and translated invariants are recorded in
docs/upstream-notation-quality.md. No upstream code or score fixture is copied.
"""

from __future__ import annotations

from fractions import Fraction

import pytest

from oud.editor.editing.tab.assignment import AssignmentPolicy, assign_chord_pitches
from petrucci import (
    AddTie,
    EnterNote,
    InputPitch,
    NotatedDuration,
    NotationMeasure,
    NotationScore,
    NotationStaff,
    NoteInputContext,
    NoteInputError,
    NoteInputTransaction,
    PitchStep,
    ScorePosition,
    WrittenPitch,
    apply_note_input,
    duration_notation,
)

GUITAR = [64, 59, 55, 50, 45, 40]
DROP_D_GUITAR = [64, 59, 55, 50, 45, 38]
RENAISSANCE_LUTE = [67, 62, 57, 53, 48, 43]
BAROQUE_LUTE = [65, 60, 56, 51, 46, 41, 39, 37, 36]


def _empty_score(*, irregular: bool = False) -> NotationScore:
    return NotationScore(
        "score",
        (NotationStaff("staff", (NotationMeasure("measure", 1, irregular=irregular),)),),
    )


def _position(onset: Fraction) -> ScorePosition:
    return ScorePosition("staff", "measure", onset)


@pytest.mark.parametrize("denominator", (1, 2, 4, 8, 16, 32, 64, 128))
@pytest.mark.parametrize("dots", (0, 1, 2, 3, 4))
def test_musescore_duration_matrix_round_trips(denominator: int, dots: int) -> None:
    duration = NotatedDuration(denominator, dots=dots)
    assert duration_notation(duration.duration) == (denominator, dots)


@pytest.mark.parametrize("denominator", (1, 2, 4, 8, 16, 32, 64))
def test_musescore_half_and_double_duration_are_inverse(denominator: int) -> None:
    duration = NotatedDuration(denominator, dots=1, tuplet_actual=3, tuplet_normal=2)
    assert duration.halved().duration == duration.duration / 2
    assert duration.halved().doubled() == duration


def test_musescore_duration_boundaries_fail_explicitly() -> None:
    with pytest.raises(NoteInputError) as short_error:
        NotatedDuration(128).halved()
    with pytest.raises(NoteInputError) as long_error:
        NotatedDuration(1).doubled()
    assert short_error.value.code == "duration-boundary"
    assert long_error.value.code == "duration-boundary"


def test_lilypond_default_duration_persists_across_typed_notes() -> None:
    duration = NotatedDuration(16, dots=2)
    result = apply_note_input(
        _empty_score(),
        NoteInputTransaction(
            (
                EnterNote(_position(Fraction(0)), InputPitch(PitchStep.C), duration=duration, event_id="first"),
                EnterNote(_position(Fraction(7, 64)), InputPitch(PitchStep.D), event_id="second"),
            ),
        ),
    )
    events = result.score.staffs[0].measures[0].events
    assert [event.duration for event in events] == [Fraction(7, 64), Fraction(7, 64)]
    assert result.context.duration == duration


def test_lilypond_enharmonic_tie_preserves_both_spellings() -> None:
    sharp = WrittenPitch(PitchStep.C, 4, alter=1)
    flat = WrittenPitch(PitchStep.D, 4, alter=-1)
    entered = apply_note_input(
        _empty_score(),
        NoteInputTransaction(
            (
                EnterNote(_position(Fraction(0)), sharp, event_id="sharp"),
                EnterNote(_position(Fraction(1, 4)), flat, event_id="flat"),
                AddTie("sharp", "flat", span_id="tie"),
            ),
        ),
    )
    events = entered.score.staffs[0].measures[0].events
    assert events[0].pitches == (sharp,)
    assert events[1].pitches == (flat,)
    assert entered.score.staffs[0].spans[0].id == "tie"


def test_typed_double_accidentals_retain_written_pitch() -> None:
    pitch = WrittenPitch(PitchStep.C, 4, alter=2)
    result = apply_note_input(
        _empty_score(),
        NoteInputTransaction((EnterNote(_position(Fraction(0)), pitch, event_id="double-sharp"),)),
    )
    assert result.score.staffs[0].measures[0].events[0].pitches == (pitch,)


def test_nearest_octave_entry_is_deterministic_at_octave_boundary() -> None:
    context = NoteInputContext(pitch_anchor=WrittenPitch(PitchStep.C, 4))
    result = apply_note_input(
        _empty_score(),
        NoteInputTransaction(
            (EnterNote(_position(Fraction(0)), InputPitch(PitchStep.B), event_id="nearest"),),
            context=context,
        ),
    )
    assert result.score.staffs[0].measures[0].events[0].pitches == (WrittenPitch(PitchStep.B, 3),)


@pytest.mark.parametrize("tuning", (GUITAR, DROP_D_GUITAR, RENAISSANCE_LUTE, BAROQUE_LUTE))
def test_musescore_tuning_round_trip_for_every_string_and_fret(tuning: list[int]) -> None:
    for string, open_pitch in enumerate(tuning, start=1):
        for fret in range(19):
            result = assign_chord_pitches([open_pitch + fret], tuning, forced_strings={0: string})
            assert result.ok, (tuning, string, fret, result.diagnostics)
            assert (result.notes[0].string, result.notes[0].fret) == (string, fret)


def test_lilypond_minimum_fret_keeps_open_strings_unless_restrained() -> None:
    loose = assign_chord_pitches([64], GUITAR, policy=AssignmentPolicy(minimum_fret=3, restrain_open_strings=False))
    restrained = assign_chord_pitches([64], GUITAR, policy=AssignmentPolicy(minimum_fret=3, restrain_open_strings=True))
    assert loose.ok and restrained.ok
    assert (loose.notes[0].string, loose.notes[0].fret) == (1, 0)
    assert restrained.notes[0].fret >= 3


def test_lilypond_open_string_survives_high_fret_in_chord() -> None:
    result = assign_chord_pitches([64, 66], GUITAR)
    assert result.ok
    assert any(note.pitch == 64 and note.fret == 0 for note in result.notes)
    assert any(note.fret > 4 for note in result.notes)
    assert len({note.string for note in result.notes}) == 2


def test_lilypond_additional_bass_strings_are_assignable() -> None:
    result = assign_chord_pitches([BAROQUE_LUTE[0], BAROQUE_LUTE[-1]], BAROQUE_LUTE)
    assert result.ok
    assert {note.string for note in result.notes} == {1, 9}
    assert all(note.fret == 0 for note in result.notes)


def test_lilypond_default_and_explicit_strings_are_deterministic() -> None:
    automatic = assign_chord_pitches([64, 59], GUITAR)
    forced = assign_chord_pitches([64, 59], GUITAR, forced_strings={0: 2, 1: 3})
    assert automatic.ok and forced.ok
    assert [(note.string, note.fret) for note in forced.notes] == [(2, 5), (3, 4)]


def test_lilypond_negative_forced_fret_is_an_explicit_failure() -> None:
    result = assign_chord_pitches([40], GUITAR, forced_strings={0: 1})
    assert not result.ok
    assert [diagnostic.code for diagnostic in result.diagnostics] == ["forced_string_impossible"]


def test_musescore_duplicate_pitch_chord_uses_distinct_strings() -> None:
    result = assign_chord_pitches([64, 64], GUITAR)
    assert result.ok
    assert len({note.string for note in result.notes}) == 2
    assert sorted(note.fret for note in result.notes) == [0, 5]


def test_overfull_duplicate_pitch_chord_fails_without_partial_assignment() -> None:
    result = assign_chord_pitches([64] * (len(GUITAR) + 1), GUITAR)
    assert not result.ok
    assert result.notes == []
    assert result.diagnostics
