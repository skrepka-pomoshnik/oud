"""Scrolling reuses immutable musical geometry and releases it on cleanup."""

from dataclasses import replace
from fractions import Fraction
from unittest.mock import patch

from petrucci import (
    FlowEvent,
    TimelineProjectionRequest,
    adapt_flow_events,
    clear_layout_cache,
    layout_score_proportional,
)
from petrucci.engraving.notation import horizontal
from petrucci.terminal import display


def test_scrolling_reuses_measure_geometry_until_cache_cleanup() -> None:
    score = adapt_flow_events(tuple(FlowEvent(str(i), Fraction(i, 4), Fraction(1, 4), (60,)) for i in range(8))).score
    request = TimelineProjectionRequest(Fraction(), Fraction(32), width=80, preamble_width=16)
    clear_layout_cache()
    with patch.object(horizontal, "_onset_groups", wraps=horizontal._onset_groups) as measure:
        first = layout_score_proportional(score, request)
        initial_work = measure.call_count
        second = layout_score_proportional(score, replace(request, origin=Fraction(1, 32)))
        assert second != first
        assert measure.call_count == initial_work
        clear_layout_cache()
        layout_score_proportional(score, request)
        assert measure.call_count > initial_work


def test_terminal_cluster_cache_does_not_retain_large_input() -> None:
    text = "界" * 1024
    with patch.object(display, "_cached_display_clusters", wraps=display._cached_display_clusters) as cached:
        assert display.display_width(text) == 2 * len(text)
    cached.assert_not_called()
