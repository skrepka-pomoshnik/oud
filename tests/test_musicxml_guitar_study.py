"""An original two-staff, two-voice classical-guitar study, as MuseScore and Guitar Pro export such scores."""

from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree as ET

from oud.editor.services.bootstrap import init_state
from oud.editor.services.io.files import render_ascii_snapshot
from oud.exports.musicxml import export_musicxml
from oud.importers.musicxml import _parse_piece, load_musicxml
from petrucci.core.model import Bar, Chord, Note, Piece

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


def test_a_file_without_show_frets_opens_with_fret_numbers() -> None:
    assert _piece().style == "italian"


def test_show_frets_letters_still_opens_as_french() -> None:
    text = (
        Path(STUDY)
        .read_text(encoding="utf-8")
        .replace('<staff-details number="2">', '<staff-details number="2" show-frets="letters">')
    )

    assert _parse_piece(ET.fromstring(text)).style == "french"  # noqa: S314 - fixture text edited in memory


def _tenth_fret_file(tmp_path: Path, details: str = "") -> Path:
    text = Path(STUDY).read_text(encoding="utf-8").replace("<fret>0</fret>", "<fret>10</fret>", 1)
    if details:
        text = text.replace('<staff-details number="2">', f'<staff-details number="2" {details}>')
    target = tmp_path / "tenth.musicxml"
    target.write_text(text, encoding="utf-8")
    return target


def test_fret_ten_of_a_guitar_file_is_a_number_not_the_lute_x(tmp_path: Path) -> None:
    state = init_state(str(_tenth_fret_file(tmp_path)), config_path=str(tmp_path / "config.toml"))

    lines = render_ascii_snapshot(state)

    assert state.settings["fretlabelmode"] == "numeric"
    assert "10" in lines
    assert "x" not in "".join(
        row.split("|", 1)[1]
        for row in lines.splitlines()
        if row[:2].strip() in {"e", "b", "g", "d", "a"} and "|" in row
    )


def test_lute_italian_tablature_written_by_oud_keeps_the_x(tmp_path: Path) -> None:
    piece = Piece(
        title="Lute",
        bars=[Bar(chords=[Chord(4, False, None, [Note(1, 10, 0)])], time_sig="4/4")],
        strings=6,
        style="italian",
    )
    target = tmp_path / "lute.musicxml"
    export_musicxml(str(target), piece, {}, {}, 12, settings={"style": "italian", "tuning": "", "time": "4/4"})

    reopened = load_musicxml(str(target))

    assert (reopened.style, reopened.fret_labels) == ("italian", None)


def test_a_numeric_fret_label_setting_survives_a_save(tmp_path: Path) -> None:
    state = init_state(str(_tenth_fret_file(tmp_path)), config_path=str(tmp_path / "config.toml"))
    target = tmp_path / "saved.musicxml"

    export_musicxml(
        str(target), state.piece, state.overrides, state.durations, state.bar_width, settings=state.settings
    )

    assert load_musicxml(str(target)).fret_labels == "numeric"
