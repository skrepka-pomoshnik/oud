from __future__ import annotations

from oud.core.model import Bar
from oud.core.render_utils import (
    chord_positions,
    smart_group_map,
    soft_beat_snap_map,
    spread_flag_positions,
    trim_right_slack_for_onsets,
)
from oud.core.view_model import _filter_redundant_positions, _parse_time_signature, _scale_col
from oud.editor.controller_utils import string_index
from oud.editor.layout import (
    auto_system_bar_plan,
    auto_system_bar_plan_with_gaps,
    bars_per_line,
    dynamic_system_starts,
    jump_system_row,
    jump_system_row_dynamic,
    system_range,
)
from oud.editor.state import EditorState


def move_left(state: EditorState) -> None:
    if state.cursor_col > 0:
        state.cursor_col -= 1
    elif state.cursor_bar > 0:
        state.cursor_bar -= 1
        state.cursor_col = state.bar_width - 1


def move_right(state: EditorState) -> None:
    if state.cursor_col < state.bar_width - 1:
        state.cursor_col += 1
    elif state.cursor_bar < len(state.piece.bars) - 1:
        state.cursor_bar += 1
        state.cursor_col = 0
    else:
        state.piece.bars.append(Bar())
        state.cursor_bar += 1
        state.cursor_col = 0
        state.modified = True


def _bar_content_width_for_cursor(state: EditorState, bar_index: int) -> int:
    if bar_index < 0 or bar_index >= len(state.piece.bars):
        return state.bar_width
    spacing_mode = state.settings.get("layout", "packed")
    if spacing_mode != "auto":
        return state.bar_width
    starts = dynamic_system_starts(state, state.screen_width)
    start = max((value for value in starts if value <= bar_index), default=0)
    bar_indices, widths = auto_system_bar_plan(state, start, state.screen_width)
    try:
        idx = bar_indices.index(bar_index)
        display_width = widths[idx]
    except ValueError:
        display_width = state.bar_width
    barpad_text = state.settings.get("barpad", "1")
    barpad = int(barpad_text) if barpad_text.isdigit() else 1
    return max(1, display_width - barpad * 2)


def _chord_positions_distinct_for_nav(
    bar: Bar,
    bar_width: int,
    default_duration: int = 4,
) -> tuple[list[tuple[int, int, bool]], int]:
    if not bar.chords:
        return chord_positions(bar, bar_width, default_duration), bar_width
    width = max(1, bar_width, len(bar.chords))
    max_width = max(width, len(bar.chords) * 2 + 2)
    while width <= max_width:
        positions = chord_positions(bar, width, default_duration)
        cols = [col for col, _denom, _dot in positions]
        if len(cols) == len(set(cols)):
            return positions, width
        width += 1
    return chord_positions(bar, max_width, default_duration), max_width


def _grid_display_map_for_nav(
    *,
    grid_width: int,
    content_width: int,
    src_to_dest: dict[int, int],
) -> list[int]:
    width = max(1, grid_width)
    content = max(1, content_width)
    mapping: list[int] = []
    prev = 0
    for grid_col in range(width):
        dest = src_to_dest.get(grid_col, _scale_col(grid_col, width, content))
        dest = max(0, min(content - 1, dest))
        if grid_col > 0 and dest < prev:
            dest = prev
        if grid_col > 0 and dest > prev + 1:
            dest = prev + 1
        mapping.append(dest)
        prev = dest
    return mapping


def _cursor_display_map_for_bar(
    state: EditorState,
    bar_index: int,
    content_width: int,
) -> list[int]:
    if bar_index < 0 or bar_index >= len(state.piece.bars):
        return [_scale_col(col, state.bar_width, content_width) for col in range(state.bar_width)]
    bar = state.piece.bars[bar_index]
    if not bar.chords:
        return [_scale_col(col, state.bar_width, content_width) for col in range(state.bar_width)]
    positions, grid_width = _chord_positions_distinct_for_nav(bar, state.bar_width, 4)
    beatsnap_mode = state.settings.get("beatsnap", "off")
    time_setting = state.settings.get("time", "C")
    time_value = bar.time_sig or time_setting
    beats, _unit, _label = _parse_time_signature(time_value)
    if beatsnap_mode == "soft" and beats > 1:
        visible_positions = (
            _filter_redundant_positions(positions)
            if state.settings.get("flagredundant", "on") == "on"
            else positions
        )
        src_to_dest = soft_beat_snap_map(
            positions,
            grid_width=grid_width,
            content_width=content_width,
            beats=beats,
            min_gap=1 if state.settings.get("justify", "stretch") == "smart" else 0,
        )
        src_to_dest = trim_right_slack_for_onsets(
            src_to_dest,
            all_positions=positions,
            visible_positions=visible_positions,
            content_width=content_width,
        )
    elif state.settings.get("justify", "stretch") == "smart":
        groups = spread_flag_positions(positions, grid_width, min_gap=0)
        src_to_dest = smart_group_map(positions, groups, content_width)
    else:
        scaled_positions = [
            (_scale_col(pos, grid_width, content_width), denom, dot)
            for (pos, denom, dot) in positions
        ]
        spread_positions = spread_flag_positions(scaled_positions, content_width, min_gap=1)
        ordered_raw = sorted(positions, key=lambda item: item[0])
        src_to_dest = {
            raw_col: scaled_col
            for (raw_col, _raw_denom, _raw_dot), (scaled_col, _denom, _dot) in zip(
                ordered_raw,
                spread_positions,
                strict=False,
            )
        }
    grid_map = _grid_display_map_for_nav(
        grid_width=grid_width,
        content_width=content_width,
        src_to_dest=src_to_dest,
    )
    return [
        grid_map[_scale_col(col, state.bar_width, grid_width)]
        for col in range(state.bar_width)
    ]


def _system_display_indices_for_bar(state: EditorState, bar_index: int) -> list[int]:
    total_strings = state.piece.strings
    base_strings = min(6, total_strings)
    indices = list(range(base_strings))
    if bar_index < 0 or bar_index >= len(state.piece.bars):
        return indices
    if state.settings.get("layout", "packed") == "auto":
        starts = dynamic_system_starts(state, state.screen_width)
        start = 0
        end = len(state.piece.bars)
        for idx, value in enumerate(starts):
            next_value = starts[idx + 1] if idx + 1 < len(starts) else len(state.piece.bars)
            if value <= bar_index < next_value:
                start = value
                end = next_value
                break
    else:
        per_line = bars_per_line(state, state.screen_width)
        start, end = system_range(state, bar_index, per_line)
    used_bass: set[int] = set()
    for bar in state.piece.bars[start:end]:
        for note in bar.notes:
            idx = note.string - 1
            if base_strings <= idx < total_strings:
                used_bass.add(idx)
        for chord in bar.chords:
            for note in chord.notes:
                idx = note.string - 1
                if base_strings <= idx < total_strings:
                    used_bass.add(idx)
    indices.extend(sorted(used_bass))
    return indices


def move_left_visual(state: EditorState) -> None:
    prev_bar = state.cursor_bar
    prev_col = state.cursor_col
    actual_string = string_index(state, state.cursor_string)
    note_stops = set(_row_note_cols(state, prev_bar, actual_string) or _note_cols(state, prev_bar))
    prev_content = _bar_content_width_for_cursor(state, prev_bar)
    prev_map = _cursor_display_map_for_bar(state, prev_bar, prev_content)
    prev_scaled = prev_map[prev_col]
    move_left(state)
    if state.cursor_bar != prev_bar:
        return
    while state.cursor_col > 0:
        if state.cursor_col in note_stops:
            break
        scaled = prev_map[state.cursor_col]
        if scaled != prev_scaled:
            break
        move_left(state)


def move_right_visual(state: EditorState) -> None:
    prev_bar = state.cursor_bar
    prev_col = state.cursor_col
    actual_string = string_index(state, state.cursor_string)
    note_stops = set(_row_note_cols(state, prev_bar, actual_string) or _note_cols(state, prev_bar))
    prev_content = _bar_content_width_for_cursor(state, prev_bar)
    prev_map = _cursor_display_map_for_bar(state, prev_bar, prev_content)
    prev_scaled = prev_map[prev_col]
    move_right(state)
    if state.cursor_bar != prev_bar:
        return
    while state.cursor_col < state.bar_width - 1:
        if state.cursor_col in note_stops:
            break
        scaled = prev_map[state.cursor_col]
        if scaled != prev_scaled:
            break
        move_right(state)


def jump_row_visual(state: EditorState, delta: int) -> None:
    prev_bar = state.cursor_bar
    prev_col = state.cursor_col
    prev_actual_string = string_index(state, state.cursor_string)
    reverse_strings = (
        state.settings.get("viewinvert", "off") == "on"
        or (
            state.settings.get("style") == "italian"
            and state.settings.get("italianorient", "normal") == "reverse"
        )
    )
    prev_display_indices = _system_display_indices_for_bar(state, prev_bar)
    if reverse_strings:
        prev_visual_rows = list(reversed(prev_display_indices))
    else:
        prev_visual_rows = prev_display_indices
    if prev_actual_string in prev_visual_rows:
        prev_visual_row = prev_visual_rows.index(prev_actual_string)
    else:
        prev_visual_row = min(max(0, state.cursor_string), max(0, len(prev_visual_rows) - 1))
    prev_content = _bar_content_width_for_cursor(state, prev_bar)
    prev_map = _cursor_display_map_for_bar(state, prev_bar, prev_content)
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

    state.cursor_bar = target_bar
    target_display_indices = _system_display_indices_for_bar(state, target_bar)
    target_visual_rows = list(reversed(target_display_indices)) if reverse_strings else target_display_indices
    if target_visual_rows:
        chosen_row = min(prev_visual_row, len(target_visual_rows) - 1)
        target_actual_string = target_visual_rows[chosen_row]
        state.cursor_string = chosen_row
    else:
        target_actual_string = prev_actual_string
    target_content = _bar_content_width_for_cursor(state, target_bar)
    target_map = _cursor_display_map_for_bar(state, target_bar, target_content)
    best_col = min(
        range(len(target_map)),
        key=lambda col: (
            abs(target_map[col] - anchor),
            abs(col - prev_col),
            col,
        ),
    )
    state.cursor_col = best_col
    # Clamp actual string onto a visible row if cursor-string and actual-string drifted.
    if target_visual_rows and target_actual_string in target_visual_rows:
        state.cursor_string = target_visual_rows.index(target_actual_string)


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


def _row_note_cols(state: EditorState, bar_index: int, actual_string: int) -> list[int]:
    if bar_index < 0 or bar_index >= len(state.piece.bars):
        return []
    cols: set[int] = set()
    bar = state.piece.bars[bar_index]
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


def move_left_note(state: EditorState) -> None:
    actual_string = string_index(state, state.cursor_string)
    cols = _row_note_cols(state, state.cursor_bar, actual_string) or _note_cols(
        state,
        state.cursor_bar,
    )
    if cols:
        for col in reversed(cols):
            if col < state.cursor_col:
                state.cursor_col = col
                return
        if state.cursor_bar > 0:
            state.cursor_bar -= 1
            prev_cols = _note_cols(state, state.cursor_bar)
            state.cursor_col = prev_cols[-1] if prev_cols else state.bar_width - 1
            return
    move_left(state)


def move_right_note(state: EditorState) -> None:
    actual_string = string_index(state, state.cursor_string)
    cols = _row_note_cols(state, state.cursor_bar, actual_string) or _note_cols(
        state,
        state.cursor_bar,
    )
    if cols:
        for col in cols:
            if col > state.cursor_col:
                state.cursor_col = col
                return
        if state.cursor_bar < len(state.piece.bars) - 1:
            state.cursor_bar += 1
        else:
            state.piece.bars.append(Bar())
            state.cursor_bar += 1
            state.modified = True
        next_cols = _note_cols(state, state.cursor_bar)
        if next_cols:
            state.cursor_col = next_cols[0]
        else:
            state.cursor_col = 0
        return
    move_right(state)
