from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from oud.exports.lilypond import export_lilypond
from oud.settings import DEFAULT_SETTINGS
from petrucci import Bar, Piece

MATRIX = Path("corpus/engraving-quality-matrix.json")


def test_engraving_matrix_links_proof_export_and_upstream_invariants() -> None:
    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))

    assert matrix["schema"] == 1
    assert matrix["profiles"] == ["petrucci", "classic"]
    assert matrix["publication_engines"]["baseline"] == "2.26"
    assert matrix["publication_engines"]["compatibility"] == "2.24"
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
    assert '\\version "2.26.0"' in petrucci
    assert "indent = 22\\mm" in petrucci
    assert "short-indent = 0\\mm" in petrucci
    assert "ragged-bottom = ##t" in petrucci
    assert "oddFooterMarkup = ##f" in petrucci
    assert "#(set-global-staff-size 16)" not in classic
    assert classic.count(r"\paper { indent = 0\mm }") == 1


def test_lilypond_224_compatibility_source_is_explicit(tmp_path: Path) -> None:
    source = tmp_path / "compat.ly"
    piece = Piece(title="Registration proof", bars=[Bar()], strings=6)
    export_lilypond(
        str(source),
        piece,
        {},
        {},
        12,
        settings={
            "lilypondversion": "2.24",
            "lyprofile": "petrucci",
            "style": "french",
            "tuning": "g4d4a3f3c3g2",
        },
    )

    assert '\\version "2.24.0"' in source.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("binary", "source_version"),
    [("lilypond-2.26", "2.26"), ("lilypond", "2.24")],
)
def test_supported_lilypond_engines_compile_without_warnings(
    tmp_path: Path,
    binary: str,
    source_version: str,
) -> None:
    executable = shutil.which(binary)
    if executable is None:
        pytest.skip(f"{binary} is not installed")
    version = subprocess.run(  # noqa: S603
        [executable, "--version"],
        capture_output=True,
        check=False,
        text=True,
    ).stdout
    if f" {source_version}." not in version:
        pytest.skip(f"{binary} is not LilyPond {source_version}")

    source = tmp_path / f"petrucci-{source_version}.ly"
    piece = Piece(title="Registration proof", bars=[Bar()], strings=6)
    export_lilypond(
        str(source),
        piece,
        {},
        {},
        12,
        settings={
            "lilypondversion": source_version,
            "lyprofile": "petrucci",
            "style": "french",
            "tuning": "g4d4a3f3c3g2",
        },
    )
    environment = os.environ.copy()
    environment["XDG_CACHE_HOME"] = str(tmp_path / "cache")

    result = subprocess.run(  # noqa: S603
        [executable, "-dno-print-pages", "-o", str(tmp_path / "proof"), str(source)],
        capture_output=True,
        check=False,
        env=environment,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "warning:" not in result.stderr.lower()


def test_lilypond_226_is_the_configured_baseline() -> None:
    assert DEFAULT_SETTINGS["lilypond"] == "lilypond-2.26"
    assert DEFAULT_SETTINGS["lilypondversion"] == "2.26"
