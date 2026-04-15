from __future__ import annotations

from oud.core.playback_timeline import (
    PlaybackCursor,
    build_timeline_from_events,
    cursor_at_time,
    cursors_at_time,
)


def test_build_timeline_from_events_converts_ticks_to_seconds() -> None:
    events = [(0, 0, 480, 0), (0, 480, 240, 2)]
    timeline = build_timeline_from_events(events, sec_per_tick=0.001)
    assert timeline == [
        PlaybackCursor(start=0.0, end=0.48, bar=0, col=0),
        PlaybackCursor(start=0.48, end=0.72, bar=0, col=2),
    ]


def test_cursor_at_time_finds_current_cursor_and_index() -> None:
    timeline = [
        PlaybackCursor(start=0.0, end=0.5, bar=1, col=0),
        PlaybackCursor(start=0.5, end=1.0, bar=1, col=3),
    ]
    idx, cursor = cursor_at_time(timeline, 0.75, start_index=0)
    assert idx == 1
    assert cursor is not None
    assert cursor.bar == 1
    assert cursor.col == 3


def test_cursor_at_time_accepts_legacy_tuple_entries() -> None:
    timeline = [(0.0, 0.5, 0, 1), (0.5, 1.0, 0, 4)]
    idx, cursor = cursor_at_time(timeline, 0.6, start_index=0)
    assert idx == 1
    assert cursor is not None
    assert cursor.col == 4


def test_cursors_at_time_returns_all_overlapping_cursors() -> None:
    timeline = [
        PlaybackCursor(start=0.0, end=0.5, bar=0, col=1),
        PlaybackCursor(start=0.0, end=0.5, bar=2, col=3),
        PlaybackCursor(start=0.5, end=1.0, bar=0, col=4),
    ]
    idx, cursors = cursors_at_time(timeline, 0.25, start_index=0)
    assert idx == 1
    assert [(cursor.bar, cursor.col) for cursor in cursors] == [(0, 1), (2, 3)]
