from __future__ import annotations

from pathlib import Path

from oud.core.tab_parser import load_tab
from oud.exports.export_tab import export_tab


def test_tab_roundtrip_basic(tmp_path) -> None:
    source = "\n".join(
        [
            "{Test Piece/Composer}",
            "-tuning g2c3f3a3d4g4",
            "b",
            "S4",
            "0a-----",
            "1b-----",
            "",
            "e",
        ],
    )
    path = tmp_path / "sample.tab"
    path.write_text(source, encoding="utf-8")

    piece = load_tab(str(path))
    assert piece.bars
    assert piece.bars[0].chords
    assert piece.tuning == "g2c3f3a3d4g4"
    assert piece.title == "Test Piece"
    assert piece.composer == "Composer"

    exported = export_tab(piece, {}, {}, bar_width=8, settings={"style": "french"})
    assert "b" in exported
    assert "e" in exported
    assert "-tuning g2c3f3a3d4g4" in exported
    assert "{Test Piece/Composer}" in exported

    out_path = tmp_path / "roundtrip.tab"
    out_path.write_text(exported, encoding="utf-8")
    piece2 = load_tab(str(out_path))
    assert len(piece2.bars) == len(piece.bars)
    assert len(piece2.bars[0].chords) == len(piece.bars[0].chords)


def test_tab_export_matches_golden(tmp_path) -> None:
    base = tmp_path / "fixtures"
    base.mkdir()
    source = (Path(__file__).parent / "fixtures" / "roundtrip_basic.tab").read_text(
        encoding="utf-8",
    )
    expected = (Path(__file__).parent / "fixtures" / "roundtrip_basic_expected.tab").read_text(encoding="utf-8")
    src_path = base / "roundtrip_basic.tab"
    src_path.write_text(source, encoding="utf-8")

    piece = load_tab(str(src_path))
    exported = export_tab(
        piece,
        overrides={},
        durations={},
        bar_width=8,
        settings={"style": "french"},
    )
    assert exported == expected
