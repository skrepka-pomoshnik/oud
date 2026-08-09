#!/usr/bin/env python3
"""Measure Petrucci's source-neutral live score path without terminal I/O."""

from __future__ import annotations

import argparse
from collections.abc import Callable
from fractions import Fraction
from statistics import median
from time import perf_counter

from petrucci import (
    FlowEvent,
    GlyphMode,
    LayoutViewport,
    adapt_flow_events,
    clear_layout_cache,
    layout_score,
    paint_score,
)


def _events(count: int) -> tuple[FlowEvent, ...]:
    return tuple(
        FlowEvent(
            id=f"event:{index}",
            onset=Fraction(index, 2),
            duration=Fraction(1, 2),
            midi_pitches=((60 + (index % 12)),),
        )
        for index in range(count)
    )


def _elapsed_ms(call: Callable[[], object]) -> float:
    started = perf_counter()
    call()
    return (perf_counter() - started) * 1_000


def benchmark(*, count: int, width: int, height: int, iterations: int) -> dict[str, float]:
    events = _events(count)
    adapted = adapt_flow_events(events)
    layout_viewport = LayoutViewport(width=width * 4, height=height)
    cold_layout_ms: list[float] = []
    for _ in range(iterations):
        clear_layout_cache()
        cold_layout_ms.append(_elapsed_ms(lambda: layout_score(adapted.score, viewport=layout_viewport)))
    layout = layout_score(adapted.score, viewport=layout_viewport)
    cached_layout_ms = [
        _elapsed_ms(lambda: layout_score(adapted.score, viewport=layout_viewport)) for _ in range(iterations)
    ]
    paint_ms: list[float] = []
    for index in range(iterations):
        x_offset = index % max(1, layout.width - width + 1)
        paint_ms.append(
            _elapsed_ms(
                lambda x_offset=x_offset: paint_score(
                    layout,
                    viewport=LayoutViewport(width=width, height=height, x_offset=x_offset),
                    glyph_mode=GlyphMode.SAFE,
                )
            )
        )
    return {
        "adapt_ms": _elapsed_ms(lambda: adapt_flow_events(events)),
        "cold_layout_ms": median(cold_layout_ms),
        "cached_layout_ms": median(cached_layout_ms),
        "paint_ms": median(paint_ms),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--events", type=int, default=256)
    parser.add_argument("--width", type=int, default=80)
    parser.add_argument("--height", type=int, default=24)
    parser.add_argument("--iterations", type=int, default=7)
    parser.add_argument("--max-live-ms", type=float)
    args = parser.parse_args()
    if min(args.events, args.width, args.height, args.iterations) <= 0:
        parser.error("events, width, height, and iterations must be positive")
    results = benchmark(count=args.events, width=args.width, height=args.height, iterations=args.iterations)
    for label, value in results.items():
        print(f"{label}: {value:.3f}")
    live_ms = results["cached_layout_ms"] + results["paint_ms"]
    print(f"cached_layout_plus_paint_ms: {live_ms:.3f}")
    return int(args.max_live_ms is not None and live_ms > args.max_live_ms)


if __name__ == "__main__":
    raise SystemExit(main())
