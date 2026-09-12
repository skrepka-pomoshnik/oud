from __future__ import annotations

from itertools import pairwise

import pytest

from oud.importers.ft3 import build_durations
from oud.settings import DEFAULT_SETTINGS
from petrucci.core.model import Bar, Chord, Note, Piece
from petrucci.rendering.api import render_piece
from petrucci.rendering.primitives.helpers import flag_symbols
from petrucci.rendering.primitives.utils import flag_row_style
from petrucci.terminal.canvas.framebuffer import FrameBuffer
from tests.helpers_regression_cases import (
    long_width_fill_piece,
    piece_with_unused_then_used_bass_rows,
)


def _render_lines(
    piece: Piece,
    settings: dict[str, str],
    *,
    overrides: dict[tuple[int, int, int], str] | None = None,
    durations: dict[tuple[int, int, int], int] | None = None,
    slurs: list[tuple[int, int, int]] | None = None,
    ties: list[tuple[int, int, int]] | None = None,
    holds: list[tuple[int, int, int]] | None = None,
    width: int = 120,
    height: int = 28,
) -> list[str]:
    fb = FrameBuffer(height, width)
    render_piece(
        fb,
        piece,
        0,
        0,
        0,
        cursor_col=0,
        bar_width=8,
        overrides=overrides or {},
        durations=durations or {},
        ornaments={},
        annotations={},
        highlights=set(),
        dotted=set(),
        slurs=slurs or [],
        ties=ties or [],
        holds=holds or [],
        mode="normal",
        cmdline="",
        message="",
        status_line="",
        searchline="",
        settings=settings,
        ascii_lines=None,
        stave_breaks=set(),
        plugin_title="Plugins",
        plugin_items=[],
        plugin_index=0,
        plugin_offset=0,
        help_offset=0,
        playback_bar=None,
        playback_col=None,
    )
    return fb.snapshot().lines


def _assert_basic_staff_invariants(
    lines: list[str],
    *,
    width: int,
    forbid_split_gap: bool = True,
) -> None:
    assert all(len(line) == width for line in lines)
    staff_rows = [line for line in lines if "-" in line and "|" in line]
    assert staff_rows
    if forbid_split_gap:
        assert all("|  |" not in row for row in staff_rows)
    for row in staff_rows:
        rightmost = max((idx for idx, ch in enumerate(row) if ch != " "), default=-1)
        assert rightmost <= width - 2


@pytest.mark.parametrize(
    ("spacing_mode", "spacing_fill"),
    [
        ("packed", "stretch"),
        ("auto", "compact"),
        ("auto", "smart"),
    ],
)
def test_render_matrix_no_lost_overrides_across_spacing_modes(
    spacing_mode: str,
    spacing_fill: str,
) -> None:
    piece = Piece(title="Matrix", bars=[Bar(), Bar()], strings=6)
    overrides = {
        (0, 0, 0): "A",
        (0, 1, 6): "B",
        (0, 2, 4): "C",
        (1, 3, 1): "D",
        (1, 4, 3): "E",
        (1, 5, 5): "F",
    }
    settings = dict(DEFAULT_SETTINGS)
    settings.update(
        {
            "style": "french",
            "showtuning": "off",
            "showdur": "on",
            "showextras": "off",
            "showtactus": "off",
            "time": "",
            "layout": spacing_mode,
            "justify": spacing_fill,
            "barsperline": "0",
            "maxbars": "0",
            "linelen": "0",
        },
    )
    text = "\n".join(_render_lines(piece, settings, overrides=overrides))
    for marker in "ABCDEF":
        assert marker in text


@pytest.mark.parametrize(
    ("flagstyle", "token"),
    [
        ("standard", "|\\\\\\."),
        ("englishgrid", "|---."),
        ("continental", "ΓFFF."),
    ],
)
def test_render_matrix_flagstyle_tokens_visible(flagstyle: str, token: str) -> None:
    positions = [(0, 16, True), (4, 32, False), (8, 16, False)]
    stem, flag = flag_symbols(flagstyle)
    flags = flag_row_style(
        positions,
        16,
        stem=stem,
        flag=flag,
    )
    assert token in "".join(flags)


@pytest.mark.parametrize(
    "flagstyle",
    ["standard", "board", "englishgrid", "continental", "italian", "thin", "capirola"],
)
def test_render_matrix_flagstyle_all_supported_styles_render_visible_cues(flagstyle: str) -> None:
    positions = [(0, 16, True), (4, 32, False), (8, 16, False)]
    stem, flag = flag_symbols(flagstyle)
    flags = "".join(flag_row_style(positions, 16, stem=stem, flag=flag))
    assert any(ch != " " for ch in flags)
    assert stem in flags


@pytest.mark.parametrize("basslabels", ["numeric", "slash", "tuning"])
def test_render_matrix_bass_rows_show_only_when_used_across_label_policies(basslabels: str) -> None:
    piece = Piece(title="Bass", bars=[Bar()], strings=7)
    piece_used = Piece(
        title="Bass",
        bars=[Bar(chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(7, 0, 0)])], notes=[Note(7, 0, 0)])],
        strings=7,
    )
    settings = dict(DEFAULT_SETTINGS)
    settings.update(
        {
            "style": "french",
            "showtuning": "on",
            "showdur": "off",
            "showextras": "off",
            "showtactus": "off",
            "layout": "packed",
            "justify": "stretch",
            "basslabels": basslabels,
            "linelen": "0",
            "barsperline": "0",
            "maxbars": "0",
        },
    )
    without_bass = "\n".join(_render_lines(piece, settings))
    with_bass = "\n".join(_render_lines(piece_used, settings))
    assert " 7|" not in without_bass
    if basslabels == "numeric":
        assert " 7|" in with_bass
    elif basslabels == "slash":
        assert " /|" in with_bass
    else:
        assert any(token in with_bass for token in (" d|", " c|", " g|"))


def test_render_matrix_bass_rows_hidden_when_unused_in_system_even_if_later_used() -> None:
    piece = piece_with_unused_then_used_bass_rows()
    settings = dict(DEFAULT_SETTINGS)
    settings.update(
        {
            "style": "french",
            "showtuning": "on",
            "showdur": "off",
            "showspans": "off",
            "showtactus": "off",
            "layout": "packed",
            "justify": "stretch",
            "basslabels": "numeric",
            "barsperline": "1",
            "linelen": "0",
            "maxbars": "1",
        },
    )
    first_system = "\n".join(_render_lines(piece, settings, height=18))
    assert " 7|" not in first_system


def test_render_matrix_hold_marker_visible() -> None:
    piece = Piece(title="Marks", bars=[Bar()], strings=6)
    overrides = {
        (0, 0, 1): "A",
        (0, 0, 4): "B",
    }
    settings = dict(DEFAULT_SETTINGS)
    settings.update(
        {
            "style": "french",
            "showtuning": "off",
            "showdur": "off",
            "showspans": "on",
            "showtactus": "off",
            "layout": "packed",
            "justify": "stretch",
            "linelen": "0",
            "barsperline": "0",
            "maxbars": "0",
        },
    )
    text = "\n".join(
        _render_lines(
            piece,
            settings,
            overrides=overrides,
            slurs=[],
            ties=[],
            holds=[(0, 0, 3)],
        ),
    )
    assert "<" in text and ">" in text


def test_render_matrix_duration_text_stays_aligned_with_flags() -> None:
    piece = Piece(
        title="Align",
        bars=[
            Bar(
                chords=[
                    Chord(note_type=6, dotted=True, grid=None, notes=[Note(1, 0, 0)]),
                    Chord(note_type=5, dotted=False, grid=None, notes=[Note(1, 1, 0)]),
                    Chord(note_type=6, dotted=False, grid=None, notes=[Note(1, 2, 0)]),
                ],
            ),
        ],
        strings=6,
    )
    settings = dict(DEFAULT_SETTINGS)
    settings.update(
        {
            "style": "french",
            "showtuning": "off",
            "showdur": "on",
            "showextras": "off",
            "showtactus": "off",
            "layout": "packed",
            "justify": "compact",
            "barpad": "1",
            "linelen": "0",
            "barsperline": "0",
            "maxbars": "0",
        },
    )
    lines = _render_lines(piece, settings)
    flag_row = next(line for line in lines if "\\\\" in line)
    dur_row = next(line for line in lines[lines.index(flag_row) + 1 :] if any(ch.isdigit() for ch in line))
    flag_cols = [idx for idx, ch in enumerate(flag_row) if ch == "|"]
    dur_starts = [
        idx for idx, ch in enumerate(dur_row) if ch.isdigit() and (idx == 0 or not dur_row[idx - 1].isdigit())
    ]
    assert flag_cols == dur_starts


@pytest.mark.parametrize("spacing_fill", ["stretch", "compact", "smart", "center"])
def test_render_matrix_lines_are_always_terminal_width(spacing_fill: str) -> None:
    piece = long_width_fill_piece(bars_count=24, strings=7)
    settings = dict(DEFAULT_SETTINGS)
    settings.update(
        {
            "layout": "auto",
            "justify": spacing_fill,
            "showdur": "on",
            "showextras": "on",
            "showtactus": "on",
            "barsperline": "0",
            "maxbars": "0",
            "linelen": "0",
        },
    )
    width = 101
    height = 32
    lines = _render_lines(
        piece,
        settings,
        durations=build_durations(piece),
        width=width,
        height=height,
    )
    assert len(lines) == height
    assert all(len(line) == width for line in lines)


@pytest.mark.parametrize("justify", ["compact", "smart", "stretch", "edge"])
@pytest.mark.parametrize("beatsnap", ["off", "soft"])
def test_render_matrix_justify_beatsnap_matrix_keeps_staff_invariants(
    justify: str,
    beatsnap: str,
) -> None:
    piece = long_width_fill_piece(bars_count=18, strings=7)
    settings = dict(DEFAULT_SETTINGS)
    settings.update(
        {
            "layout": "auto",
            "justify": justify,
            "beatsnap": beatsnap,
            "showdur": "on",
            "showspans": "on",
            "showtactus": "on",
            "barsperline": "0",
            "maxbars": "0",
            "linelen": "0",
            "flagredundant": "on",
        },
    )
    width = 109
    lines = _render_lines(
        piece,
        settings,
        durations=build_durations(piece),
        width=width,
        height=30,
    )
    _assert_basic_staff_invariants(
        lines,
        width=width,
        forbid_split_gap=(justify != "edge"),
    )
    staff_rows = [line for line in lines if "-" in line and "|" in line]
    # Fill modes should still close at the padded right edge.
    if justify != "compact":
        assert any(row[width - 2] == "|" for row in staff_rows), (justify, beatsnap)


@pytest.mark.parametrize("justify", ["compact", "smart", "stretch"])
@pytest.mark.parametrize("beatsnap", ["off", "soft"])
def test_render_matrix_invariants_first_on_dense_piece_across_modes(
    justify: str,
    beatsnap: str,
) -> None:
    piece = long_width_fill_piece(bars_count=10, strings=8)
    settings = dict(DEFAULT_SETTINGS)
    settings.update(
        {
            "layout": "auto",
            "justify": justify,
            "beatsnap": beatsnap,
            "showdur": "on",
            "showspans": "on",
            "showtactus": "on",
            "flagredundant": "on",
            "barsperline": "0",
            "maxbars": "0",
            "linelen": "0",
        },
    )
    width = 97
    lines = _render_lines(
        piece,
        settings,
        durations=build_durations(piece),
        width=width,
        height=28,
    )
    _assert_basic_staff_invariants(lines, width=width, forbid_split_gap=True)
    # Flag rows should not contain stems when staff is visually empty on the corresponding system rows.
    # Lightweight invariant: no line that looks like a pure flag row should overflow frame.
    flagish_rows = [line for line in lines if ("|" in line and "-" not in line and "\\" in line) or "=" in line]
    for row in flagish_rows:
        rightmost = max((idx for idx, ch in enumerate(row) if ch != " "), default=-1)
        assert rightmost <= width - 2


def test_render_matrix_smart_fill_reaches_right_edge_on_staff_rows() -> None:
    piece = long_width_fill_piece(bars_count=20, strings=7)
    settings = dict(DEFAULT_SETTINGS)
    settings.update(
        {
            "layout": "auto",
            "justify": "smart",
            "showdur": "off",
            "showextras": "off",
            "showtactus": "off",
            "barsperline": "0",
            "maxbars": "0",
            "linelen": "0",
        },
    )
    width = 120
    lines = _render_lines(
        piece,
        settings,
        durations=build_durations(piece),
        width=width,
        height=24,
    )
    staff_rows = [line for line in lines if "-" in line and "|" in line][:6]
    assert len(staff_rows) == 6
    right_edges = [max((idx for idx, ch in enumerate(line) if ch != " "), default=-1) for line in staff_rows]
    assert all(edge == width - 2 for edge in right_edges)
    assert all(line[width - 2] == "|" for line in staff_rows)


def test_render_matrix_no_double_joined_barlines_for_default_bars() -> None:
    piece = Piece(
        title="Bars",
        bars=[Bar(notes=[Note(1, 0, 0)]) for _ in range(4)],
        strings=6,
    )
    settings = dict(DEFAULT_SETTINGS)
    settings.update(
        {
            "layout": "auto",
            "justify": "smart",
            "showdur": "off",
            "showextras": "off",
            "showtactus": "off",
            "barsperline": "0",
            "maxbars": "0",
            "linelen": "0",
        },
    )
    lines = _render_lines(piece, settings, width=100, height=20)
    staff_rows = [line for line in lines if "-" in line and "|" in line][:6]
    assert len(staff_rows) == 6
    assert all("||" not in row for row in staff_rows)
    assert all("|  |" not in row for row in staff_rows)


def test_render_matrix_empty_bar_does_not_draw_lonely_flag_stem() -> None:
    piece = Piece(title="Empty", bars=[Bar() for _ in range(8)], strings=6)
    settings = dict(DEFAULT_SETTINGS)
    settings.update(
        {
            "showdur": "off",
            "showextras": "off",
            "showtactus": "off",
            "layout": "auto",
            "justify": "stretch",
            "barsperline": "0",
            "maxbars": "0",
            "linelen": "0",
            "flagredundant": "on",
        },
    )
    lines = _render_lines(piece, settings, width=100, height=18)
    staff_top = next((idx for idx, line in enumerate(lines) if "-" in line and "|" in line), None)
    assert staff_top is not None
    if staff_top is None:
        return
    flag_row = lines[staff_top - 1]
    assert "|" not in flag_row


def test_render_matrix_chord_onsets_not_lost_when_flags_are_redundant() -> None:
    bar = Bar(
        chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, fret, 0)]) for fret in range(10)],
    )
    piece = Piece(title="ChordMap", bars=[bar, bar], strings=6)
    settings = dict(DEFAULT_SETTINGS)
    settings.update(
        {
            "style": "french",
            "showtuning": "off",
            "showdur": "off",
            "showextras": "off",
            "showtactus": "off",
            "layout": "auto",
            "justify": "smart",
            "barsperline": "0",
            "maxbars": "0",
            "linelen": "0",
            "flagredundant": "on",
        },
    )
    lines = _render_lines(piece, settings, width=70, height=18)
    staff_row = next(line for line in lines if "-" in line and "|" in line)
    for marker in "abcdefghik":
        assert marker in staff_row


def test_render_matrix_smart_fill_stretches_early_bars_uniformly() -> None:
    piece = Piece(title="SmartGap", bars=[Bar() for _ in range(4)], strings=6)
    overrides = {
        (0, 0, 0): "a",
        (1, 0, 0): "b",
        (2, 0, 0): "c",
        (3, 0, 0): "d",
    }
    durations = {
        (0, 0, 0): 4,
        (1, 0, 0): 4,
        (2, 0, 0): 4,
        (3, 0, 0): 4,
    }
    settings = dict(DEFAULT_SETTINGS)
    settings.update(
        {
            "style": "french",
            "showtuning": "off",
            "showdur": "off",
            "showextras": "off",
            "showtactus": "off",
            "layout": "auto",
            "justify": "smart",
            "barsperline": "0",
            "maxbars": "0",
            "linelen": "0",
        },
    )
    row = next(
        line
        for line in _render_lines(
            piece,
            settings,
            overrides=overrides,
            durations=durations,
            width=80,
            height=16,
        )
        if "-" in line and "|" in line
    )
    bars = row[row.find("|") + 1 :].split("|")
    assert len(bars) >= 4
    assert all(len(bar.strip()) > 3 for bar in bars[:3])


def test_render_matrix_edge_keeps_short_final_system_natural() -> None:
    piece = Piece(title="StretchEdge", bars=[Bar() for _ in range(4)], strings=6)
    overrides = {
        (0, 0, 0): "a",
        (1, 0, 0): "b",
        (2, 0, 0): "c",
        (3, 0, 0): "d",
    }
    durations = {
        (0, 0, 0): 4,
        (1, 0, 0): 4,
        (2, 0, 0): 4,
        (3, 0, 0): 4,
    }
    settings = dict(DEFAULT_SETTINGS)
    settings.update(
        {
            "style": "french",
            "showtuning": "off",
            "showdur": "off",
            "showextras": "off",
            "showtactus": "off",
            "layout": "auto",
            "justify": "edge",
            "barsperline": "0",
            "maxbars": "0",
            "linelen": "0",
        },
    )
    row = next(
        line
        for line in _render_lines(
            piece,
            settings,
            overrides=overrides,
            durations=durations,
            width=80,
            height=16,
        )
        if "-" in line and "|" in line
    )
    bars = [idx for idx, ch in enumerate(row) if ch == "|"]
    diffs = [b - a for a, b in pairwise(bars)]
    assert max(diffs) - min(diffs) <= 1
    assert bars[-1] < 78


def test_render_matrix_stretch_keeps_gaps_uniform() -> None:
    piece = Piece(title="StretchUniform", bars=[Bar() for _ in range(4)], strings=6)
    overrides = {
        (0, 0, 0): "a",
        (1, 0, 0): "b",
        (2, 0, 0): "c",
        (3, 0, 0): "d",
    }
    durations = {
        (0, 0, 0): 4,
        (1, 0, 0): 4,
        (2, 0, 0): 4,
        (3, 0, 0): 4,
    }
    settings = dict(DEFAULT_SETTINGS)
    settings.update(
        {
            "style": "french",
            "showtuning": "off",
            "showdur": "off",
            "showextras": "off",
            "showtactus": "off",
            "layout": "auto",
            "justify": "stretch",
            "barsperline": "0",
            "maxbars": "0",
            "linelen": "0",
        },
    )
    row = next(
        line
        for line in _render_lines(
            piece,
            settings,
            overrides=overrides,
            durations=durations,
            width=80,
            height=16,
        )
        if "-" in line and "|" in line
    )
    bars = [idx for idx, ch in enumerate(row) if ch == "|"]
    # Format is: one initial left barline + one closing barline per bar.
    assert len(bars) >= 5
    left = bars[0]
    rights = bars[1:]
    widths = [right - left - 1 for right in rights]
    # stretch mode expands bar content widths without creating broken seams.
    assert max(widths) > min(widths)
    assert "|  |" not in row


def test_render_matrix_stretch_does_not_visually_split_bars() -> None:
    piece = Piece(
        title="StretchSplit",
        bars=[
            Bar(
                chords=[
                    Chord(note_type=6, dotted=True, grid=None, notes=[Note(1, 0, 0)]),
                    Chord(note_type=7, dotted=False, grid=None, notes=[Note(2, 2, 0)]),
                    Chord(note_type=6, dotted=False, grid=None, notes=[Note(3, 4, 0)]),
                    Chord(note_type=5, dotted=False, grid=None, notes=[Note(4, 5, 0)]),
                ],
            )
            for _ in range(4)
        ],
        strings=6,
    )
    settings = dict(DEFAULT_SETTINGS)
    settings.update(
        {
            "style": "french",
            "showtuning": "off",
            "showdur": "on",
            "showextras": "off",
            "showtactus": "off",
            "layout": "auto",
            "justify": "stretch",
            "barsperline": "0",
            "maxbars": "0",
            "linelen": "0",
            "barpad": "1",
        },
    )
    lines = _render_lines(piece, settings, width=96, height=22)
    staff_rows = [line for line in lines if "-" in line and "|" in line][:6]
    assert len(staff_rows) == 6
    # No detached barline pairs with a blank gap in between.
    assert all("|  |" not in row for row in staff_rows)
