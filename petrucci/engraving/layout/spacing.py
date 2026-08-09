from __future__ import annotations

from dataclasses import dataclass

from petrucci.core.model import Bar
from petrucci.terminal.view.model import (
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


@dataclass(frozen=True)
class _AutoBarRequest:
    bars: list[Bar]
    bar_start: int
    usable_width: int
    bar_width: int
    overrides: dict[tuple[int, int, int], str]
    durations: dict[tuple[int, int, int], int]
    default_duration: int
    dotted: set[tuple[int, int]]
    bar_gap: int
    spacing_fill: str
    stave_breaks: set[int]
    bars_per_line_limit: int
    max_chords: int
    chord_wrap_limit: int


def _selected_bar_indices(request: _AutoBarRequest) -> tuple[list[int], int, int]:
    if request.bar_start < 0 or request.bar_start >= len(request.bars):
        return [], 0, 0
    compact = compact_fill_enabled(request.spacing_fill)
    width_limited = _bars_fit(
        request.bars,
        request.bar_start,
        request.bar_gap,
        request.usable_width,
        request.bar_width,
        request.overrides,
        request.durations,
        request.default_duration,
        request.dotted,
        max_chords=request.max_chords,
        compact=compact,
        chord_wrap_limit=request.chord_wrap_limit,
    )
    per_line = width_limited
    if request.bars_per_line_limit > 0:
        per_line = min(per_line, request.bars_per_line_limit)
    end = _next_system_start(
        request.bars,
        request.bar_start,
        max(1, per_line),
        request.stave_breaks,
    )
    end = min(len(request.bars), end)
    return list(range(request.bar_start, end)), end, width_limited


def _measured_widths(request: _AutoBarRequest, indices: list[int]) -> list[int]:
    width_fn = _bar_compact_width if compact_fill_enabled(request.spacing_fill) else _bar_display_width
    return [
        width_fn(
            request.bars[index],
            index,
            request.bar_width,
            request.overrides,
            request.durations,
            request.default_duration,
            request.dotted,
        )
        for index in indices
    ]


def _trim_to_width(
    indices: list[int],
    widths: list[int],
    usable_width: int,
    bar_gap: int,
) -> tuple[list[int], list[int], list[int]]:
    gaps = [bar_gap for _ in range(max(0, len(widths) - 1))]
    while widths and _total_width(widths, gaps) > usable_width:
        widths.pop()
        indices = indices[: len(widths)]
        gaps = [bar_gap for _ in range(max(0, len(widths) - 1))]
    return indices, widths, gaps


def _stretch_widths(widths: list[int], extra: int) -> None:
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


def _smart_widths(widths: list[int], extra: int) -> None:
    index = 0
    while extra > 0:
        widths[index] += 1
        extra -= 1
        index = (index + 1) % len(widths)


def _edge_gaps(gaps: list[int], extra: int) -> None:
    if len(gaps) == 1:
        gaps[0] += extra
        return
    while extra > 0:
        gaps[0] += 1
        extra -= 1
        if extra > 0:
            gaps[-1] += 1
            extra -= 1


def _distribute_extra(spacing_fill: str, widths: list[int], gaps: list[int], extra: int) -> None:
    if spacing_fill == "stretch":
        _stretch_widths(widths, extra)
    elif spacing_fill == "smart":
        _smart_widths(widths, extra)
    elif spacing_fill == "edge":
        _edge_gaps(gaps, extra)


def _should_justify(
    request: _AutoBarRequest,
    widths: list[int],
    bar_end: int,
    width_limited: int,
) -> bool:
    ended_at_break = bar_end in request.stave_breaks or (
        bar_end > request.bar_start and request.bars[bar_end - 1].system_break
    )
    width_limited_end = min(len(request.bars), request.bar_start + width_limited)
    return (
        len(widths) > 1
        and bar_end < len(request.bars)
        and bar_end == width_limited_end
        and not ended_at_break
        and request.chord_wrap_limit <= 0
    )


def auto_bar_plan(
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
    request = _AutoBarRequest(
        bars,
        bar_start,
        usable_width,
        bar_width,
        overrides,
        durations,
        default_duration,
        dotted,
        bar_gap,
        spacing_fill,
        stave_breaks,
        bars_per_line_limit,
        max_chords,
        chord_wrap_limit,
    )
    indices, bar_end, width_limited = _selected_bar_indices(request)
    widths = _measured_widths(request, indices)
    indices, widths, gaps = _trim_to_width(indices, widths, usable_width, bar_gap)
    extra = max(0, usable_width - _total_width(widths, gaps))
    if widths and extra > 0 and _should_justify(request, widths, bar_end, width_limited):
        _distribute_extra(spacing_fill, widths, gaps, extra)
    return indices, widths, gaps
