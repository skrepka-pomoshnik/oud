from __future__ import annotations

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
