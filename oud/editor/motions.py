from __future__ import annotations

from dataclasses import dataclass

from oud.core.model import Bar
from oud.core.render_utils import chord_positions, spread_flag_positions
from oud.core.tab_policy import rows_reversed, visual_row_indices
from oud.editor.controller_utils import string_index
from oud.editor.layout import (
    auto_system_bar_plan_with_gaps,
    bars_per_line,
    dynamic_system_starts,
    jump_system_row,
    jump_system_row_dynamic,
)
from oud.editor.state import EditorState
from oud.editor.visual_cursor_map import (
    bar_content_width_for_cursor,
    cursor_display_map_for_bar,
    system_display_indices_for_bar,
)


@dataclass(frozen=True)
class CursorMotionTarget:
    bar: int
    col: int
    append_bar: bool = False
    cursor_string: int | None = None


def apply_motion_target(state: EditorState, target: CursorMotionTarget) -> None:
    if target.append_bar:
        state.piece.bars.append(Bar())
        state.modified = True
    state.cursor_bar = target.bar
    state.cursor_col = target.col
    if target.cursor_string is not None:
        state.cursor_string = target.cursor_string


def _bar_has_grid_data(state: EditorState, bar_index: int) -> bool:
    return any(b == bar_index for (b, _s, _c) in state.overrides) or any(
        b == bar_index for (b, _s, _c) in state.durations
    )


def _chord_cols(state: EditorState, bar_index: int) -> list[int]:
    if bar_index < 0 or bar_index >= len(state.piece.bars):
        return []
    bar = state.piece.bars[bar_index]
    if not bar.chords or _bar_has_grid_data(state, bar_index):
        return []
    positions = spread_flag_positions(
        chord_positions(bar, state.bar_width, default_duration=4),
        state.bar_width,
        min_gap=1,
    )
    return sorted({col for col, _denom, _dot in positions})


def _grid_cols(state: EditorState, bar_index: int) -> list[int]:
    cols: set[int] = set()
    for b, _s, col in state.durations:
        if b == bar_index:
            cols.add(col)
    if cols:
        return sorted(cols)
    for (b, _s, col), value in state.overrides.items():
        if b == bar_index and value and value != "-":
            cols.add(col)
    return sorted(cols)


def _note_cols(state: EditorState, bar_index: int) -> list[int]:
    chord_cols = _chord_cols(state, bar_index)
    grid_cols = _grid_cols(state, bar_index)
    if not chord_cols:
        return grid_cols
    if not grid_cols:
        return chord_cols
    return sorted(set(chord_cols) | set(grid_cols))


def _bar_start_col(state: EditorState, bar_index: int) -> int:
    cols = _note_cols(state, bar_index)
    return cols[0] if cols else 0


def _bar_end_col(state: EditorState, bar_index: int) -> int:
    cols = _note_cols(state, bar_index)
    return cols[-1] if cols else max(0, state.bar_width - 1)


def _row_note_cols(state: EditorState, bar_index: int, actual_string: int) -> list[int]:
    if bar_index < 0 or bar_index >= len(state.piece.bars):
        return []
    cols: set[int] = set()
    bar: Bar = state.piece.bars[bar_index]
    for (b, s, col), value in state.overrides.items():
        if b == bar_index and s == actual_string and value and value != "-":
            cols.add(col)
    if bar.chords and not _bar_has_grid_data(state, bar_index):
        positions = spread_flag_positions(
            chord_positions(bar, state.bar_width, default_duration=4),
            state.bar_width,
            min_gap=1,
        )
        for chord, (col, _denom, _dot) in zip(bar.chords, positions, strict=False):
            if any((note.string - 1) == actual_string for note in chord.notes):
                cols.add(col)
    return sorted(cols)


def target_move_left(state: EditorState) -> CursorMotionTarget:
    if state.cursor_col > 0:
        return CursorMotionTarget(state.cursor_bar, state.cursor_col - 1)
    if state.cursor_bar > 0:
        return CursorMotionTarget(state.cursor_bar - 1, state.bar_width - 1)
    return CursorMotionTarget(state.cursor_bar, state.cursor_col)


def target_move_right(state: EditorState) -> CursorMotionTarget:
    if state.cursor_col < state.bar_width - 1:
        return CursorMotionTarget(state.cursor_bar, state.cursor_col + 1)
    if state.cursor_bar < len(state.piece.bars) - 1:
        return CursorMotionTarget(state.cursor_bar + 1, 0)
    return CursorMotionTarget(state.cursor_bar + 1, 0, append_bar=True)


def target_move_left_visual(state: EditorState) -> CursorMotionTarget:
    return _target_move_visual(state, -1)


def target_move_right_visual(state: EditorState) -> CursorMotionTarget:
    return _target_move_visual(state, 1)


def _target_move_visual(state: EditorState, delta: int) -> CursorMotionTarget:
    target = CursorMotionTarget(state.cursor_bar, state.cursor_col)
    if delta not in (-1, 1):
        return target
    bar_index = state.cursor_bar
    if bar_index < 0 or bar_index >= len(state.piece.bars):
        return target
    next_col = state.cursor_col + delta
    if next_col < 0:
        target = target_move_left(state)
    elif next_col >= state.bar_width:
        target = target_move_right(state)
    else:
        content_width = bar_content_width_for_cursor(state, bar_index)
        mapping = cursor_display_map_for_bar(state, bar_index, content_width)
        if not (0 <= state.cursor_col < len(mapping) and 0 <= next_col < len(mapping)):
            target = CursorMotionTarget(bar_index, next_col)
        else:
            current_display_col = mapping[state.cursor_col]
            if mapping[next_col] != current_display_col:
                target = CursorMotionTarget(bar_index, next_col)
            else:
                target = _target_move_visual_collapsed(
                    state,
                    bar_index=bar_index,
                    next_col=next_col,
                    current_display_col=current_display_col,
                    mapping=mapping,
                    delta=delta,
                )
    return target


def _target_wrap_horizontal_visual(state: EditorState, delta: int) -> CursorMotionTarget:
    if delta < 0:
        if state.cursor_bar > 0:
            return CursorMotionTarget(state.cursor_bar - 1, state.bar_width - 1)
        return CursorMotionTarget(state.cursor_bar, 0)
    if state.cursor_bar < len(state.piece.bars) - 1:
        return CursorMotionTarget(state.cursor_bar + 1, 0)
    return CursorMotionTarget(state.cursor_bar + 1, 0, append_bar=True)


def _target_move_visual_collapsed(
    state: EditorState,
    *,
    bar_index: int,
    next_col: int,
    current_display_col: int,
    mapping: list[int],
    delta: int,
) -> CursorMotionTarget:
    actual_string = string_index(state, state.cursor_string)
    note_cols = set(_row_note_cols(state, bar_index, actual_string)) or set(
        _note_cols(state, bar_index),
    )
    if not note_cols:
        return CursorMotionTarget(bar_index, next_col)
    scan = next_col
    while 0 <= scan < len(mapping) and mapping[scan] == current_display_col:
        if scan in note_cols:
            return CursorMotionTarget(bar_index, scan)
        scan += delta
    if 0 <= scan < state.bar_width:
        return CursorMotionTarget(bar_index, scan)
    return _target_wrap_horizontal_visual(state, delta)


def target_move_left_note(state: EditorState) -> CursorMotionTarget:
    actual_string = string_index(state, state.cursor_string)
    cols = _row_note_cols(state, state.cursor_bar, actual_string) or _note_cols(
        state,
        state.cursor_bar,
    )
    if cols:
        for col in reversed(cols):
            if col < state.cursor_col:
                return CursorMotionTarget(state.cursor_bar, col)
        if state.cursor_bar > 0:
            prev_bar = state.cursor_bar - 1
            prev_cols = _note_cols(state, prev_bar)
            return CursorMotionTarget(
                prev_bar,
                prev_cols[-1] if prev_cols else state.bar_width - 1,
            )
    return target_move_left(state)


def target_move_right_note(state: EditorState) -> CursorMotionTarget:
    actual_string = string_index(state, state.cursor_string)
    cols = _row_note_cols(state, state.cursor_bar, actual_string) or _note_cols(
        state,
        state.cursor_bar,
    )
    if cols:
        for col in cols:
            if col > state.cursor_col:
                return CursorMotionTarget(state.cursor_bar, col)
        next_bar = state.cursor_bar + 1
        if state.cursor_bar >= len(state.piece.bars) - 1:
            return CursorMotionTarget(next_bar, 0, append_bar=True)
        next_cols = _note_cols(state, next_bar)
        return CursorMotionTarget(next_bar, next_cols[0] if next_cols else 0)
    return target_move_right(state)


def target_bar_next(state: EditorState, count: int = 1) -> CursorMotionTarget:
    if not state.piece.bars:
        return CursorMotionTarget(0, 0)
    target_bar = min(len(state.piece.bars) - 1, state.cursor_bar + max(1, count))
    return CursorMotionTarget(target_bar, _bar_start_col(state, target_bar))


def target_bar_prev(state: EditorState, count: int = 1) -> CursorMotionTarget:
    if not state.piece.bars:
        return CursorMotionTarget(0, 0)
    target_bar = max(0, state.cursor_bar - max(1, count))
    return CursorMotionTarget(target_bar, _bar_start_col(state, target_bar))


def target_bar_start(state: EditorState) -> CursorMotionTarget:
    return CursorMotionTarget(state.cursor_bar, _bar_start_col(state, state.cursor_bar))


def target_bar_end(state: EditorState) -> CursorMotionTarget:
    return CursorMotionTarget(state.cursor_bar, _bar_end_col(state, state.cursor_bar))


def target_jump_first_bar(state: EditorState) -> CursorMotionTarget:
    if not state.piece.bars:
        return CursorMotionTarget(0, 0)
    return CursorMotionTarget(0, _bar_start_col(state, 0))


def target_jump_last_bar(state: EditorState) -> CursorMotionTarget:
    if not state.piece.bars:
        return CursorMotionTarget(0, 0)
    target_bar = max(0, len(state.piece.bars) - 1)
    return CursorMotionTarget(target_bar, _bar_start_col(state, target_bar))


def target_home_bar(state: EditorState, bar_index: int) -> CursorMotionTarget:
    if not state.piece.bars:
        return CursorMotionTarget(0, 0)
    target_bar = max(0, min(bar_index, len(state.piece.bars) - 1))
    return CursorMotionTarget(target_bar, 0)


def target_step_display_row(state: EditorState, delta: int) -> CursorMotionTarget:
    return CursorMotionTarget(
        state.cursor_bar,
        state.cursor_col,
        cursor_string=state.cursor_string + delta,
    )


def target_snap_previous_time_slot_if_needed(state: EditorState) -> CursorMotionTarget:
    bar = state.cursor_bar
    col = state.cursor_col
    string = string_index(state, state.cursor_string)
    if col <= 0:
        return CursorMotionTarget(bar, col)
    if any(
        (bar, s_idx, col) in state.overrides or (bar, s_idx, col) in state.durations
        for s_idx in range(state.piece.strings)
    ):
        return CursorMotionTarget(bar, col)
    if not any(
        (bar, s_idx, col - 1) in state.overrides or (bar, s_idx, col - 1) in state.durations
        for s_idx in range(state.piece.strings)
    ):
        return CursorMotionTarget(bar, col)
    if (bar, string, col - 1) in state.overrides or (bar, string, col - 1) in state.durations:
        return CursorMotionTarget(bar, col)
    return CursorMotionTarget(bar, col - 1)


def target_snap_to_chord_slot(state: EditorState) -> CursorMotionTarget:
    bar_index = state.cursor_bar
    if bar_index < 0 or bar_index >= len(state.piece.bars):
        return CursorMotionTarget(state.cursor_bar, state.cursor_col)
    bar = state.piece.bars[bar_index]
    if not bar.chords:
        return CursorMotionTarget(state.cursor_bar, state.cursor_col)
    has_grid = any(b == bar_index for (b, _s, _c) in state.overrides) or any(
        b == bar_index for (b, _s, _c) in state.durations
    )
    if has_grid:
        return CursorMotionTarget(state.cursor_bar, state.cursor_col)
    slots = [
        col
        for (col, _denom, _dot) in spread_flag_positions(
            chord_positions(bar, state.bar_width, default_duration=4),
            state.bar_width,
            min_gap=1,
        )
    ]
    if not slots or state.cursor_col in slots:
        return CursorMotionTarget(state.cursor_bar, state.cursor_col)
    cur = state.cursor_col
    best = min(
        slots,
        key=lambda c: (abs(c - cur), 0 if c <= cur else 1, -c),
    )
    return CursorMotionTarget(state.cursor_bar, best)


def target_advance_next_bar_home(state: EditorState) -> CursorMotionTarget:
    if state.cursor_bar >= len(state.piece.bars) - 1:
        return CursorMotionTarget(state.cursor_bar + 1, 0, append_bar=True)
    return CursorMotionTarget(min(state.cursor_bar + 1, len(state.piece.bars) - 1), 0)


def target_jump_row_visual(state: EditorState, delta: int) -> CursorMotionTarget:  # noqa: C901, PLR0912
    prev_bar = state.cursor_bar
    prev_col = state.cursor_col
    prev_actual_string = string_index(state, state.cursor_string)
    reverse_strings = rows_reversed(
        style=state.settings.get("style", "french"),
        italian_orient=state.settings.get("italianorient", "normal"),
        viewinvert=state.settings.get("viewinvert", "off"),
    )
    prev_display_indices = system_display_indices_for_bar(state, prev_bar)
    prev_visual_rows = visual_row_indices(prev_display_indices, reverse=reverse_strings)
    if prev_actual_string in prev_visual_rows:
        prev_visual_row = prev_visual_rows.index(prev_actual_string)
    else:
        prev_visual_row = min(max(0, state.cursor_string), max(0, len(prev_visual_rows) - 1))
    prev_content = bar_content_width_for_cursor(state, prev_bar)
    prev_map = cursor_display_map_for_bar(state, prev_bar, prev_content)
    anchor = prev_map[prev_col]
    barpad_text = state.settings.get("barpad", "1")
    barpad = int(barpad_text) if barpad_text.isdigit() else 1

    if state.settings.get("layout", "packed") == "auto":
        starts = dynamic_system_starts(state, state.screen_width)
        current_idx = 0
        for idx, start in enumerate(starts):
            end = starts[idx + 1] if idx + 1 < len(starts) else len(state.piece.bars)
            if start <= prev_bar < end:
                current_idx = idx
                break
        target_idx = min(len(starts) - 1, max(0, current_idx + delta))
        if target_idx == current_idx:
            target_bar = prev_bar
        else:
            current_start = starts[current_idx]
            target_start = starts[target_idx]
            current_indices, current_widths, current_gaps = auto_system_bar_plan_with_gaps(
                state,
                current_start,
                state.screen_width,
            )
            target_indices, target_widths, target_gaps = auto_system_bar_plan_with_gaps(
                state,
                target_start,
                state.screen_width,
            )

            def _spans(
                indices: list[int],
                widths: list[int],
                gaps: list[int],
            ) -> list[tuple[int, int, int]]:
                x = 0
                spans: list[tuple[int, int, int]] = []
                for idx2, abs_bar in enumerate(indices):
                    w = max(1, widths[idx2])
                    spans.append((abs_bar, x, x + w))
                    x += w + (gaps[idx2] if idx2 < len(gaps) else 0)
                return spans

            current_spans = _spans(current_indices, current_widths, current_gaps)
            target_spans = _spans(target_indices, target_widths, target_gaps)
            current_span = next((span for span in current_spans if span[0] == prev_bar), None)
            if current_span is None or not target_spans:
                target_bar = jump_system_row_dynamic(
                    state,
                    prev_bar,
                    delta,
                    state.screen_width,
                )
            else:
                _bar_abs, x0, x1 = current_span
                local_x = min(max(0, barpad + anchor), max(0, x1 - x0 - 1))
                anchor_x = x0 + local_x
                containing = next(
                    (abs_bar for (abs_bar, t0, t1) in target_spans if t0 <= anchor_x < t1),
                    None,
                )
                if containing is not None:
                    target_bar = containing
                else:
                    target_bar = min(
                        target_spans,
                        key=lambda span: abs(((span[1] + span[2]) // 2) - anchor_x),
                    )[0]
    else:
        per_line = bars_per_line(state, state.screen_width)
        target_bar = jump_system_row(state, prev_bar, delta, per_line)

    target_display_indices = system_display_indices_for_bar(state, target_bar)
    target_visual_rows = visual_row_indices(target_display_indices, reverse=reverse_strings)
    if target_visual_rows:
        chosen_row = min(prev_visual_row, len(target_visual_rows) - 1)
        target_actual_string = target_visual_rows[chosen_row]
        target_cursor_string = chosen_row
    else:
        target_actual_string = prev_actual_string
        target_cursor_string = state.cursor_string
    target_content = bar_content_width_for_cursor(state, target_bar)
    target_map = cursor_display_map_for_bar(state, target_bar, target_content)
    best_col = min(
        range(len(target_map)),
        key=lambda col: (
            abs(target_map[col] - anchor),
            abs(col - prev_col),
            col,
        ),
    )
    if target_visual_rows and target_actual_string in target_visual_rows:
        target_cursor_string = target_visual_rows.index(target_actual_string)
    return CursorMotionTarget(
        target_bar,
        best_col,
        False,
        cursor_string=target_cursor_string,
    )
