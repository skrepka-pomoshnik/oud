from __future__ import annotations

from collections.abc import Callable

from oud.editor.bar_ops import delete_bar
from oud.editor.controller_utils import consume_count, string_index
from oud.editor.edit_ops import clear_cell
from oud.editor.find_ops import perform_find, repeat_find
from oud.editor.keymap import (
    NormalActionBindings,
    count_bindings,
    help_action_bindings,
    movement_keys,
    normal_action_bindings,
    normal_bindings,
    pending_bindings,
)
from oud.editor.layout import bars_per_line
from oud.editor.messages import UNSAVED_QUIT
from oud.editor.midi_control import start_midi, stop_midi
from oud.editor.navigation import move_left_note, move_right_note
from oud.editor.search_ops import (
    jump_mark,
    jump_match,
    repeat_word_search,
    search_word_under_cursor,
    set_mark,
)
from oud.editor.state import EditorState


def handle_normal(state: EditorState, key: int) -> bool:  # noqa: PLR0911, PLR0912, C901
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

    if state.pending_mark:
        if 32 <= key <= 126:
            name = chr(key)
            if state.pending_mark == "set":
                set_mark(state, name)
            else:
                jump_mark(state, name)
        state.pending_mark = ""
        return True

    if state.pending_find:
        if 32 <= key <= 126:
            find_char = chr(key)
            count = consume_count(state)
            perform_find(state, state.pending_find, find_char, count=count)
        state.pending_find = ""
        return True

    def handle_pending_key() -> bool:  # noqa: PLR0911
        if not state.pending_key:
            return False
        if state.pending_key == "g" and key in pending_keys.gg:
            state.cursor_bar = 0
            state.cursor_col = 0
            state.pending_key = ""
            return True
        if state.pending_key == "g" and key in pending_keys.gj:
            from oud.core.tuning_utils import parse_bass_strings, tuning_count  # noqa: PLC0415

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
                move_right_note(state)
        state.pending_key = ""
        return True
    if key in action_keys.pending:
        state.pending_key = chr(key)
        return True
    if key in action_keys.word_search_forward:
        search_word_under_cursor(state, 1)
        return True
    if key in action_keys.word_search_backward:
        search_word_under_cursor(state, -1)
        return True
    if key in action_keys.word_search_next:
        repeat_word_search(state, reverse=False)
        return True
    if key in action_keys.word_search_prev:
        repeat_word_search(state, reverse=True)
        return True
    if key in action_keys.match_jump:
        jump_match(state)
        return True
    if key in action_keys.mark_set:
        state.pending_mark = "set"
        return True
    if key in action_keys.mark_jump_line or key in action_keys.mark_jump_exact:
        state.pending_mark = "jump"
        return True
    if key in action_keys.find_forward:
        state.pending_find = "f"
        return True
    if key in action_keys.find_backward:
        state.pending_find = "F"
        return True
    if key in action_keys.till_forward:
        state.pending_find = "t"
        return True
    if key in action_keys.till_backward:
        state.pending_find = "T"
        return True
    if key in action_keys.find_repeat:
        count = consume_count(state)
        repeat_find(state, reverse=False, count=count)
        return True
    if key in action_keys.find_repeat_reverse:
        count = consume_count(state)
        repeat_find(state, reverse=True, count=count)
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
            move_left_note(state)
        return True
    if key in keys.right:
        for _ in range(count):
            move_right_note(state)
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
