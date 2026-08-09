from __future__ import annotations

from petrucci.core.model import Bar, Note
from petrucci.engraving.layout.spacing import auto_bar_plan, collision_base_bar_widths


def _bars(count: int) -> list[Bar]:
    return [Bar(notes=[Note(1, 0, 0)]) for _ in range(count)]


def _total(widths: list[int], gaps: list[int]) -> int:
    return sum(widths) + sum(gaps)


def test_auto_bar_plan_stretch_fills_usable_width() -> None:
    bars = _bars(20)
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
    bars = _bars(20)
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
    bars = _bars(20)
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


def test_auto_bar_plan_keeps_sparse_final_system_at_natural_width() -> None:
    indices, widths, gaps = auto_bar_plan(
        bars=_bars(2),
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

    assert indices == [0, 1]
    assert widths == [4, 4]
    assert gaps == [1]


def test_auto_bar_plan_keeps_manual_short_system_at_natural_width() -> None:
    indices, widths, gaps = auto_bar_plan(
        bars=_bars(20),
        bar_start=0,
        usable_width=60,
        bar_width=8,
        overrides={},
        durations={},
        default_duration=4,
        dotted=set(),
        bar_gap=1,
        spacing_fill="smart",
        stave_breaks={2},
    )

    assert indices == [0, 1]
    assert widths == [4, 4]
    assert gaps == [1]


def test_collision_pass_discards_preexpanded_widths_before_justifying() -> None:
    bars = _bars(2)
    widths = collision_base_bar_widths(
        should_justify=True,
        planned_widths=[30, 29],
        bars=bars,
        bar_indices=[0, 1],
        bar_width=8,
        overrides={},
        durations={},
        default_duration=4,
        dotted=set(),
    )
    assert widths == [4, 4]
