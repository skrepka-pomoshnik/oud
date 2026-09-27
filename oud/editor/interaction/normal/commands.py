from __future__ import annotations

from oud.editor.commands.dispatch import cmd_bar, cmd_open, paste_bar, row_first_note_col, show_help
from oud.editor.commands.plugins.operations import enter_plugin_mode
from oud.editor.commands.query.find import perform_find, repeat_find
from oud.editor.commands.query.search import (
    jump_mark,
    jump_match,
    repeat_word_search,
    search_word_under_cursor,
    set_mark,
)
from oud.editor.core.coordinates import consume_count, string_index
from oud.editor.core.feedback.messages import UNSAVED_QUIT
from oud.editor.core.input.modes import Mode
from oud.editor.core.session import clear_insert_transient, enter_insert_mode, enter_replace_mode, set_mode
from oud.editor.core.state import EditorState, UndoAction
from oud.editor.editing.primitives.edits import clear_cell, record_action, undo_group
from oud.editor.editing.primitives.ranges import bar_range_from_cursor, deletable_bar_range_from_cursor
from oud.editor.editing.primitives.undo import redo, undo
from oud.editor.editing.score.operations import delete_bar_range, yank_bar_range
from oud.editor.navigation.motions import CursorMotionTarget, apply_motion_target, target_move_right_note
from oud.editor.services.media.midi import start_midi, stop_midi
from petrucci.core.music.tuning import parse_bass_strings, tuning_count


def quit_editor(state: EditorState) -> bool:
    """Return False to stop the editor; modified documents need a second press."""
    clear_insert_transient(state)
    if state.modified and not state.pending_quit:
        state.pending_quit = True
        state.message = UNSAVED_QUIT
        return True
    stop_midi(state)
    return False


def open_prompt(state: EditorState, mode: Mode) -> None:
    set_mode(state, mode)
    state.cmdline = ""
    state.searchline = ""


def open_page(state: EditorState, mode: Mode) -> None:
    set_mode(state, mode)
    if mode is Mode.INFO:
        state.info_offset = 0
    else:
        state.help_offset = 0


def help_pager(state: EditorState) -> None:
    show_help(state)


def plugins(state: EditorState) -> None:
    enter_plugin_mode(state)


def reload_file(state: EditorState) -> None:
    if state.modified:
        state.message = "Unsaved changes. Save or use :e to reload."
        return
    if not state.path:
        state.message = "No file to reload"
        return
    cmd_open(state, state.path)
    state.message = f"Reloaded: {state.path}"


def insert(state: EditorState) -> None:
    enter_insert_mode(state)


def replace_once(state: EditorState) -> None:
    enter_insert_mode(state, replace_once=True)


def replace_mode(state: EditorState) -> None:
    enter_replace_mode(state)


def delete_notes(state: EditorState) -> None:
    count = consume_count(state)
    with undo_group(state, label="delete-cell-count"):
        for _ in range(count):
            clear_cell(state, state.cursor_bar, string_index(state, state.cursor_string), state.cursor_col)
            if count > 1 and not _move_after_delete(state):
                break


def undo_edit(state: EditorState) -> None:
    undo(state, config_path=state.config_path)


def redo_edit(state: EditorState) -> None:
    redo(state, config_path=state.config_path)


def bar_command(state: EditorState, action: str) -> None:
    cmd_bar(state, action)


def delete_bars(state: EditorState) -> None:
    bar_range = deletable_bar_range_from_cursor(state, consume_count(state))
    if yank_bar_range(state, bar_range):
        delete_bar_range(state, bar_range)


def yank_bars(state: EditorState) -> None:
    yank_bar_range(state, bar_range_from_cursor(state, consume_count(state)))


def paste_bars(state: EditorState) -> None:
    paste_bar(state, state.cursor_bar + 1)


def paste_bars_before(state: EditorState) -> None:
    paste_bar(state, state.cursor_bar)


def add_bass_course(state: EditorState) -> None:
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
    before = _course_snapshot(state)
    state.piece.strings += 1
    state.cursor_string = state.piece.strings - 1
    state.settings["strings"] = str(state.piece.strings)
    if tuning:
        state.settings["tuning"] = tuning + token
    record_action(state, UndoAction(kind="courses", data={"prev": before, "new": _course_snapshot(state)}))
    state.message = f"Bass string {token} added"


def row_first_note(state: EditorState) -> None:
    apply_motion_target(state, CursorMotionTarget(state.cursor_bar, row_first_note_col(state)))


def find_glyph(state: EditorState, kind: str, char: str) -> None:
    perform_find(state, kind, char, count=consume_count(state))


def repeat_glyph_find(state: EditorState, *, reverse: bool) -> None:
    repeat_find(state, reverse=reverse, count=consume_count(state))


def word_search(state: EditorState, direction: int) -> None:
    search_word_under_cursor(state, direction)


def word_search_repeat(state: EditorState, *, reverse: bool) -> None:
    repeat_word_search(state, reverse=reverse)


def match_jump(state: EditorState) -> None:
    jump_match(state)


def mark_set(state: EditorState, char: str) -> None:
    set_mark(state, char)


def mark_jump(state: EditorState, char: str) -> None:
    jump_mark(state, char)


def toggle_playback(state: EditorState) -> None:
    if state.midi_proc is not None and state.midi_proc.poll() is None:
        stop_midi(state)
    else:
        start_midi(state)


def _course_snapshot(state: EditorState) -> dict[str, object]:
    return {
        "strings": state.piece.strings,
        "settings_strings": state.settings.get("strings"),
        "tuning": state.settings.get("tuning"),
    }


def _move_after_delete(state: EditorState) -> bool:
    target = target_move_right_note(state)
    if target.append_bar:
        return False
    before = (state.cursor_bar, state.cursor_col, state.cursor_string)
    apply_motion_target(state, target)
    return (state.cursor_bar, state.cursor_col, state.cursor_string) != before
