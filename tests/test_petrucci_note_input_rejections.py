from __future__ import annotations

from fractions import Fraction

import pytest

from petrucci import (
    AddLyric,
    AddSlur,
    AddTie,
    DeleteEvent,
    EnterNote,
    EnterRest,
    EventInputStyle,
    EventKind,
    InputPitch,
    LyricSyllable,
    NotatedDuration,
    NotationEvent,
    NotationMeasure,
    NotationScore,
    NotationSpan,
    NotationStaff,
    NoteInputError,
    NoteInputOperation,
    NoteInputTransaction,
    PitchStep,
    RemoveLyric,
    RemoveSlur,
    RemoveTie,
    ReplacePitch,
    ScorePosition,
    SpanKind,
    StemDirection,
    TimeSignature,
    WrittenPitch,
    apply_note_input,
)

C4 = WrittenPitch(PitchStep.C, 4)
D4 = WrittenPitch(PitchStep.D, 4)
E4 = WrittenPitch(PitchStep.E, 4)


def _at(onset: Fraction, *, staff_id: str = "staff-1", measure_id: str = "measure-1") -> ScorePosition:
    return ScorePosition(staff_id, measure_id, onset)


def _event(event_id: str, onset: Fraction, *pitches: WrittenPitch) -> NotationEvent:
    kind = EventKind.NOTE if pitches else EventKind.REST
    return NotationEvent(event_id, onset, Fraction(1, 4), kind, pitches)


def _score() -> NotationScore:
    """Measure 1 holds C4, C4, a rest, and D4; a tie, a slur, and a lyric are attached."""

    events = (
        _event("n1", Fraction(0), C4),
        _event("n2", Fraction(1, 4), C4),
        _event("r1", Fraction(1, 2)),
        _event("n3", Fraction(3, 4), D4),
    )
    measures = (
        NotationMeasure("measure-1", 1, events, time_signature=TimeSignature(4, 4)),
        NotationMeasure("measure-2", 2, ()),
    )
    staff = NotationStaff(
        "staff-1",
        measures,
        lyrics=(LyricSyllable("lyric-1", "n1", "la"),),
        spans=(
            NotationSpan("tie-1", SpanKind.TIE, "n1", "n2"),
            NotationSpan("slur-1", SpanKind.SLUR, "n2", "n3"),
        ),
    )
    return NotationScore("score", (staff,))


REJECTIONS: list[tuple[str, NoteInputOperation, str]] = [
    ("unknown staff", EnterRest(_at(Fraction(0), staff_id="other")), "unknown-staff"),
    ("unknown measure", EnterRest(_at(Fraction(0), measure_id="missing")), "unknown-measure"),
    ("unknown event", DeleteEvent(_at(Fraction(0)), "missing"), "unknown-event"),
    ("unknown span", RemoveTie("missing"), "unknown-span"),
    ("unknown lyric", RemoveLyric("missing"), "unknown-lyric"),
    ("blank requested ID", EnterNote(_at(Fraction(0), measure_id="measure-2"), C4, event_id=" "), "invalid-id"),
    ("reused requested ID", EnterNote(_at(Fraction(0), measure_id="measure-2"), C4, event_id="n1"), "duplicate-id"),
    ("note on an occupied onset", EnterNote(_at(Fraction(0)), E4), "event-collision"),
    ("chord on empty onset", EnterNote(_at(Fraction(0), measure_id="measure-2"), E4, chord=True), "chord-target"),
    ("chord on a rest", EnterNote(_at(Fraction(1, 2)), E4, chord=True), "chord-target"),
    ("chord repeats a pitch", EnterNote(_at(Fraction(0)), C4, chord=True), "duplicate-pitch"),
    ("repitch a rest", ReplacePitch(_at(Fraction(1, 2)), "r1", E4), "not-a-note"),
    ("repitch a missing chord member", ReplacePitch(_at(Fraction(0)), "n1", E4, pitch_index=1), "pitch-index"),
    ("event in another measure", DeleteEvent(_at(Fraction(0), measure_id="measure-2"), "n1"), "position-mismatch"),
    ("tie ends before it starts", AddTie("n2", "n1"), "invalid-tie"),
    ("slur to a rest", AddSlur("n2", "r1"), "invalid-slur"),
    ("slur ends before it starts", AddSlur("n3", "n1"), "invalid-slur"),
    ("remove a slur as a tie", RemoveTie("slur-1"), "not-a-tie"),
    ("remove a tie as a slur", RemoveSlur("tie-1"), "not-a-slur"),
    ("second lyric in one verse", AddLyric("n1", "lo"), "lyric-collision"),
    ("empty lyric", AddLyric("n2", ""), "invalid-event"),
]


@pytest.mark.parametrize(
    ("operation", "code"),
    [(operation, code) for _label, operation, code in REJECTIONS],
    ids=[label for label, _operation, _code in REJECTIONS],
)
def test_rejected_operation_reports_its_code_and_index_without_mutating_the_score(
    operation: NoteInputOperation,
    code: str,
) -> None:
    score = _score()
    valid_first = EnterRest(_at(Fraction(1, 2), measure_id="measure-2"))

    with pytest.raises(NoteInputError) as caught:
        apply_note_input(score, NoteInputTransaction((valid_first, operation)))

    assert caught.value.code == code
    assert caught.value.operation_index == 1
    assert score == _score()


def test_repitch_rejects_a_pitch_already_in_the_chord() -> None:
    chord = apply_note_input(_score(), NoteInputTransaction((EnterNote(_at(Fraction(0)), E4, chord=True),))).score

    with pytest.raises(NoteInputError) as caught:
        apply_note_input(chord, NoteInputTransaction((ReplacePitch(_at(Fraction(0)), "n1", E4, pitch_index=0),)))

    assert caught.value.code == "duplicate-pitch"


def test_stacking_keeps_the_duration_and_replacing_takes_the_given_one() -> None:
    result = apply_note_input(
        _score(),
        NoteInputTransaction(
            (
                EnterNote(_at(Fraction(0)), InputPitch(PitchStep.G, octave=4), chord=True),
                EnterNote(
                    _at(Fraction(3, 4)),
                    E4,
                    replace_event_id="n3",
                    duration=NotatedDuration(8),
                    style=EventInputStyle(stem=StemDirection.DOWN, fermata=True),
                ),
            ),
        ),
    )

    events = {event.id: event for event in result.score.staffs[0].measures[0].events}
    assert events["n1"].pitches == (C4, WrittenPitch(PitchStep.G, 4))
    assert events["n1"].duration == Fraction(1, 4)
    assert events["n3"].pitches == (E4,)
    assert events["n3"].duration == Fraction(1, 8)
    assert events["n3"].stem is StemDirection.DOWN
    assert events["n3"].fermata is True


def test_inserted_events_are_kept_in_onset_order() -> None:
    score = apply_note_input(
        _score(),
        NoteInputTransaction(
            (
                EnterNote(_at(Fraction(1, 2), measure_id="measure-2"), D4, event_id="late"),
                EnterNote(_at(Fraction(0), measure_id="measure-2"), C4, event_id="early"),
            ),
        ),
    ).score

    assert [event.id for event in score.staffs[0].measures[1].events] == ["early", "late"]
