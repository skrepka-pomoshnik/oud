from __future__ import annotations

import copy
from collections.abc import Callable

from oud.core.render_utils import chord_positions, format_fret, note_type_to_denom
from oud.core.tuning_utils import parse_bass_strings, tuning_count
from oud.editor.bar_ops import delete_bar
from oud.editor.controller_utils import consume_count, cursor_key, string_index
from oud.editor.edit_ops import (
    apply_duration,
    apply_override,
    clear_cell,
    clear_cell_note,
    record_action,
)
from oud.editor.keymap import (
    NormalActionBindings,
    count_bindings,
    help_action_bindings,
    insert_bindings,
    italian_duration_digits,
    movement_keys,
    normal_action_bindings,
    normal_bindings,
    pending_bindings,
)
from oud.editor.layout import bars_per_line
from oud.editor.messages import UNSAVED_QUIT
from oud.editor.midi_control import start_midi, stop_midi
from oud.editor.navigation import move_left, move_right
from oud.editor.ops import (
    chord_index_at_col,
    denom_to_note_type,
    duration_value,
    french_to_fret,
    is_french_fret,
    is_italian_fret,
    italian_to_fret,
    set_chord_note,
)
from oud.editor.rhythm import advance_if_overflow, column_denom, column_has_duration
from oud.editor.state import EditorState, UndoAction


def _column_has_notes(state: EditorState, bar_index: int, col: int) -> bool:
    return any(
        (bar_index, s_idx, col) in state.overrides
        for s_idx in range(state.piece.strings)
    )


def _flatten_chords_to_grid(state: EditorState, bar_index: int) -> None:
    if bar_index < 0 or bar_index >= len(state.piece.bars):
        return
    bar = state.piece.bars[bar_index]
    if not bar.chords:
        return
    style = state.settings.get("style", "french")
    french_c = state.settings.get("frenchc", "normal")
    french_e = state.settings.get("frenche", "normal")
    positions = chord_positions(bar, state.bar_width, default_duration=4)
    for chord, (col, _denom, _dot) in zip(bar.chords, positions, strict=False):
        for note in chord.notes:
            s_idx = note.string - 1
            if s_idx < 0 or s_idx >= state.piece.strings:
                continue
            key = (bar_index, s_idx, col)
            state.overrides[key] = format_fret(
                style,
                note.fret,
                french_c=french_c,
                french_e=french_e,
            )
        denom = note_type_to_denom(chord.note_type) or 4
        state.durations[(bar_index, 0, col)] = denom
        if chord.dotted:
            state.dotted.add((bar_index, col))
    bar.chords = []
    bar.notes = []
    state.modified = True


def _apply_duration_key(state: EditorState, dur: int) -> bool:
    state.current_duration = dur
    advance_if_overflow(state, dur, string_index(state, state.cursor_string))
    if 0 <= state.cursor_bar < len(state.piece.bars):
        _flatten_chords_to_grid(state, state.cursor_bar)
    bar = state.cursor_bar
    if 0 <= bar < len(state.piece.bars) and state.piece.bars[bar].chords:
        bar_obj = state.piece.bars[bar]
        idx = chord_index_at_col(bar_obj, state.bar_width, state.cursor_col)
        note_type = denom_to_note_type(dur)
        if idx is not None and note_type is not None:
            prev_chords = copy.deepcopy(bar_obj.chords)
            bar_obj.chords[idx].note_type = note_type
            record_action(
                state,
                UndoAction(
                    kind="chords",
                    data={"bar": bar, "prev": prev_chords, "new": bar_obj.chords},
                ),
            )
            state.modified = True
        else:
            apply_duration(state, cursor_key(state), dur)
    else:
        apply_duration(state, cursor_key(state), dur)
    state.message = f"Duration {dur}"
    return True


def _handle_insert_dot(state: EditorState) -> bool:
    bar_col = (state.cursor_bar, state.cursor_col)
    if 0 <= state.cursor_bar < len(state.piece.bars):
        _flatten_chords_to_grid(state, state.cursor_bar)
    bar = state.cursor_bar
    if 0 <= bar < len(state.piece.bars) and state.piece.bars[bar].chords:
        bar_obj = state.piece.bars[bar]
        idx = chord_index_at_col(bar_obj, state.bar_width, state.cursor_col)
        if idx is not None:
            prev_chords = copy.deepcopy(bar_obj.chords)
            bar_obj.chords[idx].dotted = not bar_obj.chords[idx].dotted
            record_action(
                state,
                UndoAction(
                    kind="chords",
                    data={"bar": bar, "prev": prev_chords, "new": bar_obj.chords},
                ),
            )
            state.modified = True
            state.message = "Dot on" if bar_obj.chords[idx].dotted else "Dot off"
            return True
    if bar_col in state.dotted:
        record_action(
            state,
            UndoAction(kind="dotted", data={"key": bar_col, "prev": True, "new": False}),
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
    advance_if_overflow(
        state,
        state.current_duration,
        string_index(state, state.cursor_string),
    )
    if 0 <= state.cursor_bar < len(state.piece.bars):
        _flatten_chords_to_grid(state, state.cursor_bar)
    apply_override(state, cursor_key(state), "r")
    if (
        not column_has_duration(state, state.cursor_bar, state.cursor_col)
        or (
            state.current_duration
            and column_denom(state, state.cursor_bar, state.cursor_col) != state.current_duration
        )
    ):
        apply_duration(state, cursor_key(state), state.current_duration)
    if state.replace_once:
        state.replace_once = False
        state.mode = "normal"
    else:
        steps = 2 if state.settings.get("grid") == "on" else 1
        for _ in range(steps):
            move_right(state)
    return True


def _handle_insert_note(state: EditorState, ch: str, style: str) -> bool:
    advance_if_overflow(
        state,
        column_denom(state, state.cursor_bar, state.cursor_col),
        string_index(state, state.cursor_string),
    )
    if 0 <= state.cursor_bar < len(state.piece.bars):
        _flatten_chords_to_grid(state, state.cursor_bar)
    bar = state.cursor_bar
    string = string_index(state, state.cursor_string)
    fret = french_to_fret(ch) if style == "french" else italian_to_fret(ch)
    if 0 <= bar < len(state.piece.bars) and state.piece.bars[bar].chords:
        if fret is not None:
            prev_chords = copy.deepcopy(state.piece.bars[bar].chords)
            if state.current_duration:
                idx = chord_index_at_col(
                    state.piece.bars[bar], state.bar_width, state.cursor_col,
                )
                note_type = denom_to_note_type(state.current_duration)
                if idx is not None and note_type is not None:
                    state.piece.bars[bar].chords[idx].note_type = note_type
            if set_chord_note(
                state.piece.bars[bar],
                state.bar_width,
                state.cursor_col,
                string + 1,
                fret,
            ):
                new_chords = copy.deepcopy(state.piece.bars[bar].chords)
                record_action(
                    state,
                    UndoAction(
                        kind="chords",
                        data={"bar": bar, "prev": prev_chords, "new": new_chords},
                    ),
                )
                state.modified = True
            else:
                apply_override(state, cursor_key(state), ch)
        else:
            apply_override(state, cursor_key(state), ch)
    else:
        apply_override(state, cursor_key(state), ch)
    if (
        not column_has_duration(state, bar, state.cursor_col)
        or (
            state.current_duration
            and column_denom(state, bar, state.cursor_col) != state.current_duration
        )
    ):
        apply_duration(state, cursor_key(state), state.current_duration)
    return True


def _handle_insert_fret_value(state: EditorState, fret: int) -> bool:
    advance_if_overflow(
        state,
        column_denom(state, state.cursor_bar, state.cursor_col),
        string_index(state, state.cursor_string),
    )
    if 0 <= state.cursor_bar < len(state.piece.bars):
        _flatten_chords_to_grid(state, state.cursor_bar)
    bar = state.cursor_bar
    string = string_index(state, state.cursor_string)
    if 0 <= bar < len(state.piece.bars) and state.piece.bars[bar].chords:
        prev_chords = copy.deepcopy(state.piece.bars[bar].chords)
        if state.current_duration:
            idx = chord_index_at_col(
                state.piece.bars[bar], state.bar_width, state.cursor_col,
            )
            note_type = denom_to_note_type(state.current_duration)
            if idx is not None and note_type is not None:
                state.piece.bars[bar].chords[idx].note_type = note_type
        if set_chord_note(
            state.piece.bars[bar],
            state.bar_width,
            state.cursor_col,
            string + 1,
            fret,
        ):
            new_chords = copy.deepcopy(state.piece.bars[bar].chords)
            record_action(
                state,
                UndoAction(
                    kind="chords",
                    data={"bar": bar, "prev": prev_chords, "new": new_chords},
                ),
            )
            state.modified = True
    else:
        text = str(fret)
        for offset, ch in enumerate(text[:2]):
            col = state.cursor_col + offset
            if col >= state.bar_width:
                break
            apply_override(state, (bar, string, col), ch)
    if (
        not column_has_duration(state, bar, state.cursor_col)
        or (
            state.current_duration
            and column_denom(state, bar, state.cursor_col) != state.current_duration
        )
    ):
        apply_duration(state, cursor_key(state), state.current_duration)
    return True


def _handle_insert_bass_slash(  # noqa: C901, PLR0911, PLR0912
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
            bar = state.cursor_bar
            col = state.cursor_col
            if 0 <= bar < len(state.piece.bars) and state.piece.bars[bar].chords:
                prev_chords = copy.deepcopy(state.piece.bars[bar].chords)
                if state.current_duration:
                    idx = chord_index_at_col(
                        state.piece.bars[bar], state.bar_width, state.cursor_col,
                    )
                    note_type = denom_to_note_type(state.current_duration)
                    if idx is not None and note_type is not None:
                        state.piece.bars[bar].chords[idx].note_type = note_type
                if set_chord_note(
                    state.piece.bars[bar],
                    state.bar_width,
                    col,
                    target + 1,
                    fret,
                ):
                    new_chords = copy.deepcopy(state.piece.bars[bar].chords)
                    record_action(
                        state,
                        UndoAction(
                            kind="chords",
                            data={"bar": bar, "prev": prev_chords, "new": new_chords},
                        ),
                    )
                    state.modified = True
                else:
                    apply_override(state, (bar, target, col), ch)
            else:
                apply_override(state, (bar, target, col), ch)
            if (
                not column_has_duration(state, bar, col)
                or (
                    state.current_duration
                    and column_denom(state, bar, col) != state.current_duration
                )
            ):
                apply_duration(state, (bar, target, col), state.current_duration)
            state.insert_prefix = ""
            if state.replace_once:
                state.replace_once = False
                state.mode = "normal"
            else:
                steps = 2 if state.settings.get("grid") == "on" else 1
                for _ in range(steps):
                    move_right(state)
            return True
        state.insert_prefix = ""
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


def _handle_insert_italian_multifret(state: EditorState, key: int, style: str) -> bool:
    if not state.insert_prefix.startswith(","):
        return False
    state.insert_prefix = state.insert_prefix or ","
    if style != "italian" or state.settings.get("italianmultifret", "on") != "on":
        state.insert_prefix = ""
        return False
    if key < 0 or key > 255:
        state.insert_prefix = ""
        return False
    ch = chr(key)
    if not ch.isdigit():
        state.insert_prefix = ""
        return False
    state.insert_prefix += ch
    digits = state.insert_prefix[1:]
    if len(digits) >= 2:
        fret = int(digits)
        if _handle_insert_fret_value(state, fret):
            if state.replace_once:
                state.replace_once = False
                state.mode = "normal"
            else:
                steps = 2 if state.settings.get("grid") == "on" else 1
                for _ in range(steps):
                    move_right(state)
        state.insert_prefix = ""
    return True


def _handle_insert_char(state: EditorState, key: int, style: str) -> bool:
    if key == ord("r"):
        return _handle_insert_rest(state)
    if 32 <= key <= 126:
        ch = chr(key).lower()
        valid = is_french_fret(ch) if style == "french" else is_italian_fret(ch)
        if valid:
            _handle_insert_note(state, ch, style)
            if state.replace_once:
                state.replace_once = False
                state.mode = "normal"
            else:
                steps = 2 if state.settings.get("grid") == "on" else 1
                for _ in range(steps):
                    move_right(state)
        else:
            state.message = "Invalid fret for current style"
        return True
    return False


def handle_insert(state: EditorState, key: int) -> bool:  # noqa: C901, PLR0911
    bindings = insert_bindings(state)
    keycodes = state.keycodes
    if key == 27:
        state.mode = "normal"
        state.replace_once = False
        state.insert_prefix = ""
        return True
    def dispatch_actions(actions: list[tuple[tuple[int, ...], Callable[[], bool]]]) -> bool:
        for keys, handler in actions:
            if key in keys:
                return handler()
        return False

    def _handle_clear() -> bool:
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
        from oud.editor.command_ops import set_barline  # noqa: PLC0415

        set_barline(state, "thin")
        return True

    def _handle_escape() -> bool:
        state.mode = "normal"
        state.replace_once = False
        return True

    def _handle_quit() -> bool:
        if state.modified and not state.pending_quit:
            state.pending_quit = True
            state.message = UNSAVED_QUIT
            return True
        stop_midi(state)
        return False

    def _handle_left() -> bool:
        move_left(state)
        return True

    def _handle_right() -> bool:
        move_right(state)
        return True

    def _handle_up() -> bool:
        state.cursor_string -= 1
        return True

    def _handle_down() -> bool:
        state.cursor_string += 1
        return True

    def _handle_prefix() -> bool:
        try:
            state.insert_prefix = chr(key)
        except ValueError:
            state.insert_prefix = ""
        return True

    if dispatch_actions(
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
    ):
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


def handle_normal(state: EditorState, key: int) -> bool:  # noqa: PLR0911, C901
    bindings = normal_bindings(state)
    action_keys = normal_action_bindings(state)
    count_keys = count_bindings()
    help_keys = help_action_bindings()
    pending_keys = pending_bindings()
    def dispatch_actions(
        actions: list[tuple[tuple[int, ...], Callable[[], None]]],
        *,
        clear_count: bool = True,
        clear_pending: bool = True,
    ) -> bool:
        for keys, handler in actions:
            if key in keys:
                handler()
                if clear_count:
                    state.count_prefix = ""
                if clear_pending:
                    state.pending_key = ""
                return True
        return False
    def handle_pending_key() -> bool:  # noqa: PLR0911
        if not state.pending_key:
            return False
        if state.pending_key == "g" and key in pending_keys.gg:
            state.cursor_bar = 0
            state.cursor_col = 0
            state.pending_key = ""
            return True
        if state.pending_key == "g" and key in pending_keys.gj:
            tuning = state.settings.get("tuning", "")
            base = tuning_count(tuning) if tuning else state.piece.strings
            bass_list = parse_bass_strings(state.settings.get("bassstrings", ""))
            if not bass_list:
                state.message = "No bass strings configured"
                state.pending_key = ""
                return True
            added = max(0, state.piece.strings - base)
            if added >= len(bass_list):
                state.message = "No more bass strings (set bassstrings)"
                state.pending_key = ""
                return True
            token = bass_list[added]
            state.piece.strings += 1
            state.cursor_string = state.piece.strings - 1
            state.settings["strings"] = str(state.piece.strings)
            if tuning:
                state.settings["tuning"] = tuning + token
            state.modified = True
            state.message = f"Bass string {token} added"
            state.pending_key = ""
            return True
        if state.pending_key == "g" and key in pending_keys.gp:
            from oud.editor.plugin_ops import enter_plugin_mode  # noqa: PLC0415

            enter_plugin_mode(state)
            state.pending_key = ""
            return True
        if state.pending_key == "d" and key in pending_keys.dd:
            from oud.editor.command_ops import yank_bar  # noqa: PLC0415

            yank_bar(state, state.cursor_bar)
            delete_bar(state, state.cursor_bar)
            state.cursor_bar = min(state.cursor_bar, len(state.piece.bars) - 1)
            state.cursor_col = 0
            state.message = "Bar deleted"
            state.pending_key = ""
            return True
        if state.pending_key == "y" and key in pending_keys.yy:
            from oud.editor.command_ops import yank_bar  # noqa: PLC0415

            yank_bar(state, state.cursor_bar)
            state.message = "Bar yanked"
            state.pending_key = ""
            return True
        state.pending_key = ""
        return True
    if key in count_keys.digits:
        digit = chr(key)
        if key == count_keys.zero and not state.count_prefix:
            state.cursor_col = 0
            return True
        state.count_prefix += digit
        return True
    if handle_pending_key():
        return True
    if key in bindings.quit:
        if state.modified and not state.pending_quit:
            state.pending_quit = True
            state.message = UNSAVED_QUIT
            return True
        stop_midi(state)
        return False
    if key in bindings.command:
        state.mode = "command"
        state.cmdline = ""
        return True
    def _handle_help() -> None:
        if key in help_keys.viewer:
            from oud.editor.command_ops import show_help  # noqa: PLC0415

            show_help(state)
        else:
            state.mode = "help"
            state.help_offset = 0

    def _handle_print() -> None:
        from oud.editor.command_ops import print_pdf  # noqa: PLC0415

        print_pdf(state)

    def _handle_play() -> None:
        if state.midi_proc is not None and state.midi_proc.poll() is None:
            stop_midi(state)
        else:
            start_midi(state)

    def _handle_search() -> None:
        state.mode = "search"
        state.searchline = ""

    def _handle_insert() -> None:
        state.mode = "insert"

    def _handle_info() -> None:
        state.mode = "info"
        state.info_offset = 0

    def _handle_replace() -> None:
        state.mode = "insert"
        state.replace_once = True

    def _handle_bar_after() -> None:
        from oud.editor.command_ops import cmd_bar  # noqa: PLC0415

        cmd_bar(state, "after")

    def _handle_bar_before() -> None:
        from oud.editor.command_ops import cmd_bar  # noqa: PLC0415

        cmd_bar(state, "before")

    def _handle_bar_delete() -> None:
        from oud.editor.command_ops import cmd_bar  # noqa: PLC0415

        cmd_bar(state, "del")

    def _handle_undo() -> None:
        from oud.editor.undo_ops import undo  # noqa: PLC0415

        undo(state, config_path=state.config_path)

    def _handle_redo() -> None:
        from oud.editor.undo_ops import redo  # noqa: PLC0415

        redo(state, config_path=state.config_path)

    def _handle_row_first() -> None:
        from oud.editor.command_ops import row_first_note_col  # noqa: PLC0415

        state.cursor_col = row_first_note_col(state)

    def _handle_paste() -> None:
        from oud.editor.command_ops import paste_bar  # noqa: PLC0415

        paste_bar(state, state.cursor_bar + 1)

    if dispatch_actions(
        [
            (bindings.help, _handle_help),
            (bindings.print_pdf, _handle_print),
            (bindings.play, _handle_play),
            (bindings.search, _handle_search),
            (bindings.insert, _handle_insert),
            (bindings.info, _handle_info),
            (bindings.replace, _handle_replace),
            (bindings.bar_after, _handle_bar_after),
            (bindings.bar_before, _handle_bar_before),
            (bindings.bar_delete, _handle_bar_delete),
            (bindings.undo, _handle_undo),
            (bindings.redo, _handle_redo),
            (action_keys.row_first, _handle_row_first),
            (action_keys.paste, _handle_paste),
        ],
    ):
        return True
    if key in action_keys.delete_cell:
        count = consume_count(state)
        for _ in range(count):
            clear_cell(
                state,
                state.cursor_bar,
                string_index(state, state.cursor_string),
                state.cursor_col,
            )
            if count > 1:
                move_right(state)
        state.pending_key = ""
        return True
    if key in action_keys.pending:
        state.pending_key = chr(key)
        return True
    if _handle_normal_movement(state, key, action_keys):
        return True
    return True


def _handle_normal_movement(  # noqa: C901, PLR0911, PLR0912
    state: EditorState,
    key: int,
    action_keys: NormalActionBindings,
) -> bool:
    count = consume_count(state)
    keys = movement_keys(state, include_arrows=True)
    if key in keys.left:
        for _ in range(count):
            move_left(state)
        return True
    if key in keys.right:
        for _ in range(count):
            move_right(state)
        return True
    if key in keys.up:
        state.cursor_string -= count
        return True
    if key in keys.down:
        state.cursor_string += count
        return True
    if key in action_keys.page_up:
        per_line = bars_per_line(state, state.screen_width)
        state.cursor_bar = max(0, state.cursor_bar - per_line * count)
        state.cursor_col = 0
        return True
    if key in action_keys.page_down:
        per_line = bars_per_line(state, state.screen_width)
        state.cursor_bar = min(len(state.piece.bars) - 1, state.cursor_bar + per_line * count)
        state.cursor_col = 0
        return True
    if key in action_keys.bar_next:
        state.cursor_bar = min(len(state.piece.bars) - 1, state.cursor_bar + count)
        state.cursor_col = 0
        return True
    if key in action_keys.bar_prev:
        state.cursor_bar = max(0, state.cursor_bar - count)
        state.cursor_col = 0
        return True
    if key in action_keys.col_start:
        state.cursor_col = 0
        return True
    if key in action_keys.col_end:
        state.cursor_col = state.bar_width - 1
        return True
    if key in action_keys.jump_bottom:
        state.cursor_bar = max(0, len(state.piece.bars) - 1)
        state.cursor_col = 0
        return True
    return False
