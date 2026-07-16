from __future__ import annotations

from fractions import Fraction
from typing import cast

import pytest

from oud.petrucci import (
    AccidentalDisplay,
    Bar,
    BarlineKind,
    BeamKind,
    Clef,
    EventKind,
    GlyphMode,
    ImportedBarContent,
    ImportedScore,
    ImportedStaff,
    LyricEvent,
    MelodyEvent,
    OrnamentKind,
    OudScoreAdapterError,
    Piece,
    PitchStep,
    ScoreTypesetOptions,
    StemDirection,
    WrittenPitch,
    notation_score_from_piece,
    typeset_score,
    written_pitch_from_token,
)


def _imported_piece() -> Piece:
    note_staff = ImportedStaff(
        kind="note",
        label="Cantus",
        bars=[
            ImportedBarContent(
                source_bar_index=0,
                time_sig="4/4",
                melody_events=[
                    MelodyEvent("c4", 0, note_type=4),
                    MelodyEvent("d4", 1, note_type=5, accidental_flags=0x0002, beam="start"),
                    MelodyEvent("r", 2, note_type=5, is_rest=True, beam="end"),
                ],
            ),
            ImportedBarContent(
                source_bar_index=1,
                melody_events=[MelodyEvent("e4", 0, note_type=2, fermata=True)],
            ),
        ],
    )
    lyric_staff = ImportedStaff(
        kind="lyrics",
        label="Cantus",
        bars=[
            ImportedBarContent(
                source_bar_index=0,
                lyric_event_rows=[
                    [LyricEvent("Can", 0, syllabic="begin"), LyricEvent("ta", 1, syllabic="end")],
                ],
            ),
            ImportedBarContent(source_bar_index=1),
        ],
    )
    return Piece(
        title="Imported song",
        composer="Composer",
        key="G",
        imported_score=ImportedScore(source_format="ft3", staffs=[note_staff, lyric_staff]),
    )


def test_oud_adapter_normalizes_imported_note_and_lyric_staff() -> None:
    score = notation_score_from_piece(_imported_piece(), score_id="imported")

    assert score.id == "imported"
    assert len(score.staffs) == 1
    staff = score.staffs[0]
    assert staff.label == "Cantus"
    assert staff.clef is Clef.TREBLE
    assert [measure.number for measure in staff.measures] == [1, 2]
    first = staff.measures[0]
    assert [event.kind for event in first.events] == [EventKind.NOTE, EventKind.NOTE, EventKind.REST]
    assert [event.onset for event in first.events] == [Fraction(0), Fraction(1, 4), Fraction(3, 8)]
    assert first.events[1].pitches == (WrittenPitch(PitchStep.D, 4, 1, AccidentalDisplay.EXPLICIT),)
    assert first.events[1].beam is BeamKind.START
    assert [lyric.text for lyric in staff.lyrics] == ["Can", "ta"]
    assert all(lyric.event_id in {event.id for event in first.events} for lyric in staff.lyrics)


def test_oud_adapter_output_uses_public_score_typesetter() -> None:
    score = notation_score_from_piece(_imported_piece())

    result = typeset_score(
        score,
        options=ScoreTypesetOptions(width=72, height=24, glyph_mode=GlyphMode.SAFE),
    )

    assert "Imported song" in result.text
    assert "Cantus" in result.text
    assert "Can" in result.text
    assert all(result.cells_for(event.id) for event in score.staffs[0].measures[0].events)


def test_oud_adapter_preserves_ft3_chords_voices_ornaments_endings_and_cut_time() -> None:
    piece = Piece(
        imported_score=ImportedScore(
            source_format="ft3",
            staffs=[
                ImportedStaff(
                    kind="note",
                    label="Bass viol",
                    bars=[
                        ImportedBarContent(
                            source_bar_index=0,
                            time_sig="C|",
                            repeat="both",
                            ending_numbers=(1,),
                            fermata=True,
                            melody_events=[
                                MelodyEvent("c3", 0, note_type=5, voice=0, ornament="+"),
                                MelodyEvent("e3", 0, note_type=5, voice=0, beam="start"),
                                MelodyEvent("d3", 1, note_type=5, voice=0, beam="end"),
                                MelodyEvent("g2", 0, note_type=4, voice=1),
                            ],
                        ),
                    ],
                ),
                ImportedStaff(
                    kind="lyrics",
                    label="Bass viol",
                    bars=[
                        ImportedBarContent(
                            source_bar_index=0,
                            lyric_event_rows=[[LyricEvent("sing", 1)]],
                        ),
                    ],
                ),
            ],
        ),
    )

    score = notation_score_from_piece(piece)
    measure = score.staffs[0].measures[0]
    chord, lower_voice, second = measure.events

    assert measure.time_signature is not None
    assert (measure.time_signature.beats, measure.time_signature.beat_unit) == (2, 2)
    assert measure.barline is BarlineKind.REPEAT_BOTH
    assert measure.ending_numbers == (1,)
    assert chord.pitches == (WrittenPitch(PitchStep.C, 3), WrittenPitch(PitchStep.E, 3))
    assert chord.onset == lower_voice.onset == Fraction(0)
    assert second.onset == Fraction(1, 8)
    assert chord.stem is StemDirection.UP
    assert lower_voice.stem is StemDirection.DOWN
    assert chord.beam is BeamKind.START
    assert chord.ornament is OrnamentKind.PLUS
    assert chord.fermata
    assert score.staffs[0].lyrics[0].event_id == second.id


@pytest.mark.parametrize(
    ("token", "flags", "expected"),
    [
        ("c4", None, WrittenPitch(PitchStep.C, 4)),
        ("c'", None, WrittenPitch(PitchStep.C, 5)),
        ("bb", None, WrittenPitch(PitchStep.B, 4, -1, AccidentalDisplay.EXPLICIT)),
        ("f4", 0x0002, WrittenPitch(PitchStep.F, 4, 1, AccidentalDisplay.EXPLICIT)),
        ("f#4", 0x2000, WrittenPitch(PitchStep.F, 4, 0, AccidentalDisplay.EXPLICIT)),
    ],
)
def test_written_pitch_from_token(
    token: str,
    flags: int | None,
    expected: WrittenPitch,
) -> None:
    assert written_pitch_from_token(token, flags) == expected


def test_oud_adapter_rejects_raw_lyrics_instead_of_guessing_alignment() -> None:
    piece = Piece(
        bars=[
            Bar(
                melody_events=[MelodyEvent("c4", 0, note_type=4)],
                lyrics=["unmapped words"],
            ),
        ],
    )

    with pytest.raises(OudScoreAdapterError, match="raw lyrics"):
        notation_score_from_piece(piece)

    score = notation_score_from_piece(piece, include_lyrics=False)
    assert score.staffs[0].lyrics == ()
    assert len(score.staffs[0].measures[0].events) == 1


def test_oud_adapter_rejects_non_boolean_lyric_policy() -> None:
    with pytest.raises(OudScoreAdapterError, match="include_lyrics must be a bool"):
        notation_score_from_piece(_imported_piece(), include_lyrics=cast(bool, 1))


def test_oud_adapter_preserves_minor_key_and_page_break_semantics() -> None:
    piece = Piece(
        key="Gm",
        bars=[
            Bar(melody_events=[MelodyEvent("c4", 0, note_type=4)]),
            Bar(
                page_break_before=True,
                melody_events=[MelodyEvent("d4", 0, note_type=4)],
            ),
        ],
    )

    score = notation_score_from_piece(piece)

    assert score.staffs[0].measures[0].key_signature is not None
    assert score.staffs[0].measures[0].key_signature.fifths == -2
    assert score.staffs[0].measures[0].forced_break_after
    assert not score.staffs[0].measures[1].forced_break_after


@pytest.mark.parametrize(
    ("piece", "message"),
    [
        (
            Piece(bars=[Bar(melody_events=[MelodyEvent("c4", 0, note_type=4, voice=-1)])]),
            "negative voice",
        ),
        (
            Piece(
                bars=[
                    Bar(
                        melody_events=[MelodyEvent("c4", 0, note_type=4)],
                        lyric_event_rows=[[LyricEvent("word", 0, verse=-1)]],
                    ),
                ],
            ),
            "negative verse",
        ),
        (
            Piece(key="not-a-key", bars=[Bar(melody_events=[MelodyEvent("c4", 0, note_type=4)])]),
            "unsupported key signature",
        ),
    ],
)
def test_oud_adapter_rejects_source_values_it_cannot_preserve(piece: Piece, message: str) -> None:
    with pytest.raises(OudScoreAdapterError, match=message):
        notation_score_from_piece(piece)
