from __future__ import annotations

from oud.core.view_model import (
    _bar_compact_width,
    _bar_display_width,
    _bars_fit,
    _next_system_start,
)
from oud.editor.state import EditorState


def bar_gap(state: EditorState) -> int:
    gap = state.settings.get("bargap", "")
    if gap.isdigit():
        return max(0, int(gap))
    mode = state.settings.get("spacingmode", "packed")
    return 1 if mode in ("packed", "auto") else 3


def bars_per_line(state: EditorState, width: int) -> int:
    fixed = state.settings.get("barsperline", "")
    if fixed.isdigit():
        fixed_value = int(fixed)
        if fixed_value > 0:
            return fixed_value
    left_margin = 3
    max_width = width
    linelen = state.settings.get("linelen", "")
    if linelen.isdigit():
        line_limit = int(linelen)
        if line_limit > 0:
            max_width = min(max_width, line_limit)
    usable_width = max(0, max_width - left_margin)
    per_line = max(1, usable_width // (state.bar_width + bar_gap(state)))
    maxbars = state.settings.get("maxbars", "")
    if maxbars.isdigit():
        limit = int(maxbars)
        if limit > 0:
            per_line = min(per_line, limit)
    return per_line


def _sorted_breaks(state: EditorState, bars: int) -> list[int]:
    breaks = [idx for idx in state.stave_breaks if 0 < idx < bars]
    return sorted(set(breaks))


def system_start_indices(state: EditorState, bars: int, per_line: int) -> list[int]:
    starts = [0]
    breaks = _sorted_breaks(state, bars)
    idx = 0
    while idx < bars:
        next_break = next((b for b in breaks if b > idx), bars)
        limit = min(next_break, idx + per_line)
        if limit >= bars:
            break
        starts.append(limit)
        idx = limit
    return starts


def system_index(state: EditorState, bar_index: int, per_line: int) -> int:
    starts = system_start_indices(state, len(state.piece.bars), per_line)
    for idx, _start in enumerate(starts):
        if idx + 1 < len(starts) and bar_index >= starts[idx + 1]:
            continue
        return idx
    return max(0, len(starts) - 1)


def system_start_index(state: EditorState, system_idx: int, per_line: int) -> int:
    starts = system_start_indices(state, len(state.piece.bars), per_line)
    if system_idx < 0:
        return 0
    if system_idx >= len(starts):
        return starts[-1]
    return starts[system_idx]


def system_range(state: EditorState, bar_index: int, per_line: int) -> tuple[int, int]:
    starts = system_start_indices(state, len(state.piece.bars), per_line)
    for idx, start in enumerate(starts):
        end = starts[idx + 1] if idx + 1 < len(starts) else len(state.piece.bars)
        if start <= bar_index < end:
            return start, end
    return 0, len(state.piece.bars)


def jump_system_row(state: EditorState, bar_index: int, delta: int, per_line: int) -> int:
    starts = system_start_indices(state, len(state.piece.bars), per_line)
    if not starts:
        return 0
    current_idx = 0
    for idx, start in enumerate(starts):
        end = starts[idx + 1] if idx + 1 < len(starts) else len(state.piece.bars)
        if start <= bar_index < end:
            current_idx = idx
            break
    current_start = starts[current_idx]
    offset = max(0, bar_index - current_start)
    target_idx = min(len(starts) - 1, max(0, current_idx + delta))
    target_start = starts[target_idx]
    target_end = starts[target_idx + 1] if target_idx + 1 < len(starts) else len(state.piece.bars)
    return min(target_end - 1, target_start + offset)


def dynamic_system_starts(state: EditorState, width: int) -> list[int]:  # noqa: C901, PLR0912
    bars = state.piece.bars
    total = len(bars)
    if total <= 0:
        return [0]
    left_margin = 3
    max_width = width
    linelen = state.settings.get("linelen", "")
    if linelen.isdigit():
        line_limit = int(linelen)
        if line_limit > 0:
            max_width = min(max_width, line_limit)
    usable_width = max(1, max_width - left_margin)
    spacing_mode = state.settings.get("spacingmode", "packed")
    spacing_fill = state.settings.get("spacingfill", "stretch")
    bargap = state.settings.get("bargap", "")
    if bargap.isdigit():
        bar_gap = max(0, int(bargap))
    else:
        bar_gap = 1 if spacing_mode in ("packed", "auto") else 3
    barsperline = state.settings.get("barsperline", "")
    bars_per_line_limit = 0
    if spacing_mode != "auto":
        bars_per_line_limit = max(1, usable_width // (state.bar_width + bar_gap))
    if barsperline.isdigit():
        limit = int(barsperline)
        if limit > 0:
            bars_per_line_limit = limit
    maxbars = state.settings.get("maxbars", "")
    if maxbars.isdigit():
        limit = int(maxbars)
        if limit > 0:
            bars_per_line_limit = (
                limit
                if bars_per_line_limit <= 0
                else min(bars_per_line_limit, limit)
            )
    max_chords = 0
    max_chords_text = state.settings.get("maxchords", "")
    if max_chords_text.isdigit():
        max_chords = int(max_chords_text)
    chord_wrap_limit = 0
    chord_wrap_text = state.settings.get("chordwrap", "")
    if chord_wrap_text.isdigit():
        chord_wrap_limit = int(chord_wrap_text)

    starts = [0]
    current = 0
    while current < total:
        if spacing_mode == "auto":
            bars_per_line = _bars_fit(
                bars,
                current,
                bar_gap,
                usable_width,
                state.bar_width,
                state.overrides,
                state.durations,
                4,
                state.dotted,
                max_chords=max_chords,
                compact=spacing_fill in ("compact", "smart", "stretch", "edge"),
                chord_wrap_limit=chord_wrap_limit,
            )
        else:
            bars_per_line = bars_per_line_limit
        if bars_per_line_limit > 0:
            bars_per_line = min(bars_per_line, bars_per_line_limit)
        bars_per_line = max(1, bars_per_line)
        next_start = _next_system_start(bars, current, bars_per_line, state.stave_breaks)
        if next_start <= current:
            break
        if next_start < total:
            starts.append(next_start)
        current = next_start
    return starts


def auto_system_bar_plan(  # noqa: C901, PLR0912
    state: EditorState,
    start_bar: int,
    width: int,
) -> tuple[list[int], list[int]]:
    bars = state.piece.bars
    total = len(bars)
    if start_bar < 0 or start_bar >= total:
        return [], []
    left_margin = 3
    max_width = width
    linelen = state.settings.get("linelen", "")
    if linelen.isdigit():
        line_limit = int(linelen)
        if line_limit > 0:
            max_width = min(max_width, line_limit)
    usable_width = max(1, max_width - left_margin)
    spacing_fill = state.settings.get("spacingfill", "stretch")
    compact_fill = spacing_fill in {"compact", "smart", "stretch", "edge"}
    bargap = state.settings.get("bargap", "")
    bar_gap = max(0, int(bargap)) if bargap.isdigit() else 1
    bars_per_line_limit = 0
    barsperline = state.settings.get("barsperline", "")
    if barsperline.isdigit():
        value = int(barsperline)
        if value > 0:
            bars_per_line_limit = value
    maxbars = state.settings.get("maxbars", "")
    if maxbars.isdigit():
        value = int(maxbars)
        if value > 0:
            bars_per_line_limit = (
                value
                if bars_per_line_limit <= 0
                else min(bars_per_line_limit, value)
            )
    max_chords_text = state.settings.get("maxchords", "0")
    max_chords = int(max_chords_text) if max_chords_text.isdigit() else 0
    chord_wrap_text = state.settings.get("chordwrap", "0")
    chord_wrap_limit = int(chord_wrap_text) if chord_wrap_text.isdigit() else 0
    bars_per_line = _bars_fit(
        bars,
        start_bar,
        bar_gap,
        usable_width,
        state.bar_width,
        state.overrides,
        state.durations,
        4,
        state.dotted,
        max_chords=max_chords,
        compact=compact_fill,
        chord_wrap_limit=chord_wrap_limit,
    )
    if bars_per_line_limit > 0:
        bars_per_line = min(bars_per_line, bars_per_line_limit)
    bars_per_line = max(1, bars_per_line)
    bar_end = _next_system_start(bars, start_bar, bars_per_line, state.stave_breaks)
    bar_end = min(total, bar_end)
    bar_indices = list(range(start_bar, bar_end))
    bar_widths: list[int] = []
    for abs_bar in bar_indices:
        if compact_fill:
            width_val = _bar_compact_width(
                bars[abs_bar],
                abs_bar,
                state.bar_width,
                state.overrides,
                state.durations,
                4,
                state.dotted,
            )
        else:
            width_val = _bar_display_width(
                bars[abs_bar],
                abs_bar,
                state.bar_width,
                state.overrides,
                state.durations,
                4,
                state.dotted,
            )
        bar_widths.append(width_val)
    while bar_widths and (sum(bar_widths) + bar_gap * max(0, len(bar_widths) - 1)) > usable_width:
        bar_widths.pop()
        bar_indices = bar_indices[: len(bar_widths)]
    total_width = sum(bar_widths) + bar_gap * max(0, len(bar_widths) - 1)
    if (
        bar_widths
        and len(bar_widths) > 1
        and spacing_fill in {"stretch", "smart"}
        and total_width < usable_width
    ):
        extra = usable_width - total_width
        idx = 0
        while extra > 0 and bar_widths:
            bar_widths[idx] += 1
            extra -= 1
            idx = (idx + 1) % len(bar_widths)
    elif bar_widths and len(bar_widths) == 1 and total_width < usable_width:
        bar_widths[0] += usable_width - total_width
    return bar_indices, bar_widths


def jump_system_row_dynamic(state: EditorState, bar_index: int, delta: int, width: int) -> int:
    starts = dynamic_system_starts(state, width)
    if not starts:
        return 0
    current_idx = 0
    for idx, start in enumerate(starts):
        end = starts[idx + 1] if idx + 1 < len(starts) else len(state.piece.bars)
        if start <= bar_index < end:
            current_idx = idx
            break
    current_start = starts[current_idx]
    offset = max(0, bar_index - current_start)
    target_idx = min(len(starts) - 1, max(0, current_idx + delta))
    target_start = starts[target_idx]
    target_end = starts[target_idx + 1] if target_idx + 1 < len(starts) else len(state.piece.bars)
    return min(target_end - 1, target_start + offset)
