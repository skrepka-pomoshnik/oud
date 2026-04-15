from __future__ import annotations

import re
import unicodedata

import pytest

from oud.core.duet_score import (
    duet_bar_mapping,
    duet_raw_bar_index,
    duet_staff_labels,
    duet_storage_mode,
    split_duet_piece_staff,
)
from oud.core.model import Bar, Chord, LyricEvent, MelodyEvent, Note, Piece
from oud.ui.adapter import Screen
from oud.ui.framebuffer import FrameBuffer
from oud.ui.render import _apply_overrides, render_piece
from oud.ui.render_text_lanes import MELODY_FILLED_NOTEHEAD_GLYPH, MELODY_NOTEHEAD_GLYPH
from oud.ui.render_vocal import melody_row_count
from tests.helpers_regression_cases import repeat_and_meter_change_piece


class _Screen(Screen):
    def __init__(self, h: int = 32, w: int = 80) -> None:
        self.h = h
        self.w = w
        self.calls: list[tuple[int, int, str, int]] = []
        self.erases = 0
        self.refreshes = 0

    def getmaxyx(self) -> tuple[int, int]:
        return self.h, self.w

    def addstr(self, y: int, x: int, text: str, attr: int = 0) -> None:
        self.calls.append((y, x, text, attr))

    def erase(self) -> None:
        self.erases += 1

    def refresh(self) -> None:
        self.refreshes += 1


def _args(mode: str = "normal"):
    piece = Piece(title="T", bars=[Bar()], strings=6)
    return {
        "stdscr": _Screen(),
        "piece": piece,
        "bar_offset": 0,
        "cursor_bar": 0,
        "cursor_string": 0,
        "cursor_col": 0,
        "bar_width": 8,
        "overrides": {},
        "durations": {},
        "ornaments": {},
        "annotations": {},
        "highlights": set(),
        "dotted": set(),
        "slurs": [],
        "ties": [],
        "holds": [],
        "mode": mode,
        "cmdline": "",
        "message": "",
        "status_line": "status",
        "searchline": "",
        "settings": {
            "style": "french",
            "showtuning": "on",
            "layout": "packed",
            "justify": "stretch",
            "barpad": "1",
            "showdur": "off",
            "showextras": "off",
            "showtactus": "off",
            "flagredundant": "on",
            "flagstems": "single",
            "flaglean": "right",
            "fretlabelmode": "auto",
            "tuninglabels": "relative",
            "basslabels": "tuning",
            "tuning": "g2c3f3a3d4g4",
            "barsperline": "3",
            "maxbars": "2",
            "measuresstep": "10",
        },
        "ascii_lines": None,
        "stave_breaks": set(),
        "plugin_title": "Plugins",
        "plugin_items": ["a"],
        "plugin_index": 0,
        "plugin_offset": 0,
        "help_offset": 0,
        "playback_bar": None,
        "playback_col": None,
    }


def _render_lines(kwargs: dict) -> list[str]:
    stdscr = kwargs.get("stdscr")
    h = getattr(stdscr, "h", 32)
    w = getattr(stdscr, "w", 80)
    fb = FrameBuffer(h, w)
    run_kwargs = dict(kwargs)
    run_kwargs["stdscr"] = fb
    render_piece(**run_kwargs)
    return fb.snapshot().lines


def _first_melody_row_idx(lines: list[str]) -> int:
    notehead_glyphs = (MELODY_NOTEHEAD_GLYPH, MELODY_FILLED_NOTEHEAD_GLYPH)
    block_rows = melody_row_count()
    for idx in range(len(lines)):
        if not lines[idx].startswith("  |"):
            continue
        if idx > 0 and lines[idx - 1].startswith("  |"):
            continue
        block = lines[idx : idx + block_rows]
        if len(block) < block_rows:
            continue
        if not all(line.startswith("  |") for line in block):
            continue
        if any(("\\" in line or any(glyph in line for glyph in notehead_glyphs) or "^" in line or "v" in line) for line in block):
            return idx
    anchor = next(
        i
        for i, line in enumerate(lines)
        if line.startswith("  |")
        and ("\\" in line or any(glyph in line for glyph in notehead_glyphs) or "^" in line or "v" in line)
    )
    while anchor > 0:
        prev = lines[anchor - 1]
        if prev.startswith("  |") or not prev.strip():
            anchor -= 1
            continue
        break
    return anchor


def _first_lyric_row(lines: list[str]) -> str:
    melody_start = _first_melody_row_idx(lines)
    return next(
        line
        for idx, line in enumerate(lines)
        if idx >= melody_start + melody_row_count()
        and line.startswith("  |")
        and re.search(r"[A-Za-z]{2,}", line)
    )


def _strip_combining(text: str) -> str:
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def test_apply_overrides_wrapper() -> None:
    cells = [list("----") for _ in range(6)]
    _apply_overrides(cells, {(0, 0, 1): "r", (0, 1, 2): "a"}, 0, 6, 4)
    assert cells[0][1] == "_"
    assert cells[1][2] == "a"


def test_render_piece_modes_and_help() -> None:
    # info
    kwargs = _args("info")
    render_piece(**kwargs)
    assert kwargs["stdscr"].refreshes == 1
    # plugin
    kwargs = _args("plugin")
    render_piece(**kwargs)
    assert kwargs["stdscr"].refreshes == 1
    # ascii preview
    kwargs = _args("normal")
    kwargs["ascii_lines"] = ["abc", "def"]
    render_piece(**kwargs)
    assert kwargs["stdscr"].refreshes == 1
    # help mode triggers second erase
    kwargs = _args("help")
    render_piece(**kwargs)
    assert kwargs["stdscr"].erases >= 2


def test_render_piece_normal_calls_systems_and_status(monkeypatch) -> None:
    called = {}

    def _fake_render_systems(*_args, **kwargs):
        called["bars_limit"] = kwargs["bars_per_line_limit"]
        called["reverse"] = kwargs["reverse_strings"]

    monkeypatch.setattr("oud.ui.render.render_systems", _fake_render_systems)
    kwargs = _args("normal")
    kwargs["settings"]["viewinvert"] = "on"
    render_piece(**kwargs)
    assert called["bars_limit"] == 2
    assert called["reverse"] is True
    assert kwargs["stdscr"].refreshes == 1


def test_render_piece_passes_explicit_barsperline_limit(monkeypatch) -> None:
    called = {}

    def _fake_render_systems(*_args, **kwargs):
        called["bars_limit"] = kwargs["bars_per_line_limit"]

    monkeypatch.setattr("oud.ui.render.render_systems", _fake_render_systems)
    kwargs = _args("normal")
    kwargs["settings"]["layout"] = "auto"
    kwargs["settings"]["barsperline"] = "4"
    kwargs["settings"]["maxbars"] = "0"
    render_piece(**kwargs)
    assert called["bars_limit"] == 4


def test_render_piece_barsperline_zero_keeps_auto_limit(monkeypatch) -> None:
    called = {}

    def _fake_render_systems(*_args, **kwargs):
        called["bars_limit"] = kwargs["bars_per_line_limit"]

    monkeypatch.setattr("oud.ui.render.render_systems", _fake_render_systems)
    kwargs = _args("normal")
    kwargs["settings"]["layout"] = "auto"
    kwargs["settings"]["barsperline"] = "0"
    kwargs["settings"]["maxbars"] = "0"
    render_piece(**kwargs)
    assert called["bars_limit"] == 0


def test_render_piece_duet_passes_staff_specific_playback_markers(monkeypatch) -> None:
    piece = Piece(
        title="Duet",
        bars=[
            Bar(chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)])]),
            Bar(chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(2, 0, 0)])]),
        ],
        strings=6,
        style="french",
        ensemble="lute 1:6-course, lute 2:6-course",
        part="score",
    )
    calls: list[list[tuple[int, int]]] = []

    def _fake_render_systems(*_args, **kwargs):
        calls.append(list(kwargs["playback_markers"]))

    monkeypatch.setattr("oud.ui.render.render_systems", _fake_render_systems)
    kwargs = _args("normal")
    kwargs["piece"] = piece
    kwargs["settings"]["duetscoreview"] = "both"
    kwargs["playback_markers"] = [(0, 1), (1, 3)]
    render_piece(**kwargs)
    assert calls == [[(0, 1)], [(0, 3)]]


def test_render_piece_duet_uses_piece_mapping_for_raw_bar_offset(monkeypatch) -> None:
    logical_bars = 20
    piece = Piece(
        title="Duet",
        bars=[
            Bar(chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, idx % 3, 0)])])
            for idx in range(logical_bars)
        ]
        + [
            Bar(chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(2, idx % 4, 0)])])
            for idx in range(logical_bars)
        ],
        strings=6,
        style="french",
        ensemble="lute 1:6-course, lute 2:6-course",
        part="score",
    )
    bar_offsets: list[int] = []

    def _fake_render_systems(*_args, **kwargs):
        bar_offsets.append(kwargs["bar_offset"])

    monkeypatch.setattr("oud.ui.render.render_systems", _fake_render_systems)
    kwargs = _args("normal")
    kwargs["piece"] = piece
    kwargs["settings"]["duetscoreview"] = "both"
    kwargs["bar_offset"] = 16
    render_piece(**kwargs)
    assert bar_offsets[:2] == [16, 16]


def test_playback_highlight_prefers_nearest_note_glyph_not_dash() -> None:
    piece = Piece(
        title="PlaybackNearest",
        strings=6,
        bars=[
            Bar(
                chords=[
                    Chord(note_type=5, dotted=False, grid=None, notes=[Note(2, 3, 0), Note(3, 5, 0), Note(4, 0, 0)]),
                    Chord(note_type=6, dotted=False, grid=None, notes=[Note(2, 1, 0), Note(3, 3, 0)]),
                    Chord(note_type=5, dotted=False, grid=None, notes=[Note(2, 0, 0), Note(3, 3, 0), Note(4, 2, 0)]),
                    Chord(note_type=5, dotted=False, grid=None, notes=[Note(3, 2, 0)]),
                ],
            ),
        ],
        style="french",
    )
    kwargs = _args("normal")
    kwargs["piece"] = piece
    kwargs["stdscr"] = _Screen(h=18, w=80)
    kwargs["bar_width"] = 12
    kwargs["playback_bar"] = 0
    kwargs["playback_col"] = 3
    fb = FrameBuffer(kwargs["stdscr"].h, kwargs["stdscr"].w)
    kwargs["stdscr"] = fb
    render_piece(**kwargs)
    snap = fb.snapshot()
    highlighted = [
        (y, x, ch)
        for y, (line, attrs) in enumerate(zip(snap.lines, snap.attrs, strict=False))
        for x, (ch, attr) in enumerate(zip(line, attrs, strict=False))
        if attr != 0 and ch not in {"^", "v", " ", "|", "-"}
    ]
    assert highlighted
    assert any(ch == "c" for _y, _x, ch in highlighted)


def test_cut_time_cue_keeps_four_equal_eighth_onsets_visibly_separate() -> None:
    piece = Piece(
        title="CutTime",
        strings=6,
        bars=[
            Bar(
                time_sig="C|",
                chords=[
                    Chord(note_type=5, dotted=False, grid=None, notes=[Note(1, 0, 0), Note(6, 0, 0)]),
                    Chord(note_type=5, dotted=False, grid=None, notes=[Note(2, 3, 0)]),
                    Chord(note_type=5, dotted=False, grid=None, notes=[Note(2, 1, 0)]),
                    Chord(note_type=5, dotted=False, grid=None, notes=[Note(2, 0, 0)]),
                ],
            ),
        ],
    )
    kwargs = _args("normal")
    kwargs["piece"] = piece
    kwargs["stdscr"] = _Screen(h=18, w=40)
    kwargs["settings"]["layout"] = "auto"
    kwargs["settings"]["justify"] = "stretch"
    kwargs["settings"]["barsperline"] = "0"
    kwargs["settings"]["maxbars"] = "0"
    lines = _render_lines(kwargs)
    staff = lines[4:10]
    bar_edges = [idx for idx, ch in enumerate(staff[0]) if ch == "|"]
    assert len(bar_edges) >= 2
    lo, hi = bar_edges[0] + 1, bar_edges[1]
    note_cols: set[int] = set()
    for row in staff:
        for idx, ch in enumerate(row[lo:hi], start=lo):
            if ch not in {"-", " ", "|", ":"} and not ch.isupper():
                note_cols.add(idx)
    assert len(note_cols) == 4
    assert min(note_cols) >= 7


def test_grid_grouped_eighths_keep_four_visible_note_columns_with_hidden_redundant_flags() -> None:
    piece = Piece(
        title="GridPacked",
        strings=6,
        bars=[
            Bar(
                chords=[
                    Chord(note_type=5, dotted=False, grid="start", notes=[Note(2, 0, 0), Note(3, 1, 0)]),
                    Chord(note_type=5, dotted=False, grid="mid", notes=[Note(2, 1, 0), Note(4, 2, 0)]),
                    Chord(note_type=5, dotted=False, grid="mid", notes=[Note(4, 3, 0)]),
                    Chord(note_type=5, dotted=False, grid="end", notes=[Note(2, 3, 0)]),
                ],
            ),
        ],
    )
    kwargs = _args("normal")
    kwargs["piece"] = piece
    kwargs["stdscr"] = _Screen(h=18, w=40)
    kwargs["settings"]["layout"] = "auto"
    kwargs["settings"]["justify"] = "smart"
    kwargs["settings"]["beatsnap"] = "soft"
    kwargs["settings"]["flagredundant"] = "on"
    kwargs["settings"]["barsperline"] = "0"
    kwargs["settings"]["maxbars"] = "0"
    lines = _render_lines(kwargs)
    staff = lines[4:10]
    bar_edges = [idx for idx, ch in enumerate(staff[0]) if ch == "|"]
    assert len(bar_edges) >= 2
    lo, hi = bar_edges[0] + 1, bar_edges[1]
    note_cols: set[int] = set()
    for row in staff:
        for idx, ch in enumerate(row[lo:hi], start=lo):
            if ch not in {"-", " ", "|", ":"} and not ch.isupper():
                note_cols.add(idx)
    assert len(note_cols) == 4


def test_render_header_hides_tuning_and_shows_readable_meta() -> None:
    kwargs = _args("normal")
    kwargs["piece"].title = "Lachrimae"
    kwargs["piece"].composer = "John Dowland"
    kwargs["piece"].bars[0].time_sig = "O"
    kwargs["settings"]["key"] = "C"
    render_piece(**kwargs)
    header_calls = [(x, text) for (y, x, text, _a) in kwargs["stdscr"].calls if y == 0]
    header_texts = [text for (_x, text) in header_calls]
    assert any("Lachrimae" in text for text in header_texts)
    assert any("John Dowland" in text for text in header_texts)
    assert any(x > 0 and "Lachrimae" in text for (x, text) in header_calls)
    assert not any("g2c3f3a3d4g4" in text for text in header_texts)
    assert not any("key:C" in text for text in header_texts)
    assert not any("[1 bars]" in text for text in header_texts)


def test_render_header_composer_aligns_with_score_right_edge() -> None:
    kwargs = _args("normal")
    kwargs["stdscr"] = _Screen(w=80, h=20)
    kwargs["piece"].title = "T"
    kwargs["piece"].composer = "ABCD"
    kwargs["settings"]["linelen"] = "40"
    render_piece(**kwargs)
    composer_call = next(
        (call for call in kwargs["stdscr"].calls if call[0] == 0 and call[2] == "ABCD"),
        None,
    )
    assert composer_call is not None
    _y, x, _text, _a = composer_call
    # Right edge of score content is linelen-2 (one right padding column reserved).
    assert x + len("ABCD") - 1 == 38


def test_render_shows_time_signature_at_left_of_score_once() -> None:
    kwargs = _args("normal")
    kwargs["piece"] = Piece(title="T", bars=[Bar(time_sig="O"), Bar()], strings=6)
    render_piece(**kwargs)
    time_calls = [
        (y, x, text)
        for (y, x, text, _a) in kwargs["stdscr"].calls
        if y >= 2
        if text.strip() in {"C", "O", "|", "/", "3", "4"}
    ]
    assert any(text.strip() == "O" for (_y, _x, text) in time_calls)
    assert any(x >= 3 for (_y, x, text) in time_calls if text.strip() == "O")


def test_render_duet_score_view_both_shows_two_staff_labels_and_brace() -> None:
    kwargs = _args("normal")
    kwargs["piece"] = Piece(
        title="Duet",
        bars=[
            Bar(chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)])]),
            Bar(chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(2, 1, 0)])]),
            Bar(chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 2, 0)])]),
            Bar(chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(3, 2, 0)])]),
        ],
        strings=6,
        style="french",
        ensemble="Discant lute:6-course, Tenor lute:6-course",
        part="score",
    )
    kwargs["settings"]["duetscoreview"] = "both"
    render_piece(**kwargs)
    texts = [text for (_y, _x, text, _a) in kwargs["stdscr"].calls]
    assert any("Discant lute" in text for text in texts)
    assert any("Tenor lute" in text for text in texts)
    assert any("{" in text for text in texts)


def test_render_duet_score_view_frame_preserves_title_and_label_text() -> None:
    kwargs = _args("normal")
    kwargs["stdscr"] = _Screen(h=28, w=100)
    kwargs["piece"] = Piece(
        title="Duet Title",
        composer="Anon",
        bars=[
            Bar(chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)])]),
            Bar(chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(2, 1, 0)])]),
            Bar(chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(3, 2, 0)])]),
            Bar(chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(4, 3, 0)])]),
        ],
        strings=6,
        style="french",
        ensemble="lute 1:6-course, lute 2:6-course",
        part="score",
    )
    kwargs["settings"]["duetscoreview"] = "both"
    lines = _render_lines(kwargs)
    assert "Duet Title" in lines[0]
    assert any("Lute 1" in line for line in lines[:12])
    assert any("Lute 2" in line for line in lines[:18])
    assert not any("Lu{e 2" in line for line in lines[:18])


def test_render_duet_score_view_single_staff_hides_other_staff() -> None:
    kwargs = _args("normal")
    kwargs["piece"] = Piece(
        title="Duet",
        bars=[
            Bar(chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)])]),
            Bar(chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(2, 1, 0)])]),
        ],
        strings=6,
        style="french",
        ensemble="lute 1:6-course, lute 2:6-course",
        part="score",
    )
    kwargs["settings"]["duetscoreview"] = "1"
    render_piece(**kwargs)
    texts = [text for (_y, _x, text, _a) in kwargs["stdscr"].calls]
    assert any("Lute 1 only" in text for text in texts)
    assert not any("Lute 2 only" in text for text in texts)


def test_render_duet_score_view_mirrors_playback_marker_on_both_staves() -> None:
    kwargs = _args("normal")
    kwargs["stdscr"] = _Screen(h=28, w=100)
    kwargs["piece"] = Piece(
        title="Duet",
        bars=[
            Bar(chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)])]),
            Bar(chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(2, 1, 0)])]),
        ],
        strings=6,
        style="french",
        ensemble="lute 1:6-course, lute 2:6-course",
        part="score",
    )
    kwargs["settings"]["duetscoreview"] = "both"
    kwargs["playback_bar"] = 1
    kwargs["playback_col"] = 0
    lines = _render_lines(kwargs)
    marker_rows = [idx for idx, line in enumerate(lines) if "^" in line]
    assert len(marker_rows) >= 2


def test_playback_marker_does_not_mutate_staff_cells_with_combining_marks() -> None:
    kwargs = _args("normal")
    kwargs["stdscr"] = _Screen(h=20, w=90)
    kwargs["piece"] = Piece(
        title="Playback Stable",
        bars=[
            Bar(
                chords=[
                    Chord(
                        note_type=4,
                        dotted=False,
                        grid=None,
                        notes=[
                            Note(
                                1,
                                0,
                                0,
                                right_fingering="dot1",
                                right_ornament="#",
                                left_fingering="4",
                            ),
                        ],
                    ),
                ],
                time_sig="C|",
            ),
        ],
        strings=6,
        style="french",
    )
    kwargs["settings"]["showextras"] = "on"
    kwargs["settings"]["showft3extras"] = "on"
    kwargs["settings"]["showfingerings"] = "on"
    kwargs["settings"]["showornaments"] = "on"
    baseline = _render_lines(kwargs)
    kwargs["playback_bar"] = 0
    kwargs["playback_col"] = 0
    with_playback = _render_lines(kwargs)
    normalized_playback = [_strip_combining(line.replace("^", " ")) for line in with_playback]
    normalized_baseline = [_strip_combining(line) for line in baseline]
    assert normalized_playback == normalized_baseline


def test_playback_highlights_active_note_cell_with_attribute() -> None:
    kwargs = _args("normal")
    kwargs["stdscr"] = _Screen(h=20, w=90)
    kwargs["piece"] = Piece(
        title="Playback Highlight",
        bars=[
            Bar(
                chords=[
                    Chord(
                        note_type=4,
                        dotted=False,
                        grid=None,
                        notes=[Note(1, 0, 0)],
                    ),
                ],
            ),
        ],
        strings=6,
        style="french",
    )
    kwargs["cursor_col"] = 10
    kwargs["playback_bar"] = 0
    kwargs["playback_col"] = 0
    render_piece(**kwargs)
    assert any(text == "a" and attr != 0 for (_y, _x, text, attr) in kwargs["stdscr"].calls)


def test_playback_renders_separate_melody_marker_when_melody_visible() -> None:
    kwargs = _args("normal")
    kwargs["stdscr"] = _Screen(h=24, w=100)
    kwargs["piece"] = Piece(
        title="Melody Marker",
        bars=[
            Bar(
                chords=[
                    Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)]),
                    Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 1, 0)]),
                    Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 2, 0)]),
                ],
                melody_events=[
                    MelodyEvent("d", 0),
                    MelodyEvent("a", 1),
                    MelodyEvent("d'", 2),
                ],
            ),
        ],
        strings=6,
        style="french",
    )
    kwargs["settings"]["showmelody"] = "on"
    kwargs["settings"]["showlyrics"] = "off"
    kwargs["playback_bar"] = 0
    kwargs["playback_col"] = 1
    lines = _render_lines(kwargs)
    assert any("^" in line for line in lines)
    assert any("v" in line for line in lines)


def test_playback_markers_do_not_mutate_vocal_text_geometry() -> None:
    kwargs = _args("normal")
    kwargs["stdscr"] = _Screen(h=28, w=110)
    kwargs["piece"] = Piece(
        title="Vocal Stable",
        bars=[
            Bar(
                chords=[
                    Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)]),
                    Chord(note_type=4, dotted=False, grid=None, notes=[Note(2, 1, 0)]),
                    Chord(note_type=4, dotted=False, grid=None, notes=[Note(3, 2, 0)]),
                ],
                melody_events=[
                    MelodyEvent("d", 0),
                    MelodyEvent("a", 1),
                    MelodyEvent("d'", 2),
                ],
                lyric_event_rows=[
                    [LyricEvent("Can", 0), LyricEvent("she", 1), LyricEvent("excuse", 2)],
                ],
            ),
        ],
        strings=6,
        style="french",
    )
    kwargs["settings"]["showmelody"] = "on"
    kwargs["settings"]["showlyrics"] = "on"
    baseline = _render_lines(kwargs)
    kwargs["playback_bar"] = 0
    kwargs["playback_col"] = 1
    with_playback = _render_lines(kwargs)
    normalized_playback = [line.replace("^", " ").replace("v", " ") for line in with_playback]
    assert normalized_playback == baseline


def test_render_duet_barlines_remain_column_aligned_between_staves() -> None:
    def _dense_bar() -> Bar:
        return Bar(
            chords=[
                Chord(note_type=8, dotted=(idx % 2 == 0), grid=None, notes=[Note(1, 1, 0)])
                for idx in range(6)
            ],
        )

    kwargs = _args("normal")
    kwargs["stdscr"] = _Screen(h=36, w=120)
    kwargs["piece"] = Piece(
        title="Duet Align",
        bars=[
            _dense_bar(),
            Bar(chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(2, 2, 0)])]),
            Bar(chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)])]),
            Bar(chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(3, 3, 0)])]),
        ],
        strings=6,
        style="french",
        ensemble="lute 1:6-course, lute 2:6-course",
        part="score",
    )
    kwargs["settings"]["duetscoreview"] = "both"
    kwargs["settings"]["layout"] = "auto"
    kwargs["settings"]["justify"] = "edge"
    lines = _render_lines(kwargs)

    top_label = next(i for i, line in enumerate(lines) if "Lute 1" in line)
    bottom_label = next(i for i, line in enumerate(lines) if "Lute 2" in line)
    top_g = next(i for i in range(top_label + 1, len(lines)) if lines[i].startswith(" g|"))
    bottom_g = next(i for i in range(bottom_label + 1, len(lines)) if lines[i].startswith(" g|"))
    top_barlines = [col for col, ch in enumerate(lines[top_g]) if ch == "|"]
    bottom_barlines = [col for col, ch in enumerate(lines[bottom_g]) if ch == "|"]
    assert top_barlines == bottom_barlines


def test_render_duet_top_staff_rows_share_same_barline_columns() -> None:
    kwargs = _args("normal")
    kwargs["stdscr"] = _Screen(h=36, w=120)
    kwargs["piece"] = Piece(
        title="Duet L1",
        bars=[
            Bar(chords=[Chord(note_type=8, dotted=False, grid=None, notes=[Note(1, 0, 0)])]),
            Bar(chords=[Chord(note_type=16, dotted=True, grid=None, notes=[Note(2, 11, 0)])]),
            Bar(chords=[Chord(note_type=8, dotted=False, grid=None, notes=[Note(3, 2, 0)])]),
            Bar(chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(4, 3, 0)])]),
        ],
        strings=6,
        style="french",
        ensemble="lute 1:6-course, lute 2:6-course",
        part="score",
    )
    kwargs["settings"]["duetscoreview"] = "both"
    lines = _render_lines(kwargs)
    top_label = next(i for i, line in enumerate(lines) if "Lute 1" in line)
    top_g = next(i for i in range(top_label + 1, len(lines)) if lines[i].startswith(" g|"))
    top_staff_rows = lines[top_g : top_g + 6]
    row_barlines = [[col for col, ch in enumerate(row) if ch == "|"] for row in top_staff_rows]
    assert row_barlines
    assert all(cols == row_barlines[0] for cols in row_barlines[1:])


def test_render_duet_top_staff_rows_have_equal_symbol_count() -> None:
    kwargs = _args("normal")
    kwargs["stdscr"] = _Screen(h=36, w=120)
    kwargs["piece"] = Piece(
        title="Duet Width",
        bars=[
            Bar(
                chords=[
                    Chord(
                        note_type=8,
                        dotted=False,
                        grid=None,
                        notes=[
                            Note(1, 0, 0, left_fingering="2", right_fingering="dot1"),
                            Note(2, 2, 0),
                        ],
                    ),
                    Chord(
                        note_type=8,
                        dotted=False,
                        grid=None,
                        notes=[Note(3, 3, 0)],
                    ),
                ],
            ),
            Bar(chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 1, 0)])]),
            Bar(chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(2, 1, 0)])]),
            Bar(chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(3, 1, 0)])]),
        ],
        strings=6,
        style="french",
        ensemble="lute 1:6-course, lute 2:6-course",
        part="score",
    )
    kwargs["settings"]["duetscoreview"] = "both"
    kwargs["settings"]["showfingerings"] = "on"
    kwargs["settings"]["showornaments"] = "on"
    lines = _render_lines(kwargs)
    top_label = next(i for i, line in enumerate(lines) if "Lute 1" in line)
    top_g = next(i for i in range(top_label + 1, len(lines)) if lines[i].startswith(" g|"))
    top_staff_rows = lines[top_g : top_g + 6]

    def _symbol_span_len(row: str) -> int:
        left = row.find("|")
        right = row.rfind("|")
        segment = row if left < 0 or right <= left else row[left : right + 1]
        return len(segment)

    counts = [_symbol_span_len(row) for row in top_staff_rows]
    assert counts
    assert len(set(counts)) == 1


def test_duet_staff_labels_and_time_fill_are_derived_from_ensemble_and_pair() -> None:
    piece = Piece(
        title="Duet",
        bars=[
            # Sequential halves duet-score storage: top staff bars first, then bottom.
            Bar(time_sig=None, chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)])]),
            Bar(time_sig="C|", chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 2, 0)])]),
            Bar(time_sig="O", chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(2, 1, 0)])]),
            Bar(time_sig=None, chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(3, 2, 0)])]),
        ],
        strings=6,
        style="french",
        ensemble="Prime lute:6-course, Bass lute:6-course",
        part="score",
    )
    assert duet_staff_labels(piece) == ("Prime lute", "Bass lute")
    top = split_duet_piece_staff(piece, 0)
    bottom = split_duet_piece_staff(piece, 1)
    assert top.bars[0].time_sig == "O"      # filled from paired staff
    assert bottom.bars[1].time_sig == "C|"   # filled from paired staff


def test_duet_mapping_uses_odd_raw_bars_for_top_staff() -> None:
    # Legacy interleaved mapping remains available for synthetic fixtures.
    assert duet_bar_mapping(0) == (1, 0)
    assert duet_bar_mapping(1) == (0, 0)
    assert duet_bar_mapping(2) == (1, 1)
    assert duet_bar_mapping(3) == (0, 1)
    assert duet_raw_bar_index(0, 0) == 1
    assert duet_raw_bar_index(1, 0) == 0


def test_duet_score_piece_defaults_to_sequential_halves_mapping() -> None:
    piece = Piece(
        title="Duet",
        bars=[Bar(), Bar(), Bar(), Bar()],
        strings=6,
        style="french",
        ensemble="lute 1:6-course, lute 2:6-course",
        part="score",
    )
    assert duet_storage_mode(piece) == "halves"
    assert duet_bar_mapping(0, piece=piece) == (0, 0)
    assert duet_bar_mapping(1, piece=piece) == (0, 1)
    assert duet_bar_mapping(2, piece=piece) == (1, 0)
    assert duet_bar_mapping(3, piece=piece) == (1, 1)
    assert duet_raw_bar_index(0, 1, piece=piece) == 1
    assert duet_raw_bar_index(1, 1, piece=piece) == 3


def test_render_numeric_time_signature_is_in_staff_not_on_first_string() -> None:
    kwargs = _args("normal")
    kwargs["piece"] = Piece(title="T", bars=[Bar(time_sig="3/4"), Bar()], strings=6)
    render_piece(**kwargs)
    numeric_calls = [
        (y, x, text)
        for (y, x, text, _a) in kwargs["stdscr"].calls
        if text.strip() == "3"
    ]
    assert numeric_calls
    # In-staff / auftact placement, not over left labels.
    assert any(x >= 3 for (_y, x, _text) in numeric_calls)
    staff_y_values = [y for (y, x, _text) in numeric_calls if x >= 3]
    assert staff_y_values
    # Not on the first string row (header row offset + first staff line).
    assert min(staff_y_values) > 2


def test_render_timesigstyle_numeric_shows_3_for_common_triple_symbol() -> None:
    kwargs = _args("normal")
    kwargs["piece"] = Piece(title="T", bars=[Bar(time_sig="O"), Bar()], strings=6)
    kwargs["settings"]["timesigstyle"] = "numeric"
    render_piece(**kwargs)
    numeric_calls = [
        (y, x, text)
        for (y, x, text, _a) in kwargs["stdscr"].calls
        if text.strip() == "3" and y >= 2 and x >= 3
    ]
    symbol_calls = [
        (y, x, text)
        for (y, x, text, _a) in kwargs["stdscr"].calls
        if text.strip() == "O" and y >= 2 and x >= 3
    ]
    assert numeric_calls
    assert not symbol_calls


def test_render_common_triple_cue_keeps_gap_before_first_melody_note() -> None:
    kwargs = _args("normal")
    kwargs["piece"] = Piece(
        title="T",
        bars=[
            Bar(
                time_sig="O",
                chords=[
                    Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)]),
                    Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 2, 0)]),
                ],
                melody_events=[MelodyEvent("b", 0, note_type=4), MelodyEvent("a", 1, note_type=4)],
            ),
        ],
        strings=6,
    )
    kwargs["settings"]["timesigstyle"] = "numeric"
    lines = _render_lines(kwargs)
    melody_start = _first_melody_row_idx(lines)
    melody_block = lines[melody_start : melody_start + melody_row_count()]
    cue_row = next(line for line in melody_block if "3" in line)
    note_row = next(
        line
        for line in melody_block
        if any(ch in {MELODY_NOTEHEAD_GLYPH, MELODY_FILLED_NOTEHEAD_GLYPH} for ch in line)
    )
    cue_x = cue_row.index("3")
    first_note = min(
        idx for idx, ch in enumerate(note_row) if ch in {MELODY_NOTEHEAD_GLYPH, MELODY_FILLED_NOTEHEAD_GLYPH}
    )
    assert first_note - cue_x >= 2


def test_render_cut_time_signature_cue_is_visible_in_first_bar() -> None:
    kwargs = _args("normal")
    kwargs["piece"] = Piece(title="Cut", bars=[Bar(time_sig="C|"), Bar()], strings=6)
    render_piece(**kwargs)
    calls = [
        (y, x, text)
        for (y, x, text, _a) in kwargs["stdscr"].calls
        if y >= 2 and x >= 3 and text.strip() in {"C|", "2"}
    ]
    assert calls


@pytest.mark.parametrize("justify", ["compact", "smart", "stretch"])
def test_render_italian_multi_digit_frets_do_not_glue_1_2_12(justify: str) -> None:
    kwargs = _args("normal")
    kwargs["piece"] = Piece(
        title="ItalianSpacing",
        bars=[
            Bar(
                chords=[
                    Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 1, 0)]),
                    Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 2, 0)]),
                    Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 12, 0)]),
                ],
            ),
        ],
        strings=6,
        style="italian",
    )
    kwargs["settings"]["style"] = "italian"
    kwargs["settings"]["showtuning"] = "off"
    kwargs["settings"]["layout"] = "auto"
    kwargs["settings"]["justify"] = justify
    kwargs["settings"]["timesigstyle"] = "numeric"
    kwargs["settings"]["showdur"] = "off"
    kwargs["settings"]["showspans"] = "off"
    kwargs["settings"]["showtactus"] = "off"
    kwargs["settings"]["flagredundant"] = "on"
    kwargs["settings"]["barsperline"] = "0"
    kwargs["settings"]["maxbars"] = "0"
    kwargs["stdscr"] = _Screen(w=80, h=18)
    lines = _render_lines(kwargs)
    staff_rows = [line for line in lines if line.count("|") >= 2 and "-" in line]
    assert staff_rows
    normalized = "\n".join(staff_rows)
    assert re.search(r"1-+2-+12", normalized) or re.search(r"12-+2-+1", normalized)
    assert "12-12" not in normalized


def test_render_italian_multifretspacing_collision_safe_spreads_more_than_tight() -> None:
    base_kwargs = _args("normal")
    base_kwargs["piece"] = Piece(
        title="ItalianSpacingPolicy",
        bars=[
            Bar(
                chords=[
                    Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 1, 0)]),
                    Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 2, 0)]),
                    Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 12, 0)]),
                ],
            ),
        ],
        strings=6,
        style="italian",
    )
    base_kwargs["settings"]["style"] = "italian"
    base_kwargs["settings"]["showtuning"] = "off"
    base_kwargs["settings"]["layout"] = "auto"
    base_kwargs["settings"]["justify"] = "smart"
    base_kwargs["settings"]["barsperline"] = "0"
    base_kwargs["settings"]["maxbars"] = "0"
    base_kwargs["stdscr"] = _Screen(w=36, h=18)

    tight_kwargs = {**base_kwargs, "settings": dict(base_kwargs["settings"])}
    tight_kwargs["settings"]["multifretspacing"] = "tight"
    safe_kwargs = {**base_kwargs, "settings": dict(base_kwargs["settings"])}
    safe_kwargs["settings"]["multifretspacing"] = "collision-safe"

    tight_text = "\n".join(_render_lines(tight_kwargs))
    safe_text = "\n".join(_render_lines(safe_kwargs))
    tight_match = re.search(r"1(-+)2(-+)12", tight_text) or re.search(r"12(-+)2(-+)1", tight_text)
    safe_match = re.search(r"1(-+)2(-+)12", safe_text) or re.search(r"12(-+)2(-+)1", safe_text)
    assert tight_match is not None and safe_match is not None
    tight_gaps = tuple(len(group) for group in tight_match.groups())
    safe_gaps = tuple(len(group) for group in safe_match.groups())
    assert sum(safe_gaps) >= sum(tight_gaps)


def test_render_fretlabelmode_switches_italian_glyph_policy() -> None:
    piece = Piece(
        title="FretLabels",
        bars=[
            Bar(
                chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(3, 10, 0)])],
            ),
        ],
        strings=6,
        style="italian",
    )

    auto_kwargs = _args("normal")
    auto_kwargs["piece"] = piece
    auto_kwargs["settings"]["style"] = "italian"
    auto_kwargs["settings"]["showtuning"] = "off"
    auto_lines = _render_lines(auto_kwargs)
    assert any("x" in line for line in auto_lines)

    letters_kwargs = _args("normal")
    letters_kwargs["piece"] = piece
    letters_kwargs["settings"]["style"] = "italian"
    letters_kwargs["settings"]["showtuning"] = "off"
    letters_kwargs["settings"]["fretlabelmode"] = "letters"
    letters_lines = _render_lines(letters_kwargs)
    assert any("l" in line for line in letters_lines)
    assert not any("x" in line for line in letters_lines)


def test_render_shows_time_signature_on_mid_system_change() -> None:
    kwargs = _args("normal")
    kwargs["piece"] = Piece(title="T", bars=[Bar(), Bar(time_sig="3/4"), Bar()], strings=6)
    kwargs["settings"]["barsperline"] = "3"
    render_piece(**kwargs)
    numeric_calls = [
        (y, x, text)
        for (y, x, text, _a) in kwargs["stdscr"].calls
        if text.strip() == "3" and y >= 2 and x >= 3
    ]
    assert numeric_calls


def test_render_draws_left_staff_barline() -> None:
    kwargs = _args("normal")
    render_piece(**kwargs)
    left_bar_calls = [
        (y, x, text)
        for (y, x, text, _a) in kwargs["stdscr"].calls
        if text == "|" and x == 2 and y >= 2
    ]
    assert left_bar_calls


def test_render_new_sheet_first_note_flag_does_not_overlap_time_cue_lane() -> None:
    kwargs = _args("normal")
    kwargs["piece"] = Piece(
        title="T",
        bars=[
            Bar(
                time_sig="O",
                chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)])],
            ),
        ],
        strings=6,
    )
    render_piece(**kwargs)

    screen = kwargs["stdscr"]
    width = screen.w
    height = screen.h
    canvas = [[" " for _ in range(width)] for _ in range(height)]
    for y, x, text, _a in screen.calls:
        if not (0 <= y < height):
            continue
        for idx, ch in enumerate(text):
            tx = x + idx
            if 0 <= tx < width:
                canvas[y][tx] = ch
    lines = ["".join(row) for row in canvas]

    cue_cells = [
        (y, x)
        for y, row in enumerate(lines)
        for x, ch in enumerate(row)
        if ch == "O"
    ]
    assert cue_cells
    cue_y, cue_x = cue_cells[0]
    # Find a flag row above the staff with visible rhythm glyphs.
    flag_row_y = next(
        y
        for y in range(max(0, cue_y - 4), cue_y)
        if "|" in lines[y] and any(ch in "\\/=-" for ch in lines[y])
    )
    assert lines[flag_row_y][cue_x] == " "


def test_render_override_first_note_flag_does_not_overlap_time_cue_lane() -> None:
    kwargs = _args("insert")
    kwargs["piece"] = Piece(title="T", bars=[Bar(time_sig="O")], strings=6)
    kwargs["overrides"] = {(0, 0, 0): "a"}
    kwargs["durations"] = {(0, 0, 0): 4}
    render_piece(**kwargs)

    screen = kwargs["stdscr"]
    width = screen.w
    height = screen.h
    canvas = [[" " for _ in range(width)] for _ in range(height)]
    for y, x, text, _a in screen.calls:
        if not (0 <= y < height):
            continue
        for idx, ch in enumerate(text):
            tx = x + idx
            if 0 <= tx < width:
                canvas[y][tx] = ch
    lines = ["".join(row) for row in canvas]

    cue_cells = [
        (y, x)
        for y, row in enumerate(lines)
        for x, ch in enumerate(row)
        if ch == "O"
    ]
    assert cue_cells
    cue_y, cue_x = cue_cells[0]
    flag_row_y = next(
        y
        for y in range(max(0, cue_y - 4), cue_y)
        if "|" in lines[y] and any(ch in "\\/=-" for ch in lines[y])
    )
    assert lines[flag_row_y][cue_x] == " "


def test_render_cut_time_first_bar_keeps_four_equal_attacks_visible() -> None:
    kwargs = _args("normal")
    kwargs["piece"] = Piece(
        title="T",
        bars=[
            Bar(
                time_sig="C|",
                chords=[
                    Chord(note_type=5, dotted=False, grid="start", notes=[Note(2, 0, 0)]),
                    Chord(note_type=5, dotted=False, grid="mid", notes=[Note(2, 1, 0)]),
                    Chord(note_type=5, dotted=False, grid="mid", notes=[Note(2, 2, 0)]),
                    Chord(note_type=5, dotted=False, grid="end", notes=[Note(2, 3, 0)]),
                ],
            ),
        ],
        strings=6,
    )
    kwargs["settings"]["showtuning"] = "off"
    kwargs["settings"]["barsperline"] = "1"
    kwargs["stdscr"] = _Screen(h=16, w=50)

    lines = _render_lines(kwargs)
    assert any(all(ch in line for ch in "abcd") for line in lines)


def test_render_repeat_glyphs_visible_on_synthetic_piece() -> None:
    kwargs = _args("normal")
    kwargs["stdscr"] = _Screen(h=39, w=121)
    kwargs["piece"] = repeat_and_meter_change_piece()
    render_piece(**kwargs)
    texts = [text for (_y, _x, text, _a) in kwargs["stdscr"].calls]
    assert sum(1 for text in texts if text == ":") >= 4
    assert not any(".:" in text for text in texts)
    assert not any(":." in text for text in texts)


def test_render_repeat_words_visible_on_synthetic_piece() -> None:
    kwargs = _args("normal")
    kwargs["stdscr"] = _Screen(h=24, w=100)
    kwargs["piece"] = repeat_and_meter_change_piece()
    kwargs["piece"].bars[0].repeat = "DC al Fine"
    render_piece(**kwargs)
    texts = [text for (_y, _x, text, _a) in kwargs["stdscr"].calls]
    assert any("DC al Fine" in text for text in texts)


def test_render_ending_cue_visible_on_synthetic_piece() -> None:
    kwargs = _args("normal")
    kwargs["stdscr"] = _Screen(h=24, w=100)
    kwargs["piece"] = Piece(
        title="T",
        bars=[
            Bar(
                ending_numbers=(1, 2),
                chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)])],
            ),
        ],
        strings=6,
    )
    render_piece(**kwargs)
    texts = [text for (_y, _x, text, _a) in kwargs["stdscr"].calls]
    assert any("[1,2.]" in text for text in texts)


def test_render_shows_duet_score_hint_from_metadata() -> None:
    kwargs = _args("normal")
    kwargs["piece"] = Piece(
        title="Spanish Measures",
        bars=[Bar(chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)])])],
        strings=6,
        piece_type="lute duet",
        ensemble="lute 1:6-course, lute 2:6-course",
        part="score",
    )
    render_piece(**kwargs)
    texts = [text for (_y, _x, text, _a) in kwargs["stdscr"].calls]
    assert any("Lute 1 / Lute 2" in text for text in texts)


def test_imported_fingering_renders_right_subscript_in_french() -> None:
    kwargs = _args("normal")
    kwargs["piece"] = Piece(
        title="T",
        bars=[
            Bar(
                chords=[
                    Chord(
                        note_type=4,
                        dotted=False,
                        grid=None,
                        notes=[Note(3, 1, 0, left_fingering="4")],
                    ),
                ],
            ),
        ],
        strings=6,
    )
    kwargs["settings"]["showfingerings"] = "on"
    kwargs["settings"]["showornaments"] = "off"
    render_piece(**kwargs)
    texts = [text for (_y, _x, text, _a) in kwargs["stdscr"].calls]
    assert any("b₄" in text for text in texts)


def test_imported_fingering_renders_right_superscript_in_italian() -> None:
    kwargs = _args("normal")
    kwargs["piece"] = Piece(
        title="T",
        bars=[
            Bar(
                chords=[
                    Chord(
                        note_type=4,
                        dotted=False,
                        grid=None,
                        notes=[Note(3, 1, 0, left_fingering="4")],
                    ),
                ],
            ),
        ],
        strings=6,
    )
    kwargs["settings"]["style"] = "italian"
    kwargs["settings"]["italianorient"] = "reverse"
    kwargs["settings"]["showfingerings"] = "on"
    kwargs["settings"]["showornaments"] = "off"
    render_piece(**kwargs)
    texts = [text for (_y, _x, text, _a) in kwargs["stdscr"].calls]
    assert any("1⁴" in text for text in texts)


@pytest.mark.parametrize(
    ("style", "italian_orient", "expected"),
    [
        ("french", None, "b₄"),
        ("italian", "reverse", "1⁴"),
    ],
)
@pytest.mark.parametrize(
    ("layout", "justify", "width"),
    [
        ("packed", "stretch", 80),
        ("auto", "stretch", 96),
        ("auto", "smart", 96),
    ],
)
def test_imported_fingering_render_matrix_stays_adjacent(
    style: str,
    italian_orient: str | None,
    expected: str,
    layout: str,
    justify: str,
    width: int,
) -> None:
    kwargs = _args("normal")
    kwargs["stdscr"] = _Screen(h=24, w=width)
    kwargs["piece"] = Piece(
        title="FingeringMatrix",
        bars=[
            Bar(
                chords=[
                    Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)]),
                    Chord(note_type=8, dotted=False, grid=None, notes=[Note(2, 1, 0)]),
                    Chord(note_type=8, dotted=False, grid=None, notes=[Note(3, 1, 0, left_fingering="4")]),
                    Chord(note_type=8, dotted=False, grid=None, notes=[Note(4, 2, 0)]),
                    Chord(note_type=8, dotted=False, grid=None, notes=[Note(5, 3, 0)]),
                ],
            ),
        ],
        strings=6,
    )
    kwargs["settings"]["style"] = style
    if italian_orient is not None:
        kwargs["settings"]["italianorient"] = italian_orient
    kwargs["settings"]["layout"] = layout
    kwargs["settings"]["justify"] = justify
    kwargs["settings"]["showfingerings"] = "on"
    kwargs["settings"]["showornaments"] = "off"
    kwargs["settings"]["showspans"] = "off"
    lines = _render_lines(kwargs)
    score_text = "\n".join(lines)
    assert expected in score_text
    mark = expected[-1]
    base = expected[:-1]
    assert f"{mark}{base}" not in score_text


def test_imported_open_string_left_hand_fingering_digits_are_suppressed() -> None:
    kwargs = _args("normal")
    kwargs["piece"] = Piece(
        title="OpenSanity",
        bars=[
            Bar(
                chords=[
                    Chord(note_type=4, dotted=False, grid=None, notes=[Note(3, 0, 0, left_fingering="4")]),
                ],
            ),
        ],
        strings=6,
    )
    kwargs["settings"]["showfingerings"] = "on"
    kwargs["settings"]["showornaments"] = "off"
    lines = _render_lines(kwargs)
    text = "\n".join(lines)
    assert "₄" not in text
    assert "⁴" not in text


@pytest.mark.parametrize(
    ("style", "italian_orient", "base"),
    [
        ("french", None, "b"),
        ("italian", "reverse", "1"),
    ],
)
def test_imported_dot_left_ornament_renders_inline_as_unicode_dot(
    style: str,
    italian_orient: str | None,
    base: str,
) -> None:
    kwargs = _args("normal")
    kwargs["piece"] = Piece(
        title="DotLeft",
        bars=[
            Bar(
                chords=[
                    Chord(note_type=4, dotted=False, grid=None, notes=[Note(3, 1, 0, left_ornament="dot-left")]),
                ],
            ),
        ],
        strings=6,
    )
    kwargs["settings"]["style"] = style
    if italian_orient is not None:
        kwargs["settings"]["italianorient"] = italian_orient
    kwargs["settings"]["showfingerings"] = "off"
    kwargs["settings"]["showornaments"] = "on"
    lines = _render_lines(kwargs)
    text = "\n".join(lines)
    assert f"{base}\u0307" in text


@pytest.mark.parametrize(
    ("style", "italian_orient", "base"),
    [
        ("french", None, "b"),
        ("italian", "reverse", "1"),
    ],
)
def test_imported_left_hand_plus_ornament_renders_inline(
    style: str,
    italian_orient: str | None,
    base: str,
) -> None:
    kwargs = _args("normal")
    kwargs["piece"] = Piece(
        title="Plus",
        bars=[
            Bar(
                chords=[
                    Chord(note_type=4, dotted=False, grid=None, notes=[Note(3, 1, 0, left_ornament="+")]),
                ],
            ),
        ],
        strings=6,
    )
    kwargs["settings"]["style"] = style
    if italian_orient is not None:
        kwargs["settings"]["italianorient"] = italian_orient
    kwargs["settings"]["showfingerings"] = "off"
    kwargs["settings"]["showornaments"] = "on"
    text = "\n".join(_render_lines(kwargs))
    assert f"{base}+" in text


def test_imported_barre_semantics_renders_as_left_hand_cue() -> None:
    kwargs = _args("normal")
    kwargs["piece"] = Piece(
        title="Barre",
        bars=[
            Bar(
                chords=[
                    Chord(note_type=4, dotted=False, grid=None, notes=[Note(3, 1, 0, barre=True)]),
                ],
            ),
        ],
        strings=6,
    )
    kwargs["settings"]["showfingerings"] = "on"
    kwargs["settings"]["showornaments"] = "off"
    text = "\n".join(_render_lines(kwargs))
    assert "[" in text


@pytest.mark.parametrize(
    ("style", "italian_orient", "base"),
    [
        ("french", None, "b"),
        ("italian", "reverse", "1"),
    ],
)
def test_imported_right_hand_dot_fingering_renders_as_combining_mark_on_note(
    style: str,
    italian_orient: str | None,
    base: str,
) -> None:
    kwargs = _args("normal")
    kwargs["piece"] = Piece(
        title="RHDot",
        bars=[
            Bar(
                chords=[
                    Chord(note_type=4, dotted=False, grid=None, notes=[Note(3, 1, 0, right_fingering="dot1")]),
                ],
            ),
        ],
        strings=6,
    )
    kwargs["settings"]["style"] = style
    if italian_orient is not None:
        kwargs["settings"]["italianorient"] = italian_orient
    kwargs["settings"]["showfingerings"] = "on"
    kwargs["settings"]["showornaments"] = "off"
    text = "\n".join(_render_lines(kwargs))
    assert f"{base}\u0323" in text


@pytest.mark.parametrize(
    ("style", "italian_orient", "fingering"),
    [
        ("french", None, "₂\u0324"),
        ("italian", "reverse", "²\u0324"),
    ],
)
def test_imported_right_hand_dots_attach_to_fingering_when_left_fingering_present(
    style: str,
    italian_orient: str | None,
    fingering: str,
) -> None:
    kwargs = _args("normal")
    kwargs["piece"] = Piece(
        title="RHDot+LH",
        bars=[
            Bar(
                chords=[
                    Chord(
                        note_type=4,
                        dotted=False,
                        grid=None,
                        notes=[Note(3, 1, 0, left_fingering="2", right_fingering="dot2")],
                    ),
                ],
            ),
        ],
        strings=6,
    )
    kwargs["settings"]["style"] = style
    if italian_orient is not None:
        kwargs["settings"]["italianorient"] = italian_orient
    kwargs["settings"]["showfingerings"] = "on"
    kwargs["settings"]["showornaments"] = "off"
    text = "\n".join(_render_lines(kwargs))
    assert fingering in text


def test_legacy_showextras_alias_no_longer_reserves_span_row_without_showspans(monkeypatch) -> None:
    captured: dict[str, bool] = {}

    def _fake_render_systems(*_args, **kwargs):
        captured["show_extras"] = kwargs["show_extras"]

    monkeypatch.setattr("oud.ui.render.render_systems", _fake_render_systems)
    kwargs = _args("normal")
    kwargs["settings"]["showextras"] = "on"
    kwargs["settings"]["showspans"] = "off"
    render_piece(**kwargs)
    assert captured["show_extras"] is False


def test_ft3_melody_and_lyrics_render_as_bar_aligned_text_rows() -> None:
    kwargs = _args("normal")
    kwargs["piece"] = Piece(
        title="Texted",
        bars=[
            Bar(
                melody_grid=" 3   3  8 a",
                lyrics=["Can", "Was she"],
                chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(3, 1, 0)])],
            ),
            Bar(
                melody_grid=" 4   3  H 8",
                lyrics=["cuse"],
                chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(3, 2, 0)])],
            ),
        ],
        strings=6,
    )
    kwargs["settings"]["showmelody"] = "on"
    kwargs["settings"]["showlyrics"] = "on"
    lines = _render_lines(kwargs)
    text = "\n".join(lines)
    assert any(
        line.startswith("  |")
        and any(glyph in line for glyph in (MELODY_NOTEHEAD_GLYPH, MELODY_FILLED_NOTEHEAD_GLYPH))
        for line in lines
    )
    assert any(line.startswith("  |") and re.search(r"[A-Za-z]", line) for line in lines)
    assert "Can" in text
    assert "Was" in text
    assert any("Was s" in line or "Was she" in line for line in lines)
    assert any(glyph in text for glyph in (MELODY_NOTEHEAD_GLYPH, MELODY_FILLED_NOTEHEAD_GLYPH))


def test_melody_notes_view_renders_staff_rows_with_noteheads() -> None:
    kwargs = _args("normal")
    kwargs["piece"] = Piece(
        title="MelodyNotes",
        bars=[
            Bar(
                melody_events=[MelodyEvent("3", 0), MelodyEvent("8", 1)],
                chords=[
                    Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)]),
                    Chord(note_type=4, dotted=False, grid=None, notes=[Note(6, 0, 0)]),
                ],
            ),
        ],
        strings=6,
    )
    kwargs["settings"]["showmelody"] = "on"
    lines = _render_lines(kwargs)
    melody_start = _first_melody_row_idx(lines)
    melody_block = lines[melody_start : melody_start + melody_row_count()]
    assert len(melody_block) == melody_row_count()
    assert any(
        any(glyph in row for glyph in (MELODY_NOTEHEAD_GLYPH, MELODY_FILLED_NOTEHEAD_GLYPH))
        for row in melody_block
    )


def test_inferred_melody_is_not_clipped_by_sparse_lyrics() -> None:
    kwargs = _args("normal")
    kwargs["bar_width"] = 24
    kwargs["piece"] = Piece(
        title="InferredVocalDense",
        bars=[
            Bar(
                lyric_event_rows=[[LyricEvent("Can", 0), LyricEvent("she", 1)]],
                chords=[
                    Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)]),
                    Chord(note_type=4, dotted=False, grid=None, notes=[Note(2, 1, 0)]),
                    Chord(note_type=4, dotted=False, grid=None, notes=[Note(3, 2, 0)]),
                    Chord(note_type=4, dotted=False, grid=None, notes=[Note(4, 3, 0)]),
                    Chord(note_type=4, dotted=False, grid=None, notes=[Note(5, 4, 0)]),
                ],
            ),
        ],
        strings=6,
    )
    kwargs["settings"]["showmelody"] = "on"
    kwargs["settings"]["showlyrics"] = "on"
    lines = _render_lines(kwargs)
    melody_start = _first_melody_row_idx(lines)
    melody_block = lines[melody_start : melody_start + melody_row_count()]
    noteheads = sum(
        row.count(MELODY_NOTEHEAD_GLYPH) + row.count(MELODY_FILLED_NOTEHEAD_GLYPH)
        for row in melody_block
    )
    assert noteheads >= 5


def test_raw_text_lanes_follow_note_onsets_without_structured_events() -> None:
    kwargs = _args("normal")
    kwargs["bar_width"] = 24
    kwargs["piece"] = Piece(
        title="RawAligned",
        bars=[
            Bar(
                melody_grid="Can she excuse",
                lyrics=["Was I so base"],
                chords=[
                    Chord(note_type=4, dotted=False, grid=None, notes=[Note(3, 1, 0)]),
                    Chord(note_type=4, dotted=False, grid=None, notes=[Note(3, 2, 0)]),
                    Chord(note_type=4, dotted=False, grid=None, notes=[Note(3, 3, 0)]),
                ],
            ),
        ],
        strings=6,
    )
    kwargs["settings"]["showmelody"] = "on"
    kwargs["settings"]["showlyrics"] = "on"
    lines = _render_lines(kwargs)
    melody_start = _first_melody_row_idx(lines)
    melody_block = lines[melody_start : melody_start + melody_row_count()]
    lyric_line = _first_lyric_row(lines)
    first_barline = lyric_line.index("|")
    second_barline = lyric_line.index("|", first_barline + 1)
    lyric_inner = lyric_line[first_barline + 1 : second_barline]
    assert not any("Can" in row for row in melody_block)
    assert any(
        any(glyph in row for glyph in (MELODY_NOTEHEAD_GLYPH, MELODY_FILLED_NOTEHEAD_GLYPH))
        for row in melody_block
    )
    assert lyric_inner.find("Was") < lyric_inner.find("I") < lyric_inner.find("so")


def test_compact_justify_packs_more_bars_per_system_than_stretch() -> None:
    def _dense_bar(seed: int) -> Bar:
        return Bar(
            chords=[
                Chord(note_type=8, dotted=(seed % 2 == 0), grid=None, notes=[Note(1, (seed + 1) % 12, 0)]),
                Chord(note_type=16, dotted=False, grid=None, notes=[Note(2, (seed + 3) % 12, 0)]),
                Chord(note_type=8, dotted=False, grid=None, notes=[Note(3, (seed + 5) % 12, 0)]),
                Chord(note_type=4, dotted=False, grid=None, notes=[Note(4, (seed + 7) % 12, 0)]),
            ],
        )

    kwargs = _args("normal")
    kwargs["stdscr"] = _Screen(h=24, w=100)
    kwargs["bar_width"] = 16
    kwargs["piece"] = Piece(
        title="Pack",
        bars=[_dense_bar(i) for i in range(8)],
        strings=6,
        style="french",
    )
    kwargs["settings"]["layout"] = "auto"

    kwargs["settings"]["justify"] = "stretch"
    stretch_lines = _render_lines(kwargs)
    stretch_g = next(line for line in stretch_lines if line.startswith(" g|"))
    stretch_bars = stretch_g.count("|")

    kwargs["settings"]["justify"] = "compact"
    compact_lines = _render_lines(kwargs)
    compact_g = next(line for line in compact_lines if line.startswith(" g|"))
    compact_bars = compact_g.count("|")

    assert compact_bars >= stretch_bars


def test_ft3_melody_and_lyrics_rows_can_be_hidden() -> None:
    kwargs = _args("normal")
    kwargs["piece"] = Piece(
        title="TextedOff",
        bars=[
            Bar(
                melody_grid=" 3   3  8 a",
                lyrics=["Can"],
                chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(3, 1, 0)])],
            ),
        ],
        strings=6,
    )
    kwargs["settings"]["showmelody"] = "off"
    kwargs["settings"]["showlyrics"] = "off"
    lines = _render_lines(kwargs)
    text = "\n".join(lines)
    assert not any(line.startswith("  |") and MELODY_NOTEHEAD_GLYPH in line for line in lines)
    assert not any(line.startswith("  |") and "Can" in line for line in lines)
    assert "Can" not in text


def test_vocal_renderer_displays_all_lyric_rows_without_two_row_cap() -> None:
    kwargs = _args("normal")
    kwargs["piece"] = Piece(
        title="ManyLyrics",
        bars=[
            Bar(
                melody_events=[MelodyEvent("3", 0)],
                lyric_event_rows=[
                    [LyricEvent("Row1", 0)],
                    [LyricEvent("Row2", 0)],
                    [LyricEvent("Row3", 0)],
                ],
                chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(3, 1, 0)])],
            ),
        ],
        strings=6,
    )
    kwargs["settings"]["showmelody"] = "on"
    kwargs["settings"]["showlyrics"] = "on"
    text = "\n".join(_render_lines(kwargs))
    assert "Row1" in text
    assert "Row2" in text
    assert "Row3" in text


def test_vocal_renderer_orders_lyric_rows_by_verse_index() -> None:
    kwargs = _args("normal")
    kwargs["bar_width"] = 20
    kwargs["piece"] = Piece(
        title="VerseOrder",
        bars=[
            Bar(
                melody_events=[MelodyEvent("3", 0)],
                lyric_event_rows=[
                    [LyricEvent("Verse2", 0, verse=1)],
                    [LyricEvent("Verse1", 0, verse=0)],
                    [LyricEvent("Verse3", 0, verse=2)],
                ],
                chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(3, 1, 0)])],
            ),
        ],
        strings=6,
    )
    kwargs["settings"]["showmelody"] = "on"
    kwargs["settings"]["showlyrics"] = "on"
    text = "\n".join(_render_lines(kwargs))
    assert text.index("Verse1") < text.index("Verse2") < text.index("Verse3")


def test_vocalpos_top_places_melody_rows_above_tab_staff() -> None:
    kwargs = _args("normal")
    kwargs["piece"] = Piece(
        title="TopVocal",
        bars=[
            Bar(
                melody_events=[MelodyEvent("3", 0)],
                lyric_event_rows=[[LyricEvent("Can", 0)]],
                chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(3, 1, 0)])],
            ),
        ],
        strings=6,
    )
    kwargs["settings"]["showmelody"] = "on"
    kwargs["settings"]["showlyrics"] = "on"
    kwargs["settings"]["vocalpos"] = "top"
    lines = _render_lines(kwargs)
    melody_idx = _first_melody_row_idx(lines)
    staff_idx = next(i for i, line in enumerate(lines) if line.startswith(" g|"))
    assert melody_idx < staff_idx


def test_vocalpos_bottom_places_melody_rows_below_tab_staff() -> None:
    kwargs = _args("normal")
    kwargs["piece"] = Piece(
        title="BottomVocal",
        bars=[
            Bar(
                melody_events=[MelodyEvent("3", 0)],
                lyric_event_rows=[[LyricEvent("Can", 0)]],
                chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(3, 1, 0)])],
            ),
        ],
        strings=6,
    )
    kwargs["settings"]["showmelody"] = "on"
    kwargs["settings"]["showlyrics"] = "on"
    kwargs["settings"]["vocalpos"] = "bottom"
    lines = _render_lines(kwargs)
    melody_idx = _first_melody_row_idx(lines)
    staff_idx = next(i for i, line in enumerate(lines) if line.startswith(" g|"))
    assert melody_idx > staff_idx


def test_ft3_structured_text_events_render_onset_aligned_over_raw_text_fallback() -> None:
    kwargs = _args("normal")
    kwargs["bar_width"] = 20
    kwargs["piece"] = Piece(
        title="StructuredText",
        bars=[
            Bar(
                melody_grid="raw melody should not win",
                lyrics=["raw lyric should not win"],
                melody_events=[
                    MelodyEvent("3", 0),
                    MelodyEvent("8", 1),
                    MelodyEvent("a", 2),
                ],
                lyric_event_rows=[
                    [
                        LyricEvent("ex", 0, syllabic="begin"),
                        LyricEvent("cuse", 1, syllabic="end"),
                        LyricEvent("me", 2, syllabic="single"),
                    ],
                ],
                chords=[
                    Chord(note_type=4, dotted=False, grid=None, notes=[Note(3, 1, 0)]),
                    Chord(note_type=4, dotted=False, grid=None, notes=[Note(3, 2, 0)]),
                    Chord(note_type=4, dotted=False, grid=None, notes=[Note(3, 3, 0)]),
                ],
            ),
        ],
        strings=6,
    )
    kwargs["settings"]["showmelody"] = "on"
    kwargs["settings"]["showlyrics"] = "on"
    text = "\n".join(_render_lines(kwargs))
    assert "raw lyric should not win" not in text
    assert "raw melody should not win" not in text
    assert "ex" in text and "cuse" in text and "me" in text
    assert "-" in text
    assert any(glyph in text for glyph in (MELODY_NOTEHEAD_GLYPH, MELODY_FILLED_NOTEHEAD_GLYPH))


def test_ft3_structured_text_events_keep_later_onsets_stable_after_long_first_token() -> None:
    kwargs = _args("normal")
    kwargs["bar_width"] = 24
    kwargs["piece"] = Piece(
        title="StructuredDense",
        bars=[
            Bar(
                melody_events=[
                    MelodyEvent("abcdefghi", 0),
                    MelodyEvent("Z", 1),
                ],
                lyric_event_rows=[
                    [
                        LyricEvent("longsyll", 0, syllabic="begin"),
                        LyricEvent("me", 1, syllabic="end"),
                    ],
                ],
                chords=[
                    Chord(note_type=4, dotted=False, grid=None, notes=[Note(3, 1, 0)]),
                    Chord(note_type=4, dotted=False, grid=None, notes=[Note(3, 2, 0)]),
                ],
            ),
        ],
        strings=6,
    )
    kwargs["settings"]["showmelody"] = "on"
    kwargs["settings"]["showlyrics"] = "on"
    lines = _render_lines(kwargs)
    lyric_line = _first_lyric_row(lines)
    first_barline = lyric_line.index("|")
    second_barline = lyric_line.index("|", first_barline + 1)
    lyric_inner = lyric_line[first_barline + 1 : second_barline]
    # "me" must appear at/after the second onset, not drifted to the far right.
    assert lyric_inner.find("me") > 0
    assert lyric_inner.find("me") < len(lyric_inner) - 3
