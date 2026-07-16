from __future__ import annotations

from fractions import Fraction

import pytest

from oud.petrucci.layout import (
    ElementRole,
    LayoutError,
    LayoutViewport,
    NotationLayoutPolicy,
    clear_layout_cache,
    layout_score,
)
from oud.petrucci.score import (
    AccidentalDisplay,
    BeamKind,
    Clef,
    EventKind,
    KeySignature,
    LyricSyllable,
    NotationEvent,
    NotationMeasure,
    NotationScore,
    NotationSpan,
    NotationStaff,
    OrnamentKind,
    PitchStep,
    SpanKind,
    TimeSignature,
    TupletRatio,
    WrittenPitch,
    pitch_from_midi,
)


def _event(event_id: str, onset: int, midi: int = 60) -> NotationEvent:
    return NotationEvent(
        id=event_id,
        onset=Fraction(onset, 4),
        duration=Fraction(1, 4),
        kind=EventKind.NOTE,
        pitches=(pitch_from_midi(midi),),
    )


def _measure(index: int, *, forced_break: bool = False) -> NotationMeasure:
    return NotationMeasure(
        id=f"measure-{index}",
        number=index,
        events=tuple(_event(f"event-{index}-{onset}", onset, 60 + onset) for onset in range(4)),
        time_signature=TimeSignature() if index == 1 else None,
        forced_break_after=forced_break,
    )


def _score(measures: int = 8) -> NotationScore:
    return NotationScore(
        id="score",
        title="Measured score",
        staffs=(
            NotationStaff(
                id="staff",
                label="Voice",
                measures=tuple(_measure(index) for index in range(1, measures + 1)),
            ),
        ),
    )


def test_layout_wraps_measured_content_and_keeps_every_event_addressable() -> None:
    score = _score()

    narrow = layout_score(score, viewport=LayoutViewport(width=60, height=24))
    wide = layout_score(score, viewport=LayoutViewport(width=120, height=40))

    assert len(narrow.systems) > len(wide.systems)
    assert len(narrow.onsets) == 32
    assert narrow.event_ids == tuple(event.id for measure in score.staffs[0].measures for event in measure.events)
    assert {position.event_id for position in narrow.onsets} == {
        event.id for measure in score.staffs[0].measures for event in measure.events
    }
    assert all(system.rect.right < narrow.width for system in narrow.systems)
    assert narrow.system_for_event("event-8-3") is not None


def test_layout_cache_ignores_paint_height_and_system_offset() -> None:
    clear_layout_cache()
    score = _score(4)

    short = layout_score(score, viewport=LayoutViewport(width=80, height=20))
    tall_scrolled = layout_score(score, viewport=LayoutViewport(width=80, height=60, system_offset=1))

    assert short is tall_scrolled


def test_forced_break_is_first_class_and_final_system_stays_natural() -> None:
    score = NotationScore(
        id="forced-score",
        staffs=(
            NotationStaff(
                id="forced-staff",
                measures=(_measure(1, forced_break=True), _measure(2), _measure(3)),
            ),
        ),
    )

    layout = layout_score(score, viewport=LayoutViewport(width=100, height=30))

    assert [(system.measure_start, system.measure_end) for system in layout.systems] == [(0, 1), (1, 3)]
    assert layout.systems[0].measure_boxes[0].width < 80


def test_layout_uses_one_onset_coordinate_for_note_and_lyric_lane() -> None:
    note = _event("same-pitch-1", 0, 60)
    repeated = _event("same-pitch-2", 1, 60)
    lyrics = (
        LyricSyllable("lyric-1", note.id, "sing"),
        LyricSyllable("lyric-2", repeated.id, "again"),
    )
    score = NotationScore(
        id="lyrics-score",
        staffs=(
            NotationStaff(
                id="lyrics-staff",
                measures=(
                    NotationMeasure(
                        "lyrics-measure",
                        1,
                        (note, repeated),
                        time_signature=TimeSignature(),
                    ),
                ),
                lyrics=lyrics,
            ),
        ),
    )

    layout = layout_score(score, viewport=LayoutViewport(width=60, height=24))

    for lyric, event in zip(lyrics, (note, repeated), strict=True):
        lyric_element = layout.elements_for(lyric.id)[0]
        onset = layout.onset_for(event.id)
        assert onset is not None
        assert lyric_element.key.role is ElementRole.LYRIC
        assert lyric_element.rect.x == onset.x
    note_onset = layout.onset_for(note.id)
    repeated_onset = layout.onset_for(repeated.id)
    assert note_onset is not None
    assert repeated_onset is not None
    assert note_onset.x != repeated_onset.x


def test_row_budget_and_clef_mapping_are_explicit() -> None:
    treble = _event("treble-e4", 0, 64)
    bass = _event("bass-g2", 0, 43)
    score = NotationScore(
        id="grand-staff",
        staffs=(
            NotationStaff(
                id="treble",
                clef=Clef.TREBLE,
                measures=(NotationMeasure("treble-measure", 1, (treble,), time_signature=TimeSignature()),),
            ),
            NotationStaff(
                id="bass",
                clef=Clef.BASS,
                measures=(NotationMeasure("bass-measure", 1, (bass,), time_signature=TimeSignature()),),
            ),
        ),
    )

    layout = layout_score(score, viewport=LayoutViewport(width=80, height=40))
    system = layout.systems[0]
    treble_head = next(
        element for element in layout.elements_for(treble.id) if element.key.role is ElementRole.NOTEHEAD
    )
    bass_head = next(element for element in layout.elements_for(bass.id) if element.key.role is ElementRole.NOTEHEAD)

    assert treble_head.rect.y == system.staff_rows[0].line_rows[-1]
    assert bass_head.rect.y == system.staff_rows[1].line_rows[-1]
    assert system.staff_rows[0].bottom < system.staff_rows[1].top


def test_row_budget_tracks_content_without_fixed_empty_padding() -> None:
    middle = _event("middle", 0, 71)
    low = _event("low", 1, 48)
    high = _event("high", 2, 84)
    compact_score = NotationScore(
        id="compact-score",
        staffs=(
            NotationStaff(
                id="compact-staff",
                measures=(NotationMeasure("compact-measure", 1, (middle,), time_signature=TimeSignature()),),
            ),
        ),
    )
    score = NotationScore(
        id="vertical-score",
        staffs=(
            NotationStaff(
                id="vertical-staff",
                measures=(
                    NotationMeasure(
                        "vertical-measure",
                        1,
                        (middle, low, high),
                        time_signature=TimeSignature(),
                    ),
                ),
            ),
        ),
    )

    compact = layout_score(compact_score, viewport=LayoutViewport(width=80, height=30))
    layout = layout_score(score, viewport=LayoutViewport(width=80, height=30))
    rows = layout.systems[0].staff_rows[0]
    event_elements = [
        element
        for event in (low, high)
        for element in layout.elements_for(event.id)
        if element.key.role in {ElementRole.NOTEHEAD, ElementRole.LEDGER_LINE, ElementRole.STEM}
    ]

    compact_rows = compact.systems[0].staff_rows[0]
    assert compact_rows.line_rows[0] - compact_rows.notation_top == 1
    assert all(rows.top <= element.rect.y and element.rect.bottom <= rows.bottom for element in event_elements)
    assert not layout.systems[0].clipped


def test_key_signatures_use_separate_conventional_treble_and_bass_positions() -> None:
    score = NotationScore(
        id="signature-score",
        staffs=(
            NotationStaff(
                id="signature-treble",
                measures=(NotationMeasure("signature-treble-measure", 1, key_signature=KeySignature(2)),),
            ),
            NotationStaff(
                id="signature-bass",
                clef=Clef.BASS,
                measures=(NotationMeasure("signature-bass-measure", 1, key_signature=KeySignature(-2)),),
            ),
        ),
    )

    layout = layout_score(score)
    treble = [
        element for element in layout.elements_for("signature-treble") if element.key.role is ElementRole.KEY_SIGNATURE
    ]
    bass = [
        element for element in layout.elements_for("signature-bass") if element.key.role is ElementRole.KEY_SIGNATURE
    ]

    assert [(element.rect.x, element.rect.y, element.value) for element in treble] == [
        (4, layout.systems[0].staff_rows[0].line_rows[0], "sharp"),
        (5, layout.systems[0].staff_rows[0].line_rows[0] + 3, "sharp"),
    ]
    assert [(element.rect.x, element.rect.y, element.value) for element in bass] == [
        (4, layout.systems[0].staff_rows[1].line_rows[-1] - 2, "flat"),
        (5, layout.systems[0].staff_rows[1].line_rows[-1] - 5, "flat"),
    ]


def test_measure_accidentals_follow_key_state_naturals_repeats_and_courtesy_signs() -> None:
    pitches = (
        WrittenPitch(PitchStep.F, 4, 1),
        WrittenPitch(PitchStep.F, 4, 1),
        WrittenPitch(PitchStep.F, 4),
        WrittenPitch(PitchStep.F, 4),
        WrittenPitch(PitchStep.F, 4, 1, AccidentalDisplay.COURTESY),
        WrittenPitch(PitchStep.F, 4, 1, AccidentalDisplay.EXPLICIT),
    )
    events = tuple(
        NotationEvent(
            f"accidental-{index}",
            Fraction(index, 8),
            Fraction(1, 8),
            EventKind.NOTE,
            (pitch,),
        )
        for index, pitch in enumerate(pitches)
    )
    score = NotationScore(
        "accidental-score",
        (
            NotationStaff(
                "accidental-staff",
                (
                    NotationMeasure(
                        "accidental-measure",
                        1,
                        events,
                        key_signature=KeySignature(1),
                    ),
                ),
            ),
        ),
    )

    layout = layout_score(score, viewport=LayoutViewport(width=100, height=24))
    values = [
        [element.value for element in layout.elements_for(event.id) if element.key.role is ElementRole.ACCIDENTAL]
        for event in events
    ]

    assert values == [[], [], ["0"], [], ["1"], ["1"]]


def test_beams_flags_and_cross_system_spans_are_semantic_elements() -> None:
    beamed = tuple(
        NotationEvent(
            id=f"beam-{index}",
            onset=Fraction(index, 8),
            duration=Fraction(1, 8),
            kind=EventKind.NOTE,
            pitches=(pitch_from_midi(64 + index),),
            beam=(BeamKind.START, BeamKind.CONTINUE, BeamKind.CONTINUE, BeamKind.END)[index],
        )
        for index in range(4)
    )
    short = NotationEvent(
        id="flagged",
        onset=Fraction(1, 2),
        duration=Fraction(1, 16),
        kind=EventKind.NOTE,
        pitches=(pitch_from_midi(69),),
    )
    tied = NotationEvent(
        id="tie-end",
        onset=Fraction(0),
        duration=Fraction(1, 4),
        kind=EventKind.NOTE,
        pitches=(pitch_from_midi(69),),
    )
    score = NotationScore(
        id="notation-structure",
        staffs=(
            NotationStaff(
                id="notation-staff",
                measures=(
                    NotationMeasure(
                        "notation-m1",
                        1,
                        (*beamed, short),
                        time_signature=TimeSignature(),
                        forced_break_after=True,
                    ),
                    NotationMeasure("notation-m2", 2, (tied,)),
                ),
                spans=(NotationSpan("tie", SpanKind.TIE, short.id, tied.id),),
            ),
        ),
    )

    layout = layout_score(score, viewport=LayoutViewport(width=80, height=30))

    assert len([element for element in layout.elements if element.key.role is ElementRole.BEAM]) == 1
    assert len([element for element in layout.elements_for(short.id) if element.key.role is ElementRole.FLAG]) == 2
    tie_segments = [element for element in layout.elements_for("tie") if element.key.role is ElementRole.TIE]
    assert len(tie_segments) == 2
    assert all(element.continuation for element in tie_segments)


def test_measure_spans_dynamics_and_lyrics_have_distinct_reserved_lanes() -> None:
    first = NotationEvent(
        "lane-first",
        Fraction(0),
        Fraction(1, 4),
        EventKind.NOTE,
        (pitch_from_midi(60),),
        dynamic="mf",
        fermata=True,
        ornament=OrnamentKind.PLUS,
    )
    second = _event("lane-second", 1, 62)
    score = NotationScore(
        "lane-score",
        (
            NotationStaff(
                "lane-staff",
                (NotationMeasure("lane-measure", 1, (first, second), ending_numbers=(1,)),),
                lyrics=(LyricSyllable("lane-lyric", first.id, "sing"),),
                spans=(NotationSpan("lane-slur", SpanKind.SLUR, first.id, second.id),),
            ),
        ),
    )

    layout = layout_score(score)
    system = layout.systems[0]
    rows = system.staff_rows[0]
    measure_number = layout.elements_for("lane-measure")[0]
    ending = next(element for element in layout.elements_for("lane-measure") if element.key.role is ElementRole.ENDING)
    slur = layout.elements_for("lane-slur")[0]
    dynamic = next(element for element in layout.elements_for(first.id) if element.key.role is ElementRole.DYNAMIC)
    ornament = next(element for element in layout.elements_for(first.id) if element.key.role is ElementRole.ORNAMENT)
    fermata = next(element for element in layout.elements_for(first.id) if element.key.role is ElementRole.FERMATA)
    lyric = layout.elements_for("lane-lyric")[0]

    assert measure_number.rect.y == rows.measure_number_row
    assert ending.rect.y == rows.ending_row
    assert slur.rect.y in rows.slur_rows
    assert ornament.rect.y == rows.ornament_row
    assert fermata.rect.y == rows.fermata_row
    assert dynamic.rect.y == rows.dynamic_row
    assert lyric.rect.y in rows.lyric_rows
    assert (
        len(
            {
                measure_number.rect.y,
                ending.rect.y,
                slur.rect.y,
                ornament.rect.y,
                fermata.rect.y,
                dynamic.rect.y,
                lyric.rect.y,
            },
        )
        == 7
    )
    assert dynamic.rect.y > rows.notation_bottom


def test_feedback_rows_are_content_derived_unless_stable_lane_is_requested() -> None:
    score = NotationScore(
        "feedback-score",
        (
            NotationStaff(
                "feedback-staff",
                (_measure(1, forced_break=True), _measure(2)),
            ),
        ),
    )

    compact = layout_score(score, feedback_event_ids=frozenset({"event-1-0"}))
    stable = layout_score(score, policy=NotationLayoutPolicy(reserve_feedback_lane=True))

    assert compact.systems[0].staff_rows[0].feedback_row is not None
    assert compact.systems[1].staff_rows[0].feedback_row is None
    assert all(system.staff_rows[0].feedback_row is not None for system in stable.systems)
    assert compact.document_height < stable.document_height


def test_layout_rejects_unrepresentable_duration_instead_of_guessing_quarter_note() -> None:
    unsupported = NotationEvent(
        "unsupported",
        Fraction(0),
        Fraction(1, 3),
        EventKind.NOTE,
        (pitch_from_midi(60),),
    )
    score = NotationScore(
        "unsupported-score",
        (NotationStaff("unsupported-staff", (NotationMeasure("unsupported-measure", 1, (unsupported,)),)),),
    )

    with pytest.raises(LayoutError, match="unsupported written duration 1/3"):
        layout_score(score)


def test_tuplet_ratio_recovers_the_written_note_value() -> None:
    triplet = NotationEvent(
        "triplet",
        Fraction(0),
        Fraction(1, 12),
        EventKind.NOTE,
        (pitch_from_midi(60),),
        tuplet=TupletRatio(3, 2),
    )
    score = NotationScore(
        "triplet-score",
        (NotationStaff("triplet-staff", (NotationMeasure("triplet-measure", 1, (triplet,)),)),),
    )

    layout = layout_score(score)

    assert any(element.key.role is ElementRole.TUPLET for element in layout.elements_for(triplet.id))
