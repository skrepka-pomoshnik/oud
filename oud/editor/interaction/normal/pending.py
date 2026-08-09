from __future__ import annotations

from oud.editor.commands.query.find import perform_find
from oud.editor.commands.query.search import jump_mark, set_mark
from oud.editor.core.coordinates import append_count_digit, consume_count
from oud.editor.core.feedback.messages import READ_ONLY_VIEWER
from oud.editor.core.input.keymap import count_bindings, pending_bindings
from oud.editor.core.state import EditorState
from oud.editor.editing.primitives.ranges import bar_range_from_cursor, deletable_bar_range_from_cursor
from oud.editor.navigation.motions import apply_motion_target, target_home_bar, target_jump_first_bar


def handle_prefix_input(state: EditorState, key: int) -> bool:
    for handler in (_handle_pending_mark, _handle_pending_find, _handle_count, _handle_pending_key):
        if handler(state, key):
            return True
    return False


def _handle_pending_mark(state: EditorState, key: int) -> bool:
    if not state.pending_mark:
        return False
    if 32 <= key <= 126:
        state.count_prefix = ""
        name = chr(key)
        if state.pending_mark == "set":
            set_mark(state, name)
        else:
            jump_mark(state, name)
    state.pending_mark = ""
    return True


def _handle_pending_find(state: EditorState, key: int) -> bool:
    if not state.pending_find:
        return False
    if 32 <= key <= 126:
        perform_find(state, state.pending_find, chr(key), count=consume_count(state))
    state.pending_find = ""
    return True


def _handle_count(state: EditorState, key: int) -> bool:
    bindings = count_bindings()
    if key not in bindings.digits:
        return False
    if key == bindings.zero and not state.count_prefix:
        apply_motion_target(state, target_home_bar(state, state.cursor_bar))
    else:
        append_count_digit(state, chr(key))
    return True


def _handle_pending_key(state: EditorState, key: int) -> bool:
    pending = state.pending_key
    if not pending:
        return False
    bindings = pending_bindings()
    matched = False
    if pending == "g":
        matched = _handle_g_prefix(state, key, bindings)
    elif pending == "d" and key in bindings.dd:
        _delete_bar_range(state)
        matched = True
    elif pending == "y" and key in bindings.yy:
        _yank_bar_range(state)
        matched = True
    state.pending_key = ""
    if not matched:
        state.count_prefix = ""
    return True


def _handle_g_prefix(state: EditorState, key: int, bindings) -> bool:
    actions = (
        (bindings.gg, _jump_first),
        (bindings.gj, _add_bass_string),
        (bindings.gh, _show_help),
        (bindings.gi, _show_info),
        (bindings.gp, _show_plugins),
        (bindings.gr, _reload),
    )
    for keys, action in actions:
        if key in keys:
            action(state)
            return True
    return False


def _jump_first(state: EditorState) -> None:
    apply_motion_target(state, target_jump_first_bar(state))


def _add_bass_string(state: EditorState) -> None:
    if state.read_only:
        state.message = READ_ONLY_VIEWER
        return
    from petrucci.tuning_utils import parse_bass_strings, tuning_count  # noqa: PLC0415

    tuning = state.settings.get("tuning", "")
    base = tuning_count(tuning) if tuning else state.piece.strings
    bass_list = parse_bass_strings(state.settings.get("bassstrings", ""))
    if not bass_list:
        state.message = "No bass strings configured"
        return
    added = max(0, state.piece.strings - base)
    if added >= len(bass_list):
        state.message = "No more bass strings (set bassstrings)"
        return
    token = bass_list[added]
    state.piece.strings += 1
    state.cursor_string = state.piece.strings - 1
    state.settings["strings"] = str(state.piece.strings)
    if tuning:
        state.settings["tuning"] = tuning + token
    state.modified = True
    state.message = f"Bass string {token} added"


def _show_help(state: EditorState) -> None:
    from oud.editor.core.session import set_mode  # noqa: PLC0415

    set_mode(state, "help")
    state.help_offset = 0


def _show_info(state: EditorState) -> None:
    from oud.editor.core.session import set_mode  # noqa: PLC0415

    set_mode(state, "info")
    state.info_offset = 0


def _show_plugins(state: EditorState) -> None:
    from oud.editor.commands.plugins.operations import enter_plugin_mode  # noqa: PLC0415

    enter_plugin_mode(state)


def _reload(state: EditorState) -> None:
    if state.modified:
        state.message = "Unsaved changes. Save or use :e to reload."
        return
    if not state.path:
        state.message = "No file to reload"
        return
    from oud.editor.commands.dispatch import cmd_open  # noqa: PLC0415

    cmd_open(state, state.path)
    state.message = f"Reloaded: {state.path}"


def _delete_bar_range(state: EditorState) -> None:
    if state.read_only:
        state.message = READ_ONLY_VIEWER
        state.count_prefix = ""
        return
    from oud.editor.editing.score.operations import delete_bar_range, yank_bar_range  # noqa: PLC0415

    bar_range = deletable_bar_range_from_cursor(state, consume_count(state))
    if yank_bar_range(state, bar_range):
        delete_bar_range(state, bar_range)


def _yank_bar_range(state: EditorState) -> None:
    from oud.editor.editing.score.operations import yank_bar_range  # noqa: PLC0415

    yank_bar_range(state, bar_range_from_cursor(state, consume_count(state)))
