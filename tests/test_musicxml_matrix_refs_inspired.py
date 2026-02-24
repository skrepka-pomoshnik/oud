from __future__ import annotations

from pathlib import Path

from oud.core.musicxml_import import load_musicxml, load_mxl
from oud.editor.load_ops import load_piece_data
from oud.exports.musicxml import export_musicxml, export_mxl


def _musicxml_supported_signature(piece) -> tuple:
    """Normalized subset expected to roundtrip through our current MusicXML support.

    Test strategy inspired by refs/luteconv fixture conversion matrix:
    compare normalized converted structure across a small real-file matrix.
    """
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
        bars.append((bar.repeat, tuple(chords)))
    return (piece.strings, tuple(bars))


def _assert_musicxml_roundtrip_subset(src_path: str, tmp_path: Path) -> None:
    piece, overrides, durations, dotted, bar_width = load_piece_data(src_path)
    width = bar_width or 12
    settings = {
        "style": piece.style or "french",
        "tuning": piece.tuning or "g2c3f3a3d4g4",
        "time": "4/4",
        "key": piece.key or "C",
    }
    xml_path = tmp_path / (Path(src_path).stem + ".musicxml")
    mxl_path = tmp_path / (Path(src_path).stem + ".mxl")
    export_musicxml(
        str(xml_path),
        piece,
        overrides=overrides,
        durations=durations,
        bar_width=width,
        settings=settings,
        dotted=dotted,
    )
    export_mxl(
        str(mxl_path),
        piece,
        overrides=overrides,
        durations=durations,
        bar_width=width,
        settings=settings,
        dotted=dotted,
    )

    xml_piece = load_musicxml(str(xml_path))
    mxl_piece = load_mxl(str(mxl_path))
    src_sig = _musicxml_supported_signature(piece)
    assert _musicxml_supported_signature(xml_piece) == src_sig
    assert _musicxml_supported_signature(mxl_piece) == src_sig


def test_musicxml_matrix_real_examples_refs_luteconv_style(tmp_path: Path) -> None:
    paths = [
        "examples/si_par_souffrir.tab",
        "examples/2_intrada_anon.tab",
        "examples/Sarabande_de_gautier.tab",
        "examples/02_forlorne_hope_8C.ft3",
        "examples/26_lachrimae_galliard_in_G.ft3",
    ]
    for path in paths:
        _assert_musicxml_roundtrip_subset(path, tmp_path)
