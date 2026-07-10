from __future__ import annotations

import copy
from collections.abc import Callable

from oud.editor.controller_utils import cursor_key, string_index
from oud.editor.edit_ops import (
    apply_duration,
    apply_override,
    clear_cell_note,
    record_action,
    undo_group,
)
from oud.editor.insert_session import (
    clear_insert_transient,
    exit_insert_mode,
    finish_replace_once,
)
from oud.editor.keymap import insert_bindings, italian_duration_digits, movement_keys
from oud.editor.messages import UNSAVED_QUIT
from oud.editor.midi_control import stop_midi
from oud.editor.motions import (
    apply_motion_target,
    target_snap_previous_time_slot_if_needed,
    target_snap_to_chord_slot,
    target_step_display_row,
)
from oud.editor.navigation import move_left, move_right
from oud.editor.ops import (
    chord_index_at_col,
    duration_value,
    french_to_fret,
    is_french_fret,
    is_italian_fret,
)
from oud.editor.rhythm import advance_if_overflow, cell_has_duration
from oud.editor.state import EditorState, UndoAction
from oud.petrucci.render_utils import (
    chord_slot_positions,
    format_fret,
    note_type_to_denom,
)


def _column_has_event(state: EditorState, bar_index: int, col: int) -> bool:
    if col < 0:
        return False
    for s_idx in range(state.piece.strings):
        key = (bar_index, s_idx, col)
        if key in state.overrides or key in state.durations:
            return True
    return False


def _commit_pending_insert_edit(state: EditorState) -> None:
    """Cancel transient insert prefixes before movement/command transitions."""
    if state.insert_prefix:
        clear_insert_transient(state)


def _replace_mode_active(state: EditorState) -> bool:
    return state.mode == "replace"


def _replace_target_exists(state: EditorState) -> bool:
    bar = state.cursor_bar
    col = state.cursor_col
    if _column_has_event(state, bar, col):
        return True
    if 0 <= bar < len(state.piece.bars):
        bar_obj = state.piece.bars[bar]
        if bar_obj.chords:
            return chord_index_at_col(bar_obj, state.bar_width, col) is not None
    return False


def _ensure_replace_target(state: EditorState) -> bool:
    if not _replace_mode_active(state):
        return True
    if _replace_target_exists(state):
        return True
    state.message = "No note to replace"
    return False


def _snap_to_previous_time_slot_if_needed(state: EditorState) -> None:
    """Align to previous onset when layering notes on another string."""
    apply_motion_target(state, target_snap_previous_time_slot_if_needed(state))


def _snap_to_previous_time_slot(state: EditorState) -> bool:
    before = (state.cursor_bar, state.cursor_col)
    _snap_to_previous_time_slot_if_needed(state)
    return (state.cursor_bar, state.cursor_col) != before


def _flatten_chords_to_grid(state: EditorState, bar_index: int) -> None:
    if bar_index < 0 or bar_index >= len(state.piece.bars):
        return
    bar = state.piece.bars[bar_index]
    if not bar.chords:
        return
    style = state.settings.get("style", "french")
    french_c = state.settings.get("frenchc", "normal")
    positions = chord_slot_positions(bar, state.bar_width, default_duration=4)
    prev_chords = copy.deepcopy(bar.chords)
    prev_notes = copy.deepcopy(bar.notes)
    for chord, (col, _denom, _dot) in zip(bar.chords, positions, strict=False):
        for note in chord.notes:
            s_idx = note.string - 1
            if s_idx < 0 or s_idx >= state.piece.strings:
                continue
            key = (bar_index, s_idx, col)
            apply_override(
                state,
                key,
                format_fret(
                    style,
                    note.fret,
                    french_c=french_c,
                ),
            )
        denom = note_type_to_denom(chord.note_type) or 4
        apply_duration(state, (bar_index, 0, col), denom)
        if chord.dotted:
            prev_dotted = (bar_index, col) in state.dotted
            record_action(
                state,
                UndoAction(
                    kind="dotted",
                    data={"key": (bar_index, col), "prev": prev_dotted, "new": True},
                ),
            )
            state.dotted.add((bar_index, col))
    bar.chords = []
    bar.notes = []
    record_action(
        state,
        UndoAction(
            kind="chords",
            data={
                "bar": bar_index,
                "prev": prev_chords,
                "new": [],
                "prev_notes": prev_notes,
                "new_notes": [],
            },
        ),
    )


def _snap_cursor_to_chord_slot(state: EditorState) -> None:
    apply_motion_target(state, target_snap_to_chord_slot(state))


def _advance_after_insert(state: EditorState) -> None:
    if finish_replace_once(state):
        return
    if _replace_mode_active(state):
        return
    steps = 2 if state.settings.get("grid") == "on" else 1
    for _ in range(steps):
        move_right(state)


def _apply_duration_key(state: EditorState, dur: int) -> bool:
    if not _ensure_replace_target(state):
        return True
    with undo_group(state, label="insert-duration"):
        snapped_previous = _snap_to_previous_time_slot(state)
        state.current_duration = dur
        advance_if_overflow(state, dur, string_index(state, state.cursor_string))
        if not snapped_previous:
            _snap_cursor_to_chord_slot(state)
        if 0 <= state.cursor_bar < len(state.piece.bars):
            _flatten_chords_to_grid(state, state.cursor_bar)
        apply_duration(state, cursor_key(state), dur)
    state.message = f"Duration {dur}"
    return True


def _handle_insert_dot(state: EditorState) -> bool:
    if not _ensure_replace_target(state):
        return True
    with undo_group(state, label="insert-dot"):
        bar_col = (state.cursor_bar, state.cursor_col)
        _snap_cursor_to_chord_slot(state)
        bar_col = (state.cursor_bar, state.cursor_col)
        if 0 <= state.cursor_bar < len(state.piece.bars):
            _flatten_chords_to_grid(state, state.cursor_bar)
        if bar_col in state.dotted:
            record_action(
                state,
                UndoAction(
                    kind="dotted",
                    data={"key": bar_col, "prev": True, "new": False},
                ),
            )
            state.dotted.discard(bar_col)
            state.message = "Dot off"
        else:
            record_action(
                state,
                UndoAction(kind="dotted", data={"key": bar_col, "prev": False, "new": True}),
            )
            state.dotted.add(bar_col)
            state.message = "Dot on"
        state.modified = True
    return True


def _handle_insert_rest(state: EditorState) -> bool:
    if not _ensure_replace_target(state):
        return True
    with undo_group(state, label="insert-rest"):
        advance_if_overflow(
            state,
            state.current_duration,
            string_index(state, state.cursor_string),
        )
        _snap_cursor_to_chord_slot(state)
        if 0 <= state.cursor_bar < len(state.piece.bars):
            _flatten_chords_to_grid(state, state.cursor_bar)
        apply_override(state, cursor_key(state), "r")
        if not cell_has_duration(
            state,
            state.cursor_bar,
            string_index(state, state.cursor_string),
            state.cursor_col,
        ):
            apply_duration(state, cursor_key(state), state.current_duration)
    _advance_after_insert(state)
    return True


def _handle_insert_note(state: EditorState, ch: str) -> bool:
    if not _ensure_replace_target(state):
        return True
    with undo_group(state, label="insert-note"):
        advance_if_overflow(
            state,
            state.current_duration,
            string_index(state, state.cursor_string),
        )
        _snap_cursor_to_chord_slot(state)
        if 0 <= state.cursor_bar < len(state.piece.bars):
            _flatten_chords_to_grid(state, state.cursor_bar)
        bar = state.cursor_bar
        string = string_index(state, state.cursor_string)
        apply_override(state, cursor_key(state), ch)
        if not cell_has_duration(state, bar, string, state.cursor_col):
            apply_duration(state, cursor_key(state), state.current_duration)
    return True


def _handle_insert_fret_value(state: EditorState, fret: int) -> bool:
    if not _ensure_replace_target(state):
        return True
    with undo_group(state, label="insert-fret"):
        advance_if_overflow(
            state,
            state.current_duration,
            string_index(state, state.cursor_string),
        )
        _snap_cursor_to_chord_slot(state)
        if 0 <= state.cursor_bar < len(state.piece.bars):
            _flatten_chords_to_grid(state, state.cursor_bar)
        bar = state.cursor_bar
        string = string_index(state, state.cursor_string)
        text = str(fret)
        for offset, ch in enumerate(text[:2]):
            col = state.cursor_col + offset
            if col >= state.bar_width:
                break
            apply_override(state, (bar, string, col), ch)
        if not cell_has_duration(state, bar, string, state.cursor_col):
            apply_duration(state, cursor_key(state), state.current_duration)
    return True


def _handle_insert_bass_slash(  # noqa: PLR0911
    state: EditorState,
    key: int,
    style: str,
) -> bool:
    if style != "french":
        return False
    if state.insert_prefix and all(ch == "/" for ch in state.insert_prefix):
        if key == ord("/"):
            state.insert_prefix += "/"
            return True
        if 32 <= key <= 126:
            ch = chr(key).lower()
            fret = french_to_fret(ch)
            if fret is None:
                state.insert_prefix = ""
                return False
            target = 6 + (len(state.insert_prefix) - 1)
            if target >= state.piece.strings:
                state.message = "Bass string not available"
                state.insert_prefix = ""
                return True
            with undo_group(state, label="insert-bass-note"):
                advance_if_overflow(state, state.current_duration, target)
                _snap_cursor_to_chord_slot(state)
                if 0 <= state.cursor_bar < len(state.piece.bars):
                    _flatten_chords_to_grid(state, state.cursor_bar)
                bar = state.cursor_bar
                col = state.cursor_col
                apply_override(state, (bar, target, col), ch)
                if not cell_has_duration(state, bar, target, col):
                    apply_duration(state, (bar, target, col), state.current_duration)
            clear_insert_transient(state)
            _advance_after_insert(state)
            return True
        clear_insert_transient(state)
        return False
    if key == ord("/"):
        state.insert_prefix = "/"
        return True
    return False


def _handle_insert_duration_key(state: EditorState, key: int, style: str) -> bool:
    if state.insert_prefix == ";":
        state.insert_prefix = ""
        if key in italian_duration_digits() and style == "italian":
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
    if key < 0 or key > 255:
        clear_insert_transient(state)
        return False
    ch = chr(key)
    if not ch.isdigit():
        clear_insert_transient(state)
        return False
    state.insert_prefix += ch
    digits = state.insert_prefix[1:]
    if len(digits) >= 2:
        fret = int(digits)
        if _handle_insert_fret_value(state, fret):
            _advance_after_insert(state)
        clear_insert_transient(state)
    return True


def _handle_insert_char(state: EditorState, key: int, style: str) -> bool:
    if key == ord("r"):
        return _handle_insert_rest(state)
    if 32 <= key <= 126:
        ch = chr(key).lower()
        valid = is_french_fret(ch) if style == "french" else is_italian_fret(ch)
        if valid:
            _handle_insert_note(state, ch)
            _advance_after_insert(state)
        else:
            state.message = "Invalid fret for current style"
        return True
    return False


def handle_insert(state: EditorState, key: int) -> bool:  # noqa: C901, PLR0911
    bindings = insert_bindings(state)
    keycodes = state.keycodes
    if key == 27:
        exit_insert_mode(state)
        return True

    def dispatch_actions(actions: list[tuple[tuple[int, ...], Callable[[], bool]]]) -> bool | None:
        for keys, handler in actions:
            if key in keys:
                return handler()
        return None

    def _handle_clear() -> bool:
        _commit_pending_insert_edit(state)
        if 0 <= state.cursor_bar < len(state.piece.bars):
            _flatten_chords_to_grid(state, state.cursor_bar)
        clear_cell_note(
            state,
            state.cursor_bar,
            string_index(state, state.cursor_string),
            state.cursor_col,
        )
        return True

    def _handle_backspace() -> bool:
        _commit_pending_insert_edit(state)
        if 0 <= state.cursor_bar < len(state.piece.bars):
            _flatten_chords_to_grid(state, state.cursor_bar)
        clear_cell_note(
            state,
            state.cursor_bar,
            string_index(state, state.cursor_string),
            state.cursor_col,
        )
        move_left(state)
        return True

    def _handle_delete() -> bool:
        _commit_pending_insert_edit(state)
        if 0 <= state.cursor_bar < len(state.piece.bars):
            _flatten_chords_to_grid(state, state.cursor_bar)
        clear_cell_note(
            state,
            state.cursor_bar,
            string_index(state, state.cursor_string),
            state.cursor_col,
        )
        move_right(state)
        return True

    def _handle_barline() -> bool:
        _commit_pending_insert_edit(state)
        from oud.editor.command_ops import set_barline  # noqa: PLC0415

        set_barline(state, "thin")
        return True

    def _handle_escape() -> bool:
        _commit_pending_insert_edit(state)
        exit_insert_mode(state)
        return True

    def _handle_quit() -> bool:
        _commit_pending_insert_edit(state)
        if state.modified and not state.pending_quit:
            state.pending_quit = True
            state.message = UNSAVED_QUIT
            return True
        stop_midi(state)
        return False

    def _handle_left() -> bool:
        _commit_pending_insert_edit(state)
        move_left(state)
        return True

    def _handle_right() -> bool:
        _commit_pending_insert_edit(state)
        move_right(state)
        return True

    def _handle_up() -> bool:
        _commit_pending_insert_edit(state)
        apply_motion_target(state, target_step_display_row(state, -1))
        return True

    def _handle_down() -> bool:
        _commit_pending_insert_edit(state)
        apply_motion_target(state, target_step_display_row(state, 1))
        return True

    def _handle_prefix() -> bool:
        try:
            state.insert_prefix = chr(key)
        except ValueError:
            clear_insert_transient(state)
        return True

    handled = dispatch_actions(
        [
            (bindings.clear, _handle_clear),
            ((keycodes.backspace, 127, 8), _handle_backspace),
            ((keycodes.dc,), _handle_delete),
            (bindings.barline, _handle_barline),
            (bindings.dot, lambda: _handle_insert_dot(state)),
            (bindings.escape, _handle_escape),
            (bindings.quit, _handle_quit),
            ((keycodes.left,), _handle_left),
            ((keycodes.right,), _handle_right),
            ((keycodes.up,), _handle_up),
            ((keycodes.down,), _handle_down),
            (bindings.prefix, _handle_prefix),
        ],
    )
    if handled is not None:
        return handled

    if _replace_mode_active(state):
        move = movement_keys(state, include_arrows=False)
        if key in move.left:
            _handle_left()
            return True
        if key in move.right:
            _handle_right()
            return True
        if key in move.up:
            _handle_up()
            return True
        if key in move.down:
            _handle_down()
            return True

    style = state.settings.get("style", "french")
    if _handle_insert_bass_slash(state, key, style):
        return True
    if _handle_insert_italian_multifret(state, key, style):
        return True
    if _handle_insert_duration_key(state, key, style):
        return True
    if _handle_insert_char(state, key, style):
        return True
    return True
