"""Ties and tab techniques on notes: read from MusicXML, written back, and reported when TAB cannot hold them."""

from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree as ET

from oud.editor.services.io.files import cmd_write
from oud.editor.services.screen.compose import compose_editor_frame
from oud.editor.services.screen.note_marks import derived_spans
from oud.exports.musicxml import musicxml_text
from oud.importers.musicxml import _parse_piece
from petrucci.core.model import Bar, Chord, Note, Piece
from tests.helpers_keyscript import keyscript_state

TAB_PART_HEAD = (
    '<part id="P1"><measure number="1"><attributes><divisions>2</divisions>'
    "<time><beats>4</beats><beat-type>4</beat-type></time>"
    "<clef><sign>TAB</sign><line>5</line></clef>"
    "<staff-details><staff-lines>6</staff-lines></staff-details></attributes>"
)


def _tab_note(string: int, fret: int, notations: str = "", tie: str = "") -> str:
    return (
        f"<note><pitch><step>E</step><octave>3</octave></pitch><duration>2</duration>{tie}"
        f"<type>quarter</type><notations>{notations}<technical><string>{string}</string>"
        f"<fret>{fret}</fret>{{extra}}</technical></notations></note>"
    )


def _score(*parts: str) -> ET.Element:
    body = "".join(f'<part-list><score-part id="P{i}"/></part-list>' for i in (1,))
    return ET.fromstring(f'<score-partwise version="3.1">{body}{"".join(parts)}</score-partwise>')  # noqa: S314


def _measure(*notes: str) -> str:
    return f"{TAB_PART_HEAD}{''.join(notes)}</measure></part>"


def _note(string: int, fret: int, *, extra: str = "", notations: str = "", tie: str = "") -> str:
    return _tab_note(string, fret, notations, tie).replace("{extra}", extra)


def _first_notes(piece: Piece) -> list[Note]:
    return [note for chord in piece.bars[0].chords for note in chord.notes]


def test_ties_are_read_from_tie_and_tied_elements() -> None:
    xml = _measure(
        _note(2, 3, tie='<tie type="start"/>', notations='<tied type="start"/>'),
        _note(2, 3, tie='<tie type="stop"/><tie type="start"/>', notations='<tied type="stop"/><tied type="start"/>'),
        _note(2, 3, notations='<tied type="stop"/>'),
    )

    ties = [note.tie for note in _first_notes(_parse_piece(_score(xml)))]

    assert ties == ["start", "continue", "stop"]


def test_hammer_on_pull_off_and_slide_are_kept_on_the_starting_note() -> None:
    xml = _measure(
        _note(1, 0, extra='<hammer-on type="start">H</hammer-on>'),
        _note(1, 2, extra='<hammer-on type="stop"/><pull-off type="start">P</pull-off>'),
        _note(1, 0, extra='<pull-off type="stop"/>', notations='<slide type="start"/>'),
        _note(1, 5, notations='<slide type="stop"/>'),
    )

    techniques = [note.technique for note in _first_notes(_parse_piece(_score(xml)))]

    assert techniques == ["hammer-on", "pull-off", "slide", None]


def test_bend_harmonic_and_fingering_are_read() -> None:
    xml = _measure(_note(2, 7, extra="<bend><bend-alter>2</bend-alter></bend><harmonic/><fingering>3</fingering>"))

    note = _first_notes(_parse_piece(_score(xml)))[0]

    assert (note.bend, note.harmonic, note.left_fingering) == (2.0, True, "3")


def _marked_piece() -> Piece:
    chords = [
        Chord(4, False, None, [Note(1, 0, 0, technique="hammer-on", tie=None), Note(3, 2, 0, tie="start")]),
        Chord(4, False, None, [Note(1, 2, 0, technique="slide"), Note(3, 2, 0, tie="stop")]),
        Chord(4, False, None, [Note(1, 5, 0, bend=1.5, harmonic=True, left_fingering="2")]),
    ]
    return Piece(title="Marks", bars=[Bar(chords=chords, time_sig="4/4")], strings=6, style="french")


def _round_trip(piece: Piece) -> tuple[str, Piece]:
    settings = {"style": "french", "tuning": "", "time": "4/4"}
    text = musicxml_text(piece, {}, {}, 12, settings=settings)
    return text, _parse_piece(ET.fromstring(text))  # noqa: S314 - text Oud just wrote


def _marks(piece: Piece) -> list[list[tuple[int, int, str | None, str | None, float | None, bool, str | None]]]:
    return [
        [(n.string, n.fret, n.tie, n.technique, n.bend, n.harmonic, n.left_fingering) for n in c.notes]
        for c in piece.bars[0].chords
    ]


def test_marks_survive_a_musicxml_round_trip() -> None:
    original = _marked_piece()

    _text, reopened = _round_trip(original)

    assert _marks(reopened) == _marks(original)


def test_a_technique_ends_on_the_next_note_of_the_same_string() -> None:
    text, _reopened = _round_trip(_marked_piece())
    root = ET.fromstring(text)  # noqa: S314 - text Oud just wrote
    notes = list(root.iter("note"))

    def kinds(note: ET.Element, name: str) -> list[str | None]:
        return [node.get("type") for node in note.iter(name)]

    assert kinds(notes[0], "hammer-on") == ["start"]
    assert kinds(notes[2], "hammer-on") == ["stop"]
    assert kinds(notes[2], "slide") == ["start"]
    assert kinds(notes[4], "slide") == ["stop"]


def test_a_tie_writes_matching_tie_and_tied_elements() -> None:
    text, _reopened = _round_trip(_marked_piece())
    notes = list(ET.fromstring(text).iter("note"))  # noqa: S314 - text Oud just wrote

    assert [node.get("type") for node in notes[1].findall("tie")] == ["start"]
    assert [node.get("type") for node in notes[1].iter("tied")] == ["start"]
    assert [node.get("type") for node in notes[3].findall("tie")] == ["stop"]


def test_tab_notes_of_other_parts_are_reported_not_called_untabbed() -> None:
    second = _measure(_note(1, 0), _note(2, 1)).replace('id="P1"', 'id="P2"')
    root = _score(_measure(_note(1, 0), _note(2, 0), _note(3, 0)), second)

    warnings = _parse_piece(root).import_warnings

    assert "MusicXML: 2 tablature notes of other parts were not read" in warnings
    assert not any("without tablature" in warning for warning in warnings)


def test_a_tab_save_names_the_note_marks_it_cannot_keep(tmp_path: Path) -> None:
    state = keyscript_state(piece=_marked_piece())
    tab_target = tmp_path / "marks.tab"
    xml_target = tmp_path / "marks.musicxml"

    assert cmd_write(state, str(tab_target))
    tab_message = state.message
    assert cmd_write(state, str(xml_target))

    assert "not saved: 1 hammer-on, 2 ties, 1 slide, 1 bend, 1 harmonic" in tab_message
    assert "not saved" not in state.message


def _rendered(piece: Piece) -> str:
    state = keyscript_state(piece=piece, width=100, height=30, settings_override={"showspans": "on"})
    return "\n".join(compose_editor_frame(state, height=30, width=100).frame.lines)


def _plain_copy() -> Piece:
    piece = _marked_piece()
    for chord in piece.bars[0].chords:
        for note in chord.notes:
            note.tie = note.technique = note.bend = None
            note.harmonic = False
    return piece


def test_ties_and_slurs_from_note_marks_are_drawn() -> None:
    assert _rendered(_marked_piece()) != _rendered(_plain_copy())


def test_derived_spans_pair_chords_of_one_bar() -> None:
    ties, slurs = derived_spans(_marked_piece().bars, 12)

    assert [span[0] for span in ties] == [0]
    assert [span[0] for span in slurs] == [0]
    assert ties[0][1] < ties[0][2]


def test_a_hammer_on_written_directly_under_notations_is_read() -> None:
    xml = _measure(
        _note(3, 0, notations='<hammer-on type="start" number="1"/>'),
        _note(3, 2, notations='<hammer-on type="stop" number="1"/>'),
    )

    techniques = [note.technique for note in _first_notes(_parse_piece(_score(xml)))]

    assert techniques == ["hammer-on", None]
