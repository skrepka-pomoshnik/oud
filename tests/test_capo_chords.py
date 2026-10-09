"""Capo and chord symbols: read from MusicXML, written back, played and drawn."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from oud.editor.services.screen.compose import compose_editor_frame
from oud.exports.midi import export_midi
from oud.exports.musicxml import musicxml_text
from oud.importers.musicxml import _parse_piece, load_musicxml
from petrucci.core.model import Bar, Chord, Note, Piece
from tests.helpers_keyscript import keyscript_state

STUDY = "tests/fixtures/musicxml/guitar_study_am.musicxml"


def _score(harmonies: str = "", capo: str = "") -> ET.Element:
    xml = (
        '<score-partwise version="3.1"><part-list><score-part id="P1"/></part-list><part id="P1">'
        '<measure number="1"><attributes><divisions>2</divisions><time><beats>4</beats><beat-type>4</beat-type></time>'
        f"<clef><sign>TAB</sign><line>5</line></clef><staff-details><staff-lines>6</staff-lines>{capo}"
        f"</staff-details></attributes>{harmonies}"
        "<note><pitch><step>E</step><octave>4</octave></pitch><duration>4</duration><type>half</type>"
        "<notations><technical><string>1</string><fret>0</fret></technical></notations></note>"
        "<note><pitch><step>E</step><octave>4</octave></pitch><duration>4</duration><type>half</type>"
        "<notations><technical><string>1</string><fret>0</fret></technical></notations></note>"
        "</measure></part></score-partwise>"
    )
    return ET.fromstring(xml)  # noqa: S314 - inline test data


def test_the_capo_fret_is_read() -> None:
    assert _parse_piece(_score(capo="<capo>3</capo>")).capo == 3
    assert _parse_piece(_score()).capo is None


def test_a_chord_symbol_is_read_from_the_kind_text_or_the_usual_suffix() -> None:
    harmonies = (
        '<harmony><root><root-step>A</root-step></root><kind text="m7">minor-seventh</kind></harmony>'
        "<harmony><root><root-step>F</root-step><root-alter>1</root-alter></root><kind>dominant</kind>"
        "<bass><bass-step>A</bass-step><bass-alter>1</bass-alter></bass></harmony>"
    )
    # The second symbol sits before the first note too, so only the first event names its symbols once.
    bar = _parse_piece(_score(harmonies)).bars[0]

    assert bar.chords[0].name == "Am7"


def test_each_symbol_belongs_to_the_event_it_precedes() -> None:
    xml = (
        '<score-partwise version="3.1"><part-list><score-part id="P1"/></part-list><part id="P1">'
        '<measure number="1"><attributes><divisions>2</divisions></attributes>'
        '<harmony><root><root-step>C</root-step></root><kind text="">major</kind></harmony>'
        "<note><pitch><step>E</step><octave>4</octave></pitch><duration>4</duration><type>half</type>"
        "<notations><technical><string>1</string><fret>0</fret></technical></notations></note>"
        "<harmony><root><root-step>G</root-step></root><kind>dominant</kind>"
        "<bass><bass-step>B</bass-step></bass></harmony>"
        "<note><pitch><step>E</step><octave>4</octave></pitch><duration>4</duration><type>half</type>"
        "<notations><technical><string>1</string><fret>0</fret></technical></notations></note>"
        "</measure></part></score-partwise>"
    )

    bar = _parse_piece(ET.fromstring(xml)).bars[0]  # noqa: S314 - inline test data

    assert [chord.name for chord in bar.chords] == ["C", "G7/B"]


def _piece(names: tuple[str | None, str | None] = ("Am", "E7"), capo: int | None = None) -> Piece:
    chords = [Chord(3, False, None, [Note(1, 0, 0)], name=name) for name in names]
    bars = [Bar(chords=chords, time_sig="4/4"), Bar(chords=[Chord(3, False, None, [Note(1, 2, 0)]) for _ in range(2)])]
    return Piece(title="T", bars=bars, strings=6, style="italian", capo=capo)


def _written(piece: Piece) -> ET.Element:
    text = musicxml_text(piece, {}, {}, 12, settings={"style": "italian", "tuning": "", "time": "4/4"})
    return ET.fromstring(text)  # noqa: S314 - Oud's own output


def test_chord_symbols_round_trip_through_musicxml() -> None:
    reopened = _parse_piece(_written(_piece()))

    assert [chord.name for chord in reopened.bars[0].chords] == ["Am", "E7"]


def test_a_symbol_is_written_as_a_harmony_before_its_note() -> None:
    measure = _written(_piece()).find(".//measure")
    assert measure is not None
    tags = [child.tag for child in measure if child.tag in {"harmony", "note"}]
    first = measure.find("harmony")

    assert tags == ["harmony", "note", "harmony", "note"]
    assert first is not None and first.findtext("root/root-step") == "A"
    assert first.findtext("kind") == "minor"


def test_the_capo_round_trips_and_raises_the_written_pitch() -> None:
    plain = _written(_piece(capo=None))
    capoed = _written(_piece(capo=2))

    def pitch(root: ET.Element) -> tuple[str | None, str | None]:
        note = root.find(".//note")
        assert note is not None
        return note.findtext("pitch/step"), note.findtext("pitch/octave")

    assert pitch(plain) == ("G", "4")
    assert pitch(capoed) == ("A", "4")  # G4 + 2 semitones; the pitch is the sounding one
    assert capoed.findtext(".//staff-details/capo") == "2"
    assert _parse_piece(capoed).capo == 2
    assert [(n.string, n.fret) for chord in _parse_piece(capoed).bars[0].chords for n in chord.notes] == [
        (1, 0),
        (1, 0),
    ]


def _frame(piece: Piece) -> list[str]:
    state = keyscript_state(piece=piece, width=80, height=16, settings_override={"style": "italian"})
    return compose_editor_frame(state, height=16, width=80).frame.lines


def test_the_capo_is_shown_at_the_left_of_the_header() -> None:
    assert _frame(_piece(capo=3))[0].startswith("Capo 3")
    assert not _frame(_piece())[0].startswith("Capo")


def test_chord_symbols_are_drawn_above_the_staff() -> None:
    lines = _frame(_piece())
    staff_start = next(index for index, line in enumerate(lines) if "|-" in line)
    above = "\n".join(lines[:staff_start])

    assert "Am" in above and "E7" in above


def test_the_guitar_study_names_its_chords() -> None:
    bars = load_musicxml(STUDY).bars

    assert [bar.chords[0].name for bar in bars] == ["Am", "Dm", "E7", "Am", "Am", "Dm", "E7", "Am"]


def test_midi_sounds_a_capoed_string_higher(tmp_path: Path) -> None:
    def note_ons(capo: int | None) -> list[int]:
        target = tmp_path / f"capo-{capo}.mid"
        export_midi(str(target), _piece(capo=capo), {}, {}, 12, settings={"style": "italian", "tuning": "e2a2d3g3b3e4"})
        data = target.read_bytes()
        return [data[index + 1] for index in range(len(data) - 2) if data[index] == 0x90]

    assert [pitch + 2 for pitch in note_ons(None)] == note_ons(2)
