from pathlib import Path

import pytest

from oud.core.ft3 import load_ft3
from oud.petrucci.typeset import TypesetOptions, typeset_piece

CORPUS = Path("lutemusic")
VIEWER_CASES = (
    "01_felice_fu_quel_anon.ft3",
    "05_can_she_excuse/can_she_excuse_4_part.ft3",
    "01_unquiet_thoughts/unquiet_thoughts_4-part.ft3",
    "now_o_now.ft3",
)


def _typeset(path: str, *, playback: tuple[int, int] | None = None):
    piece = load_ft3(str(CORPUS / path))
    result = typeset_piece(
        piece,
        options=TypesetOptions(width=100, height=50),
        playback=playback,
    )
    return piece, result


def test_local_ft3_corpus_has_no_unresolved_viewer_warnings() -> None:
    paths = sorted(CORPUS.rglob("*.ft3"))
    assert len(paths) >= 35
    warned: dict[str, list[str]] = {}
    for path in paths:
        warnings = load_ft3(str(path)).import_warnings
        if warnings:
            warned[str(path.relative_to(CORPUS))] = warnings
    assert warned == {}


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
    assert playing.lines != idle.lines
    assert "^" in playing.text
    assert playing.frame.attrs != idle.frame.attrs
