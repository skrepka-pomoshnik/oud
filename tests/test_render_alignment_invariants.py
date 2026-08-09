from __future__ import annotations

from itertools import pairwise

import pytest

from oud.editor.navigation.layout import auto_system_bar_plan_with_gaps, dynamic_system_starts
from oud.importers.ft3 import build_durations
from petrucci.core.model import Bar, Chord, Note, Piece
from petrucci.rendering.api import render_piece
from petrucci.rendering.primitives.geometry import _scale_chord_row
from petrucci.rendering.primitives.helpers import apply_overrides
from petrucci.rendering.primitives.spacing import (
    build_chord_scale_map as _build_chord_scale_map,
)
from petrucci.rendering.primitives.spacing import (
    chord_positions_distinct as _chord_positions_distinct,
)
from petrucci.rendering.primitives.utils import bar_cells_from_chords, smart_group_map
from petrucci.terminal.canvas.framebuffer import FrameBuffer
from petrucci.terminal.view.model import _filter_redundant_positions, _scale_col
from tests.helpers_regression_cases import (
    dense_auftact_piece,
    dense_flag_alignment_piece,
    mk_bar,
    mk_chord,
    mk_piece,
    multi_bar_spacing_piece,
    piece_with_unused_then_used_bass_rows,
    regression_state,
)


def _usable_width_for_state(state) -> int:
    left_margin = 3
    max_width = state.screen_width
    linelen = state.settings.get("linelen", "")
    if linelen.isdigit() and int(linelen) > 0:
        max_width = min(max_width, int(linelen))
    right_padding = 1
    return max(1, max_width - left_margin - right_padding)


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


@pytest.mark.parametrize("justify", ["stretch", "smart", "edge"])
def test_auto_system_plan_only_fills_nonfinal_width_limited_systems(justify: str) -> None:
    state = regression_state(multi_bar_spacing_piece(), justify=justify, width=121, bar_width=12)
    state.settings["layout"] = "auto"
    state.settings["justify"] = justify
    usable_width = _usable_width_for_state(state)
    starts = dynamic_system_starts(state, state.screen_width)
    assert starts
    for start in starts:
        bar_indices, bar_widths, gaps = auto_system_bar_plan_with_gaps(state, start, state.screen_width)
        if not bar_indices:
            continue
        assert len(bar_indices) == len(bar_widths)
        assert len(gaps) == max(0, len(bar_widths) - 1)
        planned_width = sum(bar_widths) + sum(gaps)
        assert planned_width <= usable_width
        if bar_indices[-1] + 1 < len(state.piece.bars):
            assert planned_width == usable_width


def test_auto_system_plan_compact_does_not_exceed_usable_width() -> None:
    state = regression_state(multi_bar_spacing_piece(), justify="compact", width=121, bar_width=12)
    state.settings["layout"] = "auto"
    state.settings["justify"] = "compact"
    usable_width = _usable_width_for_state(state)
    starts = dynamic_system_starts(state, state.screen_width)
    assert starts
    for start in starts:
        _idx, bar_widths, gaps = auto_system_bar_plan_with_gaps(state, start, state.screen_width)
        if not bar_widths:
            continue
        assert sum(bar_widths) + sum(gaps) <= usable_width


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


@pytest.mark.parametrize("time_sig", ["C", "O", "3/4"])
@pytest.mark.parametrize("justify", ["smart", "stretch"])
def test_geometry_time_cue_auftact_dense_first_beats_no_overlap(
    time_sig: str,
    justify: str,
) -> None:
    state = regression_state(dense_auftact_piece(time_sig), justify=justify, width=100, bar_width=10)
    state.settings["layout"] = "auto"
    state.settings["justify"] = justify
    state.settings["beatsnap"] = "soft"
    state.settings["flagredundant"] = "on"
    state.settings["timesigstyle"] = "numeric" if time_sig == "3/4" else "symbol"
    lines = _render_state_lines(state, height=20)
    staff_rows = [line for line in lines if "-" in line and line.count("|") >= 2]
    assert staff_rows
    first_staff = staff_rows[0]
    first_bar_start = first_staff.find("|") + 1
    first_bar_end = first_staff.find("|", first_bar_start)
    assert first_bar_end > first_bar_start
    seg = first_staff[first_bar_start:first_bar_end]
    # Cue is in the auftact lane and must not glue to first note glyph in dense starts.
    assert "Ca" not in seg and "Oa" not in seg and "3a" not in seg, (time_sig, justify, seg)


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


def test_synthetic_beatsnap_soft_does_not_introduce_left_slack_on_cue_free_bar() -> None:
    piece = Piece(
        title="BeatSnapNoSlack",
        bars=[
            Bar(chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)])], time_sig="C"),
            Bar(
                chords=[
                    Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 2, 0)]),
                    Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 2, 0)]),
                    Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 2, 0)]),
                    Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 2, 0)]),
                ],
            ),
        ],
        strings=6,
        style="french",
    )
    state = regression_state(piece, justify="smart", width=90, bar_width=10)
    state.settings["layout"] = "auto"
    state.settings["beatsnap"] = "soft"
    state.settings["showdur"] = "off"
    state.settings["showtactus"] = "off"
    state.settings["showextras"] = "off"
    lines = _render_state_lines(state, height=18)
    staff_rows = [line for line in lines if line.count("|") >= 3 and "-" in line]
    assert staff_rows
    row = staff_rows[0]
    bars = [idx for idx, ch in enumerate(row) if ch == "|"]
    assert len(bars) >= 3
    second_seg = row[bars[1] + 1 : bars[2]]
    first_note = next((i for i, ch in enumerate(second_seg) if ch not in ("-", " ")), None)
    assert first_note is not None
    assert first_note <= 2, second_seg


@pytest.mark.parametrize("dotplacement", ["afterflag", "afterstem"])
def test_flag_dotplacement_modes_keep_right_edge_alignment_and_visible_dot(
    dotplacement: str,
) -> None:
    piece = Piece(
        title="DotPolicy",
        bars=[
            Bar(
                chords=[
                    Chord(note_type=6, dotted=True, grid=None, notes=[Note(1, 0, 0)]),
                    Chord(note_type=7, dotted=False, grid=None, notes=[Note(2, 1, 0)]),
                    Chord(note_type=6, dotted=False, grid=None, notes=[Note(3, 2, 0)]),
                ],
            ),
            Bar(
                chords=[Chord(note_type=5, dotted=False, grid=None, notes=[Note(1, 0, 0)])],
            ),
        ],
        strings=6,
        style="french",
    )
    state = regression_state(piece, justify="smart", width=80, bar_width=12)
    state.settings["layout"] = "auto"
    state.settings["dotplacement"] = dotplacement
    lines = _render_state_lines(state, height=18)
    flagged = [line for line in lines if "|" in line and ("\\" in line or "." in line)]
    staff = [line for line in lines if line.count("|") >= 2 and "-" in line]
    assert flagged
    assert any("." in line for line in flagged)
    assert staff
    right_edges = {line.rfind("|") for line in staff}
    assert len(right_edges) == 1


@pytest.mark.parametrize("justify", ["smart", "stretch"])
def test_synthetic_multi_bar_no_broken_bar_seams(justify: str) -> None:
    state = regression_state(multi_bar_spacing_piece(), justify=justify, width=120, bar_width=12)
    lines = _render_state_lines(state, height=26)
    staff_rows = [line for line in lines if "-" in line and "|" in line]
    assert staff_rows
    # Broken seam pattern between adjacent bars must never appear.
    assert all("|  |" not in row for row in staff_rows)


@pytest.mark.parametrize("justify", ["smart", "stretch"])
def test_synthetic_short_score_keeps_natural_right_edge(justify: str) -> None:
    width = 120
    state = regression_state(multi_bar_spacing_piece(), justify=justify, width=width, bar_width=12)
    lines = _render_state_lines(state, height=26)
    staff_rows = [line for line in lines if "-" in line and "|" in line]
    assert staff_rows
    assert all(0 < row.rfind("|") < width - 2 for row in staff_rows)


def test_collision_limited_dense_bar_system_reaches_right_edge() -> None:
    dense_bar = Bar(
        chords=[
            Chord(
                note_type=note_type,
                dotted=dotted,
                grid=grid,
                notes=[Note(string, fret, 0) for string, fret in notes],
            )
            for note_type, dotted, grid, notes in (
                (6, True, None, ((2, 2), (3, 3))),
                (7, False, None, ((2, 4),)),
                (6, False, None, ((1, 0), (3, 2))),
                (7, False, "start", ((2, 4),)),
                (7, False, "end", ((1, 0),)),
                (6, True, None, ((1, 2), (3, 0))),
                (7, False, None, ((1, 4),)),
                (6, False, None, ((1, 5),)),
                (7, False, "start", ((1, 4),)),
                (7, False, "end", ((1, 2),)),
            )
        ],
    )
    piece = Piece(
        bars=[dense_bar, *[mk_bar([mk_chord(4, [(1, 0)])]) for _ in range(20)]],
        strings=6,
    )
    width = 80
    state = regression_state(piece, justify="smart", width=width, bar_width=12)

    lines = _render_state_lines(state, height=20)
    first_system_staff = next(line for line in lines if "-" in line and "|" in line)

    assert first_system_staff.rfind("|") == width - 2


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
    staff_start = next(idx for idx, line in enumerate(lines) if line.count("|") >= 2 and line.count("-") >= 8)
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


def test_nonchord_duration_flags_anchor_only_to_visible_note_columns() -> None:
    bar = Bar(
        notes=[
            Note(raw_pos=0, string=2, fret=3),
            Note(raw_pos=0, string=3, fret=0),
            Note(raw_pos=0, string=5, fret=2),
            Note(raw_pos=0, string=2, fret=3),
            Note(raw_pos=0, string=3, fret=0),
            Note(raw_pos=0, string=5, fret=2),
            Note(raw_pos=0, string=2, fret=2),
            Note(raw_pos=0, string=2, fret=3),
            Note(raw_pos=0, string=1, fret=0),
            Note(raw_pos=0, string=5, fret=4),
        ],
        time_sig="O",
    )
    piece = Piece(title="AnchoredFlags", bars=[bar], strings=6, style="french")
    state = regression_state(piece, justify="smart", width=120, bar_width=10)
    state.settings["layout"] = "auto"
    state.settings["showdur"] = "off"
    state.settings["showspans"] = "off"
    state.settings["showtactus"] = "off"
    state.settings["flagstems"] = "single"
    state.settings["flagredundant"] = "on"
    # Explicit duration change arrives before the next note column and must anchor to
    # that note, not to an empty inherited slot.
    for col, denom in ((0, 8), (1, 16), (2, 16), (3, 16), (4, 16), (5, 4)):
        state.durations[(0, 0, col)] = denom

    lines = _render_state_lines(state, height=18)
    staff_start = next(idx for idx, line in enumerate(lines) if line.count("|") >= 2 and line.count("-") >= 8)
    flag_row = lines[staff_start - 2]
    staff_rows = lines[staff_start : staff_start + 6]
    barlines = [idx for idx, ch in enumerate(staff_rows[0]) if ch == "|"]
    assert len(barlines) >= 2
    x0 = barlines[0] + 1
    x1 = barlines[1]
    seg_flag = flag_row[x0:x1]
    seg_staff = [row[x0:x1] for row in staff_rows]
    for col, ch in enumerate(seg_flag):
        if ch != "|":
            continue
        under = [row[col] for row in seg_staff]
        assert any(g not in ("-", " ", "|") for g in under), (col, seg_flag, under)


def test_geometry_double_stem_rows_anchor_to_dense_chords() -> None:
    piece = mk_piece(
        [
            mk_bar(
                [
                    mk_chord(6, [(1, 0), (3, 2)]),
                    mk_chord(6, [(2, 1), (4, 0)]),
                    mk_chord(5, [(1, 2), (5, 1)]),
                    mk_chord(6, [(3, 3), (6, 0)]),
                    mk_chord(5, [(1, 4), (2, 2)]),
                ],
                time_sig="C",
            ),
        ],
        strings=6,
        title="DoubleStemDense",
    )
    state = regression_state(piece, justify="smart", width=100, bar_width=12)
    state.settings["layout"] = "auto"
    state.settings["showdur"] = "off"
    state.settings["showspans"] = "off"
    state.settings["showtactus"] = "off"
    state.settings["flagstems"] = "double"
    lines = _render_state_lines(state, height=18)
    staff_start = next(idx for idx, line in enumerate(lines) if line.count("|") >= 2 and line.count("-") >= 8)
    flag_row = lines[staff_start - 2]
    stem_row = lines[staff_start - 1]
    staff_rows = lines[staff_start : staff_start + 6]
    assert "|" in flag_row
    assert "|" in stem_row
    barlines = [idx for idx, ch in enumerate(staff_rows[0]) if ch == "|"]
    assert len(barlines) >= 2
    for x0, x1 in pairwise(barlines):
        seg_flag = flag_row[x0 + 1 : x1]
        seg_stem = stem_row[x0 + 1 : x1]
        seg_staff = [row[x0 + 1 : x1] for row in staff_rows]
        for col, ch in enumerate(seg_stem):
            if ch != "|":
                continue
            assert seg_flag[col] == "|" or seg_flag[col] in {"\\", "/", "="}
            under = [row[col] for row in seg_staff]
            if any(g not in ("-", " ", "|") for g in under):
                continue
            # Double-width stems may occupy a continuation column immediately to the
            # right of the onset anchor; that continuation column need not carry a
            # notehead directly underneath.
            assert col > 0 and seg_stem[col - 1] == "|", (col, seg_flag, seg_stem, under)


def test_geometry_tie_and_gliss_cues_on_chords_preserve_noteheads() -> None:
    piece = mk_piece(
        [
            mk_bar(
                [
                    mk_chord(5, [(1, 10), (3, 2), (6, 0)]),
                    mk_chord(6, [(1, 11), (4, 1)]),
                    mk_chord(6, [(1, 12), (2, 3), (5, 0)]),
                    mk_chord(5, [(1, 10), (3, 4)]),
                ],
                time_sig="O",
            ),
            mk_bar(
                [mk_chord(4, [(2, 2), (4, 0)])],
            ),
        ],
        strings=6,
        title="SpanChordGeom",
    )
    state = regression_state(piece, justify="smart", width=110, bar_width=12)
    state.settings["layout"] = "auto"
    state.settings["showspans"] = "on"
    state.settings["showtactus"] = "off"
    state.settings["showdur"] = "off"
    state.settings["glisscuestyle"] = "slash"
    state.settings["tiecuestyle"] = "bracket"
    state.settings["tienoteheads"] = "parenthesize"
    state.settings["style"] = "french"
    state.ties = [(0, 0, 2)]
    state.glisses = [(0, 1, 3)]
    lines = _render_state_lines(state, height=20)
    staff_rows = [line for line in lines if line.count("|") >= 2 and "-" in line]
    assert staff_rows
    # Multi-digit French frets 10/11/12 => l/m/n should survive cue pressure.
    text = "\n".join(lines)
    assert "l" in text and "m" in text and "n" in text
    # Tie/gliss cues should also be visible.
    assert any(ch in text for ch in ["[", "]", "(", ")", "/", "\\"])


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
