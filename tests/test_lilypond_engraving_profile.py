from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from oud.exports.lilypond import export_lilypond
from oud.importers.ft3 import load_ft3
from oud.settings import DEFAULT_SETTINGS
from petrucci import Bar, Piece
from petrucci.engraving.layout.engine import LayoutViewport, NotationLayoutPolicy, layout_score
from scripts.corpus.fetch import load_manifest, manifest_paths
from tests.engraving_quality_matrix import (
    MATRIX_PATH,
    assert_lilypond_contract,
    assert_proof_contract,
    fixture_for,
    load_quality_matrix,
)

MATRIX = MATRIX_PATH


def test_engraving_matrix_links_proof_export_and_upstream_invariants() -> None:
    matrix = load_quality_matrix()

    assert matrix["schema"] == 1
    assert matrix["profiles"] == ["petrucci", "classic"]
    assert matrix["publication_engines"]["baseline"] == "2.26"
    assert matrix["publication_engines"]["compatibility"] == "2.24"
    assert len(matrix["cases"]) >= 5
    assert "gerbode-multiverse-registration" in {case["id"] for case in matrix["cases"]}
    case_ids = {case["id"] for case in matrix["cases"]}
    assert len(matrix["microcases"]) >= 3
    assert len(matrix["upstream_microcases"]) >= 4
    for microcase in matrix["microcases"]:
        assert microcase["case"] in case_ids
        assert microcase["assertions"]
    for microcase in matrix["upstream_microcases"]:
        assert microcase["test"]
        assert microcase["sources"]
        assert microcase["invariant"]
    for case in matrix["cases"]:
        assert case["features"]
        assert case["fixture"] == case["id"]
        assert case["proof"]["required_roles"]
        assert case["lilypond"]["contains"]
        assert case["petrucci_contract"]
        assert case["lilypond_contract"]
        assert case["upstream"]


def test_quality_matrix_drives_petrucci_and_lilypond_contracts(tmp_path: Path) -> None:
    matrix = load_quality_matrix()
    for case in matrix["cases"]:
        fixture = fixture_for(case["fixture"])
        layout = layout_score(
            fixture.score,
            viewport=LayoutViewport(width=160, height=60),
            policy=NotationLayoutPolicy(show_title=False),
        )
        assert_proof_contract(case, fixture, layout)

        source = tmp_path / f"{case['id']}.ly"
        settings = dict(DEFAULT_SETTINGS)
        settings.update(fixture.settings)
        export_lilypond(
            str(source),
            fixture.piece,
            fixture.overrides,
            fixture.durations,
            12,
            settings=settings,
            slurs=fixture.slurs,
            ties=fixture.ties,
        )
        assert_lilypond_contract(case, source.read_text(encoding="utf-8"))


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
        timeout=10,
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
        timeout=60,
    )

    assert result.returncode == 0, result.stderr
    assert "warning:" not in result.stderr.lower()


def test_curated_ft3_exports_compile_with_lilypond_baseline(tmp_path: Path) -> None:
    executable = shutil.which(DEFAULT_SETTINGS["lilypond"])
    if executable is None:
        pytest.skip(f"{DEFAULT_SETTINGS['lilypond']} is not installed")
    version = subprocess.run(  # noqa: S603
        [executable, "--version"],
        capture_output=True,
        check=False,
        text=True,
        timeout=10,
    ).stdout
    if " 2.26." not in version:
        pytest.skip("configured LilyPond binary is not 2.26")

    manifest = load_manifest(Path("tests/fixtures/ft3/manifests/ft3-regression.json"))
    paths = manifest_paths(manifest)
    missing = [path for path in paths if not path.is_file()]
    if missing:
        pytest.skip(f"external FT3 regression corpus is incomplete ({len(missing)} missing files)")

    environment = os.environ.copy()
    environment["XDG_CACHE_HOME"] = str(tmp_path / "cache")
    settings = dict(DEFAULT_SETTINGS)
    settings.update({"lilypondversion": "2.26", "lyprofile": "petrucci"})
    for index, path in enumerate(paths):
        piece = load_ft3(str(path))
        piece_settings = dict(settings)
        if piece.tuning:
            piece_settings["tuning"] = piece.tuning
        source = tmp_path / f"curated-{index:03d}.ly"
        export_lilypond(
            str(source),
            piece,
            {},
            {},
            12,
            settings=piece_settings,
        )
        result = subprocess.run(  # noqa: S603
            [executable, "-dno-print-pages", "-o", str(tmp_path / f"compiled-{index:03d}"), str(source)],
            capture_output=True,
            check=False,
            env=environment,
            text=True,
            timeout=60,
        )
        output = f"{result.stdout}\n{result.stderr}".lower()
        assert result.returncode == 0, f"{path}: {result.stderr}"
        assert "warning:" not in output, f"{path}: {result.stderr}"


def test_lilypond_226_is_the_configured_baseline() -> None:
    assert DEFAULT_SETTINGS["lilypond"] == "lilypond-2.26"
    assert DEFAULT_SETTINGS["lilypondversion"] == "2.26"
    assert DEFAULT_SETTINGS["lytabrhythm"] == "full"
