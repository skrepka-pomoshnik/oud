from __future__ import annotations

from scripts.rendering.benchmark_flow import benchmark
from scripts.rendering.petrucci_hidden_meter_example import render_example as render_hidden_meter
from scripts.rendering.petrucci_overlay_example import render_example as render_overlay


def test_repeated_layout_and_score_replacement_stay_bounded() -> None:
    results = benchmark(count=24, width=48, height=18, iterations=3, replacements=66)

    assert results["cached_layout_p95_ms"] < 1_000
    assert results["paint_p95_ms"] < 1_000
    assert results["batch_lookup_p95_ms"] < 1_000
    assert results["resize_p95_ms"] < 2_000
    assert results["replacement_p95_ms"] < 2_000
    assert results["replacement_peak_growth_kib"] < 64 * 1_024
    assert results["replacement_retained_after_clear_kib"] < 1_024
    assert results["max_layout_width"] <= 80
    assert results["max_document_height"] <= 64


def test_handoff_examples_are_runnable() -> None:
    overlay = render_overlay()
    hidden_meter = render_hidden_meter()

    assert "@" in overlay
    assert "~" in overlay
    assert "meter=3/4; glyph=hidden" in hidden_meter
