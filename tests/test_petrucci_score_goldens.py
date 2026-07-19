from __future__ import annotations

from fractions import Fraction
from pathlib import Path

from petrucci import (
    AccidentalDisplay,
    BeamKind,
    EventKind,
    GlyphMode,
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
    StemDirection,
    Syllabic,
    TimeSignature,
    TupletRatio,
    WrittenPitch,
    layout_collisions,
    pitch_from_midi,
    typeset_score,
)

FIXTURES = Path(__file__).parent / "fixtures"
WIDTHS = (60, 80, 120)


def _note(
    event_id: str,
    onset: Fraction,
    duration: Fraction,
    midi: int,
    **kwargs,
) -> NotationEvent:
    return NotationEvent(
        event_id,
        onset,
        duration,
        EventKind.NOTE,
        (pitch_from_midi(midi),),
        **kwargs,
    )


def _acceptance_score() -> NotationScore:
    dense = NotationEvent(
        "dense-chord",
        Fraction(0),
        Fraction(1, 12),
        EventKind.NOTE,
        (
            WrittenPitch(PitchStep.C, 4, 1, AccidentalDisplay.EXPLICIT),
            WrittenPitch(PitchStep.D, 4),
            WrittenPitch(PitchStep.G, 5),
        ),
        dynamic="ff",
        ornament=OrnamentKind.TURN,
        editorial_brackets=True,
        grace=True,
        tuplet=TupletRatio(3, 2),
    )
    voice_rest = NotationEvent("voice-rest", Fraction(0), Fraction(1, 4), EventKind.REST, voice=1, dynamic="pp")
    repeated_first = _note(
        "repeated-first",
        Fraction(1, 4),
        Fraction(3, 16),
        60,
        beam=BeamKind.START,
        stem=StemDirection.UP,
    )
    repeated_second = _note(
        "repeated-second",
        Fraction(7, 16),
        Fraction(1, 16),
        60,
        beam=BeamKind.END,
        stem=StemDirection.UP,
    )
    high = _note("high-ledger", Fraction(1, 2), Fraction(1, 4), 96, ornament=OrnamentKind.TRILL)
    sparse_rest = NotationEvent("sparse-rest", Fraction(0), Fraction(1), EventKind.REST)
    tied = _note("tied-repeat", Fraction(0), Fraction(1, 4), 60)
    middle_rest = NotationEvent("middle-rest", Fraction(1, 4), Fraction(1, 4), EventKind.REST)
    accidental = NotationEvent(
        "courtesy-flat",
        Fraction(1, 2),
        Fraction(1, 4),
        EventKind.NOTE,
        (WrittenPitch(PitchStep.B, 3, -1, AccidentalDisplay.COURTESY),),
    )
    low = _note("low-ledger", Fraction(3, 4), Fraction(1, 4), 36)
    polyphony = tuple(
        NotationEvent(
            f"poly-{voice}",
            Fraction(0),
            Fraction(1, 4),
            EventKind.REST if voice % 3 == 2 else EventKind.NOTE,
            () if voice % 3 == 2 else (pitch_from_midi(48 + (voice * 3)),),
            voice=voice,
            dynamic=("p", "mf", "f")[voice % 3],
            stem=StemDirection.UP if voice % 2 == 0 else StemDirection.DOWN,
        )
        for voice in range(8)
    )
    measures = (
        NotationMeasure(
            "dense-measure",
            1,
            (dense, voice_rest, repeated_first, repeated_second, high),
            time_signature=TimeSignature(),
            forced_break_after=True,
        ),
        NotationMeasure("sparse-measure", 2, (sparse_rest,), forced_break_after=True),
        NotationMeasure("varied-measure", 3, (tied, middle_rest, accidental, low)),
        NotationMeasure("poly-measure", 4, polyphony),
    )
    lyrics = (
        LyricSyllable("dense-lyric-1", dense.id, "Bright", verse=0, syllabic=Syllabic.BEGIN),
        LyricSyllable("dense-lyric-2", repeated_first.id, "notes", verse=0, syllabic=Syllabic.END),
        LyricSyllable("dense-verse-2", dense.id, "Second", verse=1),
        LyricSyllable("varied-lyric", tied.id, "again", extender=True),
        *(LyricSyllable(f"poly-lyric-{voice}", event.id, f"voice{voice}") for voice, event in enumerate(polyphony)),
    )
    return NotationScore(
        "golden-score",
        (
            NotationStaff(
                "golden-staff",
                measures,
                label="Voice",
                lyrics=lyrics,
                spans=(
                    NotationSpan("outer-slur", SpanKind.SLUR, dense.id, high.id),
                    NotationSpan("inner-slur", SpanKind.SLUR, dense.id, repeated_second.id),
                    NotationSpan("cross-system-tie", SpanKind.TIE, repeated_second.id, tied.id),
                ),
            ),
        ),
        title="Petrucci acceptance",
        composer="Oud",
    )


def _structural_snapshot() -> str:
    score = _acceptance_score()
    lines: list[str] = []
    for width in WIDTHS:
        result = typeset_score(
            score,
            options=ScoreTypesetOptions(width=width, height=48, glyph_mode=GlyphMode.SAFE),
        )
        layout = result.layout
        lines.append(f"width={width}")
        lines.append(f"systems={[(system.measure_start, system.measure_end) for system in layout.systems]}")
        lines.append(f"clipped={[system.clipped_event_ids for system in layout.systems]}")
        lines.append(f"collisions={layout_collisions(layout)}")
        active_ids = ("dense-chord", "sparse-rest", "tied-repeat", "poly-7")
        locations = {event_id: layout.location_for(event_id) for event_id in active_ids}
        assert all(location is not None for location in locations.values())
        lines.append(
            "active="
            + ",".join(
                f"{event_id}:{location.system_index}"
                for event_id, location in locations.items()
                if location is not None
            ),
        )
    return "\n".join(lines) + "\n"


def _text_snapshot() -> str:
    score = _acceptance_score()
    sections: list[str] = []
    for width in WIDTHS:
        layout_result = typeset_score(
            score,
            options=ScoreTypesetOptions(width=width, height=38, glyph_mode=GlyphMode.SAFE),
        )
        offsets = (
            (0, len(layout_result.layout.systems) - 1)
            if width == WIDTHS[0]
            else (len(layout_result.layout.systems) - 1,)
        )
        for system_offset in offsets:
            result = typeset_score(
                score,
                options=ScoreTypesetOptions(
                    width=width,
                    height=38,
                    system_offset=system_offset,
                    glyph_mode=GlyphMode.SAFE,
                ),
            )
            sections.append(f"=== width={width} system={system_offset} ===")
            sections.append(result.text.rstrip())
    return "\n".join(sections) + "\n"


def test_width_matrix_matches_structural_and_text_goldens() -> None:
    assert _structural_snapshot() == (FIXTURES / "petrucci_score_widths.struct.snap.txt").read_text(encoding="utf-8")
    assert _text_snapshot() == (FIXTURES / "petrucci_score_widths.text.snap.txt").read_text(encoding="utf-8")


def test_width_matrix_preserves_active_ids_across_resize_and_clipping() -> None:
    score = _acceptance_score()
    for width in WIDTHS:
        result = typeset_score(
            score,
            options=ScoreTypesetOptions(width=width, height=48, glyph_mode=GlyphMode.SAFE),
        )
        assert layout_collisions(result.layout) == ()
        for event_id in ("dense-chord", "sparse-rest", "tied-repeat", "poly-7"):
            location = result.layout.location_for(event_id)
            assert location is not None
            active = typeset_score(
                score,
                options=ScoreTypesetOptions(
                    width=width,
                    height=48,
                    system_offset=location.system_index,
                    glyph_mode=GlyphMode.SAFE,
                ),
            )
            assert active.cells_for(event_id)
