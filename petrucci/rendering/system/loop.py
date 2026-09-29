from __future__ import annotations

from petrucci.engraving.layout.map import LayoutBlockPolicy, block_height, layout_block_rows
from petrucci.engraving.layout.systems import AutoSystemPlanOptions, plan_auto_system, plan_fixed_system
from petrucci.input.tablature.policy import system_display_indices_for_bars, visual_row_indices
from petrucci.rendering.bar.state import (
    prepare_bar_basics,
    prepare_bar_layout,
    prepare_bar_marks,
    prepare_bar_metadata,
)
from petrucci.rendering.primitives.cues import draw_static_bar_rows
from petrucci.rendering.primitives.helpers import safe_addstr
from petrucci.rendering.rhythm.rows import _render_rhythm_rows
from petrucci.rendering.staff.rows import _render_staff_and_playback
from petrucci.rendering.system.types import SystemLayout, SystemRenderContext
from petrucci.terminal.view.model import _string_label


def render_system_sequence(context: SystemRenderContext) -> None:
    bar_start = context.bar_offset
    row_start = context.header_row + 1
    for system_index in range(context.systems):
        if bar_start >= len(context.piece.bars):
            break
        system = _system_layout(context, bar_start)
        _draw_system_frame(context, system, system_index=system_index, row_start=row_start)
        _render_bars(context, system, bar_start=bar_start, row_start=row_start)
        bar_start = system.bar_end
        row_start += system.block_height


def _system_layout(context: SystemRenderContext, bar_start: int) -> SystemLayout:
    if context.spacing_mode == "auto":
        plan = plan_auto_system(
            AutoSystemPlanOptions(
                piece=context.piece,
                usable_width=context.usable_width,
                bar_width=context.bar_width,
                overrides=context.overrides,
                durations=context.durations,
                default_duration=context.default_duration,
                dotted=context.dotted,
                bar_gap=context.bar_gap,
                spacing_fill=context.spacing_fill,
                stave_breaks=context.stave_breaks,
                bars_per_line_limit=context.bars_per_line_limit,
                max_chords=context.max_chords,
                chord_wrap_limit=context.chord_wrap_limit,
                total_strings=context.total_strings,
                barpad=context.barpad,
                show_dur=context.show_dur,
                hide_redundant=context.hide_redundant,
                settings=context.settings,
            ),
            bar_start=bar_start,
        )
    else:
        plan = plan_fixed_system(
            context.piece,
            bar_start=bar_start,
            bars_per_line_limit=context.bars_per_line_limit,
            stave_breaks=context.stave_breaks,
        )
    display_indices = system_display_indices_for_bars(
        context.piece.bars[bar_start : plan.bar_end],
        total_strings=context.total_strings,
        edited_strings={string for bar, string, _column in context.overrides if bar_start <= bar < plan.bar_end},
    )
    display_strings = len(display_indices)
    visual_indices = visual_row_indices(display_indices, reverse=context.reverse_strings)
    layout_policy = LayoutBlockPolicy(
        strings=display_strings,
        include_meta=context.include_meta,
        show_dur=context.show_dur,
        show_extras=context.show_extras,
        show_tuplets=context.show_tuplets,
        show_tactus=context.show_tactus,
        double_stems=context.double_stems,
        show_melody=context.show_melody,
        melody_rows_count=context.melody_rows_count,
        show_lyrics=context.show_lyrics,
        lyric_rows_count=context.lyric_rows_count,
        vocal_pos=context.vocal_pos,
    )
    rows = layout_block_rows(layout_policy)
    content_height = block_height(layout_policy)
    lyric_base = rows.get("lyric")
    lyric_offsets = (
        tuple((lyric_base or 0) + index for index in range(max(0, context.lyric_rows_count)))
        if lyric_base is not None and context.lyric_rows_count > 0
        else ()
    )
    return SystemLayout(
        plan.bar_end,
        list(plan.bar_widths),
        list(plan.gaps_after),
        display_strings,
        visual_indices,
        rows,
        content_height,
        lyric_offsets,
    )


def _draw_system_frame(
    context: SystemRenderContext,
    system: SystemLayout,
    *,
    system_index: int,
    row_start: int,
) -> None:
    for row in range(row_start, row_start + system.block_height):
        safe_addstr(context.stdscr, row, 0, " " * context.width)
    for display_index, actual in enumerate(system.visual_indices[: system.display_strings]):
        label = "  "
        if system_index == 0:
            label = _string_label(actual, context.total_strings, context.tuning_labels, context.basslabels)
        safe_addstr(context.stdscr, row_start + (system.rows["staff"] or 0) + display_index, 0, label)
    melody_base = system.rows.get("melody")
    if melody_base is not None:
        for index in range(context.melody_rows_count):
            safe_addstr(context.stdscr, row_start + melody_base + index, 0, "  ")
    for lyric_row in system.lyric_row_offsets:
        safe_addstr(context.stdscr, row_start + lyric_row, 0, "  ")


def _render_bars(
    context: SystemRenderContext,
    system: SystemLayout,
    *,
    bar_start: int,
    row_start: int,
) -> None:
    bar_x = _first_bar_x(context, system)
    for local_index, bar in enumerate(context.piece.bars[bar_start : system.bar_end]):
        display_width = _render_bar(
            context,
            system,
            bar,
            abs_bar=bar_start + local_index,
            local_index=local_index,
            bar_x=bar_x,
            row_start=row_start,
        )
        gap = system.gaps_after[local_index] if local_index < len(system.gaps_after) else 0
        bar_x += display_width + (gap if context.spacing_mode == "auto" else context.bar_gap)


def _first_bar_x(context: SystemRenderContext, system: SystemLayout) -> int:
    if context.spacing_mode != "auto" or not system.bar_widths or context.spacing_fill != "center":
        return context.left_margin
    total_width = sum(system.bar_widths) + context.bar_gap * max(0, len(system.bar_widths) - 1)
    return context.left_margin + max(0, (context.usable_width - total_width) // 2)


def _cursor_grid_col(context: SystemRenderContext, bar, basics, *, abs_bar: int) -> int | None:
    """Grid column of the cursor event in a chord bar, or None to scale ``cursor_col``."""

    if abs_bar != context.cursor_bar or context.cursor_event is None or not bar.chords:
        return None
    columns = [column for column, _denom, _dot in basics.chord_positions]
    if context.cursor_event < len(columns):
        return columns[context.cursor_event]
    return min(columns[-1] + 1, basics.grid_width - 1)


def _render_bar(
    context: SystemRenderContext,
    system: SystemLayout,
    bar,
    *,
    abs_bar: int,
    local_index: int,
    bar_x: int,
    row_start: int,
) -> int:
    basics = prepare_bar_basics(context, bar)
    metadata = prepare_bar_metadata(
        context,
        system,
        bar,
        abs_bar=abs_bar,
        local_index=local_index,
        grid_width=basics.grid_width,
    )
    marks = prepare_bar_marks(context, system, bar, basics, abs_bar=abs_bar)
    layout = prepare_bar_layout(
        context,
        system,
        bar,
        basics,
        metadata,
        abs_bar=abs_bar,
        local_index=local_index,
    )
    scaled = draw_static_bar_rows(
        context,
        system,
        metadata,
        marks,
        layout,
        abs_bar=abs_bar,
        bar_x=bar_x,
        row_start=row_start,
    )
    positions, src_to_dest, grid_map, text_onsets = _render_rhythm_rows(
        context.stdscr,
        bar=bar,
        abs_bar=abs_bar,
        bar_width=context.bar_width,
        bar_x=bar_x,
        barpad=context.barpad,
        beats=metadata.beats,
        cells=basics.cells,
        chord_positions_all=basics.chord_positions,
        cursor_bar=context.cursor_bar,
        cursor_col=context.cursor_col,
        cursor_grid_col=_cursor_grid_col(context, bar, basics, abs_bar=abs_bar),
        default_duration=context.default_duration,
        display_width=layout.display_width,
        dotted=context.dotted,
        draw_pad=layout.draw_pad,
        durations=context.durations,
        french_c=basics.french_c,
        fretlabelmode=basics.fretlabelmode,
        grid_width=basics.grid_width,
        hide_redundant=context.hide_redundant,
        overrides=context.overrides,
        pad=layout.pad,
        row_start=row_start,
        rows=system.rows,
        scale_bar=layout.scale_bar,
        settings=context.settings,
        show_dur=context.show_dur,
        spacing_fill=context.spacing_fill,
        spacing_mode=context.spacing_mode,
        style=basics.style,
        style_policy=context.style_policy,
        total_strings=context.total_strings,
        ann_cells=marks.ann_cells,
        slur_cells=marks.slur_cells,
        tie_cells=marks.tie_cells,
        hold_cells=marks.hold_cells,
        gliss_cells=marks.gliss_cells,
        tuplet_cells=marks.tuplet_cells,
        scaled_slur_row=scaled.slur,
        scaled_tie_row=scaled.tie,
        scaled_hold_row=scaled.hold,
        scaled_gliss_row=scaled.gliss,
        scaled_tuplet_row=scaled.tuplet,
    )
    _render_staff_and_playback(
        context.stdscr,
        piece=context.piece,
        bar=bar,
        abs_bar=abs_bar,
        ann_cells=marks.ann_cells,
        ann_target_rows=marks.ann_target_rows,
        bar_width=context.bar_width,
        bar_x=bar_x,
        barline=metadata.barline,
        barpad=context.barpad,
        cells=basics.cells,
        cursor_bar=context.cursor_bar,
        cursor_col=context.cursor_col,
        cursor_grid_col=_cursor_grid_col(context, bar, basics, abs_bar=abs_bar),
        cursor_display_maps=context.cursor_display_maps,
        cursor_string=context.cursor_string,
        display_width=layout.display_width,
        draw_pad=layout.draw_pad,
        effective_playback_markers=context.effective_playback_markers,
        grid_map=grid_map,
        grid_width=basics.grid_width,
        highlights=context.highlights,
        lyric_row_offsets=system.lyric_row_offsets,
        melody_rows_count=context.melody_rows_count,
        orn_cells=marks.orn_cells,
        orn_target_rows=marks.orn_target_rows,
        playback_cache=context.playback_cache,
        positions=positions,
        repeat_left=metadata.repeat_left,
        repeat_right=metadata.repeat_right,
        repeat_rows=metadata.repeat_rows,
        row_start=row_start,
        rows=system.rows,
        scale_bar=layout.scale_bar,
        settings=context.settings,
        show_time_sig_here=layout.show_time_signature,
        sig_label=metadata.sig_label,
        src_to_dest=src_to_dest,
        style=basics.style,
        system_display_strings=system.display_strings,
        system_visual_indices=system.visual_indices,
        text_onset_cols=text_onsets,
        time_value=metadata.time_value,
        tuning_pitches=context.tuning_pitches,
        width=context.width,
    )
    return layout.display_width
