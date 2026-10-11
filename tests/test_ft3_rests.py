"""FT3 tablature rests: an object that is only its header, kept as a chord without notes."""

from __future__ import annotations

from pathlib import Path

from oud.importers.ft3 import load_ft3
from oud.importers.ft3.musical.tab import _decode_ft3_note_position, parse_bar
from tests.helpers_ft3 import chord, ft3_bar, write_ft3

QUARTER, EIGHTH = 4, 5


def test_an_object_without_notes_is_a_rest_with_its_value() -> None:
    bar = parse_bar(
        ft3_bar([chord((1, 0), note_type=QUARTER), chord(note_type=EIGHTH), chord((2, 1), note_type=EIGHTH)])
    )

    assert [(c.note_type, bool(c.notes)) for c in bar.chords] == [(QUARTER, True), (EIGHTH, False), (EIGHTH, True)]


def test_a_dotted_rest_keeps_its_dot() -> None:
    bar = parse_bar(ft3_bar([chord(note_type=QUARTER, dotted=True), chord((1, 0), note_type=EIGHTH)]))

    assert (bar.chords[0].note_type, bar.chords[0].dotted, bar.chords[0].notes) == (QUARTER, True, [])


def test_a_bar_of_one_rest_is_kept_as_a_bar(tmp_path: Path) -> None:
    bars = [ft3_bar([chord(note_type=QUARTER, dotted=True)], meter="3/4"), ft3_bar([chord((1, 0), note_type=QUARTER)])]

    piece = load_ft3(str(write_ft3(tmp_path / "rest.ft3", "Rest first", bars)))

    assert [len(bar.chords) for bar in piece.bars] == [1, 1]
    assert piece.bars[0].chords[0].notes == []


def test_the_notes_of_a_chord_after_a_rest_are_not_lost() -> None:
    bar = parse_bar(ft3_bar([chord(note_type=EIGHTH), chord((3, 2), (5, 0), note_type=EIGHTH)]))

    assert sorted((note.string, note.fret) for note in bar.chords[1].notes) == [(3, 2), (5, 0)]


def test_string_byte_one_is_read_like_a_bass_course() -> None:
    assert _decode_ft3_note_position(1, ord("b"), 0) == _decode_ft3_note_position(8, ord("b"), 0) == (7, 1)
    assert _decode_ft3_note_position(1, ord("2"), 0x20) == (9, 0)
    assert _decode_ft3_note_position(0, ord("a"), 0) is None
