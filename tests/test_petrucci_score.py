from __future__ import annotations

from dataclasses import FrozenInstanceError
from fractions import Fraction
from typing import cast

import pytest

from oud.petrucci.score import (
    EventKind,
    LyricSyllable,
    NotationEvent,
    NotationMeasure,
    NotationScore,
    NotationStaff,
    OrnamentKind,
    PitchStep,
    ScoreValidationError,
    TimeSignature,
    WrittenPitch,
    duration_notation,
    pitch_from_midi,
)


def _event(event_id: str, onset: Fraction, midi: int = 60) -> NotationEvent:
    return NotationEvent(
        id=event_id,
        onset=onset,
        duration=Fraction(1, 4),
        kind=EventKind.NOTE,
        pitches=(pitch_from_midi(midi),),
    )


def _score(*events: NotationEvent, lyrics: tuple[LyricSyllable, ...] = ()) -> NotationScore:
    return NotationScore(
        id="score",
        title="Canonical",
        staffs=(
            NotationStaff(
                id="staff",
                measures=(
                    NotationMeasure(
                        id="measure-1",
                        number=1,
                        events=events,
                        time_signature=TimeSignature(4, 4),
                    ),
                ),
                lyrics=lyrics,
            ),
        ),
    )


def test_canonical_score_is_immutable_and_keeps_repeated_pitch_ids_distinct() -> None:
    first = _event("note-1", Fraction(0), 60)
    second = _event("note-2", Fraction(1, 4), 60)

    score = _score(first, second)

    assert score.staffs[0].measures[0].events == (first, second)
    assert first.pitches == second.pitches
    assert first.id != second.id
    attribute = "voice"
    with pytest.raises(FrozenInstanceError):
        setattr(first, attribute, 2)


def test_score_rejects_duplicate_ids_across_element_kinds() -> None:
    event = _event("staff", Fraction(0))

    with pytest.raises(ScoreValidationError, match="duplicate score element ID 'staff'"):
        _score(event)


def test_score_rejects_non_fraction_timing_and_measure_overflow() -> None:
    with pytest.raises(ScoreValidationError, match="event onset must be a Fraction"):
        NotationEvent(
            id="note",
            onset=cast(Fraction, 0.0),
            duration=Fraction(1, 4),
            kind=EventKind.NOTE,
            pitches=(WrittenPitch(PitchStep.C, 4),),
        )

    overflowing = NotationEvent(
        id="late",
        onset=Fraction(7, 8),
        duration=Fraction(1, 4),
        kind=EventKind.NOTE,
        pitches=(WrittenPitch(PitchStep.C, 4),),
    )
    with pytest.raises(ScoreValidationError, match="ends after measure"):
        _score(overflowing)


def test_note_rest_and_lyric_contracts_fail_explicitly() -> None:
    with pytest.raises(ScoreValidationError, match="at least one pitch"):
        NotationEvent("empty-note", Fraction(0), Fraction(1, 4), EventKind.NOTE)
    with pytest.raises(ScoreValidationError, match="cannot contain pitches"):
        NotationEvent(
            "pitched-rest",
            Fraction(0),
            Fraction(1, 4),
            EventKind.REST,
            (WrittenPitch(PitchStep.C, 4),),
        )
    with pytest.raises(ScoreValidationError, match="cannot contain an ornament"):
        NotationEvent(
            "ornamented-rest",
            Fraction(0),
            Fraction(1, 4),
            EventKind.REST,
            ornament=OrnamentKind.PLUS,
        )

    event = _event("note", Fraction(0))
    lyric = LyricSyllable(id="lyric", event_id="missing", text="la")
    with pytest.raises(ScoreValidationError, match="references unknown event"):
        _score(event, lyrics=(lyric,))


@pytest.mark.parametrize("ending_numbers", [(0,), (2, 1), (1, 1)])
def test_measure_rejects_invalid_ending_numbers(ending_numbers: tuple[int, ...]) -> None:
    with pytest.raises(ScoreValidationError, match="ending numbers"):
        NotationMeasure("ending", 1, ending_numbers=ending_numbers)


@pytest.mark.parametrize(
    ("duration", "expected"),
    [
        (Fraction(1), (1, 0)),
        (Fraction(1, 2), (2, 0)),
        (Fraction(3, 8), (4, 1)),
        (Fraction(7, 32), (8, 2)),
        (Fraction(1, 3), None),
    ],
)
def test_duration_notation(duration: Fraction, expected: tuple[int, int] | None) -> None:
    assert duration_notation(duration) == expected


def test_pitch_from_midi_has_deterministic_sharp_and_flat_spellings() -> None:
    assert pitch_from_midi(61) == WrittenPitch(PitchStep.C, 4, 1)
    assert pitch_from_midi(61, prefer_sharps=False) == WrittenPitch(PitchStep.D, 4, -1)
    assert pitch_from_midi(60).midi == 60
