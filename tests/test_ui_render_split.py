from __future__ import annotations

import re
import unicodedata

from oud.presentation.ui.adapter import Screen
from petrucci.adapters.duet import (
    duet_bar_mapping,
    duet_raw_bar_index,
    duet_staff_labels,
    duet_storage_mode,
    split_duet_piece_staff,
)
from petrucci.core.model import Bar, Chord, LyricEvent, MelodyEvent, Note, Piece
from petrucci.rendering.api import _apply_overrides, render_piece
from petrucci.rendering.staff.text import MELODY_FILLED_NOTEHEAD_GLYPH, MELODY_NOTEHEAD_GLYPH
from petrucci.rendering.staff.vocal import melody_row_count
from petrucci.rendering.system.status import status_attr_for_message
from petrucci.terminal.canvas.framebuffer import FrameBuffer


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


def test_render_piece_applies_message_severity_to_status_row() -> None:
    kwargs = _args()
    kwargs["message"] = "Write failed"
    kwargs["message_level"] = "error"
    render_piece(**kwargs)

    status_calls = [call for call in kwargs["stdscr"].calls if call[0] == kwargs["stdscr"].h - 1]
    assert status_calls
    assert status_calls[-1][3] == status_attr_for_message("error")


def _first_melody_row_idx(lines: list[str]) -> int:  # noqa: C901
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
        if any(
            ("\\" in line or any(glyph in line for glyph in notehead_glyphs) or "^" in line or "v" in line)
            for line in block
        ):
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
        if idx >= melody_start + melody_row_count() and line.startswith("  |") and re.search(r"[A-Za-z]{2,}", line)
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

    monkeypatch.setattr("petrucci.rendering.bar.legacy.render_systems", _fake_render_systems)
    kwargs = _args("normal")
    kwargs["settings"]["viewinvert"] = "on"
    render_piece(**kwargs)
    assert called["bars_limit"] == 2
    assert called["reverse"] is True
    assert kwargs["stdscr"].refreshes == 1


def test_render_piece_draws_partial_next_system_above_status() -> None:
    kwargs = _args("normal")
    kwargs["stdscr"] = _Screen(h=19, w=80)
    kwargs["piece"] = Piece(
        title="Partial",
        bars=[
            Bar(chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)])]),
            Bar(chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 1, 0)])]),
        ],
        strings=6,
    )
    kwargs["settings"]["barsperline"] = "1"
    kwargs["settings"]["maxbars"] = "0"

    lines = _render_lines(kwargs)

    assert any("b" in line for line in lines[11:-1])
    assert "status" in lines[-1]


def test_render_piece_hides_orphaned_one_line_system_preview() -> None:
    kwargs = _args("normal")
    kwargs["stdscr"] = _Screen(h=24, w=80)
    kwargs["piece"] = Piece(
        title="No orphan",
        bars=[
            Bar(chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, fret, 0)])]) for fret in (0, 1, 2)
        ],
        strings=6,
    )
    kwargs["settings"].update({"barsperline": "1", "maxbars": "1", "measures": "system"})

    lines = _render_lines(kwargs)

    assert not any(line.strip() == "3" for line in lines)
    assert not any("c" in line for line in lines[19:-1])


def test_render_piece_passes_explicit_barsperline_limit(monkeypatch) -> None:
    called = {}

    def _fake_render_systems(*_args, **kwargs):
        called["bars_limit"] = kwargs["bars_per_line_limit"]

    monkeypatch.setattr("petrucci.rendering.bar.legacy.render_systems", _fake_render_systems)
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

    monkeypatch.setattr("petrucci.rendering.bar.legacy.render_systems", _fake_render_systems)
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

    monkeypatch.setattr("petrucci.rendering.system.duet.render_systems", _fake_render_systems)
    kwargs = _args("normal")
    kwargs["piece"] = piece
    kwargs["settings"]["duetscoreview"] = "both"
    kwargs["playback_markers"] = [(0, 1), (1, 3)]
    render_piece(**kwargs)
    assert calls == [[(0, 1)], [(0, 3)]]


def test_render_piece_duet_publishes_cursor_maps_for_raw_bars() -> None:
    kwargs = _args("normal")
    kwargs["piece"] = Piece(
        title="Duet maps",
        bars=[
            Bar(chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)])]),
            Bar(chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 1, 0)])]),
            Bar(chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(2, 2, 0)])]),
            Bar(chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(2, 3, 0)])]),
        ],
        strings=6,
        style="french",
        ensemble="lute 1:6-course, lute 2:6-course",
        part="score",
    )
    kwargs["settings"]["duetscoreview"] = "both"
    cursor_maps: dict[int, list[int]] = {}
    kwargs["cursor_display_maps"] = cursor_maps
    render_piece(**kwargs)
    assert set(cursor_maps) == {0, 1, 2, 3}
    assert all(len(mapping) == kwargs["bar_width"] for mapping in cursor_maps.values())


def test_render_piece_duet_builds_shared_minimal_playback_cache() -> None:
    kwargs = _args("normal")
    kwargs["piece"] = Piece(
        title="Duet playback cache",
        bars=[
            Bar(chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)])]),
            Bar(chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 1, 0)])]),
            Bar(chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(2, 2, 0)])]),
            Bar(chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(2, 3, 0)])]),
        ],
        strings=6,
        style="french",
        ensemble="lute 1:6-course, lute 2:6-course",
        part="score",
    )
    kwargs["settings"]["duetscoreview"] = "both"
    playback_cache = {}
    kwargs["playback_cache"] = playback_cache
    render_piece(**kwargs)
    assert playback_cache[(0, 0)] == playback_cache[(2, 0)]
    assert len({y for y, _x, _text, _attr in playback_cache[(0, 0)]}) >= 2


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

    monkeypatch.setattr("petrucci.rendering.system.duet.render_systems", _fake_render_systems)
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


def test_system_height_only_reserves_bass_course_where_used() -> None:
    kwargs = _args("normal")
    kwargs["stdscr"] = _Screen(h=28, w=80)
    kwargs["piece"] = Piece(
        title="Local bass height",
        bars=[
            Bar(chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)])]),
            Bar(chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(7, 0, 0)])]),
        ],
        strings=7,
        style="french",
    )
    kwargs["settings"].update({"barsperline": "1", "maxbars": "1", "measures": "system"})
    lines = _render_lines(kwargs)
    number_rows = [idx for idx, line in enumerate(lines) if line.strip() in {"1", "2"}]
    assert number_rows == [1, 10]


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
            chords=[Chord(note_type=8, dotted=(idx % 2 == 0), grid=None, notes=[Note(1, 1, 0)]) for idx in range(6)],
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
    assert top.bars[0].time_sig == "O"  # filled from paired staff
    assert bottom.bars[1].time_sig == "C|"  # filled from paired staff


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
