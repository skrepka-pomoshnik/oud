from __future__ import annotations

from petrucci.render_helpers import safe_addstr
from petrucci.render_marks import (
    _TUPLET_CUE_GLYPHS,
    _merge_nonspace_rows,
    _merge_span_rows_with_cue_priority,
    _overlay_sparse_mark_chars,
)
from petrucci.render_rhythm_types import RhythmRenderContext

SPARSE_CUES = {"(", ")", "[", "]", "<", ">", "/", "\\"} | _TUPLET_CUE_GLYPHS
SPAN_KEYS = ("slur", "hold", "gliss", "tie", "tuplet")


def draw_span_rows(context: RhythmRenderContext, grid_map: list[int], *, overlay_sparse: bool) -> None:
    for y in _span_y_values(context):
        merged = _merged_scaled_row(context, y)
        safe_addstr(context.stdscr, y, context.bar_x, "".join(merged))
        if overlay_sparse:
            _overlay_sparse_mark_chars(
                context.stdscr,
                y=y,
                bar_x=context.bar_x,
                draw_pad=context.draw_pad,
                grid_map=grid_map,
                row_cells=_merged_source_row(context, y),
                keep=SPARSE_CUES,
            )


def overlay_annotation_cues(context: RhythmRenderContext, grid_map: list[int]) -> None:
    row = context.rows.get("ann")
    if row is None:
        return
    _overlay_sparse_mark_chars(
        context.stdscr,
        y=context.row_start + row,
        bar_x=context.bar_x,
        draw_pad=context.draw_pad,
        grid_map=grid_map,
        row_cells=context.ann_cells,
        keep=SPARSE_CUES,
    )


def _span_y_values(context: RhythmRenderContext) -> set[int]:
    return {context.row_start + (context.rows[key] or 0) for key in SPAN_KEYS if context.rows.get(key) is not None}


def _row_at_y(context: RhythmRenderContext, key: str, row: list[str] | None, y: int) -> list[str] | None:
    offset = context.rows.get(key)
    return row if offset is not None and y == context.row_start + offset else None


def _merged_scaled_row(context: RhythmRenderContext, y: int) -> list[str]:
    return _merge_span_rows_with_cue_priority(
        slur_row=_row_at_y(context, "slur", context.scaled_slur_row, y),
        hold_row=_row_at_y(context, "hold", context.scaled_hold_row, y),
        gliss_row=_row_at_y(context, "gliss", context.scaled_gliss_row, y),
        tie_row=_row_at_y(context, "tie", context.scaled_tie_row, y),
        tuplet_row=_row_at_y(context, "tuplet", context.scaled_tuplet_row, y),
    )


def _source_or_blank(context: RhythmRenderContext, key: str, row: list[str], y: int) -> list[str]:
    return row if _row_at_y(context, key, row, y) is not None else [" "] * context.grid_width


def _merged_source_row(context: RhythmRenderContext, y: int) -> list[str]:
    ann = _source_or_blank(context, "ann", context.ann_cells, y)
    return _merge_nonspace_rows(
        ann,
        _source_or_blank(context, "slur", context.slur_cells, y),
        _source_or_blank(context, "hold", context.hold_cells, y),
        _source_or_blank(context, "gliss", context.gliss_cells, y),
        _source_or_blank(context, "tie", context.tie_cells, y),
        _source_or_blank(context, "tuplet", context.tuplet_cells, y),
    )
