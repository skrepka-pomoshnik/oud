#!/usr/bin/env python3
"""Render a clipped proportional score with highlighting and a pitch trace."""

from __future__ import annotations

from fractions import Fraction

from petrucci import (
    EventKind,
    GlyphMode,
    LayoutViewport,
    NotationEvent,
    NotationLayoutPolicy,
    NotationMeasure,
    NotationScore,
    NotationStaff,
    ProjectionRounding,
    TimelineProjectionRequest,
    layout_score_proportional,
    paint_score,
    pitch_from_midi,
    project_continuous_pitch,
    round_projection,
)


def _score() -> NotationScore:
    events = tuple(
        NotationEvent(
            f"voice:event:{index}",
            Fraction(index, 4),
            Fraction(1, 4),
            EventKind.NOTE,
            (pitch_from_midi(midi),),
        )
        for index, midi in enumerate((60, 64, 67, 72))
    )
    measure = NotationMeasure("voice:measure:1", 1, events)
    return NotationScore("overlay-example", (NotationStaff("voice", (measure,)),))


def render_example() -> str:
    score = _score()
    request = TimelineProjectionRequest(
        origin=Fraction(1, 8),
        columns_per_whole=Fraction(48),
        width=64,
        preamble_width=16,
    )
    layout = layout_score_proportional(score, request, policy=NotationLayoutPolicy(show_title=False))
    frame = paint_score(
        layout,
        viewport=LayoutViewport(width=request.width, height=16),
        glyph_mode=GlyphMode.SAFE,
    )
    lines = [list(line) for line in frame.lines]
    for row, column in frame.cells_for_many(("voice:event:2",))["voice:event:2"]:
        lines[row][column] = "@"
    sample_time = Fraction(5, 8)
    staff_rows = layout.systems[0].staff_rows[0]
    pitch = project_continuous_pitch(
        score,
        "voice",
        sample_time,
        Fraction(271, 4),
        bottom_row=staff_rows.line_rows[-1],
        rounding=ProjectionRounding.NEAREST,
    )
    sample_x = round_projection(
        request.preamble_width + (sample_time - request.origin) * request.columns_per_whole,
        request.rounding,
    )
    if 0 <= pitch.rounded_row < len(lines) and 0 <= sample_x < request.width:
        lines[pitch.rounded_row][sample_x] = "~"
    return "\n".join("".join(line) for line in lines)


def main() -> int:
    print(render_example())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
