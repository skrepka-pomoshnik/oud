from __future__ import annotations

from oud.petrucci.model import Bar
from oud.petrucci.view_model import (
    _bar_compact_width,
    _bar_display_width,
    _bars_fit,
    _next_system_start,
)

_COMPACT_AUTO_FILLS = {"compact", "smart", "stretch", "edge"}


def compact_fill_enabled(spacing_fill: str) -> bool:
    return spacing_fill in _COMPACT_AUTO_FILLS


def short_system_bar_floor(
    *,
    should_justify: bool,
    bar_width: int,
    barpad: int,
    usable_width: int,
) -> int:
    if should_justify:
        return 1
    natural = max(1, bar_width) + (max(0, barpad) * 2) + 2
    return min(max(1, usable_width), natural)


def justified_extra_width(
    *,
    should_justify: bool,
    usable_width: int,
    widths: list[int],
    gaps: list[int],
) -> int:
    if not should_justify:
        return 0
    return max(0, usable_width - _total_width(widths, gaps))


def collision_base_bar_widths(
    *,
    should_justify: bool,
    planned_widths: list[int],
    bars: list[Bar],
    bar_indices: list[int],
    bar_width: int,
    overrides: dict[tuple[int, int, int], str],
    durations: dict[tuple[int, int, int], int],
    default_duration: int,
    dotted: set[tuple[int, int]],
) -> list[int]:
    if not should_justify:
        return planned_widths
    return [
        _bar_compact_width(
            bars[bar_index],
            bar_index,
            bar_width,
            overrides,
            durations,
            default_duration,
            dotted,
        )
        for bar_index in bar_indices
    ]


def _total_width(widths: list[int], gaps: list[int]) -> int:
    return sum(widths) + sum(gaps)


def auto_bar_plan(  # noqa: C901, PLR0912
    *,
    bars: list[Bar],
    bar_start: int,
    usable_width: int,
    bar_width: int,
    overrides: dict[tuple[int, int, int], str],
    durations: dict[tuple[int, int, int], int],
    default_duration: int,
    dotted: set[tuple[int, int]],
    bar_gap: int,
    spacing_fill: str,
    stave_breaks: set[int],
    bars_per_line_limit: int = 0,
    max_chords: int = 0,
    chord_wrap_limit: int = 0,
) -> tuple[list[int], list[int], list[int]]:
    if bar_start < 0 or bar_start >= len(bars):
        return [], [], []
    compact_fill = compact_fill_enabled(spacing_fill)
    width_limited_bars = _bars_fit(
        bars,
        bar_start,
        bar_gap,
        usable_width,
        bar_width,
        overrides,
        durations,
        default_duration,
        dotted,
        max_chords=max_chords,
        compact=compact_fill,
        chord_wrap_limit=chord_wrap_limit,
    )
    bars_per_line = width_limited_bars
    if bars_per_line_limit > 0:
        bars_per_line = min(bars_per_line, bars_per_line_limit)
    bars_per_line = max(1, bars_per_line)
    bar_end = _next_system_start(bars, bar_start, bars_per_line, stave_breaks)
    bar_end = min(len(bars), bar_end)
    bar_indices = list(range(bar_start, bar_end))
    widths: list[int] = []
    for abs_bar in bar_indices:
        width_fn = _bar_compact_width if compact_fill else _bar_display_width
        widths.append(
            width_fn(
                bars[abs_bar],
                abs_bar,
                bar_width,
                overrides,
                durations,
                default_duration,
                dotted,
            ),
        )
    gaps = [bar_gap for _ in range(max(0, len(widths) - 1))]
    while widths and _total_width(widths, gaps) > usable_width:
        widths.pop()
        bar_indices = bar_indices[: len(widths)]
        gaps = [bar_gap for _ in range(max(0, len(widths) - 1))]
    extra = max(0, usable_width - _total_width(widths, gaps))
    ended_at_break = bar_end in stave_breaks or (bar_end > bar_start and bars[bar_end - 1].system_break)
    width_limited_end = min(len(bars), bar_start + width_limited_bars)
    should_justify = (
        len(widths) > 1
        and bar_end < len(bars)
        and bar_end == width_limited_end
        and not ended_at_break
        and chord_wrap_limit <= 0
    )
    if not widths or extra <= 0 or not should_justify:
        return bar_indices, widths, gaps
    if spacing_fill == "stretch":
        # Edge-stretch: keep inter-bar gaps compact and spend extra space
        # inside bars with a left/right emphasis to preserve readable systems.
        left = 0
        right = len(widths) - 1
        while extra > 0 and left <= right:
            widths[left] += 1
            extra -= 1
            if extra <= 0:
                break
            if right != left:
                widths[right] += 1
                extra -= 1
            left += 1
            right -= 1
            if left > right:
                left = 0
                right = len(widths) - 1
        return bar_indices, widths, gaps
    if spacing_fill == "smart":
        idx = 0
        while extra > 0:
            widths[idx] += 1
            extra -= 1
            idx = (idx + 1) % len(widths)
        return bar_indices, widths, gaps
    if spacing_fill == "edge":
        if len(gaps) == 1:
            gaps[0] += extra
        else:
            while extra > 0:
                gaps[0] += 1
                extra -= 1
                if extra <= 0:
                    break
                gaps[-1] += 1
                extra -= 1
        return bar_indices, widths, gaps
    return bar_indices, widths, gaps
