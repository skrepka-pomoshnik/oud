#!/usr/bin/env python3
"""Measure Petrucci's source-neutral live score path without terminal I/O."""

from __future__ import annotations

import argparse
import gc
import tracemalloc
from collections.abc import Callable
from fractions import Fraction
from statistics import median
from time import perf_counter

from petrucci import (
    FlowEvent,
    GlyphMode,
    LayoutViewport,
    NotationScore,
    ScoreLayout,
    adapt_flow_events,
    clear_layout_cache,
    layout_score,
    paint_score,
)


def _events(count: int, generation: int = 0) -> tuple[FlowEvent, ...]:
    return tuple(
        FlowEvent(
            id=f"generation:{generation}:event:{index}",
            onset=Fraction(index, 4),
            duration=Fraction(1, 4),
            midi_pitches=(48 + ((index + generation) % 24),),
        )
        for index in range(count)
    )


def _elapsed_ms(call: Callable[[], object]) -> float:
    started = perf_counter()
    call()
    return (perf_counter() - started) * 1_000


def _p95(values: list[float]) -> float:
    ordered = sorted(values)
    index = max(0, (len(ordered) * 95 + 99) // 100 - 1)
    return ordered[index]


def _measure_interactions(
    score: NotationScore,
    layout: ScoreLayout,
    *,
    width: int,
    height: int,
    iterations: int,
) -> dict[str, float]:
    cached_viewport = LayoutViewport(width=width * 3)
    cached = [_elapsed_ms(lambda: layout_score(score, viewport=cached_viewport)) for _ in range(iterations)]
    paints: list[float] = []
    frame = paint_score(layout, viewport=LayoutViewport(width=width, height=height), glyph_mode=GlyphMode.SAFE)
    for index in range(iterations):
        x_offset = (index * 7) % max(1, layout.width - width + 1)
        paints.append(
            _elapsed_ms(
                lambda x_offset=x_offset: paint_score(
                    layout,
                    viewport=LayoutViewport(width=width, height=height, x_offset=x_offset),
                    glyph_mode=GlyphMode.SAFE,
                )
            )
        )
    lookups = [_elapsed_ms(lambda: frame.cells_for_many(layout.event_ids)) for _ in range(iterations)]
    resize_times: list[float] = []
    resized_layouts: list[ScoreLayout] = []
    for index in range(iterations):
        resized_width = (width, width + 16, width + 32)[index % 3]
        resized_height = height + (index % 2) * 6
        started = perf_counter()
        resized_layouts.append(layout_score(score, viewport=LayoutViewport(width=resized_width, height=resized_height)))
        resize_times.append((perf_counter() - started) * 1_000)
    return {
        "cached_layout_ms": median(cached),
        "cached_layout_p95_ms": _p95(cached),
        "paint_ms": median(paints),
        "paint_p95_ms": _p95(paints),
        "batch_lookup_p95_ms": _p95(lookups),
        "resize_p95_ms": _p95(resize_times),
        "max_layout_width": float(max(item.width for item in resized_layouts)),
        "max_document_height": float(max(item.document_height for item in resized_layouts)),
    }


def _measure_replacements(*, count: int, width: int, height: int, replacements: int) -> dict[str, float]:
    clear_layout_cache()
    gc.collect()
    tracemalloc.start()
    baseline = tracemalloc.get_traced_memory()[0]
    times: list[float] = []
    max_width = 0
    max_height = 0
    replacement_score: NotationScore | None = None
    replacement_layout: ScoreLayout | None = None
    try:
        for generation in range(1, replacements + 1):
            replacement_score = adapt_flow_events(_events(count, generation)).score
            started = perf_counter()
            replacement_layout = layout_score(replacement_score, viewport=LayoutViewport(width=width, height=height))
            times.append((perf_counter() - started) * 1_000)
            max_width = max(max_width, replacement_layout.width)
            max_height = max(max_height, replacement_layout.document_height)
        peak = tracemalloc.get_traced_memory()[1]
        clear_layout_cache()
        replacement_score = None
        replacement_layout = None
        gc.collect()
        retained = max(0, tracemalloc.get_traced_memory()[0] - baseline)
    finally:
        clear_layout_cache()
        tracemalloc.stop()
    return {
        "replacement_p95_ms": _p95(times),
        "replacement_peak_growth_kib": (peak - baseline) / 1_024,
        "replacement_retained_after_clear_kib": retained / 1_024,
        "replacement_layout_width": float(max_width),
        "replacement_document_height": float(max_height),
    }


def benchmark(*, count: int, width: int, height: int, iterations: int, replacements: int = 66) -> dict[str, float]:
    events = _events(count)
    started = perf_counter()
    adapted = adapt_flow_events(events)
    adapt_ms = (perf_counter() - started) * 1_000
    layout_viewport = LayoutViewport(width=width * 3, height=height)
    cold_layout_ms: list[float] = []
    for _ in range(iterations):
        clear_layout_cache()
        cold_layout_ms.append(_elapsed_ms(lambda: layout_score(adapted.score, viewport=layout_viewport)))
    layout = layout_score(adapted.score, viewport=layout_viewport)
    results = {
        "adapt_ms": adapt_ms,
        "cold_layout_ms": median(cold_layout_ms),
    }
    results.update(_measure_interactions(adapted.score, layout, width=width, height=height, iterations=iterations))
    results.update(_measure_replacements(count=count, width=width, height=height, replacements=replacements))
    results["cached_layout_plus_paint_ms"] = results["cached_layout_ms"] + results["paint_ms"]
    results["max_layout_width"] = max(results["max_layout_width"], results["replacement_layout_width"])
    results["max_document_height"] = max(results["max_document_height"], results["replacement_document_height"])
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--events", type=int, default=256)
    parser.add_argument("--width", type=int, default=80)
    parser.add_argument("--height", type=int, default=24)
    parser.add_argument("--iterations", type=int, default=7)
    parser.add_argument("--replacements", type=int, default=66)
    parser.add_argument("--max-live-ms", type=float)
    parser.add_argument("--max-frame-ms", type=float)
    parser.add_argument("--max-peak-kib", type=float)
    parser.add_argument("--max-retained-kib", type=float)
    args = parser.parse_args()
    if min(args.events, args.width, args.height, args.iterations, args.replacements) <= 0:
        parser.error("events, width, height, iterations, and replacements must be positive")
    results = benchmark(
        count=args.events,
        width=args.width,
        height=args.height,
        iterations=args.iterations,
        replacements=args.replacements,
    )
    for label, value in results.items():
        print(f"{label}: {value:.3f}")
    frame_ms = max(results["paint_p95_ms"], results["resize_p95_ms"], results["replacement_p95_ms"])
    retained_kib = results["replacement_retained_after_clear_kib"]
    failed = args.max_live_ms is not None and results["cached_layout_plus_paint_ms"] > args.max_live_ms
    failed |= args.max_frame_ms is not None and frame_ms > args.max_frame_ms
    failed |= args.max_peak_kib is not None and results["replacement_peak_growth_kib"] > args.max_peak_kib
    failed |= args.max_retained_kib is not None and retained_kib > args.max_retained_kib
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
