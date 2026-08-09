from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from oud.exports.lilypond import export_lilypond
from petrucci import Bar, Piece

MATRIX = Path("corpus/engraving-quality-matrix.json")


def test_engraving_matrix_links_proof_export_and_upstream_invariants() -> None:
    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))

    assert matrix["schema"] == 1
    assert matrix["profiles"] == ["petrucci", "classic"]
    assert len(matrix["cases"]) >= 5
    for case in matrix["cases"]:
        assert case["features"]
        assert case["petrucci_contract"]
        assert case["lilypond_contract"]
        assert case["upstream"]


def _export_profile(tmp_path: Path, profile: str) -> str:
    path = tmp_path / f"{profile}.ly"
    piece = Piece(title="Registration proof", bars=[Bar()], strings=6)
    export_lilypond(
        str(path),
        piece,
        {},
        {},
        12,
        settings={"lyprofile": profile, "style": "french", "tuning": "g4d4a3f3c3g2"},
    )
    return path.read_text(encoding="utf-8")


def test_petrucci_profile_is_default_and_classic_is_an_escape_hatch(tmp_path: Path) -> None:
    petrucci = _export_profile(tmp_path, "petrucci")
    classic = _export_profile(tmp_path, "classic")

    assert "#(set-global-staff-size 16)" in petrucci
    assert "\\override StaffSymbol.thickness = #0.7" in petrucci
    assert "\\override TabNoteHead.font-size = #-1" in petrucci
    assert "#(set-global-staff-size 16)" not in classic
    assert classic.count(r"\paper { indent = 0\mm }") == 1


@pytest.mark.skipif(shutil.which("lilypond") is None, reason="LilyPond is not installed")
def test_petrucci_profile_compiles_without_warnings(tmp_path: Path) -> None:
    source = tmp_path / "petrucci.ly"
    piece = Piece(title="Registration proof", bars=[Bar()], strings=6)
    export_lilypond(
        str(source),
        piece,
        {},
        {},
        12,
        settings={"lyprofile": "petrucci", "style": "french", "tuning": "g4d4a3f3c3g2"},
    )

    result = subprocess.run(  # noqa: S603
        ["lilypond", "-dno-print-pages", "-o", str(tmp_path / "proof"), str(source)],  # noqa: S607
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "warning:" not in result.stderr.lower()
