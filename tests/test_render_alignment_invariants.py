from __future__ import annotations

import pytest

from oud.core.ft3 import build_durations
from oud.core.model import Bar, Chord, Note, Piece
from oud.core.render_utils import bar_cells_from_chords, smart_group_map
from oud.core.view_model import _filter_redundant_positions, _scale_col
from oud.editor.layout import auto_system_bar_plan_with_gaps, dynamic_system_starts
from oud.ui.framebuffer import FrameBuffer
from oud.ui.render import render_piece
from oud.ui.render_helpers import apply_overrides
from oud.ui.render_system import _build_chord_scale_map, _chord_positions_distinct, _scale_chord_row
from tests.helpers_regression_cases import (
    dense_flag_alignment_piece,
    multi_bar_spacing_piece,
    piece_with_unused_then_used_bass_rows,
    regression_state,
)


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
        src_to_dest = smart_group_map(positions, ordered_flags, content_width, min_gap=2)
    else:
        _, src_to_dest = _build_chord_scale_map(
            positions,
            bar_width=grid_width,
            content_width=content_width,
            min_gap=2,
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


def test_synthetic_first_bar_time_cue_does_not_glue_equal_noteheads() -> None:
    piece = Piece(
        title="NoGlue",
        bars=[
            Bar(
                time_sig="O",
                chords=[
                    Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 2, 0)]),
                    Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 2, 0)]),
                    Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 2, 0)]),
                ],
            ),
            Bar(chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)])]),
        ],
        strings=6,
        style="french",
    )
    state = regression_state(piece, justify="smart", width=80, bar_width=10)
    state.settings["layout"] = "auto"
    state.settings["justify"] = "smart"
    state.settings["beatsnap"] = "soft"
    state.settings["flagredundant"] = "on"
    lines = _render_state_lines(state, height=18)
    staff_rows = [line for line in lines if line.count("|") >= 2 and "-" in line]
    assert staff_rows
    first_staff = staff_rows[0]
    first_bar_start = first_staff.find("|") + 1
    first_bar_end = first_staff.find("|", first_bar_start)
    assert first_bar_end > first_bar_start
    seg = first_staff[first_bar_start:first_bar_end]
    assert "cc" not in seg, seg


def test_synthetic_first_bar_time_cue_no_glue_under_denmark_like_compression() -> None:
    # Regression for the Denmark Galliard first tact shape:
    # auto/smart + beatsnap=soft + time cue in bar 1 + many bars on row can squeeze
    # repeated equal noteheads into "cc" if width planning/mapping trims too hard.
    filler = [
        Bar(
            chords=[
                Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)]),
                Chord(note_type=4, dotted=False, grid=None, notes=[Note(2, 0, 0)]),
            ],
        )
        for _ in range(10)
    ]
    piece = Piece(
        title="NoGlueDenmarkLike",
        bars=[
            Bar(
                time_sig="O",
                chords=[
                    Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 2, 0)]),
                    Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 2, 0)]),
                    Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 2, 0)]),
                ],
            ),
            *filler,
        ],
        strings=8,
        style="french",
    )
    state = regression_state(piece, justify="smart", width=121, bar_width=10)
    state.settings["layout"] = "auto"
    state.settings["justify"] = "smart"
    state.settings["beatsnap"] = "soft"
    state.settings["flagredundant"] = "on"
    state.settings["flagstems"] = "double"
    state.settings["timesigstyle"] = "symbol"
    lines = _render_state_lines(state, height=24)
    staff_rows = [line for line in lines if line.count("|") >= 2 and "-" in line]
    assert staff_rows
    first_staff = staff_rows[0]
    first_bar_start = first_staff.find("|") + 1
    first_bar_end = first_staff.find("|", first_bar_start)
    assert first_bar_end > first_bar_start
    seg = first_staff[first_bar_start:first_bar_end]
    assert "cc" not in seg, seg


@pytest.mark.parametrize("justify", ["smart", "stretch", "compact"])
def test_synthetic_dense_bar_no_lonely_stems_and_no_flag_collapse(justify: str) -> None:
    state = regression_state(dense_flag_alignment_piece(), justify=justify, bar_width=12)
    state.settings["layout"] = "auto"
    state.settings["justify"] = justify
    state.settings["barpad"] = "1"
    state.settings["flagredundant"] = "on"
    state.bar_width = max(state.bar_width, 10)

    flag_cols, scaled_rows = _flag_cols_and_rows(state, 0)
    assert flag_cols, justify
    assert len(flag_cols) == len(set(flag_cols)), (justify, flag_cols)
    for col in flag_cols:
        assert any(row[col] not in ("-", " ") for row in scaled_rows), (justify, col)


@pytest.mark.parametrize("justify", ["smart", "stretch"])
def test_synthetic_dense_bar_flags_anchor_to_note_onsets_strict(justify: str) -> None:
    state = regression_state(dense_flag_alignment_piece(), justify=justify, bar_width=12)
    state.settings["layout"] = "auto"
    state.settings["justify"] = justify
    state.settings["barpad"] = "1"
    state.settings["flagredundant"] = "on"
    state.bar_width = max(state.bar_width, 10)

    flag_cols, scaled_rows = _flag_cols_and_rows(state, 0)
    assert flag_cols
    # Strict: every rendered flag column must be directly above a real note glyph.
    for col in flag_cols:
        col_glyphs = [row[col] for row in scaled_rows]
        assert any(ch not in ("-", " ", "|") for ch in col_glyphs), (justify, col, col_glyphs)


def _render_state_lines(state, *, height: int = 24) -> list[str]:
    fb = FrameBuffer(height, state.screen_width or 120)
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


def test_synthetic_system_inlines_time_sig() -> None:
    state = regression_state(piece_with_unused_then_used_bass_rows(), justify="stretch", width=80, bar_width=10)
    state.settings["tuning"] = "g2c3f3a3d4g4d2"
    lines = _render_state_lines(state)
    # Time signature should be inlined into a staff row, not on a standalone row.
    assert any(("C" in line or "O" in line) and "|" in line and "-" in line for line in lines)
    assert not any(line.strip() in {"C", "O", "3/4", "4/4"} for line in lines[:10])


@pytest.mark.parametrize("justify", ["smart", "stretch"])
def test_synthetic_multi_bar_no_broken_bar_seams(justify: str) -> None:
    state = regression_state(multi_bar_spacing_piece(), justify=justify, width=120, bar_width=12)
    lines = _render_state_lines(state, height=26)
    staff_rows = [line for line in lines if "-" in line and "|" in line]
    assert staff_rows
    # Broken seam pattern between adjacent bars must never appear.
    assert all("|  |" not in row for row in staff_rows)


@pytest.mark.parametrize("justify", ["smart", "stretch"])
def test_synthetic_multi_bar_staff_rows_reach_right_edge(justify: str) -> None:
    width = 120
    state = regression_state(multi_bar_spacing_piece(), justify=justify, width=width, bar_width=12)
    lines = _render_state_lines(state, height=26)
    staff_rows = [line for line in lines if "-" in line and "|" in line]
    assert staff_rows
    assert all(row.rfind("|") == width - 2 for row in staff_rows)


def test_synthetic_staff_rows_keep_dash_before_right_barline() -> None:
    width = 120
    state = regression_state(multi_bar_spacing_piece(), justify="stretch", width=width, bar_width=12)
    lines = _render_state_lines(state, height=26)
    staff_rows = [line for line in lines if "-" in line and "|" in line]
    assert staff_rows
    for row in staff_rows:
        right = row.rfind("|")
        if right <= 0:
            continue
        assert row[right - 1] == "-", row


def test_synthetic_final_frame_smart_stem_anchors_have_notes_under() -> None:
    state = regression_state(multi_bar_spacing_piece(), justify="smart", width=120, bar_width=12)
    lines = _render_state_lines(state, height=26)
    # Find the first rendered staff row dynamically (layout rows vary with settings).
    staff_start = next(
        idx
        for idx, line in enumerate(lines)
        if line.count("|") >= 2 and line.count("-") >= 8
    )
    flag_row = lines[staff_start - 2]
    staff_rows = lines[staff_start : staff_start + 6]
    assert len(staff_rows) == 6
    barlines = [idx for idx, ch in enumerate(staff_rows[0]) if ch == "|"]
    assert len(barlines) >= 3
    for i in range(len(barlines) - 1):
        x0 = barlines[i] + 1
        x1 = barlines[i + 1]
        seg_flag = flag_row[x0:x1]
        seg_staff = [row[x0:x1] for row in staff_rows]
        for col, ch in enumerate(seg_flag):
            if ch != "|":
                continue
            under = [row[col] for row in seg_staff]
            assert any(g not in ("-", " ", "|") for g in under), (i, col, seg_flag, under)


@pytest.mark.parametrize("justify", ["smart", "stretch"])
def test_synthetic_dense_bar_no_event_column_merge(justify: str) -> None:
    state = regression_state(dense_flag_alignment_piece(), justify=justify, bar_width=12)
    bar_index = 0
    state.settings["layout"] = "auto"
    state.settings["justify"] = justify
    state.settings["barpad"] = "1"
    state.settings["flagredundant"] = "on"
    state.bar_width = max(state.bar_width, 12)

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
    visible_cols = sorted(
        {
            col
            for col in range(grid_width)
            if any(cells[s_idx][col] not in ("-", " ") for s_idx in range(state.piece.strings))
        },
    )
    assert visible_cols
    content_width = _content_width_for_bar(state, bar_index)
    ordered_flags = sorted(_filter_redundant_positions(positions), key=lambda item: item[0])
    if justify == "smart":
        src_to_dest = smart_group_map(positions, ordered_flags, content_width)
    else:
        _, src_to_dest = _build_chord_scale_map(
            positions,
            bar_width=grid_width,
            content_width=content_width,
            min_gap=1,
        )
    mapped = [src_to_dest.get(col, _scale_col(col, grid_width, content_width)) for col in visible_cols]
    assert len(mapped) == len(set(mapped))
