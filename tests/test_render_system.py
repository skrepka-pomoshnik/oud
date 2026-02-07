from __future__ import annotations

from pathlib import Path

from oud.core.ft3 import load_ft3
from oud.core.view_model import _filter_redundant_positions
from oud.ui.render_bar import build_flag_rows
from oud.ui.render_system import (
    _build_chord_scale_map,
    _chord_positions_distinct,
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
