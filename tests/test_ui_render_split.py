from __future__ import annotations

import re

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
from tests.helpers_regression_cases import repeat_and_meter_change_piece


class _Screen(Screen):
    def __init__(self, h: int = 20, w: int = 80) -> None:
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
    h = getattr(stdscr, "h", 24)
    w = getattr(stdscr, "w", 80)
    fb = FrameBuffer(h, w)
    run_kwargs = dict(kwargs)
    run_kwargs["stdscr"] = fb
    render_piece(**run_kwargs)
    return fb.snapshot().lines


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
    normalized_playback = [line.replace("^", " ") for line in with_playback]
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
    assert "\nm " in text
    assert "\ny " in text
    assert "Can" in text
    assert "Was she" in text
    for token in ("3", "8", "a", "4", "H"):
        assert token in text


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
    text = "\n".join(_render_lines(kwargs))
    assert "\nm " not in text
    assert "\ny " not in text
    assert "Can" not in text


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
    melody_idx = next(i for i, line in enumerate(lines) if line.startswith("m "))
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
    melody_idx = next(i for i, line in enumerate(lines) if line.startswith("m "))
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
    assert "3" in text and "8" in text and "a" in text
