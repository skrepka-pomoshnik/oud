from __future__ import annotations

from oud.core.model import Bar, Piece
from oud.ui.adapter import Screen
from oud.ui.render import _apply_overrides, render_piece


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
            "spacingmode": "packed",
            "spacingfill": "stretch",
            "barpad": "1",
            "showdur": "off",
            "showextras": "off",
            "showtactus": "off",
            "flagredundant": "on",
            "flagstems": "single",
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


def test_render_header_hides_tuning_and_shows_readable_meta() -> None:
    kwargs = _args("normal")
    kwargs["piece"].title = "Lachrimae"
    kwargs["piece"].bars[0].time_sig = "O"
    kwargs["settings"]["key"] = "C"
    render_piece(**kwargs)
    header_texts = [text for (y, _x, text, _a) in kwargs["stdscr"].calls if y == 0]
    assert any("Lachrimae" in text for text in header_texts)
    assert not any("g2c3f3a3d4g4" in text for text in header_texts)
    all_text = " ".join(text for (_y, _x, text, _a) in kwargs["stdscr"].calls)
    assert "key:C" not in all_text


def test_render_draws_left_staff_barline() -> None:
    kwargs = _args("normal")
    render_piece(**kwargs)
    left_bar_calls = [
        (y, x, text)
        for (y, x, text, _a) in kwargs["stdscr"].calls
        if text == "|" and x == 2 and y >= 2
    ]
    assert left_bar_calls
