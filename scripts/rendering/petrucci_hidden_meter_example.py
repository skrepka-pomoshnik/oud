#!/usr/bin/env python3
"""Hide a meter glyph without removing the score's musical meter."""

from __future__ import annotations

from fractions import Fraction

from petrucci import (
    EventKind,
    GlyphMode,
    NotationEvent,
    NotationLayoutPolicy,
    NotationMeasure,
    NotationScore,
    NotationStaff,
    ScoreTypesetOptions,
    TimeSignature,
    pitch_from_midi,
    typeset_score,
)


def _score() -> tuple[NotationScore, TimeSignature]:
    notes = tuple(
        NotationEvent(
            f"meter:event:{index}",
            Fraction(index, 4),
            Fraction(1, 4),
            EventKind.NOTE,
            (pitch_from_midi(midi),),
        )
        for index, midi in enumerate((60, 62, 64))
    )
    meter = TimeSignature(3, 4)
    measure = NotationMeasure(
        "meter:measure:1",
        1,
        notes,
        time_signature=meter,
    )
    score = NotationScore("hidden-meter-example", (NotationStaff("voice", (measure,)),))
    return score, meter


def render_example() -> str:
    score, meter = _score()
    result = typeset_score(
        score,
        options=ScoreTypesetOptions(
            width=56,
            height=16,
            glyph_mode=GlyphMode.SAFE,
            policy=NotationLayoutPolicy(show_title=False, show_time_signature=False),
        ),
    )
    return f"meter={meter.beats}/{meter.beat_unit}; glyph=hidden\n{result.text}"


def main() -> int:
    print(render_example())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
