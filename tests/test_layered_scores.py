"""FT3 scores with notation staffs are editable and save to MusicXML without losing those staffs."""

from __future__ import annotations

from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from oud.editor.core.document import DocumentMode, classify_document
from oud.editor.editing.primitives.undo import undo
from oud.editor.editing.score.operations import cmd_bar
from oud.editor.services.bootstrap import init_state
from oud.editor.services.io.files import cmd_write
from oud.editor.services.screen.compose import compose_editor_frame
from oud.exports.musicxml import musicxml_text
from petrucci.core.model import (
    Bar,
    Chord,
    ImportedBarContent,
    ImportedScore,
    ImportedStaff,
    LyricEvent,
    MelodyEvent,
    Note,
    Piece,
)
from tests.helpers_keyscript import keyscript_state


def _tab_bar(fret: int) -> Bar:
    return Bar(chords=[Chord(3, False, None, [Note(1, fret, 0)])], time_sig="2/4")


def _layered_piece() -> Piece:
    notes = ImportedStaff(
        kind="note",
        label="Cantus",
        bars=[
            ImportedBarContent(
                0,
                melody_events=[
                    MelodyEvent("c'", 0, note_type=4, slur_start=True),
                    MelodyEvent("r", 1, note_type=4, is_rest=True, fermata=True),
                    MelodyEvent("d'", 2, note_type=5, beam="start", harmonic=True),
                    MelodyEvent("e'", 3, note_type=5, beam="end", fingering="2"),
                ],
            ),
            ImportedBarContent(
                1,
                melody_events=[
                    MelodyEvent("f#", 0, note_type=5, dotted=True, slur_end=True, beam="start"),
                    MelodyEvent("bb,", 1, note_type=6, beam="continue"),
                    MelodyEvent("bb,", 2, note_type=4, tie_from_previous=True, beam="end"),
                ],
            ),
        ],
    )
    lyrics = ImportedStaff(
        kind="lyrics",
        label="Cantus",
        bars=[
            ImportedBarContent(0, lyric_event_rows=[[LyricEvent("Tri", 0, syllabic="begin")]]),
            ImportedBarContent(
                1,
                lyric_event_rows=[[LyricEvent("ste", 0, syllabic="end"), LyricEvent("", 1, extender=True)]],
            ),
        ],
    )
    piece = Piece(title="Layered", bars=[_tab_bar(0), _tab_bar(2)], strings=6, style="french")
    piece.imported_score = ImportedScore("ft3", [notes, lyrics])
    return piece


def _staffs(piece: Piece) -> list[tuple[str, str | None, list[tuple[int, list[object]]]]]:
    assert piece.imported_score is not None
    return [
        (
            staff.kind,
            staff.label,
            [
                (
                    bar.source_bar_index,
                    [
                        (
                            (e.text, e.onset_index, e.note_type, e.dotted, e.is_rest, e.tie_from_previous),
                            (e.fermata, e.slur_start, e.slur_end, e.beam, e.fingering, e.harmonic),
                        )
                        for e in bar.melody_events
                    ]
                    + [
                        (row_index, e.text, e.onset_index, e.syllabic, e.extender)
                        for row_index, row in enumerate(bar.lyric_event_rows)
                        for e in row
                    ],
                )
                for bar in staff.bars
                if bar.melody_events or bar.lyric_event_rows
            ],
        )
        for staff in piece.imported_score.staffs
    ]


def _note_bar_indices(piece: Piece) -> list[int]:
    assert piece.imported_score is not None
    return [bar.source_bar_index for bar in piece.imported_score.staffs[0].bars]


def test_layered_ft3_with_tablature_is_editable() -> None:
    assert classify_document("song.ft3", _layered_piece()) is DocumentMode.IMPORTED_PROJECTION

    vocal_only = _layered_piece()
    vocal_only.bars = [Bar(), Bar()]
    assert classify_document("song.ft3", vocal_only) is DocumentMode.IMPORTED_READ_ONLY


def test_notation_staffs_survive_musicxml_save_and_reopen(tmp_path: Path) -> None:
    state = keyscript_state(piece=_layered_piece(), settings_override={"time": "2/4"})
    target = tmp_path / "layered.musicxml"

    assert cmd_write(state, str(target))
    assert "1 notation staff" in state.message
    reopened = init_state(str(target), config_path=str(tmp_path / "config.toml"))

    assert _staffs(reopened.piece) == _staffs(_layered_piece())
    assert [[(n.string, n.fret) for c in bar.chords for n in c.notes] for bar in reopened.piece.bars] == [
        [(1, 0)],
        [(1, 2)],
    ]
    assert reopened.document_mode is DocumentMode.NATIVE


def test_tab_save_of_a_layered_score_is_refused_not_lossy(tmp_path: Path) -> None:
    state = keyscript_state(piece=_layered_piece())
    target = tmp_path / "layered.tab"

    assert not cmd_write(state, str(target))
    assert "notation staff" in state.message
    assert not target.exists()


def test_bar_insert_and_delete_keep_staffs_aligned_and_undo_restores_them() -> None:
    state = keyscript_state(piece=_layered_piece())
    before = _staffs(state.piece)

    state.cursor_bar = 0
    cmd_bar(state, "add")
    assert _note_bar_indices(state.piece) == [0, 2]

    cmd_bar(state, "delete")
    assert _staffs(state.piece) == before

    state.cursor_bar = 0
    cmd_bar(state, "delete")
    assert _note_bar_indices(state.piece) == [0]
    assert state.piece.imported_score is not None
    assert state.piece.imported_score.staffs[0].bars[0].melody_events[0].text == "f#"

    undo(state, config_path="config.toml")
    assert _staffs(state.piece) == before


@pytest.mark.parametrize(("width", "height"), [(80, 24), (120, 40)])
def test_the_lute_label_never_overwrites_the_tablature_staff(width: int, height: int) -> None:
    state = keyscript_state(piece=_layered_piece(), width=width, height=height, settings_override={"time": "2/4"})
    lines = compose_editor_frame(state, height=height, width=width).frame.lines

    first = next(index for index, line in enumerate(lines) if "|a" in line)
    tab_rows = lines[first : first + 6]
    staff_column = tab_rows[0].index("|a")

    # The label sits in its own column and the staff keeps its barline and lines.
    assert [row[staff_column] for row in tab_rows] == ["|"] * 6, tab_rows
    assert tab_rows[2].startswith("lute ")
    assert all(row[:staff_column].strip() == "" for index, row in enumerate(tab_rows) if index != 2)
    assert tab_rows[2][staff_column + 1 :].startswith("-")


def test_a_solo_piece_has_no_label_over_its_staff() -> None:
    piece = Piece(title="Solo", bars=[_tab_bar(0), _tab_bar(2)], strings=6, style="french")
    state = keyscript_state(piece=piece, width=80, height=24, settings_override={"time": "2/4"})
    lines = compose_editor_frame(state, height=24, width=80).frame.lines

    assert not any(line.startswith("lute") for line in lines)


def test_beams_are_written_only_where_there_is_one() -> None:
    text = musicxml_text(_layered_piece(), {}, {}, 12, settings={"style": "french"})
    beams = [beam.text for beam in ET.fromstring(text).iter("beam")]  # noqa: S314 - text Oud just wrote

    assert beams == ["begin", "end", "begin", "continue", "end"]
