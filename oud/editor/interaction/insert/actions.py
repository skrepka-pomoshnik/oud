from __future__ import annotations

from collections.abc import Callable, Mapping
from types import MappingProxyType

from oud.editor.core.coordinates import string_index
from oud.editor.core.input.keymap import Action, keymap_for
from oud.editor.core.input.modes import Mode
from oud.editor.core.session import (
    clear_insert_transient,
    exit_insert_mode,
    finish_replace_once,
)
from oud.editor.core.state import EditorState
from oud.editor.editing.primitives.edits import undo_group
from oud.editor.editing.primitives.tablature import (
    duration_value,
    french_to_fret,
    is_french_fret,
    is_italian_fret,
    italian_to_fret,
)
from oud.editor.editing.tab.typing import delete_at_cursor, set_duration, toggle_dot, type_fret, type_rest
from oud.editor.interaction.normal.commands import quit_editor
from oud.editor.navigation.motions import apply_motion_target, target_step_display_row
from oud.editor.navigation.steps import move_left, move_right

_ITALIAN_DURATION_DIGITS = frozenset(ord(digit) for digit in "1234567")
_BASS_COURSE_START = 6


def _commit_pending_insert_edit(state: EditorState) -> None:
    """Cancel transient insert prefixes before movement/command transitions."""
    if state.insert_prefix:
        clear_insert_transient(state)


def _replace_mode_active(state: EditorState) -> bool:
    return state.mode == Mode.REPLACE


def _advance_after_insert(state: EditorState) -> None:
    if finish_replace_once(state):
        return
    if _replace_mode_active(state):
        return
    move_right(state)


def _enter_fret(state: EditorState, course_index: int, fret: int) -> None:
    with undo_group(state, label="insert-fret"):
        entered = type_fret(state, course_index, fret, replace_only=_replace_mode_active(state))
    if entered:
        _advance_after_insert(state)


def _apply_duration_key(state: EditorState, dur: int) -> bool:
    set_duration(state, dur)
    return True


def _handle_insert_dot(state: EditorState) -> bool:
    toggle_dot(state)
    return True


def _handle_insert_rest(state: EditorState) -> bool:
    _commit_pending_insert_edit(state)
    if type_rest(state, replace_only=_replace_mode_active(state)):
        _advance_after_insert(state)
    return True


def _insert_bass_note(state: EditorState, target: int, ch: str) -> None:
    clear_insert_transient(state)
    fret = french_to_fret(ch)
    if fret is not None:
        _enter_fret(state, target, fret)


def _continue_bass_slash(state: EditorState, key: int) -> bool:
    if key == ord("/"):
        state.insert_prefix += "/"
        return True
    if not ord(" ") <= key <= ord("~"):
        clear_insert_transient(state)
        return False
    ch = chr(key).lower()
    if french_to_fret(ch) is None:
        clear_insert_transient(state)
        return False
    target = _BASS_COURSE_START + (len(state.insert_prefix) - 1)
    if target >= state.piece.strings:
        state.message = "Bass string not available"
        clear_insert_transient(state)
        return True
    _insert_bass_note(state, target, ch)
    return True


def _handle_insert_bass_slash(
    state: EditorState,
    key: int,
    style: str,
) -> bool:
    if style != "french":
        return False
    if state.insert_prefix and all(ch == "/" for ch in state.insert_prefix):
        return _continue_bass_slash(state, key)
    if key == ord("/"):
        state.insert_prefix = "/"
        return True
    return False


def _handle_insert_duration_key(state: EditorState, key: int, style: str) -> bool:
    if state.insert_prefix == ";":
        state.insert_prefix = ""
        if key in _ITALIAN_DURATION_DIGITS and style == "italian":
            digit = int(chr(key))
            dur = {1: 1, 2: 2, 3: 4, 4: 8, 5: 16, 6: 32, 7: 64}.get(digit)
            if dur is not None:
                return _apply_duration_key(state, dur)
    dur = duration_value(key, style)
    if dur is not None:
        return _apply_duration_key(state, dur)
    return False


def _handle_insert_italian_multifret(
    state: EditorState,
    key: int,
    style: str,
) -> bool:
    if not state.insert_prefix.startswith(","):
        return False
    state.insert_prefix = state.insert_prefix or ","
    if style != "italian" or state.settings.get("italianmultifret", "on") != "on":
        clear_insert_transient(state)
        return False
    min_input_byte = 0
    max_input_byte = 255
    if key < min_input_byte or key > max_input_byte:
        clear_insert_transient(state)
        return False
    ch = chr(key)
    if not ch.isdigit():
        clear_insert_transient(state)
        return False
    state.insert_prefix += ch
    digits = state.insert_prefix[1:]
    min_multifret_digits = 2
    if len(digits) >= min_multifret_digits:
        clear_insert_transient(state)
        _enter_fret(state, string_index(state, state.cursor_string), int(digits))
    return True


def _handle_insert_char(state: EditorState, key: int, style: str) -> bool:
    if ord(" ") <= key <= ord("~"):
        ch = chr(key).lower()
        valid = is_french_fret(ch) if style == "french" else is_italian_fret(ch)
        fret = french_to_fret(ch) if style == "french" else italian_to_fret(ch)
        if valid and fret is not None:
            _enter_fret(state, string_index(state, state.cursor_string), fret)
        else:
            state.message = "Invalid fret for current style"
        return True
    return False


def _delete_at_cursor(state: EditorState) -> bool:
    _commit_pending_insert_edit(state)
    return delete_at_cursor(state, string_index(state, state.cursor_string))


def _handle_insert_clear(state: EditorState) -> bool:
    _delete_at_cursor(state)
    return True


def _handle_insert_backspace(state: EditorState) -> bool:
    _delete_at_cursor(state)
    move_left(state)
    return True


def _handle_insert_delete(state: EditorState) -> bool:
    # A removed event pulls the next one under the cursor, so only step past a kept one.
    if not _delete_at_cursor(state):
        move_right(state)
    return True


def _handle_insert_barline(state: EditorState) -> bool:
    _commit_pending_insert_edit(state)
    from oud.editor.commands.dispatch import set_barline  # noqa: PLC0415

    set_barline(state, "thin")
    return True


def _handle_insert_escape(state: EditorState) -> bool:
    _commit_pending_insert_edit(state)
    exit_insert_mode(state)
    return True


def _handle_insert_horizontal(state: EditorState, motion: Callable[[EditorState], None]) -> bool:
    _commit_pending_insert_edit(state)
    motion(state)
    return True


def _handle_insert_vertical(state: EditorState, delta: int) -> bool:
    _commit_pending_insert_edit(state)
    apply_motion_target(state, target_step_display_row(state, delta))
    return True


def _handle_insert_prefix(state: EditorState, key: int) -> bool:
    try:
        state.insert_prefix = chr(key)
    except ValueError:
        clear_insert_transient(state)
    return True


def _dispatch_insert_content(state: EditorState, key: int) -> None:
    style = state.settings.get("style", "french")
    for handler in (
        _handle_insert_bass_slash,
        _handle_insert_italian_multifret,
        _handle_insert_duration_key,
        _handle_insert_char,
    ):
        if handler(state, key, style):
            return


InsertHandler = Callable[[EditorState, int], bool]
_INSERT_HANDLERS: Mapping[Action, InsertHandler] = MappingProxyType(
    {
        Action.QUIT: lambda state, _key: quit_editor(state),
        Action.INSERT_EXIT: lambda state, _key: _handle_insert_escape(state),
        Action.INSERT_REST: lambda state, _key: _handle_insert_rest(state),
        Action.INSERT_CLEAR: lambda state, _key: _handle_insert_clear(state),
        Action.INSERT_BACKSPACE: lambda state, _key: _handle_insert_backspace(state),
        Action.INSERT_DELETE: lambda state, _key: _handle_insert_delete(state),
        Action.INSERT_BARLINE: lambda state, _key: _handle_insert_barline(state),
        Action.INSERT_DOT: lambda state, _key: _handle_insert_dot(state),
        Action.INSERT_PREFIX: _handle_insert_prefix,
        Action.INSERT_LEFT: lambda state, _key: _handle_insert_horizontal(state, move_left),
        Action.INSERT_RIGHT: lambda state, _key: _handle_insert_horizontal(state, move_right),
        Action.INSERT_UP: lambda state, _key: _handle_insert_vertical(state, -1),
        Action.INSERT_DOWN: lambda state, _key: _handle_insert_vertical(state, 1),
    },
)


def handle_insert(state: EditorState, key: int) -> bool:
    """Dispatch table keys first; every other key is fret, duration or prefix content."""
    action = keymap_for(state, Mode.INSERT).lookup((key,))
    if action is not None:
        return _INSERT_HANDLERS[action](state, key)
    _dispatch_insert_content(state, key)
    return True
