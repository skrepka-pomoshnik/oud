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
            "layout": "packed",
            "justify": "stretch",
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
    # Inlined time signature is drawn as a small multi-row block (>=3 rows).
    inline_rows = [(y, text) for (y, _x, text) in time_calls if text.strip() in {"O", "|", "/", "4"}]
    assert len(inline_rows) >= 3
    assert sum(1 for (_y, _x, text) in time_calls if text.strip().startswith("O")) == 1


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
