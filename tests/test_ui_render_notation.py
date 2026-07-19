from __future__ import annotations

import re

import pytest

from oud.ui.adapter import Screen
from petrucci.framebuffer import FrameBuffer
from petrucci.model import Bar, Chord, MelodyEvent, Note, Piece
from petrucci.render import render_piece
from petrucci.render_text_lanes import MELODY_FILLED_NOTEHEAD_GLYPH, MELODY_NOTEHEAD_GLYPH
from petrucci.render_vocal import melody_row_count
from tests.helpers_regression_cases import repeat_and_meter_change_piece
from tests.render_test_utils import first_melody_row_idx as _first_melody_row_idx


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


def test_render_numeric_time_signature_is_in_staff_not_on_first_string() -> None:
    kwargs = _args("normal")
    kwargs["piece"] = Piece(title="T", bars=[Bar(time_sig="3/4"), Bar()], strings=6)
    render_piece(**kwargs)
    numeric_calls = [(y, x, text) for (y, x, text, _a) in kwargs["stdscr"].calls if text.strip() == "3"]
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
        (y, x, text) for (y, x, text, _a) in kwargs["stdscr"].calls if text.strip() == "3" and y >= 2 and x >= 3
    ]
    symbol_calls = [
        (y, x, text) for (y, x, text, _a) in kwargs["stdscr"].calls if text.strip() == "O" and y >= 2 and x >= 3
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
        line for line in melody_block if any(ch in {MELODY_NOTEHEAD_GLYPH, MELODY_FILLED_NOTEHEAD_GLYPH} for ch in line)
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
        (y, x, text) for (y, x, text, _a) in kwargs["stdscr"].calls if y >= 2 and x >= 3 and text.strip() in {"C|", "2"}
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
        (y, x, text) for (y, x, text, _a) in kwargs["stdscr"].calls if text.strip() == "3" and y >= 2 and x >= 3
    ]
    assert numeric_calls


def test_render_draws_left_staff_barline() -> None:
    kwargs = _args("normal")
    render_piece(**kwargs)
    left_bar_calls = [(y, x, text) for (y, x, text, _a) in kwargs["stdscr"].calls if text == "|" and x == 2 and y >= 2]
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

    cue_cells = [(y, x) for y, row in enumerate(lines) for x, ch in enumerate(row) if ch == "O"]
    assert cue_cells
    cue_y, cue_x = cue_cells[0]
    # Find a flag row above the staff with visible rhythm glyphs.
    flag_row_y = next(
        y for y in range(max(0, cue_y - 4), cue_y) if "|" in lines[y] and any(ch in "\\/=-" for ch in lines[y])
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

    cue_cells = [(y, x) for y, row in enumerate(lines) for x, ch in enumerate(row) if ch == "O"]
    assert cue_cells
    cue_y, cue_x = cue_cells[0]
    flag_row_y = next(
        y for y in range(max(0, cue_y - 4), cue_y) if "|" in lines[y] and any(ch in "\\/=-" for ch in lines[y])
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


def test_imported_arpeggio_renders_as_inline_colon() -> None:
    kwargs = _args("normal")
    kwargs["piece"] = Piece(
        title="Arpeggio",
        bars=[
            Bar(
                chords=[
                    Chord(
                        note_type=4,
                        dotted=False,
                        grid=None,
                        notes=[Note(1, 1, 0, arpeggio="top"), Note(2, 2, 0, arpeggio="bottom")],
                    ),
                ],
            ),
        ],
        strings=6,
    )
    kwargs["settings"]["showornaments"] = "on"
    assert ":" in "\n".join(_render_lines(kwargs))


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

    monkeypatch.setattr("petrucci.render.render_systems", _fake_render_systems)
    kwargs = _args("normal")
    kwargs["settings"]["showextras"] = "on"
    kwargs["settings"]["showspans"] = "off"
    render_piece(**kwargs)
    assert captured["show_extras"] is False
