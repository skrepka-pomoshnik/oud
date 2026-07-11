from oud.editor.ops import (
    chord_index_at_col,
    delete_chord,
    denom_to_note_type,
    duration_value,
    french_to_fret,
    fret_to_french,
    fret_to_italian,
    insert_chord,
    is_french_fret,
    is_italian_fret,
    italian_to_fret,
    set_chord_note,
)
from oud.petrucci.model import Bar, Chord, Note


def test_duration_value_maps_french_keys() -> None:
    assert duration_value(ord("1"), "french") == 1
    assert duration_value(ord("2"), "french") == 2
    assert duration_value(ord("3"), "french") == 4
    assert duration_value(ord("4"), "french") == 8
    assert duration_value(ord("5"), "french") == 16
    assert duration_value(ord("6"), "french") == 32
    assert duration_value(ord("7"), "french") == 64


def test_duration_value_does_not_map_french_fret_letters() -> None:
    for ch in "ehqstw":
        assert duration_value(ord(ch), "french") is None


def test_duration_value_italian_ctrl_keys() -> None:
    assert duration_value(1, "italian") == 1
    assert duration_value(4, "italian") == 8
    assert duration_value(6, "italian") == 32
    assert duration_value(9, "italian") is None


def test_denom_to_note_type() -> None:
    assert denom_to_note_type(4) == 4
    assert denom_to_note_type(8) == 5
    assert denom_to_note_type(256) == 10
    assert denom_to_note_type(999) is None


def test_fret_conversions() -> None:
    assert is_french_fret("a")
    assert is_french_fret("r")
    assert is_french_fret("s")
    assert is_french_fret("t")
    assert not is_french_fret("z")
    assert french_to_fret("c") == 2
    assert french_to_fret("r") == 16
    assert french_to_fret("z") is None
    assert fret_to_french(2) == "c"
    assert fret_to_french(16) == "r"
    assert fret_to_french(99) is None
    assert is_italian_fret("0")
    assert is_italian_fret("x")
    assert not is_italian_fret("a")
    assert italian_to_fret("7") == 7
    assert italian_to_fret("x") == 10
    assert italian_to_fret("a") is None
    assert fret_to_italian(9) == "9"
    assert fret_to_italian(10) == "x"
    assert fret_to_italian(99) is None


def test_chord_helpers() -> None:
    bar = Bar(chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)])])
    assert chord_index_at_col(bar, 12, 0) == 0
    assert set_chord_note(bar, 12, 0, 1, 2) is True
    assert bar.chords[0].notes[0].fret == 2
    assert set_chord_note(bar, 12, 0, 1, None) is True
    assert bar.chords == []


def test_destructive_chord_helpers_require_exact_slot() -> None:
    bar = Bar(chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)])])
    assert chord_index_at_col(bar, 12, 1) == 0
    assert chord_index_at_col(bar, 12, 1, exact=True) is None
    assert set_chord_note(bar, 12, 1, 1, None) is False
    assert bar.chords
    assert delete_chord(bar, 12, 1) is False
    assert bar.chords


def test_insert_delete_chord() -> None:
    bar = Bar()
    insert_chord(bar, 12, 0)
    assert len(bar.chords) == 1
    insert_chord(bar, 12, 0)
    assert len(bar.chords) == 2
    assert delete_chord(bar, 12, 0) is True
    assert len(bar.chords) == 1
    assert delete_chord(bar, 12, 99) is False
