"""Oud → MusicXML → Oud keeps everything Oud models (TODO C16 step 1)."""

from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from oud.exports.musicxml import musicxml_text
from oud.importers.musicxml import _parse_piece
from oud.importers.tab import load_tab
from petrucci.core.model import Bar, Chord, Note, Piece

DEFAULT_METER = "4/4"


def _chord(note_type: int, *notes: tuple[int, int], dotted: bool = False) -> Chord:
    return Chord(note_type, dotted, None, [Note(course, fret, 0) for course, fret in notes])


def _round_trip(piece: Piece) -> tuple[str, Piece]:
    settings = {"style": piece.style or "french", "tuning": piece.tuning or "", "time": "4/4"}
    text = musicxml_text(piece, {}, {}, 12, settings=settings)
    return text, _parse_piece(ET.fromstring(text))  # noqa: S314 - text Oud just wrote


def _events(piece: Piece) -> list[tuple[str, list[tuple[int, bool, list[tuple[int, int]]]]]]:
    # MusicXML always states the first bar's meter, so compare the meter in effect, not where it is written.
    meter = DEFAULT_METER
    events = []
    for bar in piece.bars:
        meter = bar.time_sig or meter
        events.append(
            (meter, [(c.note_type, c.dotted, sorted((n.string, n.fret) for n in c.notes)) for c in bar.chords])
        )
    return events


def _metadata(piece: Piece) -> tuple[object, ...]:
    return (piece.title, piece.composer, piece.author, piece.tuning, piece.tempo, piece.strings, piece.style)


@pytest.mark.parametrize("style", ["french", "italian"])
def test_everything_oud_models_survives(style: str) -> None:
    piece = Piece(
        title="S",
        composer="C",
        author="A",
        bars=[
            Bar(chords=[_chord(4, (1, 0), (7, 0)), _chord(5, (2, 3), dotted=True), _chord(6), _chord(6, (10, 0))]),
            Bar(chords=[_chord(4, (1, 12)), _chord(4), _chord(4, (3, 1))], time_sig="3/4"),
            Bar(chords=[_chord(3, (1, 0))], time_sig="2/4"),
        ],
        strings=10,
        style=style,
    )
    piece.bars[0].time_sig = "4/4"
    piece.tuning = "c2d2e2f2g2c3f3a3d4g4"
    piece.tempo = 90

    text, back = _round_trip(piece)

    assert _events(back) == _events(piece)
    assert _metadata(back) == _metadata(piece)
    assert "<software>Oud</software>" in text


def test_no_composer_is_not_read_back_as_unknown() -> None:
    _text, back = _round_trip(Piece(title="T", bars=[Bar(chords=[_chord(4, (1, 0))])], strings=6, style="french"))
    assert back.composer is None


@pytest.mark.parametrize(
    "path",
    sorted([*Path("examples").glob("*.tab"), *Path("tests/fixtures").glob("**/*.tab")]),
    ids=str,
)
def test_repo_tab_files_survive_musicxml(path: Path) -> None:
    piece = load_tab(str(path))
    _text, back = _round_trip(piece)

    assert _events(back) == _events(piece)
    assert _metadata(back)[:2] == _metadata(piece)[:2]
    assert (back.tuning, back.tempo, back.style) == (piece.tuning, piece.tempo, piece.style or "french")
