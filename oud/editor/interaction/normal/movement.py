from __future__ import annotations

from collections.abc import Callable

from oud.editor.core.coordinates import consume_count
from oud.editor.core.input.modes import VISUAL_MODES, Mode
from oud.editor.core.session import set_mode
from oud.editor.core.state import EditorState
from oud.editor.editing.visual import (
    clear_visual_mode,
    delete_visual_rows,
    enter_visual_mode,
    visual_bar_range,
    yank_visual_rows,
)
from oud.editor.navigation.motions import (
    CursorMotionTarget,
    apply_counted_visual_motion,
    apply_motion_target,
    target_bar_end,
    target_bar_next,
    target_bar_prev,
    target_bar_start,
    target_home_bar,
    target_jump_first_bar,
    target_jump_last_bar,
    target_jump_row_visual,
    target_move_left_note,
    target_move_right_note,
)
from oud.editor.navigation.view.focus import cycle_view_staff, visible_view_staffs
from oud.editor.navigation.viewport import (
    jump_viewport_section_page,
    scroll_viewport_page,
    scroll_viewport_system,
)
from oud.editor.services.media.midi import start_midi

VISUAL_LOOP_COUNT = 2


def move_horizontal(state: EditorState, direction: int) -> None:
    count = consume_count(state)
    if state.settings.get("movementmode", "visual") == "note":
        target = target_move_left_note if direction < 0 else target_move_right_note
        _apply_counted_motion(state, count, target)
    else:
        apply_counted_visual_motion(state, direction, count)


def move_vertical(state: EditorState, direction: int) -> None:
    delta = direction * consume_count(state)
    if state.read_only and len(visible_view_staffs(state.piece)) > 1:
        cycle_view_staff(state, delta)
    else:
        state.cursor_string += delta
        state.clamp()


def jump_row(state: EditorState, direction: int) -> None:
    """Move to the same offset in the next rendered row; viewers scroll a system."""
    delta = direction * consume_count(state)
    if state.read_only:
        scroll_viewport_system(state, state.screen_width, state.screen_height, delta)
    else:
        apply_motion_target(state, target_jump_row_visual(state, delta))


def scroll_page(state: EditorState, direction: int) -> None:
    scroll_viewport_page(state, state.screen_width, state.screen_height, direction * consume_count(state))


def jump_section(state: EditorState, direction: int) -> None:
    jump_viewport_section_page(state, direction * consume_count(state))


def step_bar(state: EditorState, direction: int) -> None:
    count = consume_count(state)
    target = target_bar_next(state, count) if direction > 0 else target_bar_prev(state, count)
    apply_motion_target(state, target)


def bar_home(state: EditorState) -> None:
    apply_motion_target(state, target_home_bar(state, state.cursor_bar))


def bar_start(state: EditorState) -> None:
    apply_motion_target(state, target_bar_start(state))


def bar_end(state: EditorState) -> None:
    apply_motion_target(state, target_bar_end(state))


def first_bar(state: EditorState) -> None:
    apply_motion_target(state, target_jump_first_bar(state))


def last_bar(state: EditorState) -> None:
    apply_motion_target(state, target_jump_last_bar(state))


def enter_visual(state: EditorState, *, linewise: bool) -> None:
    if state.mode not in VISUAL_MODES:
        state.visual_anchor = (state.cursor_bar, state.cursor_string, state.cursor_col)
    enter_visual_mode(state, linewise=linewise)


def exit_visual(state: EditorState) -> None:
    clear_visual_mode(state)
    state.message = ""


def visual_command(state: EditorState) -> None:
    state.visual_anchor = None
    set_mode(state, Mode.COMMAND)
    state.cmdline = ""


def visual_yank(state: EditorState) -> None:
    yank_visual_rows(state)


def visual_play(state: EditorState) -> None:
    bar_range = visual_bar_range(state)
    start_midi(state, start_bar=bar_range.start, end_bar=bar_range.end - 1, loop_count=VISUAL_LOOP_COUNT)


def visual_delete(state: EditorState, *, change: bool) -> None:
    delete_visual_rows(state, change=change)


def _apply_counted_motion(
    state: EditorState,
    count: int,
    target_for_state: Callable[[EditorState], CursorMotionTarget],
) -> None:
    for _ in range(count):
        before = (state.cursor_bar, state.cursor_col, state.cursor_string, len(state.piece.bars))
        target = target_for_state(state)
        apply_motion_target(state, target)
        after = (state.cursor_bar, state.cursor_col, state.cursor_string, len(state.piece.bars))
        if target.append_bar or after == before:
            break
