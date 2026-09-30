"""An original two-staff, two-voice classical-guitar study, as MuseScore and Guitar Pro export such scores."""

from __future__ import annotations

from pathlib import Path

from oud.importers.musicxml import load_musicxml
from petrucci.core.model import Piece

STUDY = "tests/fixtures/musicxml/guitar_study_am.musicxml"


def _piece() -> Piece:
    return load_musicxml(STUDY)


def test_the_study_opens_with_its_metadata_and_bars() -> None:
    piece = _piece()

    assert piece.title == "Study in A minor for guitar"
    assert (piece.strings, piece.tuning, len(piece.bars)) == (6, "e2a2d3g3b3e4", 8)


def test_the_repeat_volta_endings_and_closing_barline_are_read() -> None:
    bars = _piece().bars

    assert bars[0].repeat == ".:"
    assert bars[6].repeat == ":." and bars[6].ending_numbers == (1,)
    assert bars[7].ending_numbers == (2,)
    assert bars[7].barline == "|."


def test_the_fermata_on_the_bass_of_the_last_bar_is_read() -> None:
    assert _piece().bars[7].fermata is True


def test_a_tie_across_the_barline_a_pull_off_and_a_harmonic_are_read() -> None:
    bars = _piece().bars
    notes = [note for bar in bars for chord in bar.chords for note in chord.notes]

    assert [n.tie for n in bars[3].chords[0].notes] == [None, "start"]
    assert [n.tie for n in bars[4].chords[0].notes] == [None, "stop"]
    assert [n.technique for n in notes if n.technique] == ["pull-off"]
    assert [(n.string, n.fret) for n in notes if n.harmonic] == [(1, 12)]


def test_the_notation_staff_is_not_reported_as_unread() -> None:
    warnings = _piece().import_warnings

    assert not any("without tablature" in warning for warning in warnings)


def test_what_is_still_lost_is_named() -> None:
    assert set(_piece().import_warnings) == {
        "MusicXML: 1 grace note was not read",
        "MusicXML: 1 tuplet group was read without tuplet timing",
    }


def test_the_fixture_is_licensed_for_the_repository() -> None:
    text = Path(STUDY).read_text(encoding="utf-8")

    assert "GPL-3.0-only" in text
