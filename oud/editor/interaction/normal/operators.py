"""Operators (`d`, `y`, `c`) over motions, and repeating the last edit with `.`.

An operator waits for one motion. The motion runs inside a visual selection that
starts at the cursor, then the selection is deleted, copied or changed, so an
operator reuses the visual-mode edits. Repeating the operator key (`dd`, `yy`)
works on [count] whole bars.
"""

from __future__ import annotations

from oud.editor.core.coordinates import consume_count
from oud.editor.core.input.keymap import Action
from oud.editor.core.state import EditorState, RepeatableEdit
from oud.editor.interaction.normal import movement as mv
from oud.editor.interaction.normal.action_input import ActionInput

OPERATORS: frozenset[Action] = frozenset({Action.OPERATOR_DELETE, Action.OPERATOR_YANK, Action.OPERATOR_CHANGE})

MOTIONS: frozenset[Action] = frozenset(
    {
        Action.MOVE_LEFT,
        Action.MOVE_RIGHT,
        Action.MOVE_UP,
        Action.MOVE_DOWN,
        Action.ROW_PREV,
        Action.ROW_NEXT,
        Action.BAR_PREV,
        Action.BAR_NEXT,
        Action.BAR_HOME,
        Action.BAR_START,
        Action.BAR_END,
        Action.ROW_FIRST_NOTE,
        Action.FIRST_BAR,
        Action.LAST_BAR,
        Action.FIND_FORWARD,
        Action.FIND_BACKWARD,
        Action.TILL_FORWARD,
        Action.TILL_BACKWARD,
        Action.FIND_REPEAT,
        Action.FIND_REPEAT_REVERSE,
        Action.MATCH_JUMP,
        Action.MARK_JUMP,
    },
)
# A find that goes nowhere cancels the operator, as in vim.
_SEARCHING_MOTIONS: frozenset[Action] = frozenset(
    {
        Action.FIND_FORWARD,
        Action.FIND_BACKWARD,
        Action.TILL_FORWARD,
        Action.TILL_BACKWARD,
        Action.FIND_REPEAT,
        Action.FIND_REPEAT_REVERSE,
        Action.MATCH_JUMP,
        Action.MARK_JUMP,
    },
)
# Edits `.` can replay: changes and inserts are not repeated because their typed text is not recorded.
REPEATABLE: frozenset[Action] = frozenset(
    {
        Action.DELETE_NOTE,
        Action.DELETE_BARS,
        Action.BAR_AFTER,
        Action.BAR_BEFORE,
        Action.BAR_DELETE,
        Action.PASTE_BARS,
        Action.PASTE_BARS_BEFORE,
    },
)
_LINE_ACTIONS: dict[Action, Action] = {
    Action.OPERATOR_DELETE: Action.DELETE_BARS,
    Action.OPERATOR_YANK: Action.YANK_BARS,
}
_MAX_COUNT = 999


def run_handler(action: Action, state: EditorState, action_input: ActionInput) -> bool:
    # The handler table refers to this module, so it is imported at call time.
    from oud.editor.interaction.normal.handlers import NORMAL_HANDLERS  # noqa: PLC0415

    return NORMAL_HANDLERS[action](state, action_input)


def start_operator(state: EditorState, operator: Action) -> None:
    state.operator_count = consume_count(state)
    state.pending_operator = operator


def cancel_operator(state: EditorState) -> None:
    state.pending_operator = None
    state.operator_count = 1
    state.count_prefix = ""


def apply_operator(state: EditorState, action: Action, action_input: ActionInput) -> bool:
    """Finish the pending operator with `action`; anything but a motion or the operator key cancels."""
    operator = state.pending_operator
    if operator is None:
        return True
    total = min(_MAX_COUNT, state.operator_count * consume_count(state))
    cancel_operator(state)
    if action is operator:
        return _apply_to_bars(state, operator, total)
    if action not in MOTIONS:
        state.message = "Operator needs a motion"
        return True
    return _apply_to_motion(state, operator, action, action_input, total)


def _apply_to_bars(state: EditorState, operator: Action, count: int) -> bool:
    line_action = _LINE_ACTIONS.get(operator)
    if line_action is None:
        state.message = "Changing whole bars is not supported; use d then i"
        return True
    state.count_prefix = str(count)
    run_handler(line_action, state, ActionInput(0))
    if operator is Action.OPERATOR_DELETE:
        state.last_edit = RepeatableEdit(line_action, count)
    return True


def _apply_to_motion(
    state: EditorState,
    operator: Action,
    motion: Action,
    action_input: ActionInput,
    count: int,
) -> bool:
    before = _position(state)
    mv.enter_visual(state, linewise=False)
    state.count_prefix = str(count) if count > 1 else ""
    run_handler(motion, state, action_input)
    state.count_prefix = ""
    if motion in _SEARCHING_MOTIONS and _position(state) == before:
        mv.exit_visual(state)
        return True
    if operator is Action.OPERATOR_YANK:
        mv.visual_yank(state)
        return True
    change = operator is Action.OPERATOR_CHANGE
    mv.visual_delete(state, change=change)
    if not change:
        state.last_edit = RepeatableEdit(motion, count, operator, action_input.char)
    return True


def _position(state: EditorState) -> tuple[int, int, int]:
    return (state.cursor_bar, state.cursor_string, state.cursor_col)


def record_edit(state: EditorState, action: Action, count: int) -> None:
    if action in REPEATABLE:
        state.last_edit = RepeatableEdit(action, count)


def repeat_last_edit(state: EditorState) -> None:
    edit = state.last_edit
    if edit is None:
        state.message = "Nothing to repeat"
        return
    count = consume_count(state) if state.count_prefix else edit.count
    if edit.operator is None:
        state.count_prefix = str(count) if count > 1 else ""
        run_handler(edit.action, state, ActionInput(0))
        state.count_prefix = ""
        return
    _apply_to_motion(state, edit.operator, edit.action, ActionInput(0, edit.motion_char), count)
