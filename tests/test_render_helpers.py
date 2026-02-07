from __future__ import annotations

from oud.core.model import Bar, Chord, Note, Piece
from oud.ui.adapter import CursesError, Screen
from oud.ui.render_helpers import (
    apply_overrides,
    bass_strings_used,
    clean_text,
    flag_symbols,
    info_lines,
    pad_row,
    render_help,
    render_info,
    render_plugin,
    safe_addstr,
)


class _Screen(Screen):
    def __init__(self, h: int = 8, w: int = 40, *, raise_value: bool = False) -> None:
        self.h = h
        self.w = w
        self.raise_value = raise_value
        self.calls: list[tuple[int, int, str, int]] = []

    def getmaxyx(self) -> tuple[int, int]:
        return self.h, self.w

    def addstr(self, y: int, x: int, text: str, attr: int = 0) -> None:
        if self.raise_value:
            raise ValueError("bad")
        if y == self.h - 1 and x + len(text) >= self.w:
            raise CursesError("ERR")
        self.calls.append((y, x, text, attr))

    def erase(self) -> None:
        return None

    def refresh(self) -> None:
        return None


def test_safe_addstr_boundaries_and_errors() -> None:
    s = _Screen()
    safe_addstr(s, 0, 0, "abc", 1)
    safe_addstr(s, -1, 0, "x")
    safe_addstr(s, 0, 100, "x")
    safe_addstr(s, 0, -1, "xy")
    assert any(call[2] == "abc" for call in s.calls)
    s2 = _Screen(raise_value=True)
    safe_addstr(s2, 0, 0, "abc")
    s3 = _Screen(h=2, w=4)
    safe_addstr(s3, 1, 2, "xx")


def test_clean_pad_and_flag_symbols() -> None:
    assert clean_text("a\x00b") == "a b"
    assert pad_row(list("ab"), 6, 1) == [" ", "a", "b", " ", " ", " "]
    assert pad_row(list("abcdef"), 4, 0) == list("abcd")
    assert flag_symbols("continental") == ("Γ", "F")
    assert flag_symbols("unknown") == ("|", "\\")


def test_info_help_plugin_and_info_render() -> None:
    piece = Piece(title="T", bars=[Bar()], strings=6, composer="C", subtitle="S", footnote="F")
    lines = info_lines(piece, {"style": "french", "time": "C"})
    assert lines[0] == "INFO"
    s = _Screen(h=6, w=30)
    render_help(s, "help", 1, 0)
    render_plugin(s, "plugin", 1, "Plugins", ["a", "b"], 1, 0, "msg")
    render_info(s, "info", 1, 0, piece, {"style": "french", "time": "C"})
    assert s.calls


def test_bass_strings_used_and_apply_overrides() -> None:
    piece = Piece(
        title="T",
        bars=[
            Bar(
                notes=[Note(string=7, fret=0, raw_pos=0)],
                chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(8, 0, 0)])],
            ),
        ],
        strings=8,
    )
    used = bass_strings_used(piece, {(0, 6, 0): "a"})
    assert 6 in used
    assert 7 in used
    cells = [list("----") for _ in range(8)]
    apply_overrides(cells, {(0, 0, 1): "r", (0, 1, 2): "c"}, 0, 8, 4)
    assert cells[0][1] == "_"
    assert cells[1][2] == "c"
