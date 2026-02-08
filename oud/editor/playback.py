from __future__ import annotations

import time

from oud.core.playback_timeline import cursor_from_entry
from oud.editor.state import EditorState


def reset_playback_animation(state: EditorState) -> None:
    state.playback_timeline = []
    state.playback_started_at = None
    state.playback_index = 0
    state.playback_bar = None
    state.playback_col = None


def update_playback_animation(state: EditorState) -> None:
    proc = state.midi_proc
    if proc is None or state.playback_started_at is None or not state.playback_timeline:
        state.playback_bar = None
        state.playback_col = None
        return
    if proc.poll() is not None:
        state.midi_proc = None
        reset_playback_animation(state)
        return
    elapsed = time.monotonic() - state.playback_started_at
    timeline = state.playback_timeline
    idx = max(0, min(state.playback_index, len(timeline) - 1))
    while idx + 1 < len(timeline) and elapsed >= cursor_from_entry(timeline[idx + 1]).start:
        idx += 1
    while idx > 0 and elapsed < cursor_from_entry(timeline[idx]).start:
        idx -= 1
    state.playback_index = idx
    cursor = cursor_from_entry(timeline[idx])
    if cursor.contains(elapsed):
        state.playback_bar = cursor.bar
        state.playback_col = cursor.col
    else:
        state.playback_bar = None
        state.playback_col = None
