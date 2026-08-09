from __future__ import annotations

import re

from oud.ui.adapter import Screen
from petrucci.framebuffer import FrameBuffer
from petrucci.model import Bar, Chord, LyricEvent, MelodyEvent, Note, Piece
from petrucci.render import render_piece
from petrucci.render_text_lanes import MELODY_FILLED_NOTEHEAD_GLYPH, MELODY_NOTEHEAD_GLYPH
from petrucci.render_vocal import melody_row_count
from tests.render_test_utils import first_lyric_row as _first_lyric_row
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
        line.startswith("  |") and any(glyph in line for glyph in (MELODY_NOTEHEAD_GLYPH, MELODY_FILLED_NOTEHEAD_GLYPH))
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
        any(glyph in row for glyph in (MELODY_NOTEHEAD_GLYPH, MELODY_FILLED_NOTEHEAD_GLYPH)) for row in melody_block
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
    noteheads = sum(row.count(MELODY_NOTEHEAD_GLYPH) + row.count(MELODY_FILLED_NOTEHEAD_GLYPH) for row in melody_block)
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
        any(glyph in row for glyph in (MELODY_NOTEHEAD_GLYPH, MELODY_FILLED_NOTEHEAD_GLYPH)) for row in melody_block
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
    kwargs["settings"]["lyricmode"] = "all"
    text = "\n".join(_render_lines(kwargs))
    assert "Row1" in text
    assert "Row2" in text
    assert "Row3" in text


def test_vocal_renderer_selects_first_or_current_lyric_stanza() -> None:
    kwargs = _args("normal")
    kwargs["piece"] = Piece(
        title="SelectedLyrics",
        bars=[
            Bar(
                melody_events=[MelodyEvent("c", 0)],
                lyric_event_rows=[
                    [LyricEvent("First", 0, verse=0)],
                    [LyricEvent("Second", 0, verse=1)],
                    [LyricEvent("Third", 0, verse=2)],
                ],
                chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(3, 1, 0)])],
            ),
        ],
        strings=6,
    )
    kwargs["settings"].update(showmelody="on", showlyrics="on", lyricmode="first")
    first_text = "\n".join(_render_lines(kwargs))
    assert "First" in first_text
    assert "Second" not in first_text

    kwargs["settings"].update(lyricmode="current", lyricverse="2")
    current_text = "\n".join(_render_lines(kwargs))
    assert "Second" in current_text
    assert "First" not in current_text


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
