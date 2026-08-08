from __future__ import annotations

from collections.abc import Callable

from oud.editor.controller_utils import consume_count, is_casual
from oud.editor.insert_session import set_mode
from oud.editor.keymap import NormalActionBindings, movement_keys, normal_action_bindings, normal_bindings
from oud.editor.messages import READ_ONLY_VIEWER
from oud.editor.midi_control import start_midi
from oud.editor.motions import (
    CursorMotionTarget,
    apply_counted_visual_motion,
    apply_motion_target,
    target_bar_end,
    target_bar_next,
    target_bar_prev,
    target_bar_start,
    target_jump_last_bar,
    target_jump_row_visual,
    target_move_left_note,
    target_move_right_note,
)
from oud.editor.state import EditorState
from oud.editor.view_focus import cycle_view_staff, visible_view_staffs
from oud.editor.viewport import scroll_viewport_page, scroll_viewport_system
from oud.editor.visual_ops import (
    clear_visual_mode,
    delete_visual_rows,
    enter_visual_mode,
    visual_bar_range,
    yank_visual_rows,
)


def handle_visual_mode(state: EditorState, key: int) -> bool:
    if _handle_visual_session(state, key):
        return True
    if _handle_visual_action(state, key):
        return True
    handle_normal_movement(state, key)
    return True


def handle_normal_movement(state: EditorState, key: int) -> bool:
    count = consume_count(state)
    action_keys = normal_action_bindings(state)
    for handler in (_horizontal_motion, _vertical_motion, _viewport_motion, _jump_motion):
        if handler(state, key, count, action_keys):
            return True
    return False


def _handle_visual_session(state: EditorState, key: int) -> bool:
    bindings = normal_bindings(state)
    if key in (27, state.keycodes.exit):
        clear_visual_mode(state)
        state.message = ""
        return True
    if key in bindings.command:
        state.visual_anchor = None
        set_mode(state, "command")
        state.cmdline = ""
        return True
    if key in (ord("v"), ord("V")):
        enter_visual_mode(state, linewise=key == ord("V"))
        return True
    return False


def _handle_visual_action(state: EditorState, key: int) -> bool:
    if key in (ord("y"), ord("Y")):
        yank_visual_rows(state)
        return True
    if key in normal_bindings(state).play:
        bar_range = visual_bar_range(state)
        start_midi(state, start_bar=bar_range.start, end_bar=bar_range.end - 1, loop_count=2)
        return True
    if key in _visual_delete_keys(state):
        return _delete_visual(state, change=False)
    if key in (ord("c"), ord("C")):
        return _delete_visual(state, change=True)
    return False


def _visual_delete_keys(state: EditorState) -> tuple[int, ...]:
    keys = (ord("D"), ord("x"), ord("X"), state.keycodes.dc)
    return keys if is_casual(state) else (ord("d"), *keys)


def _delete_visual(state: EditorState, *, change: bool) -> bool:
    if state.read_only:
        state.message = READ_ONLY_VIEWER
    else:
        delete_visual_rows(state, change=change)
    return True


def _horizontal_motion(state: EditorState, key: int, count: int, _actions: NormalActionBindings) -> bool:
    keys = movement_keys(state, include_arrows=True)
    note_mode = state.settings.get("movementmode", "visual") == "note"
    if key in keys.left:
        _move_horizontal(state, -1, count, note_mode)
        return True
    if key in keys.right:
        _move_horizontal(state, 1, count, note_mode)
        return True
    return False


def _move_horizontal(state: EditorState, direction: int, count: int, note_mode: bool) -> None:
    if note_mode:
        target = target_move_left_note if direction < 0 else target_move_right_note
        _apply_counted_motion(state, count, target)
    else:
        apply_counted_visual_motion(state, direction, count)


def _vertical_motion(state: EditorState, key: int, count: int, _actions: NormalActionBindings) -> bool:
    keys = movement_keys(state, include_arrows=True)
    if key in keys.up:
        _move_vertical(state, -count)
        return True
    if key in keys.down:
        _move_vertical(state, count)
        return True
    return False


def _move_vertical(state: EditorState, delta: int) -> None:
    if state.read_only and len(visible_view_staffs(state.piece)) > 1:
        cycle_view_staff(state, delta)
    else:
        state.cursor_string += delta
        state.clamp()


def _viewport_motion(state: EditorState, key: int, count: int, actions: NormalActionBindings) -> bool:
    directions = (
        (actions.scroll_up, lambda: scroll_viewport_page(state, state.screen_width, state.screen_height, -count)),
        (actions.scroll_down, lambda: scroll_viewport_page(state, state.screen_width, state.screen_height, count)),
        (actions.page_up, lambda: _jump_system(state, -count)),
        (actions.page_down, lambda: _jump_system(state, count)),
    )
    for keys, action in directions:
        if key in keys:
            action()
            return True
    return False


def _jump_system(state: EditorState, delta: int) -> None:
    if state.read_only:
        scroll_viewport_system(state, state.screen_width, state.screen_height, delta)
    else:
        apply_motion_target(state, target_jump_row_visual(state, delta))


def _jump_motion(state: EditorState, key: int, count: int, actions: NormalActionBindings) -> bool:
    targets = (
        (actions.bar_next, lambda: target_bar_next(state, count)),
        (actions.bar_prev, lambda: target_bar_prev(state, count)),
        (actions.col_start, lambda: target_bar_start(state)),
        (actions.col_end, lambda: target_bar_end(state)),
        (actions.jump_bottom, lambda: target_jump_last_bar(state)),
    )
    for keys, target in targets:
        if key in keys:
            apply_motion_target(state, target())
            return True
    return False


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
