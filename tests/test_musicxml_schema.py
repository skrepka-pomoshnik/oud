"""Oud's MusicXML output validates against the W3C schema (needs xmllint and the schema; see docs/musicxml-support.md)."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from oud.exports.musicxml import musicxml_text
from oud.importers.tab import load_tab
from petrucci.core.model import Bar, Chord, Note, Piece
from tests.test_layered_scores import _layered_piece

SCHEMA_FILES = ("musicxml.xsd", "xml.xsd", "xlink.xsd")
REMOTE_IMPORTS = {
    "http://www.musicxml.org/xsd/xml.xsd": "xml.xsd",
    "http://www.musicxml.org/xsd/xlink.xsd": "xlink.xsd",
}

pytestmark = pytest.mark.musicxml_schema


def _chord(note_type: int, *notes: tuple[int, int], dotted: bool = False) -> Chord:
    return Chord(note_type, dotted, None, [Note(course, fret, 0) for course, fret in notes])


def _edge_piece() -> Piece:
    piece = Piece(
        title="Edge",
        composer="C",
        author="A",
        strings=10,
        style="italian",
        bars=[
            Bar(chords=[_chord(4, (1, 0), (7, 0)), _chord(5, (2, 12), dotted=True), _chord(6), _chord(6, (10, 0))]),
            Bar(chords=[_chord(4, (1, 1))], time_sig="3"),
            Bar(),
            Bar(chords=[_chord(2, (1, 0))], time_sig="6/8", repeat=".:"),
            Bar(chords=[_chord(9, (1, 0))], time_sig="C|", repeat=":."),
        ],
    )
    piece.bars[0].time_sig = "C"
    piece.tuning = "c2d2e2f2g2c3f3a3d4g4"
    piece.tempo = 90
    return piece


@pytest.fixture(scope="module")
def schema(tmp_path_factory: pytest.TempPathFactory) -> Path:
    xmllint = shutil.which("xmllint")
    directory = os.environ.get("MUSICXML_SCHEMA_DIR", "")
    if not xmllint or not directory:
        pytest.skip("set MUSICXML_SCHEMA_DIR to the schema/ folder of github.com/w3c/musicxml and install xmllint")
    target = tmp_path_factory.mktemp("musicxml-schema")
    for name in SCHEMA_FILES:
        text = (Path(directory) / name).read_text(encoding="utf-8")
        for remote, local in REMOTE_IMPORTS.items():
            text = text.replace(remote, local)
        (target / name).write_text(text, encoding="utf-8")
    return target / "musicxml.xsd"


def _validate(schema: Path, text: str, tmp_path: Path) -> None:
    xmllint = shutil.which("xmllint")
    assert xmllint is not None
    document = tmp_path / "score.musicxml"
    document.write_text(text, encoding="utf-8")
    result = subprocess.run(  # noqa: S603 - xmllint from PATH, fixed arguments, no shell
        [xmllint, "--noout", "--schema", str(schema), str(document)],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    "path",
    sorted([*Path("examples").glob("*.tab"), *Path("tests/fixtures").glob("**/*.tab")]),
    ids=str,
)
def test_repo_tab_files_export_valid_musicxml(schema: Path, path: Path, tmp_path: Path) -> None:
    piece = load_tab(str(path))
    settings = {"style": piece.style or "french", "tuning": piece.tuning or ""}

    _validate(schema, musicxml_text(piece, {}, {}, 12, settings=settings), tmp_path)


def test_layered_score_exports_valid_musicxml(schema: Path, tmp_path: Path) -> None:
    _validate(schema, musicxml_text(_layered_piece(), {}, {}, 12, settings={"style": "french"}), tmp_path)


def test_edge_cases_export_valid_musicxml(schema: Path, tmp_path: Path) -> None:
    piece = _edge_piece()
    _validate(
        schema, musicxml_text(piece, {}, {}, 12, settings={"style": "italian", "tuning": piece.tuning or ""}), tmp_path
    )
