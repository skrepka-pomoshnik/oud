from __future__ import annotations

import pytest

from oud.core.ft3 import build_durations
from oud.core.render_utils import bar_cells_from_chords, smart_group_map
from oud.core.view_model import _filter_redundant_positions, _scale_col
from oud.editor.init import init_state
from oud.editor.layout import auto_system_bar_plan_with_gaps, dynamic_system_starts
from oud.ui.framebuffer import FrameBuffer
from oud.ui.render import render_piece
from oud.ui.render_helpers import apply_overrides
from oud.ui.render_system import _build_chord_scale_map, _chord_positions_distinct, _scale_chord_row


def _content_width_for_bar(state, bar_index: int) -> int:
    starts = dynamic_system_starts(state, state.screen_width)
    start = max(value for value in starts if value <= bar_index)
    bar_indices, bar_widths, _gaps = auto_system_bar_plan_with_gaps(
        state,
        start,
        state.screen_width,
    )
    local_idx = bar_indices.index(bar_index)
    display_width = bar_widths[local_idx]
    barpad = int(state.settings.get("barpad", "1") or "1")
    return max(1, display_width - (barpad * 2))


def _flag_cols_and_rows(state, bar_index: int) -> tuple[list[int], list[str]]:
    bar = state.piece.bars[bar_index]
    positions, grid_width = _chord_positions_distinct(bar, state.bar_width, default_duration=4)
    cells = bar_cells_from_chords(
        bar,
        state.piece.strings,
        grid_width,
        4,
        state.settings.get("style", "french"),
        french_c=state.settings.get("frenchc", "normal"),
    )
    apply_overrides(cells, state.overrides, bar_index, state.piece.strings, grid_width)
    visible_cols = {
        col
        for col in range(grid_width)
        if any(cells[s_idx][col] not in ("-", " ") for s_idx in range(state.piece.strings))
    }
    positions = [item for item in positions if item[0] in visible_cols]
    ordered_flags = sorted(_filter_redundant_positions(positions), key=lambda item: item[0])
    content_width = _content_width_for_bar(state, bar_index)
    justify = state.settings.get("justify", "stretch")
    if justify == "smart":
        src_to_dest = smart_group_map(positions, ordered_flags, content_width)
    else:
        _, src_to_dest = _build_chord_scale_map(
            positions,
            bar_width=grid_width,
            content_width=content_width,
            min_gap=1,
        )
    flag_cols = [
        src_to_dest.get(raw_col, _scale_col(raw_col, grid_width, content_width))
        for raw_col, _denom, _dot in ordered_flags
    ]
    scaled_rows = [
        "".join(
            _scale_chord_row(
                cells[s_idx],
                fill_char="-",
                src_to_dest=src_to_dest,
                bar_width=grid_width,
                content_width=content_width,
            ),
        )
        for s_idx in range(state.piece.strings)
    ]
    return flag_cols, scaled_rows


@pytest.mark.parametrize("justify", ["smart", "stretch", "compact"])
@pytest.mark.parametrize(
    ("path", "bar_index"),
    [
        ("examples/26_lachrimae_galliard_in_G.ft3", 0),
        ("examples/02_forlorne_hope_8C.ft3", 9),
        ("lutemusic/17_galliard_3_earl_of_essex_galliard_dowlandJ.ft3", 28),
    ],
)
def test_real_fixtures_no_lonely_stems_and_no_flag_collapse(
    justify: str,
    path: str,
    bar_index: int,
) -> None:
    state = init_state(path, config_path="config.toml")
    state.settings["layout"] = "auto"
    state.settings["justify"] = justify
    state.settings["barpad"] = "1"
    state.settings["flagredundant"] = "on"
    state.screen_width = 120
    state.bar_width = max(state.bar_width, 10)

    flag_cols, scaled_rows = _flag_cols_and_rows(state, bar_index)
    assert flag_cols, (path, bar_index, justify)
    assert len(flag_cols) == len(set(flag_cols)), (path, bar_index, justify, flag_cols)
    for col in flag_cols:
        assert any(row[col] not in ("-", " ") for row in scaled_rows), (
            path,
            bar_index,
            justify,
            col,
        )


def _render_lines(path: str, justify: str, width: int = 120, height: int = 26) -> list[str]:
    state = init_state(path, config_path="config.toml")
    state.settings.update(
        {
            "layout": "auto",
            "justify": justify,
            "showdur": "on",
            "showextras": "on",
            "showtactus": "on",
            "showmeta": "off",
            "barpad": "1",
            "barsperline": "0",
            "maxbars": "0",
            "linelen": "0",
        },
    )
    fb = FrameBuffer(height, width)
    render_piece(
        fb,
        state.piece,
        0,
        0,
        0,
        0,
        state.bar_width,
        state.overrides,
        build_durations(state.piece),
        state.ornaments,
        state.annotations,
        state.highlights,
        state.dotted,
        state.slurs,
        state.ties,
        state.holds,
        "normal",
        "",
        "",
        "",
        "",
        state.settings,
        None,
        state.stave_breaks,
        "Plugins",
        [],
        0,
        0,
        0,
        None,
        None,
    )
    return fb.snapshot().lines


@pytest.mark.parametrize("justify", ["smart", "stretch"])
@pytest.mark.parametrize(
    "path",
    [
        "examples/26_lachrimae_galliard_in_G.ft3",
        "examples/02_forlorne_hope_8C.ft3",
        "lutemusic/17_galliard_3_earl_of_essex_galliard_dowlandJ.ft3",
    ],
)
def test_real_fixtures_no_broken_bar_seams(path: str, justify: str) -> None:
    lines = _render_lines(path, justify)
    staff_rows = [line for line in lines if "-" in line and "|" in line]
    assert staff_rows
    # Broken seam pattern between adjacent bars must never appear.
    assert all("|  |" not in row for row in staff_rows)
