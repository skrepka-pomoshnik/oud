from __future__ import annotations

from petrucci.rendering.bar.render import build_flag_rows
from petrucci.rendering.primitives.geometry import (
    _anchor_flag_positions_to_note_cols,
    _grid_display_map,
    _place_duration_cells_aligned,
)
from petrucci.rendering.primitives.helpers import pad_row, safe_addstr
from petrucci.rendering.rhythm.cues import draw_span_rows
from petrucci.rendering.rhythm.types import FlagRowPlan, RhythmRenderContext, RhythmRenderResult
from petrucci.rendering.primitives.spacing import build_chord_scale_map as _build_chord_scale_map
from petrucci.rendering.primitives.spacing import note_event_columns as _note_event_columns
from petrucci.rendering.primitives.utils import spread_flag_positions
from petrucci.terminal.view.model import (
    FlagPositionRequest,
    _bar_durations,
    _filter_redundant_positions,
    _flag_positions_all,
    _scale_col,
    duration_display,
    flag_positions_from_durations,
)


def render_grid_rhythm(context: RhythmRenderContext) -> RhythmRenderResult:
    visible_cols = _note_event_columns(context.cells, context.total_strings, context.grid_width)
    flags = _grid_flag_positions(context, visible_cols)
    plan, grid_map = _grid_flag_plan(context, flags, visible_cols)
    draw_span_rows(context, grid_map, overlay_sparse=False)
    _draw_flag_rows(context, plan)
    _draw_durations(context, flags, plan)
    return RhythmRenderResult([], plan.src_to_dest, grid_map, [])


def _grid_flag_positions(
    context: RhythmRenderContext,
    visible_cols: list[int],
) -> list[tuple[int, int, bool]]:
    explicit = bool(context.bar.notes) or _has_override_content(context)
    if context.hide_redundant and explicit:
        flags = flag_positions_from_durations(
            context.durations,
            context.abs_bar,
            context.total_strings,
            context.bar_width,
            context.default_duration,
            dotted=context.dotted,
        )
        flags = _filter_redundant_positions(flags)
    elif context.hide_redundant:
        flags = []
    else:
        flags = _flag_positions_all(
            FlagPositionRequest(
                durations=context.durations,
                bar_index=context.abs_bar,
                strings=context.total_strings,
                bar_width=context.bar_width,
                default_duration=context.default_duration,
                dotted=context.dotted,
            )
        )
    return _anchor_flag_positions_to_note_cols(flags, visible_cols)


def _has_override_content(context: RhythmRenderContext) -> bool:
    return any(
        bar == context.abs_bar and value not in ("", "-", " ")
        for (bar, _string, _column), value in context.overrides.items()
    ) or any(bar == context.abs_bar for bar, _string, _column in context.durations)


def _grid_flag_plan(
    context: RhythmRenderContext,
    flags: list[tuple[int, int, bool]],
    visible_cols: list[int],
) -> tuple[FlagRowPlan, list[int]]:
    if context.scale_bar:
        return _scaled_grid_plan(context, flags, visible_cols)
    flag_cells, stem_cells = build_flag_rows(
        flags,
        spacing_mode=context.spacing_mode,
        display_width=context.display_width,
        bar_width=context.bar_width,
        barpad=context.pad,
        flagstyle=context.style_policy.flagstyle,
        flaglean=context.style_policy.flaglean,
        stem_width=context.style_policy.stem_width,
        dotplacement=context.style_policy.dotplacement,
    )
    if context.draw_pad:
        flag_cells = pad_row(flag_cells, context.display_width, context.draw_pad)
        stem_cells = pad_row(stem_cells, context.display_width, context.draw_pad)
    duration_positions = [(column, column) for column, _denom, _dot in flags]
    grid_map = list(range(max(1, context.grid_width)))
    return FlagRowPlan(flag_cells, stem_cells, {}, duration_positions), grid_map


def _scaled_grid_plan(
    context: RhythmRenderContext,
    flags: list[tuple[int, int, bool]],
    visible_cols: list[int],
) -> tuple[FlagRowPlan, list[int]]:
    content_width = max(1, context.display_width - context.draw_pad * 2)
    event_gap = 1 if context.spacing_fill == "compact" else 2
    event_positions = [(column, 2, False) for column in visible_cols]
    src_to_dest: dict[int, int] = {}
    if event_positions:
        src_to_dest = _build_chord_scale_map(
            event_positions,
            context.grid_width,
            content_width,
            min_gap=event_gap,
        )[1]
        src_to_dest = _spread_event_map(event_positions, src_to_dest, content_width, event_gap)
    final_flags = [
        (src_to_dest.get(column, _scale_col(column, context.grid_width, content_width)), denom, dot)
        for column, denom, dot in flags
    ]
    duration_positions = [
        (column, src_to_dest.get(column, _scale_col(column, context.grid_width, content_width)))
        for column, _denom, _dot in flags
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
    )
    plan = FlagRowPlan(
        pad_row(flag_cells, context.display_width, context.draw_pad),
        pad_row(stem_cells, context.display_width, context.draw_pad),
        src_to_dest,
        duration_positions,
    )
    grid_map = _grid_display_map(
        grid_width=context.grid_width,
        content_width=content_width,
        src_to_dest=src_to_dest,
    )
    return plan, grid_map


def _spread_event_map(
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
            _scale_col(
                mapping.get(column, _scale_col(column, content_width, content_width)), content_width, anchor_width
            ),
            2,
            False,
        )
        for column, _denom, _dot in positions
    ]
    spread = spread_flag_positions(seeded, anchor_width, min_gap=min_gap)
    return {
        raw_column: display_column
        for (raw_column, _denom, _dot), (display_column, _denom2, _dot2) in zip(
            positions,
            spread,
            strict=False,
        )
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
    flags: list[tuple[int, int, bool]],
    plan: FlagRowPlan,
) -> None:
    if not context.show_dur or context.rows["dur"] is None:
        return
    if context.scale_bar:
        content_width = max(1, context.display_width - context.draw_pad * 2)
        duration_cells = [" "] * content_width
        for (_raw_col, denom, dot), (_source, target) in zip(flags, plan.duration_positions, strict=False):
            _place_duration_cells_aligned(duration_cells, target, duration_display(denom, dot))
        duration_cells = pad_row(duration_cells, context.display_width, context.draw_pad)
    else:
        duration_cells = _bar_durations(
            context.durations,
            context.abs_bar,
            context.total_strings,
            context.bar_width,
            context.default_duration,
            hide_redundant=context.hide_redundant,
            dotted=context.dotted,
        )
        duration_cells = pad_row(duration_cells, context.display_width, context.draw_pad)
    safe_addstr(
        context.stdscr,
        context.row_start + (context.rows["dur"] or 0),
        context.bar_x,
        "".join(duration_cells),
    )
