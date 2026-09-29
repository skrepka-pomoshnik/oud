"""FT3 scores with notation staffs are editable and save to MusicXML without losing those staffs."""

from __future__ import annotations

from pathlib import Path

from oud.editor.core.document import DocumentMode, classify_document
from oud.editor.editing.primitives.undo import undo
from oud.editor.editing.score.operations import cmd_bar
from oud.editor.services.bootstrap import init_state
from oud.editor.services.io.files import cmd_write
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
                    MelodyEvent("c'", 0, note_type=4),
                    MelodyEvent("r", 1, note_type=4, is_rest=True),
                ],
            ),
            ImportedBarContent(
                1,
                melody_events=[
                    MelodyEvent("f#", 0, note_type=5, dotted=True),
                    MelodyEvent("bb,", 1, note_type=6),
                    MelodyEvent("bb,", 2, note_type=4, tie_from_previous=True),
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
                        (e.text, e.onset_index, e.note_type, e.dotted, e.is_rest, e.tie_from_previous)
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
