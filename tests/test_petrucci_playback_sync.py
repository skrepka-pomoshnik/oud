from types import SimpleNamespace
from typing import cast

from oud.editor.core.state import EditorState, PlaybackState
from oud.editor.services.media.playback import advance_playback_cursor
from oud.exports._midi_projection import _timed_vocal_events, build_playback_timeline
from oud.exports._midi_serialization import _polyphonic_score_midi_note_events
from petrucci.model import Bar, ImportedBarContent, ImportedScore, ImportedStaff, MelodyEvent, Piece
from petrucci.piece_score_view import typeset_piece_score_view
from petrucci.vocal_line import VocalEvent


def _polyphonic_piece() -> Piece:
    staffs = [
        ImportedStaff("note", "Cantus", [ImportedBarContent(0, melody_events=[MelodyEvent("c4", 0)])]),
        ImportedStaff("note", "Bassus", [ImportedBarContent(0, melody_events=[MelodyEvent("g2", 0)])]),
    ]
    bars = [Bar(melody_events=[MelodyEvent("c4", 0)])]
    return Piece(bars=bars, imported_score=ImportedScore("ft3", staffs))


def test_explicit_polyphonic_voices_use_independent_clocks() -> None:
    events = [
        VocalEvent(0, 0, 60, 4, False, voice=0),
        VocalEvent(0, 0, 48, 4, False, voice=1),
        VocalEvent(1, 1, 62, 4, False, voice=0),
    ]

    timed = _timed_vocal_events(events, [], has_explicit_melody=True)

    assert timed[0][1] == timed[1][1] == 0
    assert timed[2][1] == timed[0][2]


def test_all_imported_staffs_play_on_distinct_channels_and_highlight() -> None:
    piece = _polyphonic_piece()
    events = _polyphonic_score_midi_note_events(
        piece,
        overrides={},
        durations={},
        bar_width=12,
        style="french",
        default_duration=4,
        start_bar=0,
        dotted=None,
        settings={},
        gate=0.85,
        pitches=[67, 62, 57, 53, 48, 43],
        ornaments=None,
    )
    note_on_channels = {payload[0] & 0x0F for _tick, payload in events if payload and payload[0] & 0xF0 == 0x90}
    assert {1, 2} <= note_on_channels

    view = typeset_piece_score_view(
        piece,
        width=80,
        height=30,
        bar_offset=0,
        cursor=(0, 0),
        playback=(0, 0),
        settings={"scoreview": "score", "showmelody": "on", "showlyrics": "off"},
    )
    assert view is not None
    for staff_index in (0, 1):
        event_id = f"piece:staff:{staff_index}:bar:0:event:0:0"
        assert any(view.result.frame.attrs[row][column] for row, column in view.result.cells_for(event_id))


def test_playback_verse_identity_drives_editor_state() -> None:
    piece = Piece(bars=[Bar(melody_events=[MelodyEvent("c4", 0)], lyrics=["one", "two"])])
    timeline = build_playback_timeline(piece, {}, {}, 12, {"playverses": "all"})
    state = cast(EditorState, SimpleNamespace(playback=PlaybackState()))
    state.playback.timeline = timeline

    advance_playback_cursor(state, timeline[-1].start)

    assert state.playback.verse == 1
