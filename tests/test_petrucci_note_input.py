from __future__ import annotations

from fractions import Fraction
from typing import Any

import pytest

from petrucci import (
    AccidentalDisplay,
    AddLyric,
    AddSlur,
    AddTie,
    BeamKind,
    ChangeDuration,
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
    NoteInputChangeKind,
    NoteInputContext,
    NoteInputError,
    NoteInputTransaction,
    OrnamentKind,
    PitchStep,
    RemoveLyric,
    RemoveSlur,
    RemoveTie,
    ReplacePitch,
    ScorePosition,
    SpanKind,
    StemDirection,
    Syllabic,
    TimeSignature,
    WrittenPitch,
    apply_note_input,
)


def _position(onset: Fraction, *, voice: int = 0, measure_id: str = "measure-1") -> ScorePosition:
    return ScorePosition("staff-1", measure_id, onset, voice)


def _score(
    *events: NotationEvent,
    lyrics: tuple[LyricSyllable, ...] = (),
    spans: tuple[NotationSpan, ...] = (),
    measures: int = 1,
) -> NotationScore:
    measure_values = [
        NotationMeasure(
            id=f"measure-{index + 1}",
            number=index + 1,
            events=events if index == 0 else (),
            time_signature=TimeSignature(4, 4) if index == 0 else None,
        )
        for index in range(measures)
    ]
    return NotationScore(
        "score",
        (NotationStaff("staff-1", tuple(measure_values), lyrics=lyrics, spans=spans),),
    )


def _note(
    event_id: str,
    onset: Fraction,
    pitch: WrittenPitch | None = None,
    *,
    voice: int = 0,
    **kwargs: Any,
) -> NotationEvent:
    return NotationEvent(
        event_id,
        onset,
        Fraction(1, 4),
        EventKind.NOTE,
        (pitch or WrittenPitch(PitchStep.C, 4),),
        voice=voice,
        **kwargs,
    )


def test_note_entry_resolves_nearest_octave_and_persists_dotted_duration() -> None:
    duration = NotatedDuration(8, dots=1)
    transaction = NoteInputTransaction(
        (
            EnterNote(_position(Fraction(0)), InputPitch(PitchStep.B), duration=duration),
            EnterNote(
                _position(Fraction(1, 4)),
                InputPitch(PitchStep.C, alter=0, accidental=AccidentalDisplay.EXPLICIT),
            ),
        ),
    )

    result = apply_note_input(_score(), transaction)

    events = result.score.staffs[0].measures[0].events
    assert [event.pitches for event in events] == [
        (WrittenPitch(PitchStep.B, 3),),
        (WrittenPitch(PitchStep.C, 4, accidental=AccidentalDisplay.EXPLICIT),),
    ]
    assert [event.duration for event in events] == [Fraction(3, 16), Fraction(3, 16)]
    assert result.context.duration == duration
    assert result.context.pitch_anchor == WrittenPitch(
        PitchStep.C,
        4,
        accidental=AccidentalDisplay.EXPLICIT,
    )


def test_note_entry_supports_independent_voices_rests_tuplets_and_grace_notes() -> None:
    triplet = NotatedDuration(8, tuplet_actual=3, tuplet_normal=2)
    transaction = NoteInputTransaction(
        (
            EnterNote(
                _position(Fraction(0), voice=0),
                WrittenPitch(PitchStep.G, 4),
                duration=triplet,
                style=EventInputStyle(grace=True, stem=StemDirection.UP, beam=BeamKind.START),
            ),
            EnterRest(_position(Fraction(0), voice=1), duration=NotatedDuration(4)),
        ),
    )

    result = apply_note_input(_score(), transaction)

    grace, rest = result.score.staffs[0].measures[0].events
    assert (grace.voice, grace.grace, grace.duration) == (0, True, Fraction(1, 12))
    assert grace.tuplet is not None and (grace.tuplet.actual, grace.tuplet.normal) == (3, 2)
    assert (grace.stem, grace.beam) == (StemDirection.UP, BeamKind.START)
    assert (rest.kind, rest.voice, rest.duration) == (EventKind.REST, 1, Fraction(1, 4))


def test_chord_entry_stacks_distinct_pitches_without_creating_another_event() -> None:
    transaction = NoteInputTransaction(
        (
            EnterNote(_position(Fraction(0)), WrittenPitch(PitchStep.C, 4), event_id="chord"),
            EnterNote(_position(Fraction(0)), WrittenPitch(PitchStep.E, 4), chord=True),
            EnterNote(_position(Fraction(0)), WrittenPitch(PitchStep.G, 4), chord=True),
        ),
    )

    result = apply_note_input(_score(), transaction)

    events = result.score.staffs[0].measures[0].events
    assert len(events) == 1
    assert events[0].id == "chord"
    assert events[0].pitches == (
        WrittenPitch(PitchStep.C, 4),
        WrittenPitch(PitchStep.E, 4),
        WrittenPitch(PitchStep.G, 4),
    )
    assert [change.kind for change in result.changes] == [
        NoteInputChangeKind.INSERT_EVENT,
        NoteInputChangeKind.STACK_PITCH,
        NoteInputChangeKind.STACK_PITCH,
    ]


def test_replace_pitch_and_duration_preserve_event_identity_and_attachments() -> None:
    source = _note(
        "note",
        Fraction(0),
        dynamic="p",
        ornament=OrnamentKind.TRILL,
        fermata=True,
        editorial_brackets=True,
    )
    transaction = NoteInputTransaction(
        (
            ReplacePitch(_position(Fraction(0)), "note", WrittenPitch(PitchStep.D, 4)),
            ChangeDuration(_position(Fraction(0)), "note", NotatedDuration(16, dots=2)),
        ),
    )

    result = apply_note_input(_score(source), transaction)

    event = result.score.staffs[0].measures[0].events[0]
    assert event.id == "note"
    assert event.pitches == (WrittenPitch(PitchStep.D, 4),)
    assert event.duration == Fraction(7, 64)
    assert (event.dynamic, event.ornament, event.fermata, event.editorial_brackets) == (
        "p",
        OrnamentKind.TRILL,
        True,
        True,
    )


def test_note_rest_replacement_is_atomic_and_removes_only_incompatible_note_style() -> None:
    source = _note(
        "event",
        Fraction(0),
        dynamic="f",
        ornament=OrnamentKind.TURN,
        fermata=True,
        editorial_brackets=True,
        grace=True,
    )

    rest_result = apply_note_input(
        _score(source),
        NoteInputTransaction((EnterRest(_position(Fraction(0)), replace_event_id="event"),)),
    )
    rest = rest_result.score.staffs[0].measures[0].events[0]
    assert rest.kind is EventKind.REST
    assert rest.id == "event"
    assert (rest.dynamic, rest.fermata) == ("f", True)
    assert (rest.ornament, rest.editorial_brackets, rest.grace) == (None, False, False)

    note_result = apply_note_input(
        rest_result.score,
        NoteInputTransaction(
            (
                EnterNote(
                    _position(Fraction(0)),
                    WrittenPitch(PitchStep.A, 4),
                    replace_event_id="event",
                ),
            ),
        ),
    )
    note = note_result.score.staffs[0].measures[0].events[0]
    assert (note.kind, note.id, note.pitches, note.dynamic, note.fermata) == (
        EventKind.NOTE,
        "event",
        (WrittenPitch(PitchStep.A, 4),),
        "f",
        True,
    )


def test_tie_from_previous_uses_same_voice_and_shared_written_pitch() -> None:
    transaction = NoteInputTransaction(
        (
            EnterNote(_position(Fraction(0), voice=0), WrittenPitch(PitchStep.C, 4), event_id="first"),
            EnterNote(_position(Fraction(0), voice=1), WrittenPitch(PitchStep.C, 4), event_id="other-voice"),
            EnterNote(
                _position(Fraction(1, 4), voice=0),
                WrittenPitch(PitchStep.C, 4),
                event_id="second",
                tie_from_previous=True,
            ),
        ),
    )

    result = apply_note_input(_score(), transaction)

    assert result.score.staffs[0].spans == (NotationSpan("input-tie-1", SpanKind.TIE, "first", "second"),)


def test_tie_from_previous_ignores_accidental_display_policy() -> None:
    score = _score(
        _note(
            "first",
            Fraction(0),
            WrittenPitch(PitchStep.F, 4, alter=1, accidental=AccidentalDisplay.EXPLICIT),
        ),
    )

    result = apply_note_input(
        score,
        NoteInputTransaction(
            (
                EnterNote(
                    _position(Fraction(1, 4)),
                    WrittenPitch(PitchStep.F, 4, alter=1, accidental=AccidentalDisplay.AUTO),
                    event_id="second",
                    tie_from_previous=True,
                ),
            ),
        ),
    )

    assert result.score.staffs[0].spans == (NotationSpan("input-tie-1", SpanKind.TIE, "first", "second"),)


def test_ties_cannot_skip_an_intervening_event_in_the_same_voice() -> None:
    score = _score(
        _note("first", Fraction(0), WrittenPitch(PitchStep.C, 4)),
        _note("middle", Fraction(1, 4), WrittenPitch(PitchStep.D, 4)),
    )
    entered = EnterNote(
        _position(Fraction(1, 2)),
        WrittenPitch(PitchStep.C, 4),
        event_id="last",
        tie_from_previous=True,
    )

    with pytest.raises(NoteInputError, match="preceding event") as shorthand_error:
        apply_note_input(score, NoteInputTransaction((entered,)))
    assert shorthand_error.value.code == "invalid-tie"

    three_notes = apply_note_input(
        score,
        NoteInputTransaction(
            (EnterNote(_position(Fraction(1, 2)), WrittenPitch(PitchStep.C, 4), event_id="last"),),
        ),
    ).score
    with pytest.raises(NoteInputError, match="consecutive events") as explicit_error:
        apply_note_input(three_notes, NoteInputTransaction((AddTie("first", "last"),)))
    assert explicit_error.value.code == "invalid-tie"


def test_add_and_remove_tie_are_explicit_operations() -> None:
    score = _score(
        _note(
            "first",
            Fraction(0),
            WrittenPitch(PitchStep.C, 4, accidental=AccidentalDisplay.EXPLICIT),
        ),
        _note("second", Fraction(1, 4)),
    )
    tied = apply_note_input(
        score,
        NoteInputTransaction((AddTie("first", "second", span_id="tie"),)),
    )
    assert tied.score.staffs[0].spans == (NotationSpan("tie", SpanKind.TIE, "first", "second"),)

    untied = apply_note_input(tied.score, NoteInputTransaction((RemoveTie("tie"),)))
    assert untied.score.staffs[0].spans == ()


def test_lyrics_and_slurs_are_transactional_and_source_independent() -> None:
    score = _score(_note("first", Fraction(0)), _note("second", Fraction(1, 4)))
    entered = apply_note_input(
        score,
        NoteInputTransaction(
            (
                AddLyric("first", "Ky", syllabic=Syllabic.BEGIN, lyric_id="lyric"),
                AddSlur("first", "second", span_id="slur"),
            ),
        ),
    )

    staff = entered.score.staffs[0]
    assert staff.lyrics == (LyricSyllable("lyric", "first", "Ky", syllabic=Syllabic.BEGIN),)
    assert staff.spans == (NotationSpan("slur", SpanKind.SLUR, "first", "second"),)

    removed = apply_note_input(
        entered.score,
        NoteInputTransaction((RemoveLyric("lyric"), RemoveSlur("slur"))),
    )
    assert removed.score.staffs[0].lyrics == ()
    assert removed.score.staffs[0].spans == ()


def test_lyrics_can_anchor_to_rests_for_source_score_alignment() -> None:
    rest = NotationEvent("rest", Fraction(0), Fraction(1, 4), EventKind.REST)

    entered = apply_note_input(
        _score(rest),
        NoteInputTransaction((AddLyric("rest", "skip", lyric_id="lyric"),)),
    )

    assert entered.score.staffs[0].lyrics == (LyricSyllable("lyric", "rest", "skip"),)


def test_delete_cascades_event_lyrics_and_spans_without_touching_other_events() -> None:
    first = _note("first", Fraction(0))
    second = _note("second", Fraction(1, 4))
    score = _score(
        first,
        second,
        lyrics=(LyricSyllable("lyric", "first", "La"),),
        spans=(NotationSpan("tie", SpanKind.TIE, "first", "second"),),
    )

    result = apply_note_input(
        score,
        NoteInputTransaction((DeleteEvent(_position(Fraction(0)), "first"),)),
    )

    staff = result.score.staffs[0]
    assert staff.measures[0].events == (second,)
    assert staff.lyrics == ()
    assert staff.spans == ()
    assert [change.kind for change in result.changes] == [
        NoteInputChangeKind.DELETE_EVENT,
        NoteInputChangeKind.REMOVE_TIE,
        NoteInputChangeKind.REMOVE_LYRIC,
    ]


def test_note_to_rest_replacement_removes_spans_but_preserves_lyrics() -> None:
    first = _note("first", Fraction(0))
    second = _note("second", Fraction(1, 4))
    score = _score(
        first,
        second,
        lyrics=(LyricSyllable("lyric", "first", "La"),),
        spans=(
            NotationSpan("tie", SpanKind.TIE, "first", "second"),
            NotationSpan("slur", SpanKind.SLUR, "first", "second"),
        ),
    )

    result = apply_note_input(
        score,
        NoteInputTransaction((EnterRest(_position(Fraction(0)), replace_event_id="first"),)),
    )

    staff = result.score.staffs[0]
    assert staff.measures[0].events[0].kind is EventKind.REST
    assert staff.lyrics == (LyricSyllable("lyric", "first", "La"),)
    assert staff.spans == ()
    assert [change.kind for change in result.changes] == [
        NoteInputChangeKind.REPLACE_EVENT,
        NoteInputChangeKind.REMOVE_TIE,
        NoteInputChangeKind.REMOVE_SLUR,
    ]


@pytest.mark.parametrize(
    "case",
    ["chord-replace", "chord-id", "rest-replace-id"],
)
def test_entry_operations_reject_mutually_exclusive_fields(case: str) -> None:
    with pytest.raises(NoteInputError) as caught:
        if case == "chord-replace":
            EnterNote(
                _position(Fraction(0)),
                WrittenPitch(PitchStep.C, 4),
                chord=True,
                replace_event_id="event",
            )
        elif case == "chord-id":
            EnterNote(
                _position(Fraction(0)),
                WrittenPitch(PitchStep.C, 4),
                event_id="new",
                chord=True,
            )
        else:
            EnterRest(_position(Fraction(0)), event_id="new", replace_event_id="event")

    assert caught.value.code == "invalid-operation"


@pytest.mark.parametrize(
    ("transaction", "code"),
    [
        (
            NoteInputTransaction(
                (
                    EnterNote(_position(Fraction(0)), WrittenPitch(PitchStep.C, 4)),
                    EnterRest(_position(Fraction(0))),
                ),
            ),
            "event-collision",
        ),
        (
            NoteInputTransaction(
                (EnterNote(_position(Fraction(0)), WrittenPitch(PitchStep.B, 9, alter=2)),),
            ),
            "pitch-out-of-range",
        ),
        (
            NoteInputTransaction(
                (EnterNote(_position(Fraction(1)), WrittenPitch(PitchStep.C, 4)),),
            ),
            "invalid-score",
        ),
    ],
)
def test_failed_transaction_reports_operation_and_leaves_original_score_unchanged(
    transaction: NoteInputTransaction,
    code: str,
) -> None:
    score = _score()

    with pytest.raises(NoteInputError) as caught:
        apply_note_input(score, transaction)

    assert caught.value.code == code
    assert caught.value.operation_index is not None
    assert score.staffs[0].measures[0].events == ()


def test_invalid_tie_and_cross_voice_replacement_fail_explicitly() -> None:
    score = _score(
        _note("first", Fraction(0), WrittenPitch(PitchStep.C, 4)),
        _note("second", Fraction(1, 4), WrittenPitch(PitchStep.D, 4)),
    )

    with pytest.raises(NoteInputError, match="must share a sounding pitch") as tie_error:
        apply_note_input(score, NoteInputTransaction((AddTie("first", "second"),)))
    assert tie_error.value.code == "invalid-tie"

    with pytest.raises(NoteInputError, match="requested onset and voice") as position_error:
        apply_note_input(
            score,
            NoteInputTransaction(
                (
                    ReplacePitch(
                        _position(Fraction(0), voice=1),
                        "first",
                        WrittenPitch(PitchStep.E, 4),
                    ),
                ),
            ),
        )
    assert position_error.value.code == "position-mismatch"

    cross_voice = _score(
        _note("voice-zero", Fraction(0), voice=0),
        _note("voice-one", Fraction(1, 4), voice=1),
    )
    with pytest.raises(NoteInputError, match="same voice") as tie_voice_error:
        apply_note_input(cross_voice, NoteInputTransaction((AddTie("voice-zero", "voice-one"),)))
    assert tie_voice_error.value.code == "invalid-tie"


def test_rest_entry_rejects_note_only_style_instead_of_discarding_it() -> None:
    transaction = NoteInputTransaction(
        (
            EnterRest(
                _position(Fraction(0)),
                style=EventInputStyle(ornament=OrnamentKind.TRILL),
            ),
        ),
    )

    with pytest.raises(NoteInputError, match="rests cannot carry") as caught:
        apply_note_input(_score(), transaction)

    assert caught.value.code == "invalid-rest-style"


def test_generated_ids_are_deterministic_and_do_not_reuse_deleted_ids() -> None:
    source = _score(_note("input-event-1", Fraction(0)))
    transaction = NoteInputTransaction(
        (
            DeleteEvent(_position(Fraction(0)), "input-event-1"),
            EnterNote(_position(Fraction(1, 4)), WrittenPitch(PitchStep.D, 4)),
        ),
        context=NoteInputContext(duration=NotatedDuration(8)),
    )

    first = apply_note_input(source, transaction)
    second = apply_note_input(source, transaction)

    assert first.score == second.score
    assert first.score.staffs[0].measures[0].events[0].id == "input-event-2"
