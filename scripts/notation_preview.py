"""Print a legal, source-independent score using terminal-native notation."""

from __future__ import annotations

import argparse
import os
import sys
from fractions import Fraction

from petrucci import (
    BeamKind,
    FlowEvent,
    FlowScoreOptions,
    GlyphMode,
    LayoutMetrics,
    NotationLayoutPolicy,
    NotationScore,
    ScoreTypesetOptions,
    TerminalNoteheads,
    adapt_flow_events,
    typeset_score,
)
from petrucci.terminal.rendering.ansi import INK, PAPER, colour_score


def example_score(*, label: str = "Voice") -> NotationScore:
    """A two-bar phrase with beams, a tied note, an accidental, and a rest."""

    events = (
        FlowEvent("e", Fraction(0), Fraction(1, 2), (64,), beam=BeamKind.START),
        FlowEvent("g", Fraction(1, 2), Fraction(1, 2), (67,), beam=BeamKind.END),
        FlowEvent("b", Fraction(1), Fraction(1), (71,)),
        FlowEvent("held", Fraction(2), Fraction(4), (71,)),
        FlowEvent("sharp", Fraction(6), Fraction(3, 4), (78,)),
        FlowEvent("rest", Fraction(27, 4), Fraction(1, 4)),
        FlowEvent("d", Fraction(7), Fraction(1), (74,)),
    )
    return adapt_flow_events(events, options=FlowScoreOptions(staff_label=label)).score


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("ascii", "advanced", "block"), default="ascii")
    parser.add_argument("--width", type=int, default=96)
    parser.add_argument("--height", type=int, default=24)
    parser.add_argument("--spacing", choices=("normal", "compact"), default="normal")
    parser.add_argument("--color", choices=("never", "auto", "always"), default="never")
    parser.add_argument("--palette", choices=("ink", "paper"), default="ink")
    parser.add_argument(
        "--highlight", action="append", default=[], metavar="EVENT_ID", help="Highlight an event, without playback"
    )
    args = parser.parse_args()
    compact = args.spacing == "compact"
    options = ScoreTypesetOptions(
        width=args.width,
        height=args.height,
        glyph_mode=GlyphMode(args.mode),
        noteheads=TerminalNoteheads(filled="*", open="o") if args.mode == "ascii" else None,
        metrics=(
            LayoutMetrics(
                event_gap=1,
                barline_gap=1,
                left_padding=0,
                right_padding=0,
                system_prefix_width=8,
                max_measure_stretch=0,
            )
            if compact
            else LayoutMetrics(event_gap=1, barline_gap=1)
        ),
        policy=NotationLayoutPolicy(
            show_title=False,
            show_measure_numbers=False,
            compact_beams=True,
            compact_spacing=compact,
            justify=not compact,
        ),
    )
    result = typeset_score(example_score(label="" if compact else "Voice"), options=options)
    coloured = args.color == "always" or (args.color == "auto" and sys.stdout.isatty() and "NO_COLOR" not in os.environ)
    output = (
        colour_score(result.semantic_frame, palette=INK if args.palette == "ink" else PAPER, active_ids=args.highlight)
        if coloured
        else result.text
    )
    print(output, end="")


if __name__ == "__main__":
    main()
