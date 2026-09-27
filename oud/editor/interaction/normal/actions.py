from __future__ import annotations

from oud.editor.core.coordinates import append_count_digit, normalize_count_prefix
from oud.editor.core.feedback.messages import READ_ONLY_VIEWER
from oud.editor.core.input.keymap import ACTION_SPECS, Action, keymap_for
from oud.editor.core.input.modes import VISUAL_MODES, Mode
from oud.editor.core.state import EditorState
from oud.editor.interaction.normal.handlers import NORMAL_HANDLERS, ActionInput

_COUNT_DIGITS = frozenset(ord(digit) for digit in "0123456789")


def handle_normal(state: EditorState, key: int) -> bool:
    """Dispatch one normal- or visual-mode key through the key table.

    Returns False only when the editor should stop.
    """
    normalize_count_prefix(state)
    if state.pending_action is not None:
        return _complete_char_action(state, key)
    if not state.pending_keys and _append_count(state, key):
        return True
    mode = Mode.VISUAL if state.mode in VISUAL_MODES else Mode.NORMAL
    keymap = keymap_for(state, mode)
    sequence = (*state.pending_keys, key)
    if keymap.is_prefix(sequence):
        state.pending_keys = sequence
        return True
    state.pending_keys = ()
    action = keymap.lookup(sequence)
    if action is None:
        state.count_prefix = ""
        return True
    return run_action(state, action, ActionInput(key))


def run_action(state: EditorState, action: Action, action_input: ActionInput) -> bool:
    """Run `action` behind the single read-only gate; wait for a char argument first."""
    spec = ACTION_SPECS[action]
    if spec.mutates and state.read_only:
        state.message = READ_ONLY_VIEWER
        state.count_prefix = ""
        return True
    if spec.takes_char and not action_input.char:
        state.pending_action = action
        if not spec.keeps_count:
            state.count_prefix = ""
        return True
    running = NORMAL_HANDLERS[action](state, action_input)
    state.count_prefix = ""
    return running


def _append_count(state: EditorState, key: int) -> bool:
    # A leading 0 is a motion, not a count digit.
    if key not in _COUNT_DIGITS or (key == ord("0") and not state.count_prefix):
        return False
    append_count_digit(state, chr(key))
    return True


def _complete_char_action(state: EditorState, key: int) -> bool:
    action = state.pending_action
    state.pending_action = None
    if action is None or not ord(" ") <= key <= ord("~"):
        state.count_prefix = ""
        return True
    return run_action(state, action, ActionInput(key, chr(key)))
