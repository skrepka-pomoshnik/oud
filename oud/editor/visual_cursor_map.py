from __future__ import annotations

from oud.editor.layout import (
    auto_system_bar_plan,
    bars_per_line,
    dynamic_system_starts,
    system_range,
)
from oud.editor.state import EditorState
from oud.petrucci.model import Bar
from oud.petrucci.render_utils import (
    chord_positions,
    smart_group_map,
    soft_beat_snap_map,
    spread_flag_positions,
    trim_right_slack_for_onsets,
)
from oud.petrucci.tab_policy import (
    bar_has_multifret_tokens,
    multifret_event_gap,
    system_display_indices_for_bars,
)
from oud.petrucci.view_model import _filter_redundant_positions, _parse_time_signature, _scale_col


def bar_content_width_for_cursor(state: EditorState, bar_index: int) -> int:
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


def cursor_display_map_for_bar(
    state: EditorState,
    bar_index: int,
    content_width: int,
) -> list[int]:
    # Prefer the map the renderer published for the last drawn frame; it is the
    # exact logical-col -> display-col mapping the user sees on screen.
    rendered = getattr(state, "display_cursor_maps", {}).get(bar_index)
    if rendered and len(rendered) == state.bar_width:
        return rendered
    if bar_index < 0 or bar_index >= len(state.piece.bars):
        return [_scale_col(col, state.bar_width, content_width) for col in range(state.bar_width)]
    bar = state.piece.bars[bar_index]
    if not bar.chords:
        return [_scale_col(col, state.bar_width, content_width) for col in range(state.bar_width)]
    positions, grid_width = _chord_positions_distinct_for_nav(bar, state.bar_width, 4)
    style = state.settings.get("style", "french")
    event_min_gap = multifret_event_gap(
        style=style,
        policy=state.settings.get("multifretspacing", "collision-safe"),
        has_multifret=bar_has_multifret_tokens(
            bar,
            style=style,
            french_c_shape=state.settings.get("frenchc", "normal"),
            label_mode=state.settings.get("fretlabelmode", "auto"),
        ),
    )
    unit_anchor_min_gap = max(1, event_min_gap - 1)
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
            min_gap=unit_anchor_min_gap,
        )
        src_to_dest = trim_right_slack_for_onsets(
            src_to_dest,
            all_positions=positions,
            visible_positions=visible_positions,
            content_width=content_width,
        )
    elif state.settings.get("justify", "stretch") == "smart":
        groups = spread_flag_positions(positions, grid_width, min_gap=0)
        src_to_dest = smart_group_map(positions, groups, content_width, min_gap=event_min_gap)
    else:
        scaled_positions = [
            (_scale_col(pos, grid_width, content_width), denom, dot)
            for (pos, denom, dot) in positions
        ]
        spread_positions = spread_flag_positions(
            scaled_positions,
            content_width,
            min_gap=event_min_gap,
        )
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


def system_display_indices_for_bar(state: EditorState, bar_index: int) -> list[int]:
    total_strings = state.piece.strings
    if bar_index < 0 or bar_index >= len(state.piece.bars):
        return system_display_indices_for_bars([], total_strings=total_strings)
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
    return system_display_indices_for_bars(
        state.piece.bars[start:end],
        total_strings=total_strings,
    )
