from __future__ import annotations

import pytest

from petrucci.model import (
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
from petrucci.piece_score_view import typeset_piece_score_view
from petrucci.typeset import TypesetOptions, typeset_piece

SETTINGS = {
    "showmelody": "on",
    "showlyrics": "on",
    "justify": "smart",
    "showdur": "off",
    "flagredundant": "on",
}


def _note_staff(label: str, source_index: int, pitch: str) -> ImportedStaff:
    return ImportedStaff(
        kind="note",
        label=label,
        bars=[
            ImportedBarContent(
                source_bar_index=source_index,
                melody_events=[MelodyEvent(pitch, 0, note_type=4)],
                time_sig="4/4",
            ),
        ],
    )


def _lyric_staff(label: str, source_index: int, text: str) -> ImportedStaff:
    return ImportedStaff(
        kind="lyrics",
        label=label,
        bars=[
            ImportedBarContent(
                source_bar_index=source_index,
                lyric_event_rows=[[LyricEvent(text, 0)]],
            ),
        ],
    )


def _imported_piece(*, tablature: bool, two_voices: bool = False) -> Piece:
    staffs = [_note_staff("soprano", 0, "c4"), _lyric_staff("soprano", 0, "sing")]
    if two_voices:
        staffs.extend((_note_staff("bass", 0, "g2"), _lyric_staff("bass", 0, "low")))
    chords = [Chord(4, False, None, [Note(1, 0, 0)])] if tablature else []
    return Piece(
        title="Imported view",
        bars=[Bar(chords=chords)],
        strings=6,
        imported_score=ImportedScore("ft3", staffs),
    )


def test_vocal_only_typeset_piece_uses_canonical_score_frame() -> None:
    result = typeset_piece(
        _imported_piece(tablature=False),
        options=TypesetOptions(width=80, height=24),
    )

    assert "Imported view" in result.text
    assert "sing" in result.text
    assert "G" in result.text
    assert result.cursor_display_maps == {0: [17]}


@pytest.mark.parametrize(("width", "height"), ((80, 24), (120, 40)))
def test_vocal_only_view_keeps_all_staffs_while_focus_selects_active_voice(width: int, height: int) -> None:
    piece = _imported_piece(tablature=False, two_voices=True)
    view = typeset_piece_score_view(
        piece,
        width=width,
        height=height,
        bar_offset=0,
        cursor=(0, 0),
        playback=(0, 0),
        settings=SETTINGS,
        focused_imported_staff_index=2,
    )

    assert view is not None
    assert len(view.result.layout.systems) == 1
    assert view.result.layout.event_ids == (
        "piece:staff:0:bar:0:event:0:0",
        "piece:staff:2:bar:0:event:0:0",
    )
    assert "bass" in view.result.text
    soprano_cells = view.result.cells_for("piece:staff:0:bar:0:event:0:0")
    bass_cells = view.result.cells_for("piece:staff:2:bar:0:event:0:0")
    assert bass_cells
    if height >= 40:
        assert "soprano" in view.result.text
        assert soprano_cells
        assert any(view.result.frame.attrs[row][column] != 0 for row, column in soprano_cells)
    else:
        assert not soprano_cells
    assert any(view.result.frame.attrs[row][column] != 0 for row, column in bass_cells)


def test_vocal_score_uses_compact_rows_and_clips_only_at_terminal_bottom() -> None:
    staffs = []
    for label in ("soprano", "alto", "tenor", "bass"):
        staffs.extend((_note_staff(label, 0, "c4"), _lyric_staff(label, 0, label)))
    piece = Piece(title="Full score", bars=[Bar()], imported_score=ImportedScore("ft3", staffs))

    view = typeset_piece_score_view(
        piece,
        width=80,
        height=18,
        bar_offset=0,
        cursor=(0, 0),
        playback=None,
        settings=SETTINGS,
    )

    assert view is not None
    system = view.result.layout.systems[0]
    assert system.rect.height > 18
    assert len(view.result.lines) == 18
    assert all(
        all(second - first == 2 for first, second in zip(rows.line_rows, rows.line_rows[1:], strict=False))
        for rows in system.staff_rows
    )
    assert all(
        second.top - first.bottom == 1 for first, second in zip(system.staff_rows, system.staff_rows[1:], strict=False)
    )
    assert all(rows.measure_number_row is None for rows in system.staff_rows)
    assert view.result.cells_for("piece:staff:0:bar:0:event:0:0")
    assert not view.result.cells_for("piece:staff:6:bar:0:event:0:0")


def test_mixed_default_aligns_canonical_voice_lyrics_and_tablature() -> None:
    piece = _imported_piece(tablature=True)
    default = typeset_piece_score_view(
        piece,
        width=80,
        height=24,
        bar_offset=0,
        cursor=(0, 0),
        playback=None,
        settings=SETTINGS,
    )
    note = typeset_piece_score_view(
        piece,
        width=80,
        height=24,
        bar_offset=0,
        cursor=(0, 0),
        playback=None,
        settings=SETTINGS,
        focused_imported_staff_index=0,
    )
    lyric = typeset_piece_score_view(
        piece,
        width=80,
        height=24,
        bar_offset=0,
        cursor=(0, 0),
        playback=None,
        settings=SETTINGS,
        focused_imported_staff_index=1,
    )

    assert default is not None
    assert len(default.result.layout.systems[0].staff_rows) == 2
    assert "sing" in default.result.text
    assert "lute" in default.result.text
    assert any("|" in line and "-" in line for line in default.result.lines)
    assert note is not None and lyric is not None
    assert note.result.text == lyric.result.text
    assert "sing" in note.result.text


def test_mixed_playback_marks_voice_and_matching_tab_chord() -> None:
    piece = _imported_piece(tablature=True)
    view = typeset_piece_score_view(
        piece,
        width=80,
        height=30,
        bar_offset=0,
        cursor=(0, 0),
        playback=(0, 0),
        settings=SETTINGS,
    )

    assert view is not None
    assert "^" in view.result.text
    assert any(attr != 0 for row in view.result.frame.attrs for attr in row)


def test_mixed_playback_maps_tab_subdivision_to_active_voice_duration() -> None:
    melody = [
        MelodyEvent("c4", 0, note_type=3),
        MelodyEvent("d4", 1, note_type=4),
        MelodyEvent("e4", 2, note_type=4),
    ]
    piece = Piece(
        bars=[
            Bar(
                chords=[Chord(5, False, None, [Note(1, 0, 0)]) for _ in range(8)],
                melody_events=melody,
            ),
        ],
        strings=6,
        imported_score=ImportedScore(
            "ft3",
            [ImportedStaff("note", "voice", [ImportedBarContent(0, melody_events=melody)])],
        ),
    )
    view = typeset_piece_score_view(
        piece,
        width=80,
        height=30,
        bar_offset=0,
        cursor=(0, 0),
        playback=(0, 3),
        settings=SETTINGS,
    )

    assert view is not None
    active_id = "piece:staff:0:bar:0:event:0:0"
    later_id = "piece:staff:0:bar:0:event:2:0"
    assert any(view.result.frame.attrs[row][column] != 0 for row, column in view.result.cells_for(active_id))
    assert all(view.result.frame.attrs[row][column] == 0 for row, column in view.result.cells_for(later_id))


def test_playback_selects_later_system_and_current_style_without_reflow() -> None:
    staffs = [
        ImportedStaff(
            kind="note",
            label="voice",
            bars=[
                ImportedBarContent(
                    source_bar_index=index,
                    melody_events=[MelodyEvent("c4", 0, note_type=4)],
                    system_break=True,
                )
                for index in range(3)
            ],
        ),
    ]
    piece = Piece(title="Follow", bars=[Bar() for _ in range(3)], imported_score=ImportedScore("ft3", staffs))
    idle = typeset_piece_score_view(
        piece,
        width=60,
        height=24,
        bar_offset=2,
        cursor=(2, 0),
        playback=None,
        settings=SETTINGS,
    )
    playing = typeset_piece_score_view(
        piece,
        width=60,
        height=24,
        bar_offset=0,
        cursor=(0, 0),
        playback=(2, 0),
        settings=SETTINGS,
    )

    assert idle is not None and playing is not None
    active_id = "piece:staff:0:bar:2:event:0:0"
    assert playing.result.cells_for(active_id)
    assert tuple(line.replace("^", " ") for line in playing.result.lines) == idle.result.lines
    assert playing.result.frame.attrs != idle.result.frame.attrs
    assert "^" in playing.result.text


def test_short_view_scrolls_to_focused_voice_without_partial_neighbor() -> None:
    piece = _imported_piece(tablature=False, two_voices=True)
    view = typeset_piece_score_view(
        piece,
        width=80,
        height=12,
        bar_offset=0,
        cursor=(0, 0),
        playback=None,
        settings=SETTINGS,
        focused_imported_staff_index=2,
    )

    assert view is not None
    assert view.result.cells_for("piece:staff:2:bar:0:event:0:0")
    assert not view.result.cells_for("piece:staff:0:bar:0:event:0:0")


def test_explicit_score_view_keeps_all_mixed_staffs_and_focus_scrolls_tall_layout() -> None:
    piece = _imported_piece(tablature=True, two_voices=True)
    settings = {**SETTINGS, "scoreview": "score"}
    full = typeset_piece_score_view(
        piece,
        width=120,
        height=40,
        bar_offset=0,
        cursor=(0, 0),
        playback=None,
        settings=settings,
        focused_imported_staff_index=0,
    )
    lower = typeset_piece_score_view(
        piece,
        width=80,
        height=12,
        bar_offset=0,
        cursor=(0, 0),
        playback=None,
        settings=settings,
        focused_imported_staff_index=2,
    )

    assert full is not None and lower is not None
    expected_staffs = ["piece:staff:0", "piece:staff:2", "piece:tab"]
    assert [rows.staff_id for rows in full.result.layout.systems[0].staff_rows] == expected_staffs
    assert "soprano" in full.result.text and "bass" in full.result.text and "lute" in full.result.text
    assert [rows.staff_id for rows in lower.result.layout.systems[0].staff_rows] == expected_staffs
    assert lower.result.cells_for("piece:staff:2:bar:0:event:0:0")


def test_explicit_staff_view_selects_one_voice_or_falls_back_to_tab() -> None:
    piece = _imported_piece(tablature=True, two_voices=True)
    settings = {**SETTINGS, "scoreview": "staff"}
    bass = typeset_piece_score_view(
        piece,
        width=80,
        height=24,
        bar_offset=0,
        cursor=(0, 0),
        playback=None,
        settings=settings,
        focused_imported_staff_index=2,
    )
    tab = typeset_piece_score_view(
        piece,
        width=80,
        height=24,
        bar_offset=0,
        cursor=(0, 0),
        playback=None,
        settings=settings,
        focused_imported_staff_index=None,
    )

    assert bass is not None
    assert [rows.staff_id for rows in bass.result.layout.systems[0].staff_rows] == ["piece:staff:2"]
    assert "bass" in bass.result.text and "soprano" not in bass.result.text and "lute" not in bass.result.text
    assert tab is None
