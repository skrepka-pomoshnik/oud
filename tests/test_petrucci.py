from __future__ import annotations

import ast
import re
import subprocess
import sys
from pathlib import Path

import petrucci
from petrucci import (
    Bar,
    Chord,
    LyricEvent,
    MelodyEvent,
    Note,
    Piece,
    TypesetOptions,
    typeset_piece,
    typeset_text,
)

_SCORE_PUBLIC_API = {
    "AccidentalDisplay",
    "ElementKey",
    "ElementRole",
    "EventLocation",
    "EventKind",
    "GlyphMode",
    "LayoutElement",
    "LayoutError",
    "LayoutMetrics",
    "LayoutViewport",
    "LyricSyllable",
    "NotationEvent",
    "NotationLayoutPolicy",
    "NotationMeasure",
    "NotationScore",
    "NotationSpan",
    "NotationStaff",
    "OnsetPosition",
    "OrnamentKind",
    "Rect",
    "ScoreLayout",
    "ScoreSystem",
    "ScoreTypesetOptions",
    "ScoreTypesetResult",
    "SemanticFrame",
    "StaffRows",
    "layout_score",
    "paint_score",
    "typeset_score",
}


def _score() -> Piece:
    return Piece(
        title="Petrucci",
        composer="ASCII",
        bars=[
            Bar(
                chords=[
                    Chord(
                        note_type=4,
                        dotted=False,
                        grid=None,
                        notes=[Note(string=1, fret=0, raw_pos=0)],
                    ),
                ],
                melody_events=[MelodyEvent(text="c4", onset_index=0, note_type=4)],
                lyric_event_rows=[[LyricEvent(text="la", onset_index=0)]],
            ),
        ],
        strings=6,
        style="french",
    )


def test_petrucci_has_no_application_layer_imports() -> None:
    package = Path("petrucci")
    forbidden: list[tuple[str, str]] = []
    for path in package.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if node.module == "oud" or node.module.startswith("oud."):
                    forbidden.append((path.name, node.module))
            elif isinstance(node, ast.Import):
                forbidden.extend(
                    (path.name, alias.name)
                    for alias in node.names
                    if alias.name == "oud" or alias.name.startswith("oud.")
                )
    assert forbidden == []


def test_public_petrucci_contract_has_no_result_policy_vocabulary() -> None:
    forbidden = re.compile(r"(?:^|_)(?:hit|missed|pending|uncertain|feedback)(?:$|_)")
    assert [name for name in petrucci.__all__ if forbidden.search(name.lower())] == []
    for removed_name in ("CellStyle", "EventOverlay", "OverlayRole"):
        assert not hasattr(petrucci, removed_name)


def test_generic_petrucci_modules_only_import_the_standard_library_and_petrucci() -> None:
    generic = (
        Path("petrucci/display.py"),
        Path("petrucci/layout.py"),
        Path("petrucci/notation_layout.py"),
        Path("petrucci/score.py"),
        Path("petrucci/system_fitting.py"),
    )
    forbidden: list[tuple[str, str]] = []
    for path in generic:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.ImportFrom) and node.module:
                names.append(node.module)
            elif isinstance(node, ast.Import):
                names.extend(alias.name for alias in node.names)
            forbidden.extend(
                (path.name, name) for name in names if name.startswith("oud.") and not name.startswith("petrucci")
            )
    assert forbidden == []


def test_importing_public_petrucci_does_not_initialize_curses() -> None:
    code = (
        "import sys; import petrucci as petrucci; "
        "[getattr(petrucci, name) for name in petrucci.__all__]; "
        "assert 'oud' not in sys.modules; "
        "assert 'curses' not in sys.modules"
    )
    completed = subprocess.run(  # noqa: S603 - fixed interpreter and source string
        [sys.executable, "-c", code],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr


def test_public_score_api_is_exported_and_resolvable() -> None:
    assert set(petrucci.__all__) >= _SCORE_PUBLIC_API
    assert all(getattr(petrucci, name) is not None for name in _SCORE_PUBLIC_API)


def test_typeset_piece_returns_frame_text_and_cursor_map() -> None:
    result = typeset_piece(
        _score(),
        options=TypesetOptions(width=64, height=30, bar_width=10),
    )

    assert len(result.lines) == 30
    assert all(len(line) == 64 for line in result.lines)
    assert "Petrucci" in result.text
    assert "la" in result.text
    assert result.cursor_display_maps


def test_typeset_text_convenience_omits_editor_status() -> None:
    text = typeset_text(
        _score(),
        options=TypesetOptions(width=64, height=22, bar_width=10),
    )

    assert "normal  len:" not in text
    assert text.endswith("\n")
