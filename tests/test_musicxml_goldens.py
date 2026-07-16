from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree as ET

from oud.editor.load_ops import load_piece_data
from oud.exports.musicxml import export_musicxml
from oud.petrucci.model import Piece

FIXTURES = Path(__file__).parent / "fixtures" / "musicxml"


def _strip_ws(node: ET.Element) -> None:
    if node.text is not None and not node.text.strip():
        node.text = None
    if node.tail is not None and not node.tail.strip():
        node.tail = None
    for child in list(node):
        _strip_ws(child)


def _normalize_xml_text(text: str) -> str:
    root = ET.fromstring(text)  # noqa: S314
    _strip_ws(root)
    return ET.tostring(root, encoding="unicode")


def _export_piece_subset_to_musicxml_text(src_path: str, bars: int, tmp_path: Path) -> str:
    piece, overrides, durations, dotted, bar_width = load_piece_data(src_path)
    sub_piece = Piece(
        title=piece.title,
        composer=piece.composer,
        tuning=piece.tuning,
        style=piece.style,
        key=piece.key,
        bars=piece.bars[:bars],
        strings=piece.strings,
    )
    tmp_out = tmp_path / "export.musicxml"
    export_musicxml(
        str(tmp_out),
        sub_piece,
        overrides=overrides,
        durations=durations,
        bar_width=bar_width or 12,
        settings={
            "style": sub_piece.style or "french",
            "tuning": sub_piece.tuning or "g2c3f3a3d4g4",
            "key": sub_piece.key or "C",
            "time": "4/4",
        },
        dotted=dotted,
    )
    text = tmp_out.read_text(encoding="utf-8")
    return _normalize_xml_text(text)


def test_musicxml_export_matches_local_tab_golden(tmp_path: Path) -> None:
    actual = _export_piece_subset_to_musicxml_text("examples/si_par_souffrir.tab", bars=2, tmp_path=tmp_path)
    expected = (FIXTURES / "si_par_souffrir_2bars.musicxml.norm").read_text(encoding="utf-8")
    assert actual == expected


def test_musicxml_export_matches_local_ft3_golden(tmp_path: Path) -> None:
    actual = _export_piece_subset_to_musicxml_text(
        "examples/26_lachrimae_galliard_in_G.ft3",
        bars=2,
        tmp_path=tmp_path,
    )
    expected = (FIXTURES / "lachrimae_2bars.musicxml.norm").read_text(encoding="utf-8")
    assert actual == expected
