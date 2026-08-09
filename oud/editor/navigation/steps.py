from __future__ import annotations

from oud.editor.core.state import EditorState
from oud.editor.navigation.motions import (
    apply_motion_target,
    target_bar_end,
    target_bar_next,
    target_bar_prev,
    target_bar_start,
    target_jump_first_bar,
    target_jump_last_bar,
    target_jump_row_visual,
    target_move_left,
    target_move_left_note,
    target_move_left_visual,
    target_move_right,
    target_move_right_note,
    target_move_right_visual,
)


def move_left(state: EditorState) -> None:
    apply_motion_target(state, target_move_left(state))


def move_right(state: EditorState) -> None:
    apply_motion_target(state, target_move_right(state))


def move_left_visual(state: EditorState) -> None:
    apply_motion_target(state, target_move_left_visual(state))


def move_right_visual(state: EditorState) -> None:
    apply_motion_target(state, target_move_right_visual(state))


def jump_row_visual(state: EditorState, delta: int) -> None:
    apply_motion_target(state, target_jump_row_visual(state, delta))


def move_left_note(state: EditorState) -> None:
    apply_motion_target(state, target_move_left_note(state))


def move_right_note(state: EditorState) -> None:
    apply_motion_target(state, target_move_right_note(state))


def bar_next(state: EditorState, count: int = 1) -> None:
    apply_motion_target(state, target_bar_next(state, count))


def bar_prev(state: EditorState, count: int = 1) -> None:
    apply_motion_target(state, target_bar_prev(state, count))


def bar_start(state: EditorState) -> None:
    apply_motion_target(state, target_bar_start(state))


def bar_end(state: EditorState) -> None:
    apply_motion_target(state, target_bar_end(state))


def jump_first_bar(state: EditorState) -> None:
    apply_motion_target(state, target_jump_first_bar(state))


def jump_last_bar(state: EditorState) -> None:
    apply_motion_target(state, target_jump_last_bar(state))
