"""Handlers for every normal- and visual-mode action in the key table."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType

from oud.editor.core.input.keymap import Action
from oud.editor.core.input.modes import Mode
from oud.editor.core.state import EditorState
from oud.editor.interaction.normal import commands as cmd
from oud.editor.interaction.normal import movement as mv


@dataclass(frozen=True)
class ActionInput:
    key: int
    char: str = ""


Handler = Callable[[EditorState, ActionInput], bool]


def _run(action: Callable[[EditorState], None]) -> Handler:
    def handler(state: EditorState, _input: ActionInput) -> bool:
        action(state)
        return True

    return handler


def _with_char(action: Callable[[EditorState, str], None]) -> Handler:
    def handler(state: EditorState, action_input: ActionInput) -> bool:
        action(state, action_input.char)
        return True

    return handler


def _find(kind: str) -> Handler:
    return _with_char(lambda state, char: cmd.find_glyph(state, kind, char))


_A = Action
NORMAL_HANDLERS: Mapping[Action, Handler] = MappingProxyType(
    {
        _A.QUIT: lambda state, _input: cmd.quit_editor(state),
        _A.COMMAND: _run(lambda state: cmd.open_prompt(state, Mode.COMMAND)),
        _A.GOTO_BAR: _run(lambda state: cmd.open_prompt(state, Mode.SEARCH)),
        _A.HELP: _run(lambda state: cmd.open_page(state, Mode.HELP)),
        _A.HELP_PAGER: _run(cmd.help_pager),
        _A.INFO: _run(lambda state: cmd.open_page(state, Mode.INFO)),
        _A.PLUGINS: _run(cmd.plugins),
        _A.RELOAD: _run(cmd.reload_file),
        _A.MOVE_LEFT: _run(lambda state: mv.move_horizontal(state, -1)),
        _A.MOVE_RIGHT: _run(lambda state: mv.move_horizontal(state, 1)),
        _A.MOVE_UP: _run(lambda state: mv.move_vertical(state, -1)),
        _A.MOVE_DOWN: _run(lambda state: mv.move_vertical(state, 1)),
        _A.ROW_PREV: _run(lambda state: mv.jump_row(state, -1)),
        _A.ROW_NEXT: _run(lambda state: mv.jump_row(state, 1)),
        _A.SCROLL_UP: _run(lambda state: mv.scroll_page(state, -1)),
        _A.SCROLL_DOWN: _run(lambda state: mv.scroll_page(state, 1)),
        _A.SECTION_PREV: _run(lambda state: mv.jump_section(state, -1)),
        _A.SECTION_NEXT: _run(lambda state: mv.jump_section(state, 1)),
        _A.BAR_PREV: _run(lambda state: mv.step_bar(state, -1)),
        _A.BAR_NEXT: _run(lambda state: mv.step_bar(state, 1)),
        _A.BAR_HOME: _run(mv.bar_home),
        _A.BAR_START: _run(mv.bar_start),
        _A.BAR_END: _run(mv.bar_end),
        _A.ROW_FIRST_NOTE: _run(cmd.row_first_note),
        _A.FIRST_BAR: _run(mv.first_bar),
        _A.LAST_BAR: _run(mv.last_bar),
        _A.VISUAL: _run(lambda state: mv.enter_visual(state, linewise=False)),
        _A.VISUAL_LINE: _run(lambda state: mv.enter_visual(state, linewise=True)),
        _A.INSERT: _run(cmd.insert),
        _A.REPLACE_ONCE: _run(cmd.replace_once),
        _A.REPLACE_MODE: _run(cmd.replace_mode),
        _A.DELETE_NOTE: _run(cmd.delete_notes),
        _A.UNDO: _run(cmd.undo_edit),
        _A.REDO: _run(cmd.redo_edit),
        _A.ADD_BASS_COURSE: _run(cmd.add_bass_course),
        _A.BAR_AFTER: _run(lambda state: cmd.bar_command(state, "after")),
        _A.BAR_BEFORE: _run(lambda state: cmd.bar_command(state, "before")),
        _A.BAR_DELETE: _run(lambda state: cmd.bar_command(state, "del")),
        _A.DELETE_BARS: _run(cmd.delete_bars),
        _A.YANK_BARS: _run(cmd.yank_bars),
        _A.PASTE_BARS: _run(cmd.paste_bars),
        _A.PASTE_BARS_BEFORE: _run(cmd.paste_bars_before),
        _A.FIND_FORWARD: _find("f"),
        _A.FIND_BACKWARD: _find("F"),
        _A.TILL_FORWARD: _find("t"),
        _A.TILL_BACKWARD: _find("T"),
        _A.FIND_REPEAT: _run(lambda state: cmd.repeat_glyph_find(state, reverse=False)),
        _A.FIND_REPEAT_REVERSE: _run(lambda state: cmd.repeat_glyph_find(state, reverse=True)),
        _A.WORD_SEARCH_FORWARD: _run(lambda state: cmd.word_search(state, 1)),
        _A.WORD_SEARCH_BACKWARD: _run(lambda state: cmd.word_search(state, -1)),
        _A.WORD_SEARCH_NEXT: _run(lambda state: cmd.word_search_repeat(state, reverse=False)),
        _A.WORD_SEARCH_PREV: _run(lambda state: cmd.word_search_repeat(state, reverse=True)),
        _A.MATCH_JUMP: _run(cmd.match_jump),
        _A.MARK_SET: _with_char(cmd.mark_set),
        _A.MARK_JUMP: _with_char(cmd.mark_jump),
        _A.PLAY: _run(cmd.toggle_playback),
        _A.VISUAL_EXIT: _run(mv.exit_visual),
        _A.VISUAL_COMMAND: _run(mv.visual_command),
        _A.VISUAL_YANK: _run(mv.visual_yank),
        _A.VISUAL_PLAY: _run(mv.visual_play),
        _A.VISUAL_DELETE: _run(lambda state: mv.visual_delete(state, change=False)),
        _A.VISUAL_CHANGE: _run(lambda state: mv.visual_delete(state, change=True)),
    },
)
