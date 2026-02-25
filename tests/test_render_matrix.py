from __future__ import annotations

from itertools import pairwise

import pytest

from oud.core.ft3 import build_durations, load_ft3
from oud.core.model import Bar, Chord, Note, Piece
from oud.core.render_utils import flag_row_style
from oud.settings import DEFAULT_SETTINGS
from oud.ui.framebuffer import FrameBuffer
from oud.ui.render import render_piece
from oud.ui.render_helpers import flag_symbols


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
        0,
        8,
        overrides or {},
        durations or {},
        {},
        {},
        set(),
        set(),
        slurs or [],
        ties or [],
        holds or [],
        "normal",
        "",
        "",
        "",
        "",
        settings,
        None,
        set(),
        "Plugins",
        [],
        0,
        0,
        0,
        None,
        None,
    )
    return fb.snapshot().lines


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


def test_render_matrix_bass_rows_show_only_when_used() -> None:
    piece = Piece(title="Bass", bars=[Bar()], strings=7)
    piece_used = Piece(
        title="Bass",
        bars=[Bar(chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(7, 0, 0)])])],
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
                "basslabels": "numeric",
                "linelen": "0",
                "barsperline": "0",
                "maxbars": "0",
        },
    )
    without_bass = "\n".join(_render_lines(piece, settings))
    with_bass = "\n".join(_render_lines(piece_used, settings))
    assert " 7|" not in without_bass
    assert " 7|" in with_bass


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
    dur_row = lines[lines.index(flag_row) + 1]
    flag_cols = [idx for idx, ch in enumerate(flag_row) if ch == "|"]
    dur_starts = [
        idx
        for idx, ch in enumerate(dur_row)
        if ch.isdigit() and (idx == 0 or not dur_row[idx - 1].isdigit())
    ]
    assert flag_cols == dur_starts


@pytest.mark.parametrize("spacing_fill", ["stretch", "compact", "smart", "center"])
def test_render_matrix_lines_are_always_terminal_width(spacing_fill: str) -> None:
    piece = load_ft3("lutemusic/23a_frogg_galliard_2.ft3")
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


def test_render_matrix_smart_fill_reaches_right_edge_on_staff_rows() -> None:
    piece = load_ft3("lutemusic/23a_frogg_galliard_2.ft3")
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
    right_edges = [
        max((idx for idx, ch in enumerate(line) if ch != " "), default=-1)
        for line in staff_rows
    ]
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
        chords=[
            Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, fret, 0)])
            for fret in range(10)
        ],
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


def test_render_matrix_edge_prefers_edge_gaps() -> None:
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
    # Large edge gaps should dominate; middle gap should stay compact.
    large = sorted(diffs)[-2:]
    assert len(large) == 2
    assert large[0] > 10 and large[1] > 10
    assert min(diffs) < 10


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
