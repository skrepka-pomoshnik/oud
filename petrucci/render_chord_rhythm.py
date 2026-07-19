from __future__ import annotations

from petrucci.render_bar import build_flag_rows
from petrucci.render_geometry import (
    _event_display_onset_cols,
    _expand_scale_map_from_anchors,
    _grid_display_map,
    _place_duration_cells_aligned,
)
from petrucci.render_helpers import pad_row, safe_addstr
from petrucci.render_rhythm_cues import draw_span_rows, overlay_annotation_cues
from petrucci.render_rhythm_types import FlagRowPlan, RhythmRenderContext, RhythmRenderResult
from petrucci.render_spacing import build_chord_scale_map as _build_chord_scale_map
from petrucci.render_spacing import note_event_columns as _note_event_columns
from petrucci.render_utils import (
    smart_group_map,
    soft_beat_snap_map,
    spread_flag_positions,
    trim_right_slack_for_onsets,
)
from petrucci.screen import A_BOLD
from petrucci.tab_policy import bar_has_multifret_tokens, multifret_event_gap
from petrucci.view_model import _beamified_chord_flag_positions, _scale_col, duration_display


def render_chord_rhythm(context: RhythmRenderContext) -> RhythmRenderResult:
    visible_cols = set(_note_event_columns(context.cells, context.total_strings, context.grid_width))
    positions = [item for item in context.chord_positions_all if item[0] in visible_cols]
    flags = _beamified_chord_flag_positions(
        context.bar,
        positions,
        hide_redundant=context.hide_redundant,
        default_duration=context.default_duration,
    )
    ordered_flags = sorted(flags, key=lambda item: item[0])
    plan = _chord_flag_plan(context, positions, ordered_flags, flags)
    content_width = max(1, context.display_width - context.draw_pad * 2)
    grid_map = _grid_display_map(
        grid_width=context.grid_width,
        content_width=content_width,
        src_to_dest=plan.src_to_dest,
    )
    text_onsets = _event_display_onset_cols(
        positions=positions,
        grid_map=grid_map,
        draw_pad=context.draw_pad,
    )
    if context.scale_bar:
        overlay_annotation_cues(context, grid_map)
    draw_span_rows(context, grid_map, overlay_sparse=context.scale_bar)
    _draw_flag_rows(context, plan)
    duration_cells, duration_map, duration_padded = _draw_durations(context, ordered_flags, plan)
    _draw_cursor(context, positions, grid_map, plan.flag_cells, duration_cells, duration_map, duration_padded)
    return RhythmRenderResult(positions, plan.src_to_dest, grid_map, text_onsets)


def _chord_flag_plan(
    context: RhythmRenderContext,
    positions: list[tuple[int, int, bool]],
    ordered_flags: list[tuple[int, int, bool]],
    flags: list[tuple[int, int, bool]],
) -> FlagRowPlan:
    if context.scale_bar:
        return _scaled_chord_plan(context, positions, ordered_flags)
    final_flags = spread_flag_positions(ordered_flags, context.bar_width, min_gap=1)
    duration_positions = [
        (raw_col, display_col)
        for (raw_col, _denom, _dot), (display_col, _denom2, _dot2) in zip(
            ordered_flags,
            final_flags,
            strict=False,
        )
    ]
    flag_cells, stem_cells = build_flag_rows(
        flags,
        spacing_mode=context.spacing_mode,
        display_width=context.display_width,
        bar_width=context.bar_width,
        barpad=context.barpad,
        flagstyle=context.style_policy.flagstyle,
        flaglean=context.style_policy.flaglean,
    )
    if context.draw_pad:
        flag_cells = pad_row(flag_cells, context.display_width, context.draw_pad)
        stem_cells = pad_row(stem_cells, context.display_width, context.draw_pad)
    return FlagRowPlan(flag_cells, stem_cells, {}, duration_positions)


def _scaled_chord_plan(
    context: RhythmRenderContext,
    positions: list[tuple[int, int, bool]],
    ordered_flags: list[tuple[int, int, bool]],
) -> FlagRowPlan:
    content_width = max(1, context.display_width - context.draw_pad * 2)
    event_gap = _event_min_gap(context)
    unit_gap = max(1, event_gap - 1)
    flag_gap = 1 if context.spacing_fill == "smart" else 0
    if any(chord.grid for chord in context.bar.chords):
        src_to_dest, flag_map = _grid_group_maps(
            context,
            positions,
            ordered_flags,
            content_width=content_width,
            event_gap=event_gap,
            unit_gap=unit_gap,
            flag_gap=flag_gap,
        )
    else:
        src_to_dest = _base_scale_map(
            context,
            positions,
            ordered_flags,
            content_width=content_width,
            min_gap=event_gap,
        )
        src_to_dest = _spread_map(positions, src_to_dest, content_width, unit_gap)
        flag_map = src_to_dest
    final_flags = [
        (flag_map.get(col, _scale_col(col, context.grid_width, content_width)), denom, dot)
        for col, denom, dot in ordered_flags
    ]
    duration_positions = [
        (col, src_to_dest.get(col, _scale_col(col, context.grid_width, content_width)))
        for col, _denom, _dot in ordered_flags
    ]
    flag_cells, stem_cells = build_flag_rows(
        final_flags,
        spacing_mode="fixed",
        display_width=content_width,
        bar_width=content_width,
        barpad=0,
        flagstyle=context.style_policy.flagstyle,
        flaglean=context.style_policy.flaglean,
        stem_width=context.style_policy.stem_width,
        dotplacement=context.style_policy.dotplacement,
        min_gap=flag_gap,
    )
    return FlagRowPlan(
        pad_row(flag_cells, context.display_width, context.draw_pad),
        pad_row(stem_cells, context.display_width, context.draw_pad),
        src_to_dest,
        duration_positions,
    )


def _event_min_gap(context: RhythmRenderContext) -> int:
    gap = multifret_event_gap(
        style=context.style,
        policy=context.settings.get("multifretspacing", "collision-safe"),
        has_multifret=bar_has_multifret_tokens(
            context.bar,
            style=context.style,
            french_c_shape=context.french_c,
            label_mode=context.fretlabelmode,
        ),
    )
    return max(1, gap - 1) if context.spacing_fill == "compact" else gap


def _grid_group_maps(
    context: RhythmRenderContext,
    positions: list[tuple[int, int, bool]],
    ordered_flags: list[tuple[int, int, bool]],
    *,
    content_width: int,
    event_gap: int,
    unit_gap: int,
    flag_gap: int,
) -> tuple[dict[int, int], dict[int, int]]:
    flag_map = _base_scale_map(
        context,
        ordered_flags,
        ordered_flags,
        content_width=content_width,
        min_gap=max(1, flag_gap),
    )
    flag_map = _spread_map(ordered_flags, flag_map, content_width, max(1, flag_gap))
    reduced_flags = len({col for col, _denom, _dot in ordered_flags}) < len({col for col, _denom, _dot in positions})
    if reduced_flags:
        src_to_dest = _base_scale_map(
            context,
            positions,
            ordered_flags,
            content_width=content_width,
            min_gap=unit_gap if context.settings.get("beatsnap", "off") == "soft" else event_gap,
        )
        src_to_dest = _spread_map(positions, src_to_dest, content_width, unit_gap)
    else:
        src_to_dest = _expand_scale_map_from_anchors(positions, flag_map, content_width=content_width)
    return src_to_dest, flag_map


def _base_scale_map(
    context: RhythmRenderContext,
    positions: list[tuple[int, int, bool]],
    visible: list[tuple[int, int, bool]],
    *,
    content_width: int,
    min_gap: int,
) -> dict[int, int]:
    beatsnap = context.settings.get("beatsnap", "off")
    if beatsnap == "soft" and context.beats > 1:
        mapping = soft_beat_snap_map(
            positions,
            grid_width=context.grid_width,
            content_width=content_width,
            beats=context.beats,
            min_gap=min_gap,
        )
        return trim_right_slack_for_onsets(
            mapping,
            all_positions=positions,
            visible_positions=visible,
            content_width=content_width,
            min_gap=min_gap,
        )
    if context.spacing_fill == "smart":
        return smart_group_map(positions, visible, content_width, min_gap=min_gap)
    return _build_chord_scale_map(positions, context.grid_width, content_width, min_gap=min_gap)[1]


def _spread_map(
    positions: list[tuple[int, int, bool]],
    mapping: dict[int, int],
    content_width: int,
    min_gap: int,
) -> dict[int, int]:
    if content_width <= 1 or not mapping:
        return mapping
    anchor_width = max(1, content_width - 1)
    seeded = [
        (
            _scale_col(mapping.get(col, _scale_col(col, content_width, content_width)), content_width, anchor_width),
            2,
            False,
        )
        for col, _denom, _dot in positions
    ]
    spread = spread_flag_positions(seeded, anchor_width, min_gap=min_gap)
    return {
        raw_col: display_col
        for (raw_col, _denom, _dot), (display_col, _denom2, _dot2) in zip(positions, spread, strict=False)
    }


def _draw_flag_rows(context: RhythmRenderContext, plan: FlagRowPlan) -> None:
    safe_addstr(
        context.stdscr, context.row_start + (context.rows["flag"] or 0), context.bar_x, "".join(plan.flag_cells)
    )
    if context.rows.get("flag2") is not None:
        safe_addstr(
            context.stdscr,
            context.row_start + (context.rows["flag2"] or 0),
            context.bar_x,
            "".join(plan.stem_cells),
        )


def _draw_durations(
    context: RhythmRenderContext,
    ordered_flags: list[tuple[int, int, bool]],
    plan: FlagRowPlan,
) -> tuple[list[str], dict[int, int], bool]:
    if not context.show_dur or context.rows["dur"] is None:
        return [], {}, False
    target_width = max(1, context.display_width - context.draw_pad * 2) if context.scale_bar else context.bar_width
    duration_cells = [" "] * target_width
    duration_map: dict[int, int] = {}
    for (raw_col, denom, dot), (_source_col, target_col) in zip(
        ordered_flags,
        plan.duration_positions,
        strict=False,
    ):
        duration_map[raw_col] = target_col
        _place_duration_cells_aligned(duration_cells, target_col, duration_display(denom, dot))
    padded = context.scale_bar or bool(context.draw_pad)
    if padded:
        duration_cells = pad_row(duration_cells, context.display_width, context.draw_pad)
    safe_addstr(
        context.stdscr,
        context.row_start + (context.rows["dur"] or 0),
        context.bar_x,
        "".join(duration_cells),
    )
    return duration_cells, duration_map, padded


def _draw_cursor(
    context: RhythmRenderContext,
    positions: list[tuple[int, int, bool]],
    grid_map: list[int],
    flag_cells: list[str],
    duration_cells: list[str],
    duration_map: dict[int, int],
    duration_padded: bool,
) -> None:
    if context.abs_bar != context.cursor_bar:
        return
    cursor_grid_col = _scale_col(context.cursor_col, context.bar_width, context.grid_width)
    matching = next((col for col, _denom, _dot in positions if col == cursor_grid_col), None)
    if matching is None:
        return
    scaled_col = grid_map[matching]
    flag_idx = context.draw_pad + scaled_col
    safe_addstr(
        context.stdscr,
        context.row_start + (context.rows["flag"] or 0),
        context.bar_x + flag_idx,
        flag_cells[flag_idx],
        A_BOLD,
    )
    _draw_duration_cursor(context, matching, scaled_col, duration_cells, duration_map, duration_padded)


def _draw_duration_cursor(
    context: RhythmRenderContext,
    raw_col: int,
    scaled_col: int,
    duration_cells: list[str],
    duration_map: dict[int, int],
    padded: bool,
) -> None:
    if not duration_cells or context.rows["dur"] is None:
        return
    duration_col = duration_map.get(raw_col, scaled_col)
    duration_idx = context.draw_pad + duration_col if padded else duration_col
    if 0 <= duration_idx < len(duration_cells):
        safe_addstr(
            context.stdscr,
            context.row_start + (context.rows["dur"] or 0),
            context.bar_x + duration_idx,
            duration_cells[duration_idx],
            A_BOLD,
        )
