"""MusicXML import says what it did not read (TODO S28-S30)."""

from __future__ import annotations

from io import StringIO
from pathlib import Path
from xml.etree import ElementTree as ET

from oud.exports.musicxml import musicxml_text
from oud.importers.musicxml import _parse_piece, load_musicxml
from oud.presentation import cli_convert
from oud.presentation.cli_convert import CommandStreams, convert_command
from tests.test_layered_scores import _layered_piece

HEAD = '<score-partwise version="4.0"><part-list>{parts}</part-list>'
PART_LIST = '<score-part id="{id}"><part-name>{id}</part-name></score-part>'


def _note(fret: int | None = None, *, string: int = 1, extra: str = "", duration: int = 4, typ: str = "quarter") -> str:
    technical = f"<notations><technical><string>{string}</string><fret>{fret}</fret></technical></notations>"
    return (
        f"<note>{extra}<pitch><step>C</step><octave>4</octave></pitch><duration>{duration}</duration>"
        f"<type>{typ}</type>{technical if fret is not None else ''}</note>"
    )


def _part(part_id: str, body: str, divisions: int = 4) -> str:
    return (
        f'<part id="{part_id}"><measure number="1"><attributes><divisions>{divisions}</divisions>'
        f"<time><beats>4</beats><beat-type>4</beat-type></time></attributes>{body}</measure></part>"
    )


def _score(*parts: tuple[str, str]) -> str:
    listing = "".join(PART_LIST.format(id=part_id) for part_id, _body in parts)
    return HEAD.format(parts=listing) + "".join(_part(part_id, body) for part_id, body in parts) + "</score-partwise>"


def _warnings(xml: str) -> list[str]:
    return _parse_piece(ET.fromstring(xml)).import_warnings  # noqa: S314 - inline test data


def test_a_score_without_tablature_says_its_notes_were_not_read() -> None:
    xml = _score(("P1", _note() + _note() + _note()))

    assert _warnings(xml) == ["MusicXML: 3 notes without tablature were not read"]


def test_notes_of_a_standard_part_beside_a_tablature_part_are_counted() -> None:
    xml = _score(("P1", _note() + _note()), ("P2", _note(0) + _note(2)))

    assert _warnings(xml) == ["MusicXML: 2 notes without tablature were not read"]


def test_one_note_is_worded_in_the_singular() -> None:
    assert _warnings(_score(("P1", _note()))) == ["MusicXML: 1 note without tablature was not read"]


def test_a_tablature_only_score_has_no_warning() -> None:
    assert _warnings(_score(("P1", _note(0) + _note(2)))) == []


def test_oud_written_notation_parts_are_not_warned_about() -> None:
    xml = musicxml_text(_layered_piece(), {}, {}, 12, settings={"style": "french"})

    assert _warnings(xml) == []


def test_conversion_still_writes_a_score_whose_notes_were_not_read(tmp_path: Path) -> None:
    source = tmp_path / "standard.musicxml"
    source.write_text(_score(("P1", _note() + _note())), encoding="utf-8")
    target = tmp_path / "standard.tab"
    errors = StringIO()

    status = convert_command(
        str(source), str(target), "config.toml", streams=CommandStreams(stdout=StringIO(), stderr=errors)
    )

    assert status == 0, errors.getvalue()
    assert target.is_file()
    assert load_musicxml(str(source)).import_warnings
    assert cli_convert.is_informational_warning("MusicXML: 2 notes without tablature were not read")


def _grace(fret: int, string: int = 2) -> str:
    return (
        "<note><grace/><pitch><step>B</step><octave>3</octave></pitch><type>eighth</type>"
        f"<notations><technical><string>{string}</string><fret>{fret}</fret></technical></notations></note>"
    )


def _chords(xml: str) -> list[list[tuple[int, int]]]:
    piece = _parse_piece(ET.fromstring(xml))  # noqa: S314 - inline test data
    return [[(n.string, n.fret) for n in c.notes] for c in piece.bars[0].chords]


def test_a_grace_note_is_not_merged_into_the_chord_it_precedes() -> None:
    xml = _score(("P1", _grace(0) + _note(0, duration=16, typ="whole")))

    assert _chords(xml) == [[(1, 0)]]
    assert _warnings(xml) == ["MusicXML: 1 grace note was not read"]


def test_grace_notes_are_counted() -> None:
    xml = _score(("P1", _grace(0) + _note(0, duration=8, typ="half") + _grace(2) + _note(2, duration=8, typ="half")))

    assert _chords(xml) == [[(1, 0)], [(1, 2)]]
    assert _warnings(xml) == ["MusicXML: 2 grace notes were not read"]
