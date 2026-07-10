from __future__ import annotations

from oud.editor.state import EditorState
from oud.petrucci.framebuffer import Frame


def view_resize(state: EditorState, *, height: int, width: int) -> bool:
    size = (height, width)
    if state.last_frame_size == size:
        return False
    state.last_frame = None
    state.last_base_frame = None
    state.playback_overlay_cache = None
    state.playback_overlay_key = None
    state.last_frame_size = size
    state.dirty_rows = set(range(max(0, height)))
    return True


def view_merge_dirty(state: EditorState, dirty: set[int]) -> set[int]:
    if state.dirty_rows:
        return dirty | state.dirty_rows
    return dirty


def view_commit_frame(state: EditorState, frame: Frame) -> None:
    state.last_frame = frame
    state.dirty_rows.clear()


def view_mark_dirty_rows(state: EditorState, rows: set[int]) -> None:
    if not rows:
        return
    state.dirty_rows |= rows
