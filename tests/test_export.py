from export_tab import export_ascii, export_tab
from model import Bar, Piece


def test_export_tab_includes_headers_and_durations() -> None:
    piece = Piece(title="T", author="A", composer="C", bars=[Bar()], strings=6)
    overrides = {(0, 0, 0): "a"}
    durations = {(0, 0, 0): 4, (0, 1, 0): 2}
    settings = {
        "style": "french",
        "measures": "start",
        "tuning": "a4b4",
        "flagstyle": "standard",
        "time": "C",
        "key": "C",
        "countdots": "off",
        "spacing": "12",
        "linelen": "80",
        "staffthick": "1",
        "fontstyle": "modern",
        "charstyle": "standard",
        "midipatch": "0",
        "grid": "off",
    }
    text = export_tab(piece, overrides, durations, bar_width=4, settings=settings)
    assert "# TITLE: T" in text
    assert "# AUTHOR: A" in text
    assert "# STYLE: french" in text
    assert "# FLAGSTYLE: standard" in text
    assert "# TIME: C" in text
    assert "# KEY: C" in text
    assert "# COUNTDOTS: off" in text
    assert "# SPACING: 12" in text
    assert "# LINELEN: 80" in text
    assert "# STAFFTHICK: 1" in text
    assert "# FONTSTYLE: modern" in text
    assert "# CHARSTYLE: standard" in text
    assert "# MIDIPATCH: 0" in text
    assert "# GRID: off" in text
    assert "Tactus:" in text
    assert "Flag: 0" in text
    assert "Dur: 4" in text
    assert "6|a" in text


def test_export_bar_numbers_respect_measures_setting() -> None:
    piece = Piece(title="T", bars=[Bar(), Bar(), Bar(), Bar(), Bar()], strings=6)
    settings = {"measures": "five", "countdots": "off"}
    text = export_tab(piece, overrides={}, durations={}, bar_width=4, settings=settings)
    assert "Bar 5" in text
    assert "Bar 1" not in text


def test_export_countdots_affects_bar_numbers() -> None:
    b0 = Bar()
    b1 = Bar()
    b1.repeat = "."
    piece = Piece(title="T", bars=[b0, b1, Bar()], strings=6)
    settings = {"measures": "every", "countdots": "on"}
    text = export_tab(piece, overrides={}, durations={}, bar_width=4, settings=settings)
    assert "Bar 3" in text


def test_export_barline_and_repeat() -> None:
    bar = Bar()
    bar.barline = "||"
    bar.repeat = ".:"
    piece = Piece(title="T", bars=[bar], strings=6)
    text = export_tab(piece, overrides={}, durations={}, bar_width=4, settings={})
    assert "Barline: ||" in text
    assert "Repeat: .:" in text


def test_export_ascii_basic() -> None:
    piece = Piece(title="T", bars=[Bar()], strings=6)
    overrides = {(0, 0, 0): "a"}
    text = export_ascii(piece, overrides, durations={}, bar_width=4, settings={})
    assert "6|a" in text
