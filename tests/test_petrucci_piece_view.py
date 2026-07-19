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
    assert " G " in result.text
    assert result.cursor_display_maps == {0: [19]}


@pytest.mark.parametrize(("width", "height"), ((80, 24), (120, 40)))
def test_each_polyphonic_staff_is_reachable_in_compact_focus(width: int, height: int) -> None:
    piece = _imported_piece(tablature=False, two_voices=True)
    for staff_index, expected_label in ((0, "soprano"), (2, "bass")):
        view = typeset_piece_score_view(
            piece,
            width=width,
            height=height,
            bar_offset=0,
            cursor=(0, 0),
            playback=None,
            settings=SETTINGS,
            focused_imported_staff_index=staff_index,
        )
        assert view is not None
        assert len(view.result.layout.systems) == 1
        assert view.result.layout.event_ids == (f"piece:staff:{staff_index}:bar:0:event:0:0",)
        assert expected_label in view.result.text
        assert view.result.cells_for(f"piece:staff:{staff_index}:bar:0:event:0:0")


def test_mixed_default_remains_tablature_but_note_and_lyric_focus_are_canonical() -> None:
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

    assert default is None
    assert note is not None and lyric is not None
    assert note.result.text == lyric.result.text
    assert "sing" in note.result.text


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
    assert playing.result.lines == idle.result.lines
    assert playing.result.frame.attrs != idle.result.frame.attrs
