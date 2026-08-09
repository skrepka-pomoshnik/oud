from __future__ import annotations

import time

from oud.editor.core.state import EditorState
from oud.services.playback.timeline import cursors_at_time


def clear_playback_cursor(state: EditorState) -> None:
    state.playback.bar = None
    state.playback.col = None
    state.playback.markers = []
    state.playback.verse = None


def prime_playback_animation(state: EditorState, timeline) -> None:
    state.playback.timeline = list(timeline)
    state.playback.started_at = None
    state.playback.index = 0
    clear_playback_cursor(state)


def start_playback_clock(state: EditorState, started_at: float) -> None:
    state.playback.started_at = started_at


def advance_playback_cursor(state: EditorState, elapsed: float) -> None:
    if not state.playback.timeline:
        clear_playback_cursor(state)
        state.playback.index = 0
        return
    idx, cursors = cursors_at_time(
        state.playback.timeline,
        elapsed,
        start_index=state.playback.index,
    )
    state.playback.index = idx
    if not cursors:
        clear_playback_cursor(state)
        return
    cursor = max(cursors, key=lambda item: (item.start, item.verse))
    state.playback.bar = cursor.bar
    state.playback.col = cursor.col
    state.playback.markers = [(item.bar, item.col) for item in cursors]
    state.playback.verse = cursor.verse


def reset_playback_animation(state: EditorState) -> None:
    prime_playback_animation(state, [])


def update_playback_animation(state: EditorState) -> bool:
    before = (state.playback.bar, state.playback.col, state.playback.index, state.midi_proc)

    def after() -> tuple[int | None, int | None, int, object]:
        return (
            state.playback.bar,
            state.playback.col,
            state.playback.index,
            state.midi_proc,
        )

    proc = state.midi_proc
    if proc is None or state.playback.started_at is None or not state.playback.timeline:
        clear_playback_cursor(state)
        return before != after()
    if proc.poll() is not None:
        state.midi_proc = None
        reset_playback_animation(state)
        return before != after()
    elapsed = time.monotonic() - state.playback.started_at
    advance_playback_cursor(state, elapsed)
    return before != after()
