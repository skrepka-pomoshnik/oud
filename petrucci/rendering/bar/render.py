from __future__ import annotations

from petrucci.rendering.primitives.helpers import flag_symbols, pad_row
from petrucci.rendering.primitives.utils import flag_row_style, spread_flag_positions, stem_row_style
from petrucci.terminal.view.model import _scale_col


def build_flag_rows(
    positions: list[tuple[int, int, bool]],
    *,
    spacing_mode: str,
    display_width: int,
    bar_width: int,
    barpad: int,
    flagstyle: str,
    flaglean: str = "right",
    stem_width: int = 1,
    dotplacement: str = "afterflag",
    min_gap: int = 1,
) -> tuple[list[str], list[str]]:
    stem, flag = flag_symbols(flagstyle, flaglean)
    if spacing_mode == "fixed":
        clamped = [(max(0, min(bar_width - 1, pos)), denom, dotted) for (pos, denom, dotted) in positions]
        flag_cells = flag_row_style(
            clamped,
            bar_width,
            stem=stem,
            flag=flag,
            stem_width=stem_width,
            dotplacement=dotplacement,
        )
        stem_cells = stem_row_style(clamped, bar_width, stem=stem, stem_width=stem_width)
        return flag_cells, stem_cells
    if spacing_mode == "auto":
        content_width = max(1, display_width - barpad * 2)
        scaled_positions = [(_scale_col(pos, bar_width, content_width), denom, dot) for (pos, denom, dot) in positions]
        scaled_positions = spread_flag_positions(
            scaled_positions,
            content_width,
            min_gap=min_gap,
        )
        flag_cells = flag_row_style(
            scaled_positions,
            content_width,
            stem=stem,
            flag=flag,
            stem_width=stem_width,
            dotplacement=dotplacement,
        )
        flag_cells = pad_row(flag_cells, display_width, barpad)
        stem_cells = stem_row_style(
            scaled_positions,
            content_width,
            stem=stem,
            stem_width=stem_width,
        )
        stem_cells = pad_row(stem_cells, display_width, barpad)
        return flag_cells, stem_cells

    spread_positions = spread_flag_positions(positions, bar_width, min_gap=min_gap)
    flag_cells = flag_row_style(
        spread_positions,
        bar_width,
        stem=stem,
        flag=flag,
        stem_width=stem_width,
        dotplacement=dotplacement,
    )
    stem_cells = stem_row_style(spread_positions, bar_width, stem=stem, stem_width=stem_width)
    return flag_cells, stem_cells
