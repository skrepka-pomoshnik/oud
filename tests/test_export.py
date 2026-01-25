from core.model import Bar, Piece
from exports.export_tab import export_ascii, export_tab, export_tab_to_file


def test_export_tab_includes_headers_and_chords() -> None:
    piece = Piece(title="T", author="A", composer="C", bars=[Bar()], strings=6)
    overrides = {(0, 0, 0): "a"}
    durations = {(0, 0, 0): 4, (0, 1, 0): 2}
    settings = {
        "style": "french",
        "tuning": "a4b4",
        "time": "C",
    }
    text = export_tab(
        piece,
        overrides,
        durations,
        bar_width=4,
        settings=settings,
        dotted=set(),
    )
    assert "-tuning a4b4" in text
    assert "{T/C}" in text
    assert "{A}" in text
    assert "b" in text
    assert "Sc" in text
    assert any(line.startswith("0") for line in text.splitlines())
    assert any(line.endswith("a") for line in text.splitlines())


def test_export_tab_writes_bar_markers() -> None:
    piece = Piece(title="T", bars=[Bar(), Bar(), Bar()], strings=6)
    text = export_tab(
        piece,
        overrides={},
        durations={},
        bar_width=4,
        settings={},
        dotted=set(),
    )
    assert text.splitlines().count("b") == 3


def test_export_tab_includes_end_marker() -> None:
    piece = Piece(title="T", bars=[Bar()], strings=6)
    text = export_tab(
        piece,
        overrides={},
        durations={},
        bar_width=4,
        settings={},
        dotted=set(),
    )
    assert text.rstrip().endswith("e")


def test_export_ascii_basic() -> None:
    piece = Piece(title="T", bars=[Bar()], strings=6)
    overrides = {(0, 0, 0): "a"}
    text = export_ascii(piece, overrides, durations={}, bar_width=4, settings={})
    assert "6|a" in text


def test_export_tab_to_file_writes_content(tmp_path) -> None:
    piece = Piece(title="T", bars=[Bar()], strings=6)
    path = tmp_path / "out.tab"
    export_tab_to_file(
        str(path),
        piece,
        overrides={},
        durations={},
        bar_width=4,
        settings={},
        dotted=set(),
    )
    content = path.read_text(encoding="utf-8")
    assert content
    assert "b" in content
