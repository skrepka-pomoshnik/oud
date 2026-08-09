from __future__ import annotations

from oud.editor.core.state import EditorState
from oud.editor.navigation.view.state import (
    view_commit_frame,
    view_mark_dirty_rows,
    view_merge_dirty,
    view_resize,
)
from petrucci.core.model import Bar, Piece
from petrucci.terminal.canvas.framebuffer import Frame


def _state() -> EditorState:
    return EditorState(Piece(title="T", bars=[Bar()]), {"style": "french"})


def test_view_resize_initializes_frame_cache_and_marks_all_rows() -> None:
    state = _state()
    changed = view_resize(state, height=5, width=10)
    assert changed is True
    assert state.last_frame is None
    assert state.last_base_frame is None
    assert state.playback_overlay_cache is None
    assert state.playback_overlay_key is None
    assert state.last_frame_size == (5, 10)
    assert state.dirty_rows == {0, 1, 2, 3, 4}


def test_view_resize_noop_when_size_unchanged() -> None:
    state = _state()
    view_resize(state, height=4, width=8)
    state.last_frame = Frame(lines=[" " * 8] * 4, attrs=[(0,) * 8] * 4)
    state.dirty_rows = {2}
    changed = view_resize(state, height=4, width=8)
    assert changed is False
    assert state.last_frame is not None
    assert state.dirty_rows == {2}


def test_view_merge_mark_and_commit() -> None:
    state = _state()
    view_mark_dirty_rows(state, {1, 3})
    assert state.dirty_rows == {1, 3}
    merged = view_merge_dirty(state, {2, 3})
    assert merged == {1, 2, 3}
    frame = Frame(lines=["a"], attrs=[(0,)])
    view_commit_frame(state, frame)
    assert state.last_frame == frame
    assert state.dirty_rows == set()
