from __future__ import annotations

import time

from oud.core.playback_timeline import cursor_at_time
from oud.editor.state import EditorState


def clear_playback_cursor(state: EditorState) -> None:
    state.playback.bar = None
    state.playback.col = None


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
    idx, cursor = cursor_at_time(
        state.playback.timeline,
        elapsed,
        start_index=state.playback.index,
    )
    state.playback.index = idx
    if cursor is None:
        clear_playback_cursor(state)
        return
    state.playback.bar = cursor.bar
    state.playback.col = cursor.col


def reset_playback_animation(state: EditorState) -> None:
    prime_playback_animation(state, [])


def update_playback_animation(state: EditorState) -> None:
    proc = state.midi_proc
    if proc is None or state.playback.started_at is None or not state.playback.timeline:
        clear_playback_cursor(state)
        return
    if proc.poll() is not None:
        state.midi_proc = None
        reset_playback_animation(state)
        return
    elapsed = time.monotonic() - state.playback.started_at
    advance_playback_cursor(state, elapsed)
