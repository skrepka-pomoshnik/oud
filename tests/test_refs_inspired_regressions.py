from __future__ import annotations

from pathlib import Path

from oud.editor.services.io.loading import load_piece_data
from oud.exports.export_tab import export_tab
from oud.importers.tab import load_tab
from petrucci.rendering.primitives.utils import chord_positions, note_type_to_denom
from tests.helpers_ft3 import write_galliard


def _piece_signature(piece) -> tuple:
    """refs/luteconv-inspired: compare normalized structure, not volatile text headers."""
    bars: list[tuple] = []
    meter = None
    for bar in piece.bars:
        # TAB states a meter only where it changes, so compare the meter in force.
        meter = bar.time_sig or meter
        chords: list[tuple] = []
        for chord in bar.chords:
            notes = tuple(sorted((n.string, n.fret) for n in chord.notes))
            chords.append((chord.note_type, bool(chord.dotted), notes))
        bars.append((meter, tuple(chords)))
    return (
        piece.title,
        piece.strings,
        piece.tuning,
        tuple(bars),
    )


def test_tab_roundtrip_matrix_on_hand_built_fixtures_refs_luteconv_style(tmp_path: Path) -> None:
    # Test strategy inspired by refs/luteconv convert_test.cpp (fixture matrix conversion).
    paths = [
        write_galliard(tmp_path),
        Path("tests/fixtures/tab/minimal_score.tab"),
        Path("examples/triste.tab"),
    ]
    for src in paths:
        piece, overrides, durations, dotted, bar_width = load_piece_data(str(src))
        width = bar_width or 12
        exported = export_tab(
            piece,
            overrides=overrides,
            durations=durations,
            bar_width=width,
            settings={"style": piece.style or "french", "tuning": piece.tuning or ""},
            dotted=dotted,
        )
        out = tmp_path / f"{src.stem}.roundtrip.tab"
        out.write_text(exported, encoding="utf-8")

        piece2 = load_tab(str(out), strings=piece.strings)
        assert len(piece2.bars) == len(piece.bars), src
        assert piece2.strings == piece.strings, src
        assert _piece_signature(piece2) == _piece_signature(piece), src


def test_chord_positions_invariants_on_hand_built_examples_refs_vexflow_tickstyle(tmp_path: Path) -> None:
    # Test idea inspired by refs/vexflow tick/tickcontext invariants: spacing timeline must be monotonic.
    paths = [write_galliard(tmp_path), Path("examples/triste.tab")]
    for path in paths:
        piece, _o, _d, _dot, _w = load_piece_data(str(path))
        for bar in piece.bars:
            positions = chord_positions(bar, bar_width=12, default_duration=4)
            cols = [col for col, _denom, _dot in positions]
            assert cols == sorted(cols), (path, cols)
            if len(cols) != len(set(cols)):
                first_dup = next(i for i in range(1, len(cols)) if cols[i] == cols[i - 1])
                assert all(col == 11 for col in cols[first_dup:]), (path, cols)
            for _col, denom, _is_dotted in positions:
                assert denom in {1, 2, 4, 8, 16, 32, 64, 128, 256}, (path, denom)
                # Sanity: displayed denominator maps to a known note type domain.
                assert any(note_type_to_denom(nt) == denom for nt in range(2, 11)), (path, denom)
