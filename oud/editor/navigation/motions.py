"""Cursor motions over stops: event onsets and each bar's append slot.

Every target names a bar and an exact onset. Horizontal motions step one stop at a
time, so every press moves to the next event however densely the bar is drawn.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from oud.editor.core.coordinates import bar_stops, stop_at_column, stop_column, string_index
from oud.editor.core.state import EditorState
from oud.editor.navigation.cursor_map import (
    bar_content_width_for_cursor,
    cursor_display_map_for_bar,
    system_display_indices_for_bar,
)
from oud.editor.navigation.layout import (
    auto_system_bar_plan_with_gaps,
    bars_per_line,
    dynamic_system_starts,
    jump_system_row,
    jump_system_row_dynamic,
)
from petrucci.core.model import Bar
from petrucci.input.tablature.mutation import event_onsets
from petrucci.input.tablature.policy import rows_reversed, visual_row_indices

START = Fraction(0)


@dataclass(frozen=True)
class CursorMotionTarget:
    bar: int
    onset: Fraction
    append_bar: bool = False
    cursor_string: int | None = None


def target_at_column(state: EditorState, bar_index: int, column: int) -> CursorMotionTarget:
    """The stop drawn at or before a display-grid column of ``bar_index``."""

    return CursorMotionTarget(bar_index, stop_at_column(state, bar_index, column))


def apply_motion_target(state: EditorState, target: CursorMotionTarget) -> None:
    if target.append_bar:
        if state.read_only:
            return
        state.piece.bars.append(Bar())
        state.modified = True
    state.cursor_bar = target.bar
    state.cursor_onset = target.onset
    if target.cursor_string is not None:
        state.cursor_string = target.cursor_string


def _stop_index(stops: tuple[Fraction, ...], onset: Fraction) -> int:
    earlier = [index for index, stop in enumerate(stops) if stop <= onset]
    return earlier[-1] if earlier else 0


def _stay(state: EditorState) -> CursorMotionTarget:
    return CursorMotionTarget(state.cursor_bar, state.cursor_onset)


def _first_stop(state: EditorState, bar_index: int) -> Fraction:
    return bar_stops(state, bar_index)[0]


def _last_stop(state: EditorState, bar_index: int) -> Fraction:
    return bar_stops(state, bar_index)[-1]


def _next_bar_start(state: EditorState) -> CursorMotionTarget:
    if state.cursor_bar < len(state.piece.bars) - 1:
        return CursorMotionTarget(state.cursor_bar + 1, _first_stop(state, state.cursor_bar + 1))
    if state.read_only:
        return _stay(state)
    return CursorMotionTarget(state.cursor_bar + 1, START, append_bar=True)


def target_move_left(state: EditorState) -> CursorMotionTarget:
    stops = bar_stops(state, state.cursor_bar)
    index = _stop_index(stops, state.cursor_onset)
    if index > 0:
        return CursorMotionTarget(state.cursor_bar, stops[index - 1])
    if state.cursor_bar > 0:
        return CursorMotionTarget(state.cursor_bar - 1, _last_stop(state, state.cursor_bar - 1))
    return CursorMotionTarget(state.cursor_bar, stops[0])


def target_move_right(state: EditorState) -> CursorMotionTarget:
    stops = bar_stops(state, state.cursor_bar)
    index = _stop_index(stops, state.cursor_onset)
    if index < len(stops) - 1:
        return CursorMotionTarget(state.cursor_bar, stops[index + 1])
    return _next_bar_start(state)


def target_move_left_visual(state: EditorState) -> CursorMotionTarget:
    return target_move_left(state)


def target_move_right_visual(state: EditorState) -> CursorMotionTarget:
    return target_move_right(state)


def apply_counted_visual_motion(state: EditorState, delta: int, count: int) -> None:
    for _ in range(count):
        before = (state.cursor_bar, state.cursor_onset, len(state.piece.bars))
        target = target_move_right(state) if delta > 0 else target_move_left(state)
        apply_motion_target(state, target)
        if target.append_bar or (state.cursor_bar, state.cursor_onset, len(state.piece.bars)) == before:
            break


def _course_onsets(state: EditorState, bar_index: int, course_index: int) -> list[Fraction]:
    """Onsets of events with a note on ``course_index``, else of every event."""

    if not 0 <= bar_index < len(state.piece.bars):
        return []
    bar = state.piece.bars[bar_index]
    onsets = event_onsets(bar)
    on_course = [
        onset
        for onset, chord in zip(onsets, bar.chords, strict=True)
        if any(note.string - 1 == course_index for note in chord.notes)
    ]
    return on_course or list(onsets)


def target_move_left_note(state: EditorState) -> CursorMotionTarget:
    course = string_index(state, state.cursor_string)
    earlier = [onset for onset in _course_onsets(state, state.cursor_bar, course) if onset < state.cursor_onset]
    if earlier:
        return CursorMotionTarget(state.cursor_bar, earlier[-1])
    if state.cursor_bar > 0:
        previous = _course_onsets(state, state.cursor_bar - 1, course)
        onset = previous[-1] if previous else _last_stop(state, state.cursor_bar - 1)
        return CursorMotionTarget(state.cursor_bar - 1, onset)
    return target_move_left(state)


def target_move_right_note(state: EditorState) -> CursorMotionTarget:
    course = string_index(state, state.cursor_string)
    later = [onset for onset in _course_onsets(state, state.cursor_bar, course) if onset > state.cursor_onset]
    if later:
        return CursorMotionTarget(state.cursor_bar, later[0])
    if state.cursor_bar >= len(state.piece.bars) - 1:
        return _next_bar_start(state)
    following = _course_onsets(state, state.cursor_bar + 1, course)
    return CursorMotionTarget(state.cursor_bar + 1, following[0] if following else START)


def target_bar_next(state: EditorState, count: int = 1) -> CursorMotionTarget:
    if not state.piece.bars:
        return CursorMotionTarget(0, START)
    target_bar = min(len(state.piece.bars) - 1, state.cursor_bar + max(1, count))
    return CursorMotionTarget(target_bar, _first_stop(state, target_bar))


def target_bar_prev(state: EditorState, count: int = 1) -> CursorMotionTarget:
    if not state.piece.bars:
        return CursorMotionTarget(0, START)
    target_bar = max(0, state.cursor_bar - max(1, count))
    return CursorMotionTarget(target_bar, _first_stop(state, target_bar))


def target_bar_start(state: EditorState) -> CursorMotionTarget:
    return CursorMotionTarget(state.cursor_bar, _first_stop(state, state.cursor_bar))


def target_bar_end(state: EditorState) -> CursorMotionTarget:
    """The last event of the bar, or the only stop of an empty bar."""

    if not 0 <= state.cursor_bar < len(state.piece.bars):
        return _stay(state)
    onsets = event_onsets(state.piece.bars[state.cursor_bar])
    return CursorMotionTarget(state.cursor_bar, onsets[-1] if onsets else START)


def target_jump_first_bar(state: EditorState) -> CursorMotionTarget:
    return CursorMotionTarget(0, _first_stop(state, 0))


def target_jump_last_bar(state: EditorState) -> CursorMotionTarget:
    target_bar = max(0, len(state.piece.bars) - 1)
    return CursorMotionTarget(target_bar, _first_stop(state, target_bar))


def target_home_bar(state: EditorState, bar_index: int) -> CursorMotionTarget:
    if not state.piece.bars:
        return CursorMotionTarget(0, START)
    return CursorMotionTarget(max(0, min(bar_index, len(state.piece.bars) - 1)), START)


def target_step_display_row(state: EditorState, delta: int) -> CursorMotionTarget:
    return CursorMotionTarget(state.cursor_bar, state.cursor_onset, cursor_string=state.cursor_string + delta)


def target_advance_next_bar_home(state: EditorState) -> CursorMotionTarget:
    if state.cursor_bar >= len(state.piece.bars) - 1:
        return CursorMotionTarget(state.cursor_bar + 1, START, append_bar=True)
    return CursorMotionTarget(state.cursor_bar + 1, START)


def _visual_row_position(actual_string: int, visual_rows: list[int], fallback: int) -> int:
    if actual_string in visual_rows:
        return visual_rows.index(actual_string)
    return min(max(0, fallback), max(0, len(visual_rows) - 1))


def _visual_system_spans(
    indices: list[int],
    widths: list[int],
    gaps: list[int],
) -> list[tuple[int, int, int]]:
    x = 0
    spans: list[tuple[int, int, int]] = []
    for idx, abs_bar in enumerate(indices):
        width = max(1, widths[idx])
        spans.append((abs_bar, x, x + width))
        x += width + (gaps[idx] if idx < len(gaps) else 0)
    return spans


def _visual_system_index(starts: list[int], bar: int, total: int) -> int:
    return next(
        (
            idx
            for idx, start in enumerate(starts)
            if start <= bar < (starts[idx + 1] if idx + 1 < len(starts) else total)
        ),
        0,
    )


def _auto_visual_target_bar(state: EditorState, bar: int, delta: int, anchor: int, barpad: int) -> int:
    starts = dynamic_system_starts(state, state.screen_width)
    if not starts:
        return bar
    current_idx = _visual_system_index(starts, bar, len(state.piece.bars))
    target_idx = min(len(starts) - 1, max(0, current_idx + delta))
    if target_idx == current_idx:
        return bar
    current_indices, current_widths, current_gaps = auto_system_bar_plan_with_gaps(
        state,
        starts[current_idx],
        state.screen_width,
    )
    target_indices, target_widths, target_gaps = auto_system_bar_plan_with_gaps(
        state,
        starts[target_idx],
        state.screen_width,
    )
    current_spans = _visual_system_spans(current_indices, current_widths, current_gaps)
    target_spans = _visual_system_spans(target_indices, target_widths, target_gaps)
    current_span = next((span for span in current_spans if span[0] == bar), None)
    if current_span is None or not target_spans:
        return jump_system_row_dynamic(state, bar, delta, state.screen_width)
    _bar_abs, x0, x1 = current_span
    local_x = min(max(0, barpad + anchor), max(0, x1 - x0 - 1))
    anchor_x = x0 + local_x
    containing = next(
        (abs_bar for abs_bar, start, end in target_spans if start <= anchor_x < end),
        None,
    )
    if containing is not None:
        return containing
    return min(target_spans, key=lambda span: abs(((span[1] + span[2]) // 2) - anchor_x))[0]


def _display_column(state: EditorState, bar_index: int, onset: Fraction) -> int:
    content = bar_content_width_for_cursor(state, bar_index)
    mapping = cursor_display_map_for_bar(state, bar_index, content)
    column = stop_column(state, bar_index, onset)
    return mapping[column] if 0 <= column < len(mapping) else column


def _nearest_drawn_stop(state: EditorState, bar_index: int, anchor: int) -> Fraction:
    stops = bar_stops(state, bar_index)
    return min(stops, key=lambda stop: (abs(_display_column(state, bar_index, stop) - anchor), stop))


def target_jump_row_visual(state: EditorState, delta: int) -> CursorMotionTarget:
    """Move to the system above or below, landing on the stop drawn nearest the cursor."""

    prev_bar = state.cursor_bar
    prev_actual_string = string_index(state, state.cursor_string)
    reverse_strings = rows_reversed(
        style=state.settings.get("style", "french"),
        italian_orient=state.settings.get("italianorient", "normal"),
        viewinvert=state.settings.get("viewinvert", "off"),
    )
    prev_visual_rows = visual_row_indices(system_display_indices_for_bar(state, prev_bar), reverse=reverse_strings)
    prev_visual_row = _visual_row_position(prev_actual_string, prev_visual_rows, state.cursor_string)
    anchor = _display_column(state, prev_bar, state.cursor_onset)
    barpad_text = state.settings.get("barpad", "1")
    barpad = int(barpad_text) if barpad_text.isdigit() else 1

    if state.settings.get("layout", "packed") == "auto":
        target_bar = _auto_visual_target_bar(state, prev_bar, delta, anchor, barpad)
    else:
        target_bar = jump_system_row(state, prev_bar, delta, bars_per_line(state, state.screen_width))

    target_visual_rows = visual_row_indices(system_display_indices_for_bar(state, target_bar), reverse=reverse_strings)
    target_cursor_string = state.cursor_string
    if target_visual_rows:
        target_cursor_string = min(prev_visual_row, len(target_visual_rows) - 1)
    return CursorMotionTarget(
        target_bar,
        _nearest_drawn_stop(state, target_bar, anchor),
        cursor_string=target_cursor_string,
    )
