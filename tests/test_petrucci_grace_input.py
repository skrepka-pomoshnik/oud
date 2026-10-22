from fractions import Fraction

import pytest

from petrucci import (
    EnterNote,
    EnterRest,
    EventInputStyle,
    EventKind,
    NotatedDuration,
    NotationMeasure,
    NotationScore,
    NotationStaff,
    NoteInputError,
    NoteInputTransaction,
    ScorePosition,
    apply_note_input,
    pitch_from_midi,
)


def _empty_score() -> NotationScore:
    return NotationScore("score", (NotationStaff("staff", (NotationMeasure("measure", 1, (), irregular=True),)),))


@pytest.mark.parametrize("order", [("grace-a", "grace-b", "main"), ("main", "grace-a", "grace-b")])
def test_grace_group_and_principal_share_onset_in_either_entry_order(order: tuple[str, ...]) -> None:
    position = ScorePosition("staff", "measure", Fraction())
    notes = {
        "grace-a": EnterNote(
            position, pitch_from_midi(64), NotatedDuration(16), "grace-a", style=EventInputStyle(grace=True)
        ),
        "grace-b": EnterNote(
            position, pitch_from_midi(62), NotatedDuration(16), "grace-b", style=EventInputStyle(grace=True)
        ),
        "main": EnterNote(position, pitch_from_midi(60), NotatedDuration(4), "main"),
    }
    result = apply_note_input(_empty_score(), NoteInputTransaction(tuple(notes[name] for name in order)))
    events = result.score.staffs[0].measures[0].events

    assert [event.id for event in events] == ["grace-a", "grace-b", "main"]
    assert [event.grace for event in events] == [True, True, False]
    assert [event.onset for event in events] == [Fraction()] * 3


def test_chord_entry_targets_principal_instead_of_its_grace_group() -> None:
    position = ScorePosition("staff", "measure", Fraction())
    operations = (
        EnterNote(position, pitch_from_midi(62), NotatedDuration(16), "grace", style=EventInputStyle(grace=True)),
        EnterNote(position, pitch_from_midi(60), NotatedDuration(4), "main"),
        EnterNote(position, pitch_from_midi(64), chord=True),
    )
    result = apply_note_input(_empty_score(), NoteInputTransaction(operations))
    grace, principal = result.score.staffs[0].measures[0].events

    assert grace.id == "grace" and grace.pitches == (pitch_from_midi(62),)
    assert principal.id == "main" and principal.pitches == (pitch_from_midi(60), pitch_from_midi(64))


def test_timed_rest_can_share_onset_with_preceding_grace() -> None:
    position = ScorePosition("staff", "measure", Fraction())
    operations = (
        EnterNote(position, pitch_from_midi(62), NotatedDuration(16), "grace", style=EventInputStyle(grace=True)),
        EnterRest(position, NotatedDuration(4), "rest"),
    )
    result = apply_note_input(_empty_score(), NoteInputTransaction(operations))
    grace, rest = result.score.staffs[0].measures[0].events

    assert grace.grace is True
    assert rest.kind is EventKind.REST and rest.grace is False


def test_grace_support_does_not_allow_two_timed_events_in_one_voice() -> None:
    source = _empty_score()
    position = ScorePosition("staff", "measure", Fraction())
    operations = (
        EnterNote(position, pitch_from_midi(62), NotatedDuration(16), "grace", style=EventInputStyle(grace=True)),
        EnterNote(position, pitch_from_midi(60), NotatedDuration(4), "main"),
        EnterRest(position, NotatedDuration(4), "collision"),
    )

    with pytest.raises(NoteInputError, match="event already exists"):
        apply_note_input(source, NoteInputTransaction(operations))
    assert source.staffs[0].measures[0].events == ()


def test_explicit_grace_chord_style_targets_grace_instead_of_principal() -> None:
    position = ScorePosition("staff", "measure", Fraction())
    style = EventInputStyle(grace=True)
    operations = (
        EnterNote(position, pitch_from_midi(62), NotatedDuration(16), "grace", style=style),
        EnterNote(position, pitch_from_midi(60), NotatedDuration(4), "main"),
        EnterNote(position, pitch_from_midi(65), chord=True, style=style),
    )
    result = apply_note_input(_empty_score(), NoteInputTransaction(operations))
    grace, principal = result.score.staffs[0].measures[0].events

    assert grace.pitches == (pitch_from_midi(62), pitch_from_midi(65))
    assert principal.pitches == (pitch_from_midi(60),)


def test_multiple_grace_chord_targets_are_rejected_instead_of_guessed() -> None:
    position = ScorePosition("staff", "measure", Fraction())
    style = EventInputStyle(grace=True)
    operations = (
        EnterNote(position, pitch_from_midi(62), NotatedDuration(16), "grace-a", style=style),
        EnterNote(position, pitch_from_midi(64), NotatedDuration(16), "grace-b", style=style),
        EnterNote(position, pitch_from_midi(65), chord=True, style=style),
    )

    with pytest.raises(NoteInputError, match="exactly one event"):
        apply_note_input(_empty_score(), NoteInputTransaction(operations))
