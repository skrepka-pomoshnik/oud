from __future__ import annotations

import gzip
from pathlib import Path

from oud.core.musicxml_import import load_musicxml, load_mxl
from oud.core.tab_parser import load_tab
from oud.editor.load_ops import load_piece_data
from oud.exports.export_tab import export_tab
from oud.exports.musicxml import export_musicxml, export_mxl
from tests.helpers_regression_cases import mk_bar, mk_chord, mk_piece


def _sig_tab_piece(piece) -> tuple:
    bars: list[tuple] = []
    for bar in piece.bars:
        chords = [
            (
                chord.note_type,
                bool(chord.dotted),
                tuple(sorted((n.string, n.fret) for n in chord.notes)),
            )
            for chord in bar.chords
        ]
        bars.append((bar.time_sig, tuple(chords)))
    return (piece.strings, piece.style, piece.tuning, tuple(bars))


def _sig_musicxml_subset(piece) -> tuple:
    bars: list[tuple] = []
    for bar in piece.bars:
        chords = [
            (
                chord.note_type,
                bool(chord.dotted),
                tuple((n.string, n.fret) for n in chord.notes),
            )
            for chord in bar.chords
        ]
        bars.append(tuple(chords))
    return (piece.strings, tuple(bars))


def _synthetic_piece():
    return mk_piece(
        [
            mk_bar(
                [
                    mk_chord(4, [(1, 0), (3, 2)]),
                    mk_chord(5, [(2, 1)]),
                    mk_chord(5, [(1, 10)]),
                ],
                time_sig="C",
                repeat=".:",
            ),
            mk_bar(
                [
                    mk_chord(4, [(7, 0), (1, 3)]),
                    mk_chord(4, [(8, 2)]),
                ],
                time_sig="O",
                barline="||",
                repeat=":.",
            ),
        ],
        strings=8,
        style="french",
        title="Synthetic Conversion",
        tuning="g2c3f3a3d4g4d2c2",
    )


def test_supported_conversion_roundtrip_matrix_synthetic_subset(tmp_path: Path) -> None:
    piece = _synthetic_piece()
    settings = {
        "style": piece.style or "french",
        "tuning": "g2c3f3a3d4g4d2c2",
        "time": "4/4",
        "key": "C",
    }

    tab_out = export_tab(piece, overrides={}, durations={}, bar_width=12, settings=settings)
    tab_path = tmp_path / "synthetic.tab"
    tab_path.write_text(tab_out, encoding="utf-8")
    tab_piece = load_tab(str(tab_path), strings=piece.strings)
    assert _sig_tab_piece(tab_piece) == _sig_tab_piece(piece)

    xml_path = tmp_path / "synthetic.musicxml"
    mxl_path = tmp_path / "synthetic.mxl"
    export_musicxml(str(xml_path), piece, {}, {}, 12, settings, dotted=set())
    export_mxl(str(mxl_path), piece, {}, {}, 12, settings, dotted=set())
    xml_piece = load_musicxml(str(xml_path))
    mxl_piece = load_mxl(str(mxl_path))
    assert _sig_musicxml_subset(xml_piece) == _sig_musicxml_subset(piece)
    assert _sig_musicxml_subset(mxl_piece) == _sig_musicxml_subset(piece)


def test_load_piece_data_synthetic_input_matrix_supported_formats(tmp_path: Path) -> None:
    piece = _synthetic_piece()
    settings = {
        "style": piece.style or "french",
        "tuning": "g2c3f3a3d4g4d2c2",
        "time": "4/4",
        "key": "C",
    }

    tab_path = tmp_path / "in.tab"
    tab_path.write_text(export_tab(piece, overrides={}, durations={}, bar_width=12, settings=settings), encoding="utf-8")

    xml_path = tmp_path / "in.musicxml"
    mxl_path = tmp_path / "in.mxl"
    export_musicxml(str(xml_path), piece, {}, {}, 12, settings, dotted=set())
    export_mxl(str(mxl_path), piece, {}, {}, 12, settings, dotted=set())

    ft3_path = tmp_path / "mini.ft3.gz"
    with gzip.open(ft3_path, "wb") as f:
        f.write(b"CPiece\x04Test\x03\x80")

    for path in (tab_path, xml_path, mxl_path, ft3_path):
        loaded_piece, overrides, durations, dotted, bar_width = load_piece_data(str(path))
        assert loaded_piece is not None
        assert isinstance(overrides, dict)
        assert isinstance(durations, dict)
        assert isinstance(dotted, set)
        assert bar_width is None or isinstance(bar_width, int)
