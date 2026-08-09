from __future__ import annotations

from collections.abc import Callable

from oud.editor.commands.query.find import repeat_find
from oud.editor.commands.query.search import jump_match, repeat_word_search, search_word_under_cursor
from oud.editor.core.coordinates import consume_count, string_index
from oud.editor.core.feedback.messages import READ_ONLY_VIEWER, UNSAVED_QUIT
from oud.editor.core.input.keymap import help_action_bindings, normal_action_bindings, normal_bindings
from oud.editor.core.session import enter_insert_mode, enter_replace_mode, set_mode
from oud.editor.core.state import EditorState
from oud.editor.editing.primitives.edits import clear_cell, undo_group
from oud.editor.editing.visual import enter_visual_mode
from oud.editor.navigation.motions import CursorMotionTarget, apply_motion_target, target_move_right_note
from oud.editor.navigation.viewport import jump_viewport_section_page
from oud.editor.services.media.midi import start_midi, stop_midi

Action = Callable[[EditorState, int], None]


def handle_session_action(state: EditorState, key: int) -> bool | None:
    bindings = normal_bindings(state)
    if key in bindings.quit:
        if state.modified and not state.pending_quit:
            state.pending_quit = True
            state.message = UNSAVED_QUIT
            return True
        stop_midi(state)
        return False
    if key in bindings.command:
        set_mode(state, "command")
        state.cmdline = ""
        return True
    if key in (ord("v"), ord("V")):
        _enter_visual(state, linewise=key == ord("V"))
        return True
    return None


def handle_primary_action(state: EditorState, key: int) -> bool:
    bindings = normal_bindings(state)
    action_keys = normal_action_bindings(state)
    help_keys = help_action_bindings()
    actions: tuple[tuple[tuple[int, ...], Action], ...] = (
        (bindings.help, lambda s, k: _show_help(s, k, help_keys.viewer)),
        (bindings.print_pdf, _print_pdf),
        (bindings.play, _toggle_playback),
        (bindings.search, _start_search),
        (bindings.insert, _insert),
        (bindings.info, _show_info),
        (bindings.replace, _replace_once),
        ((ord("R"),), _replace_mode),
        (bindings.bar_after, lambda s, _k: _bar_action(s, "after")),
        (bindings.bar_before, lambda s, _k: _bar_action(s, "before")),
        (bindings.bar_delete, lambda s, _k: _bar_action(s, "del")),
        (bindings.undo, _undo),
        (bindings.redo, _redo),
        (action_keys.row_first, _row_first),
        (action_keys.paste, _paste),
        (action_keys.section_prev, lambda state, _key: _jump_section_page(state, -1)),
        (action_keys.section_next, lambda state, _key: _jump_section_page(state, 1)),
    )
    return _dispatch(state, key, actions)


def handle_delete_action(state: EditorState, key: int) -> bool:
    if key not in normal_action_bindings(state).delete_cell:
        return False
    if state.read_only:
        state.message = READ_ONLY_VIEWER
        return True
    count = consume_count(state)
    with undo_group(state, label="delete-cell-count"):
        for _ in range(count):
            clear_cell(state, state.cursor_bar, string_index(state, state.cursor_string), state.cursor_col)
            if count > 1 and not _move_after_delete(state):
                break
    state.pending_key = ""
    return True


def handle_search_action(state: EditorState, key: int) -> bool:
    for handler in (_handle_pending_prefix, _handle_word_search, _handle_mark_or_find_prefix, _handle_find_repeat):
        if handler(state, key):
            return True
    return False


def _dispatch(state: EditorState, key: int, actions: tuple[tuple[tuple[int, ...], Action], ...]) -> bool:
    for keys, action in actions:
        if key in keys:
            action(state, key)
            state.count_prefix = ""
            state.pending_key = ""
            return True
    return False


def _enter_visual(state: EditorState, *, linewise: bool) -> None:
    state.count_prefix = ""
    state.pending_key = ""
    state.visual_anchor = (state.cursor_bar, state.cursor_string, state.cursor_col)
    enter_visual_mode(state, linewise=linewise)


def _show_help(state: EditorState, key: int, viewer_keys: tuple[int, ...]) -> None:
    if key in viewer_keys:
        from oud.editor.commands.dispatch import show_help  # noqa: PLC0415

        show_help(state)
        return
    set_mode(state, "help")
    state.help_offset = 0


def _print_pdf(state: EditorState, _key: int) -> None:
    from oud.editor.commands.dispatch import print_pdf  # noqa: PLC0415

    print_pdf(state)


def _toggle_playback(state: EditorState, _key: int) -> None:
    if state.midi_proc is not None and state.midi_proc.poll() is None:
        stop_midi(state)
    else:
        start_midi(state)


def _start_search(state: EditorState, _key: int) -> None:
    set_mode(state, "search")
    state.searchline = ""


def _editable_action(state: EditorState, action: Callable[[], None]) -> None:
    if state.read_only:
        state.message = READ_ONLY_VIEWER
    else:
        action()


def _insert(state: EditorState, _key: int) -> None:
    _editable_action(state, lambda: enter_insert_mode(state))


def _show_info(state: EditorState, _key: int) -> None:
    set_mode(state, "info")
    state.info_offset = 0


def _replace_once(state: EditorState, _key: int) -> None:
    _editable_action(state, lambda: enter_insert_mode(state, replace_once=True))


def _replace_mode(state: EditorState, _key: int) -> None:
    _editable_action(state, lambda: enter_replace_mode(state))


def _bar_action(state: EditorState, action: str) -> None:
    def apply() -> None:
        from oud.editor.commands.dispatch import cmd_bar  # noqa: PLC0415

        cmd_bar(state, action)

    _editable_action(state, apply)


def _undo(state: EditorState, _key: int) -> None:
    def apply() -> None:
        from oud.editor.editing.primitives.undo import undo  # noqa: PLC0415

        undo(state, config_path=state.config_path)

    _editable_action(state, apply)


def _redo(state: EditorState, _key: int) -> None:
    def apply() -> None:
        from oud.editor.editing.primitives.undo import redo  # noqa: PLC0415

        redo(state, config_path=state.config_path)

    _editable_action(state, apply)


def _row_first(state: EditorState, _key: int) -> None:
    from oud.editor.commands.dispatch import row_first_note_col  # noqa: PLC0415

    apply_motion_target(state, CursorMotionTarget(state.cursor_bar, row_first_note_col(state)))


def _jump_section_page(state: EditorState, direction: int) -> None:
    jump_viewport_section_page(state, direction * consume_count(state))


def _paste(state: EditorState, _key: int) -> None:
    def apply() -> None:
        from oud.editor.commands.dispatch import paste_bar  # noqa: PLC0415

        paste_bar(state, state.cursor_bar + 1)

    _editable_action(state, apply)


def _move_after_delete(state: EditorState) -> bool:
    target = target_move_right_note(state)
    if target.append_bar:
        return False
    before = (state.cursor_bar, state.cursor_col, state.cursor_string)
    apply_motion_target(state, target)
    return (state.cursor_bar, state.cursor_col, state.cursor_string) != before


def _handle_pending_prefix(state: EditorState, key: int) -> bool:
    if key not in normal_action_bindings(state).pending:
        return False
    state.pending_key = chr(key)
    return True


def _handle_word_search(state: EditorState, key: int) -> bool:
    bindings = normal_action_bindings(state)
    actions = (
        (bindings.word_search_forward, lambda: search_word_under_cursor(state, 1)),
        (bindings.word_search_backward, lambda: search_word_under_cursor(state, -1)),
        (bindings.word_search_next, lambda: repeat_word_search(state, reverse=False)),
        (bindings.word_search_prev, lambda: repeat_word_search(state, reverse=True)),
        (bindings.match_jump, lambda: jump_match(state)),
    )
    for keys, action in actions:
        if key in keys:
            state.count_prefix = ""
            action()
            return True
    return False


def _handle_mark_or_find_prefix(state: EditorState, key: int) -> bool:
    bindings = normal_action_bindings(state)
    prefixes = (
        (bindings.mark_set, "pending_mark", "set"),
        ((*bindings.mark_jump_line, *bindings.mark_jump_exact), "pending_mark", "jump"),
        (bindings.find_forward, "pending_find", "f"),
        (bindings.find_backward, "pending_find", "F"),
        (bindings.till_forward, "pending_find", "t"),
        (bindings.till_backward, "pending_find", "T"),
    )
    for keys, field, value in prefixes:
        if key in keys:
            if field == "pending_mark":
                state.count_prefix = ""
            setattr(state, field, value)
            return True
    return False


def _handle_find_repeat(state: EditorState, key: int) -> bool:
    bindings = normal_action_bindings(state)
    if key in bindings.find_repeat:
        repeat_find(state, reverse=False, count=consume_count(state))
        return True
    if key in bindings.find_repeat_reverse:
        repeat_find(state, reverse=True, count=consume_count(state))
        return True
    return False
