from pathlib import Path

import pytest

from oud.exports.lilypond import export_lilypond
from oud.importers.ft3 import load_ft3
from petrucci.model import Piece
from petrucci.typeset import TypesetOptions, typeset_piece
from scripts.fetch_ft3_corpus import load_manifest, manifest_paths

CORPUS = Path("lutemusic")
VIEWER_CASES = (
    "01_felice_fu_quel_anon.ft3",
    "05_can_she_excuse/can_she_excuse_4_part.ft3",
    "01_unquiet_thoughts/unquiet_thoughts_4-part.ft3",
    "now_o_now.ft3",
)


@pytest.fixture(scope="module")
def loaded_corpus() -> list[tuple[Path, Piece]]:
    manifest = load_manifest(Path("corpus/ft3-regression.json"))
    paths = [path for path in manifest_paths(manifest) if path.is_relative_to(CORPUS.resolve())]
    missing = [path for path in paths if not path.is_file()]
    if missing:
        pytest.skip("fetch corpus/ft3-regression.json before running external corpus tests")
    return [(path, load_ft3(str(path))) for path in paths]


def _typeset(path: str, *, playback: tuple[int, int] | None = None):
    piece = load_ft3(str(CORPUS / path))
    result = typeset_piece(
        piece,
        options=TypesetOptions(width=100, height=50),
        playback=playback,
    )
    return piece, result


def test_local_ft3_corpus_has_no_unresolved_viewer_warnings(
    loaded_corpus: list[tuple[Path, Piece]],
) -> None:
    assert len(loaded_corpus) == 17
    warned: dict[str, list[str]] = {}
    for path, piece in loaded_corpus:
        warnings = piece.import_warnings
        if warnings:
            warned[str(path.relative_to(CORPUS))] = warnings
    assert warned == {}


def test_local_ft3_corpus_has_no_unknown_imported_staffs(
    loaded_corpus: list[tuple[Path, Piece]],
) -> None:
    unknown = {}
    for path, piece in loaded_corpus:
        score = piece.imported_score
        if score is None:
            continue
        kinds = [staff.kind for staff in score.staffs]
        if "unknown" in kinds:
            unknown[str(path.relative_to(CORPUS))] = kinds
    assert unknown == {}


def test_local_ft3_metadata_keys_are_covered_by_canonical_fields(
    loaded_corpus: list[tuple[Path, Piece]],
) -> None:
    canonical_keys = {"type", "dif", "ensemble", "part", "piece", "arranger", "con"}
    uncovered: dict[str, list[str]] = {}
    for path, piece in loaded_corpus:
        extra = sorted(key for key in piece.raw_metadata if key not in canonical_keys and not key.endswith("key"))
        if extra:
            uncovered[str(path.relative_to(CORPUS))] = extra
        if any(key.endswith("key") for key in piece.raw_metadata):
            assert piece.key
        if "type" in piece.raw_metadata:
            assert piece.piece_type
        if "ensemble" in piece.raw_metadata:
            assert piece.ensemble
    assert uncovered == {}


def test_local_ft3_corpus_exports_to_lilypond(
    loaded_corpus: list[tuple[Path, Piece]],
    tmp_path: Path,
) -> None:
    for index, (source, piece) in enumerate(loaded_corpus):
        target = tmp_path / f"{index:02d}.ly"
        export_lilypond(
            str(target),
            piece,
            overrides={},
            durations={},
            bar_width=12,
            settings={"showmelody": "on", "showlyrics": "on"},
        )
        text = target.read_text(encoding="utf-8")
        assert "Staff" in text, source
        assert len(text) > 100, source


@pytest.mark.parametrize("path", VIEWER_CASES)
def test_release_viewer_cases_render_visible_score_content(path: str) -> None:
    piece, result = _typeset(path)
    assert piece.import_warnings == []
    assert result.cursor_display_maps
    assert sum("|" in line for line in result.lines) >= 6
    if piece.imported_score is not None:
        assert all(staff.kind != "unknown" for staff in piece.imported_score.staffs)


def test_felice_narrow_view_keeps_at_least_one_tablature_bar() -> None:
    _piece, result = _typeset("01_felice_fu_quel_anon.ft3")
    assert any(line.lstrip().startswith("6|") and "-" in line for line in result.lines)


@pytest.mark.parametrize(
    "path",
    (
        "05_can_she_excuse/can_she_excuse_4_part.ft3",
        "01_unquiet_thoughts/unquiet_thoughts_4-part.ft3",
        "now_o_now.ft3",
    ),
)
def test_vocal_and_multipart_playback_updates_shared_render_map(path: str) -> None:
    _piece, idle = _typeset(path)
    _piece, playing = _typeset(path, playback=(0, 0))
    assert playing.frame.attrs != idle.frame.attrs
    if playing.lines == idle.lines:
        assert "^" not in playing.text  # Canonical score overlays do not reflow glyph geometry.
    else:
        assert "^" in playing.text
