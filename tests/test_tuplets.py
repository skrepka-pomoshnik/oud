"""Tuplet members of a tablature bar keep their ratio: length, layout, files, playback and beams."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from fractions import Fraction
from itertools import pairwise
from pathlib import Path

from oud.exports.lilypond import export_lilypond
from oud.exports.midi.projection import TICKS_PER_QUARTER, _bar_chord_events
from oud.exports.musicxml import musicxml_text, tuplet_marks
from oud.importers.musicxml import _parse_piece
from oud.settings import DEFAULT_SETTINGS
from petrucci.core.model import Bar, Chord, Note, Piece
from petrucci.input.tablature.mutation import bar_content_length, event_onsets
from petrucci.rendering.bar.beams import beam_groups, guitar_rows
from petrucci.rendering.primitives.utils import chord_positions

EIGHTH, QUARTER = 5, 4
THIRD = Fraction(2, 3)


def _chord(note_type: int, fret: int, *, triplet: bool = False) -> Chord:
    chord = Chord(note_type, False, None, [Note(1, fret, 0)])
    if triplet:
        chord.tuplet_actual, chord.tuplet_normal = 3, 2
    return chord


def _triplet_bar() -> Bar:
    return Bar(
        chords=[_chord(QUARTER, 0), *(_chord(EIGHTH, fret, triplet=True) for fret in (1, 2, 3)), _chord(QUARTER, 5)],
        time_sig="3/4",
    )


def test_a_triplet_of_eighths_fills_one_quarter() -> None:
    assert [chord.tuplet_factor for chord in _triplet_bar().chords] == [1, THIRD, THIRD, THIRD, 1]
    assert bar_content_length(_triplet_bar()) == Fraction(3, 4)
    assert event_onsets(_triplet_bar()) == (
        Fraction(0),
        Fraction(1, 4),
        Fraction(1, 4) + Fraction(1, 12),
        Fraction(1, 4) + Fraction(2, 12),
        Fraction(1, 2),
    )


def test_the_columns_of_a_triplet_are_evenly_spaced() -> None:
    columns = [column for column, _denom, _dot in chord_positions(_triplet_bar(), 31, 4)]

    gaps = [later - earlier for earlier, later in pairwise(columns[1:5])]
    assert max(gaps) - min(gaps) <= 1  # whole columns, so a third rounds to one column more or less


def _text(piece: Piece) -> str:
    return musicxml_text(piece, {}, {}, 12, settings={"style": "italian", "tuning": "", "time": "3/4"})


def test_musicxml_writes_the_ratio_and_the_group_marks() -> None:
    root = ET.fromstring(_text(Piece(title="T", bars=[_triplet_bar()], strings=6)))  # noqa: S314 - Oud's own output
    notes = list(root.iter("note"))
    triplets = [note for note in notes if note.find("time-modification") is not None]

    assert len(triplets) == 3
    assert [note.findtext("time-modification/actual-notes") for note in triplets] == ["3"] * 3
    assert [note.findtext("time-modification/normal-notes") for note in triplets] == ["2"] * 3
    assert [note.findtext("duration") for note in triplets] == ["160"] * 3
    marks = [[node.get("type") for node in note.iter("tuplet")] for note in triplets]
    assert marks == [["start"], [], ["stop"]]


def test_a_triplet_survives_a_musicxml_round_trip() -> None:
    text = _text(Piece(title="T", bars=[_triplet_bar()], strings=6))

    bar = _parse_piece(ET.fromstring(text)).bars[0]  # noqa: S314 - Oud's own output

    assert [(c.note_type, c.tuplet_actual, c.tuplet_normal) for c in bar.chords] == [
        (QUARTER, None, None),
        (EIGHTH, 3, 2),
        (EIGHTH, 3, 2),
        (EIGHTH, 3, 2),
        (QUARTER, None, None),
    ]
    assert bar_content_length(bar) == Fraction(3, 4)


def test_two_adjacent_triplets_are_two_groups() -> None:
    chords = [_chord(EIGHTH, fret, triplet=True) for fret in range(6)]

    marks = tuplet_marks(chords)

    assert [marks.get(id(chord)) for chord in chords] == ["start", None, "stop", "start", None, "stop"]


def test_midi_plays_a_triplet_member_in_two_thirds_of_its_written_time() -> None:
    bar = _triplet_bar()

    events = _bar_chord_events(bar, 0, 6, {}, {}, bar_width=12, style="italian", default_duration=4, dotted=None)

    eighth = TICKS_PER_QUARTER // 2
    assert [duration for _start, duration, _col, _notes in events] == [
        TICKS_PER_QUARTER,
        round(eighth * THIRD),
        round(eighth * THIRD),
        round(eighth * THIRD),
        TICKS_PER_QUARTER,
    ]


def test_lilypond_writes_the_triplet_as_a_tuplet_block(tmp_path: Path) -> None:
    piece = Piece(title="T", bars=[_triplet_bar()], strings=6, style="italian")
    target = tmp_path / "score.ly"

    export_lilypond(str(target), piece, {}, {}, 12, settings={**DEFAULT_SETTINGS, "style": "italian"})

    lines = [line.strip() for line in target.read_text(encoding="utf-8").splitlines()]
    block = lines.index("\\tuplet 3/2 {")
    assert lines[block + 4] == "}"


def test_three_triplet_eighths_share_one_beam_with_their_number() -> None:
    positions = [(0, 4, False), (4, 8, False), (8, 8, False), (12, 8, False), (18, 4, False)]
    ratios = [Fraction(1), THIRD, THIRD, THIRD, Fraction(1)]

    assert [[col for col, _d, _o in group] for group in beam_groups(positions, ratios)] == [[4, 8, 12]]
    beams, _stems = guitar_rows(positions, 20, ratios, [0, 3, 3, 3, 0])
    assert "".join(beams).strip() == "____3____"


def test_without_the_ratio_the_third_eighth_falls_in_the_next_beat() -> None:
    positions = [(0, 4, False), (4, 8, False), (8, 8, False), (12, 8, False)]

    assert [[col for col, _d, _o in group] for group in beam_groups(positions)] == [[4, 8], [12]]
