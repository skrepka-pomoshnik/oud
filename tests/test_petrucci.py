from __future__ import annotations

import ast
from pathlib import Path

from oud.core.model import Piece as LegacyPiece
from oud.petrucci import (
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
from oud.petrucci import render as petrucci_render
from oud.ui import render as legacy_render


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


def test_petrucci_model_is_canonical_legacy_model() -> None:
    assert LegacyPiece is Piece
    assert legacy_render is petrucci_render


def test_petrucci_has_no_core_or_ui_imports() -> None:
    package = Path("oud/petrucci")
    forbidden: list[tuple[str, str]] = []
    for path in package.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if node.module.startswith(("oud.core", "oud.ui")):
                    forbidden.append((path.name, node.module))
            elif isinstance(node, ast.Import):
                forbidden.extend(
                    (path.name, alias.name)
                    for alias in node.names
                    if alias.name.startswith(("oud.core", "oud.ui"))
                )
    assert forbidden == []


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
