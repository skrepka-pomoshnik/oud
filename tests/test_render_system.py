from __future__ import annotations

from itertools import pairwise

from oud.core.render_utils import smart_group_map, spread_flag_positions
from oud.core.view_model import _filter_redundant_positions, bar_cells_from_chords
from oud.editor.layout import auto_system_bar_plan_with_gaps, dynamic_system_starts
from oud.ui.render_bar import build_flag_rows
from oud.ui.render_system import (
    _build_chord_scale_map,
    _chord_positions_distinct,
    _grid_display_map,
    _place_duration_cells_aligned,
    _required_flag_content_width,
    _scale_chord_row,
)
from tests.helpers_regression_cases import regression_state, stem_alignment_problem_piece


def test_build_chord_scale_map_keeps_ordered_columns() -> None:
    positions = [(0, 4, True), (2, 16, False), (3, 16, False), (5, 8, False)]
    scaled, mapping = _build_chord_scale_map(positions, bar_width=8, content_width=10)
    assert len(scaled) == len(positions)
    assert mapping[0] < mapping[2] < mapping[3] < mapping[5]


def test_build_chord_scale_map_separates_duration_groups() -> None:
    positions = [(0, 4, True), (2, 16, False), (3, 16, False), (5, 8, False)]
    _scaled, mapping = _build_chord_scale_map(positions, bar_width=8, content_width=10)
    assert mapping[3] - mapping[2] >= 1
    assert mapping[5] - mapping[3] >= 1


def test_scale_chord_row_aligns_notes_to_shared_columns() -> None:
    positions = [(0, 4, True), (2, 16, False), (3, 16, False), (5, 8, False)]
    _scaled, mapping = _build_chord_scale_map(positions, bar_width=8, content_width=10)

    row_a = list("--ef--e-")
    row_b = list("--ab----")
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


def test_scale_chord_row_keeps_anchor_without_drift_on_collision() -> None:
    # Force two source notes to map to the same destination.
    row = list("-ca-----")
    scaled = _scale_chord_row(
        row,
        fill_char="-",
        src_to_dest={},
        bar_width=8,
        content_width=3,
    )
    text = "".join(scaled)
    # No nearest-free-slot drift: one anchored cell remains (last write wins).
    assert text == "a--"


def test_place_duration_cells_aligned_keeps_stem_anchor() -> None:
    row = [" " for _ in range(10)]
    _place_duration_cells_aligned(row, 0, "8")
    _place_duration_cells_aligned(row, 1, "16")
    _place_duration_cells_aligned(row, 3, "32")
    assert "".join(row).startswith("81632")


def test_required_flag_content_width_accounts_for_tails() -> None:
    positions = [(0, 8, False), (1, 16, False), (2, 8, False), (3, 8, False)]
    # Current cue mapping: 8th=3 cells, 16th=4 cells; plus gaps => 16 total.
    assert _required_flag_content_width(positions) == 16


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


def test_dense_synthetic_flags_do_not_collapse_to_pipes() -> None:
    piece = stem_alignment_problem_piece()
    bar = piece.bars[10]
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
    assert any(ch in "\\/" for ch in text)
    assert "|||||" not in text
    assert width >= 8


def test_first_synthetic_bar_stem_aligns_to_second_string_note() -> None:
    piece = stem_alignment_problem_piece()
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
    note_cols = [idx for idx, ch in enumerate(scaled_row) if ch != "-"]
    filtered_raw_cols = [col for (col, _den, _dot) in filtered]
    target_filtered_raw = next(col for col in filtered_raw_cols if cells[1][col] != "-")
    target_col = src_to_dest.get(target_filtered_raw, -1)
    assert len(stem_cols) >= 2
    assert target_col in stem_cols
    assert target_col in note_cols


def test_smart_flags_align_with_note_columns_in_synthetic_dense_bar() -> None:
    piece = stem_alignment_problem_piece()
    bar = piece.bars[1]
    positions, width = _chord_positions_distinct(bar, bar_width=8, default_duration=4)
    ordered_flags = sorted(_filter_redundant_positions(positions), key=lambda item: item[0])
    content_width = 40
    _, src_to_dest = _build_chord_scale_map(
        positions,
        bar_width=width,
        content_width=content_width,
        min_gap=2,
    )
    render_positions = [
        (src_to_dest.get(col, 0), denom, dot) for (col, denom, dot) in ordered_flags
    ]
    final_positions = spread_flag_positions(render_positions, content_width, min_gap=1)
    final_map = {
        raw_col: final_col
        for (raw_col, _denom, _dot), (final_col, _d2, _dot2) in zip(
            ordered_flags,
            final_positions,
            strict=False,
        )
    }
    cells = bar_cells_from_chords(bar, piece.strings, width, 4, "french", french_c="normal")
    scaled_rows = [
        _scale_chord_row(
            cells[s_idx],
            fill_char="-",
            src_to_dest=final_map,
            bar_width=width,
            content_width=content_width,
        )
        for s_idx in range(piece.strings)
    ]
    for raw_col, final_col in final_map.items():
        has_note = any(cells[s_idx][raw_col] != "-" for s_idx in range(piece.strings))
        assert has_note
        assert any(row[final_col] != "-" for row in scaled_rows)


def test_synthetic_8course_bar_smart_no_lonely_stems() -> None:
    state = regression_state(stem_alignment_problem_piece(), width=120, bar_width=8, justify="smart")
    state.settings["layout"] = "auto"
    state.settings["justify"] = "smart"
    state.settings["barpad"] = "1"
    state.settings["flagredundant"] = "on"
    state.screen_width = 120
    bar_idx = 9

    starts = dynamic_system_starts(state, state.screen_width)
    start = max(value for value in starts if value <= bar_idx)
    bar_indices, bar_widths, _gaps = auto_system_bar_plan_with_gaps(
        state,
        start,
        state.screen_width,
    )
    local_idx = bar_indices.index(bar_idx)
    display_width = bar_widths[local_idx]
    content_width = max(1, display_width - 2)
    bar = state.piece.bars[bar_idx]
    positions, grid_width = _chord_positions_distinct(bar, state.bar_width, default_duration=4)
    cells = bar_cells_from_chords(
        bar,
        state.piece.strings,
        grid_width,
        4,
        state.settings.get("style", "french"),
        french_c="normal",
    )
    visible_cols = {col for col in range(grid_width) if any(cells[s][col] != "-" for s in range(state.piece.strings))}
    positions = [item for item in positions if item[0] in visible_cols]
    ordered_flags = sorted(_filter_redundant_positions(positions), key=lambda item: item[0])
    src_to_dest = smart_group_map(positions, ordered_flags, content_width)
    scaled_rows = [
        _scale_chord_row(
            cells[s_idx],
            fill_char="-",
            src_to_dest=src_to_dest,
            bar_width=grid_width,
            content_width=content_width,
        )
        for s_idx in range(state.piece.strings)
    ]
    for raw_col, _denom, _dot in ordered_flags:
        stem_col = src_to_dest[raw_col]
        assert any(row[stem_col] != "-" for row in scaled_rows), (raw_col, stem_col)


def test_all_synthetic_8course_smart_stems_have_notes_underneath() -> None:
    state = regression_state(stem_alignment_problem_piece(), width=120, bar_width=8, justify="smart")
    state.settings["layout"] = "auto"
    state.settings["justify"] = "smart"
    state.settings["barpad"] = "1"
    state.settings["flagredundant"] = "on"
    state.screen_width = 120

    for start in dynamic_system_starts(state, state.screen_width):
        bar_indices, bar_widths, _gaps = auto_system_bar_plan_with_gaps(
            state,
            start,
            state.screen_width,
        )
        for local_idx, bar_idx in enumerate(bar_indices):
            bar = state.piece.bars[bar_idx]
            if not bar.chords:
                continue
            display_width = bar_widths[local_idx]
            content_width = max(1, display_width - 2)
            positions, grid_width = _chord_positions_distinct(
                bar,
                state.bar_width,
                default_duration=4,
            )
            if not positions:
                continue
            cells = bar_cells_from_chords(
                bar,
                state.piece.strings,
                grid_width,
                4,
                state.settings.get("style", "french"),
                french_c="normal",
            )
            visible_cols = {
                col
                for col in range(grid_width)
                if any(cells[s][col] != "-" for s in range(state.piece.strings))
            }
            positions = [item for item in positions if item[0] in visible_cols]
            ordered_flags = sorted(_filter_redundant_positions(positions), key=lambda item: item[0])
            if not ordered_flags:
                continue
            src_to_dest = smart_group_map(positions, ordered_flags, content_width)
            scaled_rows = [
                _scale_chord_row(
                    cells[s_idx],
                    fill_char="-",
                    src_to_dest=src_to_dest,
                    bar_width=grid_width,
                    content_width=content_width,
                )
                for s_idx in range(state.piece.strings)
            ]
            for raw_col, _denom, _dot in ordered_flags:
                stem_col = src_to_dest[raw_col]
                assert any(row[stem_col] != "-" for row in scaled_rows), (
                    bar_idx,
                    raw_col,
                    stem_col,
                )
