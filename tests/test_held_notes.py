"""A note that rings longer than its chord (a held bass under moving notes) keeps its own length."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from fractions import Fraction

from oud.editor.services.io.dropped import dropped_marks_text
from oud.editor.services.screen.compose import compose_editor_frame
from oud.exports.midi.projection import TICKS_PER_QUARTER, _bar_chord_events
from oud.exports.musicxml import musicxml_text
from oud.importers.musicxml import _parse_piece, load_musicxml
from petrucci.core.model import Bar, Chord, Note, Piece
from petrucci.input.tablature.mutation import bar_content_length
from tests.helpers_keyscript import keyscript_state

STUDY = "tests/fixtures/musicxml/guitar_study_am.musicxml"
EIGHTH = 5


def _held_bar() -> Bar:
    """Four eighths in 2/4 over a bass note that rings the whole bar."""

    bass = Note(5, 0, 0, sustain=Fraction(1, 2))
    chords = [Chord(EIGHTH, False, None, [Note(1, fret, 0)]) for fret in (0, 2, 3, 5)]
    chords[0].notes.append(bass)
    return Bar(chords=chords, time_sig="2/4")


def _round_trip(bar: Bar) -> Bar:
    piece = Piece(title="T", bars=[bar], strings=6, style="italian")
    text = musicxml_text(piece, {}, {}, 12, settings={"style": "italian", "tuning": "", "time": "2/4"})
    return _parse_piece(ET.fromstring(text)).bars[0]  # noqa: S314 - Oud's own output


def test_the_study_keeps_the_half_note_bass_under_its_eighths() -> None:
    first = load_musicxml(STUDY).bars[0]

    held = [(note.string, note.fret, note.sustain) for chord in first.chords for note in chord.notes if note.sustain]
    assert held == [(5, 0, Fraction(1, 2)), (4, 2, Fraction(1, 2))]
    assert bar_content_length(first) == 1


def test_a_bass_tied_across_the_barline_is_a_whole_note() -> None:
    fourth = load_musicxml(STUDY).bars[3]

    assert [note.sustain for chord in fourth.chords for note in chord.notes if note.sustain] == [Fraction(1)]


def test_the_held_note_goes_in_a_second_voice_when_written() -> None:
    text = musicxml_text(
        Piece(title="T", bars=[_held_bar()], strings=6, style="italian"),
        {},
        {},
        12,
        settings={"style": "italian", "tuning": "", "time": "2/4"},
    )
    measure = ET.fromstring(text).find(".//measure")  # noqa: S314 - Oud's own output
    assert measure is not None
    notes = measure.findall("note")
    voices = [note.findtext("voice") for note in notes]

    assert voices == ["1", "1", "1", "1", "2"]
    assert measure.find("backup/duration") is not None
    held = notes[-1]
    assert (held.findtext("duration"), held.findtext("type")) == ("960", "half")


def test_a_held_note_survives_a_musicxml_round_trip() -> None:
    bar = _round_trip(_held_bar())

    assert [[note.sustain for note in chord.notes] for chord in bar.chords] == [
        [None, Fraction(1, 2)],
        [None],
        [None],
        [None],
    ]
    assert bar_content_length(bar) == Fraction(1, 2)


def test_a_bar_without_held_notes_is_written_in_one_voice() -> None:
    bar = Bar(chords=[Chord(EIGHTH, False, None, [Note(1, 0, 0)]) for _ in range(4)], time_sig="2/4")
    text = musicxml_text(
        Piece(title="T", bars=[bar], strings=6),
        {},
        {},
        12,
        settings={"style": "italian", "tuning": "", "time": "2/4"},
    )

    assert "<voice>" not in text and "<backup>" not in text


def test_midi_rings_the_held_note_for_its_own_length() -> None:
    events = _bar_chord_events(
        _held_bar(), 0, 6, {}, {}, bar_width=12, style="italian", default_duration=4, dotted=None
    )

    longest = max(events, key=lambda event: event[1])
    assert longest[1] == 2 * TICKS_PER_QUARTER
    assert [note.string for note in longest[3]] == [5]


def test_the_ring_is_drawn_along_the_string() -> None:
    state = keyscript_state(
        piece=Piece(title="T", bars=[_held_bar()], strings=6, style="italian"),
        width=60,
        height=16,
        settings_override={"style": "italian", "fretlabelmode": "numeric", "justify": "stretch"},
    )

    lines = compose_editor_frame(state, height=16, width=60).frame.lines
    staff = [line for line in lines if "|-" in line]

    assert "0=" in staff[4]  # the fifth course, where the bass sits


def test_a_tab_save_names_the_held_notes_it_cannot_keep() -> None:
    state = keyscript_state(piece=Piece(title="T", bars=[_held_bar()], strings=6))

    assert "1 held note" in dropped_marks_text(state, tab=True)
