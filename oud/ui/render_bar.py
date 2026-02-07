from __future__ import annotations

from oud.core.render_utils import flag_row_style, spread_flag_positions, stem_row_style
from oud.core.view_model import _scale_col
from oud.ui.render_helpers import flag_symbols, pad_row


def build_flag_rows(
    positions: list[tuple[int, int, bool]],
    *,
    spacing_mode: str,
    display_width: int,
    bar_width: int,
    barpad: int,
    flagstyle: str,
) -> tuple[list[str], list[str]]:
    stem, flag = flag_symbols(flagstyle)
    if spacing_mode == "auto":
        content_width = max(1, display_width - barpad * 2)
        scaled_positions = [
            (_scale_col(pos, bar_width, content_width), denom, dot)
            for (pos, denom, dot) in positions
        ]
        scaled_positions = spread_flag_positions(
            scaled_positions,
            content_width,
            min_gap=1,
        )
        flag_cells = flag_row_style(
            scaled_positions,
            content_width,
            stem=stem,
            flag=flag,
        )
        flag_cells = pad_row(flag_cells, display_width, barpad)
        stem_cells = stem_row_style(
            scaled_positions,
            content_width,
            stem=stem,
        )
        stem_cells = pad_row(stem_cells, display_width, barpad)
        return flag_cells, stem_cells

    spread_positions = spread_flag_positions(positions, bar_width, min_gap=1)
    flag_cells = flag_row_style(
        spread_positions,
        bar_width,
        stem=stem,
        flag=flag,
    )
    stem_cells = stem_row_style(spread_positions, bar_width, stem=stem)
    return flag_cells, stem_cells
