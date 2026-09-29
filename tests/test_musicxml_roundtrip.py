"""Oud → MusicXML → Oud keeps everything Oud models (TODO C16 step 1)."""

from __future__ import annotations

from pathlib import Path
from typing import Any
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


def _repeats(piece: Piece) -> list[str | None]:
    return [bar.repeat for bar in piece.bars]


@pytest.mark.parametrize("marker", [".:", ":.", ":|:"])
def test_a_repeat_marker_stays_on_its_bar_through_repeated_saves(marker: str) -> None:
    bars = [Bar(chords=[_chord(4, (1, 0))]) for _ in range(4)]
    bars[1].repeat = marker
    piece = Piece(title="T", bars=bars, strings=6, style="french")
    expected = [None, marker, None, None]

    for _ in range(3):
        _text, piece = _round_trip(piece)
        assert _repeats(piece) == expected


def _has_forward_repeat_at_left(measure: ET.Element) -> bool:
    for barline in measure.findall("barline"):
        repeat = barline.find("repeat")
        if barline.get("location") == "left" and repeat is not None and repeat.get("direction") == "forward":
            return True
    return False


def test_a_start_repeat_is_written_at_the_left_of_its_own_measure() -> None:
    bars = [Bar(chords=[_chord(4, (1, 0))]) for _ in range(3)]
    bars[1].repeat = ".:"
    text, _piece = _round_trip(Piece(title="T", bars=bars, strings=6, style="french"))
    part = ET.fromstring(text).find("part")  # noqa: S314 - text Oud just wrote
    assert part is not None

    assert [_has_forward_repeat_at_left(measure) for measure in part.findall("measure")] == [False, True, False]


def _first_bar_after_round_trip(**fields: Any) -> Bar:
    bars = [Bar(chords=[_chord(4, (1, 0))], **fields), Bar(chords=[_chord(4, (1, 1))])]
    _text, piece = _round_trip(Piece(title="T", bars=bars, strings=6, style="french"))
    return piece.bars[0]


def test_a_bar_fermata_is_read_back() -> None:
    assert _first_bar_after_round_trip(fermata=True).fermata is True
    assert _first_bar_after_round_trip().fermata is False


@pytest.mark.parametrize("dynamic", ["ppp", "mf", "sfz", "fp", "dolce"])
def test_a_bar_dynamic_is_read_back(dynamic: str) -> None:
    assert _first_bar_after_round_trip(dynamic=dynamic).dynamic == dynamic


def test_repeat_words_are_not_read_as_dynamics() -> None:
    assert _first_bar_after_round_trip(repeat="DC al Fine").dynamic is None


@pytest.mark.parametrize("barline", ["||", ":", " ", "|."])
def test_a_barline_style_is_read_back(barline: str) -> None:
    assert _first_bar_after_round_trip(barline=barline).barline == barline


def test_a_plain_barline_and_a_repeat_barline_are_not_styles() -> None:
    assert _first_bar_after_round_trip().barline is None
    assert _first_bar_after_round_trip(repeat=":.").barline is None


def _endings_after_round_trip(endings: list[tuple[int, ...]]) -> list[tuple[int, ...]]:
    bars = [Bar(chords=[_chord(4, (1, 0))], ending_numbers=numbers) for numbers in endings]
    _text, piece = _round_trip(Piece(title="T", bars=bars, strings=6, style="french"))
    return [bar.ending_numbers for bar in piece.bars]


@pytest.mark.parametrize(
    "endings",
    [
        [(), (1,), ()],
        [(), (1,), (1,), (2,), ()],
        [(1, 2), (), (2,), (2,)],
        [(1,), (2,)],
        [(1,), (2,), (3,)],
    ],
    ids=["one bar", "two-bar volta then one bar", "shared then two-bar", "adjacent", "three voltas"],
)
def test_volta_endings_round_trip(endings: list[tuple[int, ...]]) -> None:
    assert _endings_after_round_trip(endings) == endings


def test_a_two_bar_volta_starts_on_the_first_bar_and_stops_on_the_second() -> None:
    bars = [Bar(chords=[_chord(4, (1, 0))], ending_numbers=(1,)) for _ in range(2)]
    text, _piece = _round_trip(Piece(title="T", bars=bars, strings=6, style="french"))
    part = ET.fromstring(text).find("part")  # noqa: S314 - text Oud just wrote
    assert part is not None

    found = [
        [(b.get("location"), e.get("type"), e.get("number")) for b in m.findall("barline") for e in b.findall("ending")]
        for m in part.findall("measure")
    ]

    assert found == [[("left", "start", "1")], [("right", "stop", "1")]]


def test_an_empty_bar_stays_empty_and_is_written_as_a_measure_rest() -> None:
    bars = [
        Bar(chords=[_chord(4, (1, 0))], time_sig="3/4"),
        Bar(),
        Bar(chords=[_chord(4, (1, 1))]),
    ]
    text, piece = _round_trip(Piece(title="T", bars=bars, strings=6, style="french"))

    assert [len(bar.chords) for bar in piece.bars] == [1, 0, 1]
    part = ET.fromstring(text).find("part")  # noqa: S314 - text Oud just wrote
    assert part is not None
    note = part.findall("measure")[1].find("note")
    assert note is not None
    rest = note.find("rest")
    assert rest is not None
    assert rest.get("measure") == "yes"
    assert note.findtext("duration") == "1440"  # 3/4 of 4 * 480, inherited from the first bar


def test_a_foreign_measure_rest_is_an_empty_bar_not_a_rest_chord() -> None:
    xml = """<score-partwise version="4.0"><part-list><score-part id="P1"><part-name>x</part-name></score-part></part-list>
<part id="P1"><measure number="1"><attributes><divisions>4</divisions><time><beats>4</beats><beat-type>4</beat-type></time></attributes>
<note><rest measure="yes"/><duration>16</duration></note></measure></part></score-partwise>"""
    piece = _parse_piece(ET.fromstring(xml))  # noqa: S314 - inline test data

    assert [len(bar.chords) for bar in piece.bars] == [0]


def test_a_real_rest_in_a_bar_is_still_a_rest_chord() -> None:
    xml = """<score-partwise version="4.0"><part-list><score-part id="P1"><part-name>x</part-name></score-part></part-list>
<part id="P1"><measure number="1"><attributes><divisions>4</divisions><time><beats>4</beats><beat-type>4</beat-type></time></attributes>
<note><rest/><duration>4</duration><type>quarter</type></note></measure></part></score-partwise>"""
    piece = _parse_piece(ET.fromstring(xml))  # noqa: S314 - inline test data

    assert [(c.note_type, c.notes) for c in piece.bars[0].chords] == [(4, [])]
