from __future__ import annotations

from oud.core.model import Bar, Note
from oud.core.spacing import auto_bar_plan


def _bars(count: int) -> list[Bar]:
    return [Bar(notes=[Note(1, 0, 0)]) for _ in range(count)]


def _total(widths: list[int], gaps: list[int]) -> int:
    return sum(widths) + sum(gaps)


def test_auto_bar_plan_stretch_fills_usable_width() -> None:
    bars = _bars(8)
    indices, widths, gaps = auto_bar_plan(
        bars=bars,
        bar_start=0,
        usable_width=60,
        bar_width=8,
        overrides={},
        durations={},
        default_duration=4,
        dotted=set(),
        bar_gap=1,
        spacing_fill="stretch",
        stave_breaks=set(),
    )
    assert indices
    assert len(indices) == len(widths)
    assert len(gaps) == max(0, len(widths) - 1)
    assert all(width > 0 for width in widths)
    assert _total(widths, gaps) == 60
    # stretch: keep compact inter-bar gaps and expand bar content widths.
    assert all(gap == 1 for gap in gaps)
    assert max(widths) > min(widths)


def test_auto_bar_plan_smart_expands_bar_content_width() -> None:
    bars = _bars(8)
    indices, widths, gaps = auto_bar_plan(
        bars=bars,
        bar_start=0,
        usable_width=60,
        bar_width=8,
        overrides={},
        durations={},
        default_duration=4,
        dotted=set(),
        bar_gap=1,
        spacing_fill="smart",
        stave_breaks=set(),
    )
    assert indices
    assert _total(widths, gaps) == 60
    # smart: distribute extra space into bar content widths
    assert max(widths) > min(widths)


def test_auto_bar_plan_edge_fills_usable_width_with_gaps() -> None:
    bars = _bars(8)
    indices, widths, gaps = auto_bar_plan(
        bars=bars,
        bar_start=0,
        usable_width=64,
        bar_width=8,
        overrides={},
        durations={},
        default_duration=4,
        dotted=set(),
        bar_gap=1,
        spacing_fill="edge",
        stave_breaks=set(),
    )
    assert indices
    assert all(width > 0 for width in widths)
    assert _total(widths, gaps) == 64


def test_auto_bar_plan_compact_never_exceeds_width() -> None:
    bars = _bars(8)
    indices, widths, gaps = auto_bar_plan(
        bars=bars,
        bar_start=0,
        usable_width=32,
        bar_width=8,
        overrides={},
        durations={},
        default_duration=4,
        dotted=set(),
        bar_gap=1,
        spacing_fill="compact",
        stave_breaks=set(),
    )
    assert indices
    assert _total(widths, gaps) <= 32


def test_auto_bar_plan_does_not_stretch_single_bar_system_to_full_width() -> None:
    bars = _bars(1)
    indices, widths, gaps = auto_bar_plan(
        bars=bars,
        bar_start=0,
        usable_width=60,
        bar_width=8,
        overrides={},
        durations={},
        default_duration=4,
        dotted=set(),
        bar_gap=1,
        spacing_fill="stretch",
        stave_breaks=set(),
    )
    assert indices == [0]
    assert gaps == []
    assert widths == [4]
