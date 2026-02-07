from __future__ import annotations

from itertools import pairwise
from pathlib import Path

from oud.core.ft3 import load_ft3
from oud.core.view_model import _filter_redundant_positions, bar_cells_from_chords
from oud.ui.render_bar import build_flag_rows
from oud.ui.render_system import (
    _build_chord_scale_map,
    _chord_positions_distinct,
    _grid_display_map,
    _place_duration_cells_aligned,
    _required_flag_content_width,
    _scale_chord_row,
)


def test_build_chord_scale_map_keeps_ordered_columns() -> None:
    positions = [(0, 4, True), (2, 16, False), (3, 16, False), (5, 8, False)]
    scaled, mapping = _build_chord_scale_map(positions, bar_width=8, content_width=10)
    assert len(scaled) == len(positions)
    assert mapping[0] < mapping[2] < mapping[3] < mapping[5]


def test_build_chord_scale_map_separates_duration_groups() -> None:
    positions = [(0, 4, True), (2, 16, False), (3, 16, False), (5, 8, False)]
    _scaled, mapping = _build_chord_scale_map(positions, bar_width=8, content_width=10)
    assert mapping[3] - mapping[2] >= 1
    assert mapping[5] - mapping[3] >= 2


def test_scale_chord_row_aligns_notes_to_shared_columns() -> None:
    positions = [(0, 4, True), (2, 16, False), (3, 16, False), (5, 8, False)]
    _scaled, mapping = _build_chord_scale_map(positions, bar_width=8, content_width=10)

    row_a = list("--e-f-e-")
    row_b = list("--a-b---")
    scaled_a = _scale_chord_row(
        row_a,
        fill_char="-",
        src_to_dest=mapping,
        bar_width=8,
        content_width=10,
    )
    scaled_b = _scale_chord_row(
        row_b,
        fill_char="-",
        src_to_dest=mapping,
        bar_width=8,
        content_width=10,
    )
    assert scaled_a[mapping[2]] == "e"
    assert scaled_b[mapping[2]] == "a"
    assert scaled_a[mapping[3]] == "f"
    assert scaled_b[mapping[3]] == "b"


def test_scale_chord_row_avoids_note_clumping_on_collision() -> None:
    # Force two nearby source notes to compress into a tiny content width.
    row = list("-ca-----")
    scaled = _scale_chord_row(
        row,
        fill_char="-",
        src_to_dest={},
        bar_width=8,
        content_width=3,
    )
    text = "".join(scaled)
    assert "c" in text
    assert "a" in text
    assert text.count("c") == 1
    assert text.count("a") == 1


def test_place_duration_cells_aligned_keeps_stem_anchor() -> None:
    row = [" " for _ in range(10)]
    _place_duration_cells_aligned(row, 0, "8")
    _place_duration_cells_aligned(row, 1, "16")
    _place_duration_cells_aligned(row, 3, "32")
    assert "".join(row).startswith("81632")


def test_required_flag_content_width_accounts_for_tails() -> None:
    positions = [(0, 8, False), (1, 16, False), (2, 8, False), (3, 8, False)]
    # spans: 2,3,2,2 plus 3 gaps => 12
    assert _required_flag_content_width(positions) == 12


def test_grid_display_map_is_monotonic() -> None:
    mapping = _grid_display_map(
        grid_width=8,
        content_width=6,
        src_to_dest={2: 4, 3: 5, 4: 3},
    )
    assert mapping == sorted(mapping)


def test_grid_display_map_does_not_skip_visual_columns() -> None:
    mapping = _grid_display_map(
        grid_width=10,
        content_width=9,
        src_to_dest={0: 0, 2: 1, 3: 2, 4: 3, 6: 4, 7: 5},
    )
    steps = [b - a for a, b in pairwise(mapping)]
    assert all(step in (0, 1) for step in steps)


def test_lachrimae_bar27_flags_do_not_collapse_to_pipes() -> None:
    root = Path(__file__).resolve().parents[1]
    piece = load_ft3(str(root / "examples" / "26_lachrimae_galliard_in_G.ft3"))
    bar = piece.bars[26]
    positions, width = _chord_positions_distinct(bar, bar_width=8, default_duration=4)
    cols = [col for col, _denom, _dot in positions]
    assert len(cols) == len(set(cols))
    filtered = _filter_redundant_positions(positions)
    content_width = _required_flag_content_width(filtered)
    flags, _stems = build_flag_rows(
        filtered,
        spacing_mode="fixed",
        display_width=content_width,
        bar_width=content_width,
        barpad=0,
        flagstyle="standard",
    )
    text = "".join(flags)
    assert "\\\\" in text
    assert "|||||" not in text
    assert width > 8


def test_lachrimae_bar1_stem_aligns_to_second_string_d() -> None:
    root = Path(__file__).resolve().parents[1]
    piece = load_ft3(str(root / "examples" / "26_lachrimae_galliard_in_G.ft3"))
    bar = piece.bars[0]
    positions, width = _chord_positions_distinct(bar, bar_width=10, default_duration=4)
    _, src_to_dest = _build_chord_scale_map(positions, bar_width=width, content_width=10)
    filtered = _filter_redundant_positions(positions)
    render_positions = [
        (src_to_dest.get(col, 0), denom, dot) for col, denom, dot in filtered
    ]
    flags, _stems = build_flag_rows(
        render_positions,
        spacing_mode="fixed",
        display_width=10,
        bar_width=10,
        barpad=0,
        flagstyle="standard",
        min_gap=0,
    )
    stem_cols = [idx for idx, ch in enumerate(flags) if ch == "|"]
    cells = bar_cells_from_chords(bar, piece.strings, width, 4, "french", french_c="normal")
    scaled_row = _scale_chord_row(
        cells[1],
        fill_char="-",
        src_to_dest=src_to_dest,
        bar_width=width,
        content_width=10,
    )
    d_col = next(idx for idx, ch in enumerate(scaled_row) if ch == "d")
    assert len(stem_cols) >= 2
    assert d_col == stem_cols[1]
