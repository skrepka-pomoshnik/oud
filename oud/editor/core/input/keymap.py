"""The editor's single key table.

Every modal key is one `Binding` from a key sequence to an `Action`. The table
is filtered by the active key style, arrow option and document kind, then
resolved against the terminal key codes. Dispatch, the read-only gate and the
generated help all read this table, so they cannot drift apart.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from functools import lru_cache
from itertools import product
from types import MappingProxyType
from typing import TYPE_CHECKING

from oud.editor.core.coordinates import allow_arrows, is_casual
from oud.editor.core.input.keycodes import KeyCodes
from oud.editor.core.input.modes import INSERT_MODES, OVERLAY_MODES, VISUAL_MODES, Mode

if TYPE_CHECKING:
    from oud.editor.core.state import EditorState

KeySequence = tuple[int, ...]


class KeyStyle(StrEnum):
    VIM = "vim"
    CASUAL = "casual"


class Scope(StrEnum):
    """Which documents a binding applies to."""

    ANY = "any"
    EDITABLE = "editable"
    READ_ONLY = "read-only"


class ActionGroup(StrEnum):
    SESSION = "Session"
    MOVE = "Move"
    VIEW = "View"
    EDIT = "Edit"
    BARS = "Bars"
    FIND = "Find and marks"
    MEDIA = "Playback and export"
    VISUAL = "Visual selection"
    INSERT = "Insert mode"
    PROMPT = "Command and go-to-bar prompts"
    PAGE = "Help, info and notes pages"
    PLUGIN = "Plugin browser"


class Action(StrEnum):
    QUIT = "quit"
    COMMAND = "command"
    GOTO_BAR = "goto-bar"
    HELP = "help"
    HELP_PAGER = "help-pager"
    INFO = "info"
    PLUGINS = "plugins"
    RELOAD = "reload"
    MOVE_LEFT = "move-left"
    MOVE_RIGHT = "move-right"
    MOVE_UP = "move-up"
    MOVE_DOWN = "move-down"
    ROW_PREV = "row-prev"
    ROW_NEXT = "row-next"
    SCROLL_UP = "scroll-up"
    SCROLL_DOWN = "scroll-down"
    SECTION_PREV = "section-prev"
    SECTION_NEXT = "section-next"
    BAR_PREV = "bar-prev"
    BAR_NEXT = "bar-next"
    BAR_HOME = "bar-home"
    BAR_START = "bar-start"
    BAR_END = "bar-end"
    ROW_FIRST_NOTE = "row-first-note"
    FIRST_BAR = "first-bar"
    LAST_BAR = "last-bar"
    VISUAL = "visual"
    VISUAL_LINE = "visual-line"
    INSERT = "insert"
    REPLACE_ONCE = "replace-once"
    REPLACE_MODE = "replace-mode"
    DELETE_NOTE = "delete-note"
    UNDO = "undo"
    REDO = "redo"
    BAR_AFTER = "bar-after"
    BAR_BEFORE = "bar-before"
    BAR_DELETE = "bar-delete"
    DELETE_BARS = "delete-bars"
    YANK_BARS = "yank-bars"
    PASTE_BARS = "paste-bars"
    ADD_BASS_COURSE = "add-bass-course"
    PLAY = "play"
    FIND_FORWARD = "find-forward"
    FIND_BACKWARD = "find-backward"
    TILL_FORWARD = "till-forward"
    TILL_BACKWARD = "till-backward"
    FIND_REPEAT = "find-repeat"
    FIND_REPEAT_REVERSE = "find-repeat-reverse"
    WORD_SEARCH_FORWARD = "word-search-forward"
    WORD_SEARCH_BACKWARD = "word-search-backward"
    WORD_SEARCH_NEXT = "word-search-next"
    WORD_SEARCH_PREV = "word-search-prev"
    MATCH_JUMP = "match-jump"
    MARK_SET = "mark-set"
    MARK_JUMP = "mark-jump"
    VISUAL_EXIT = "visual-exit"
    VISUAL_COMMAND = "visual-command"
    VISUAL_YANK = "visual-yank"
    VISUAL_PLAY = "visual-play"
    VISUAL_DELETE = "visual-delete"
    VISUAL_CHANGE = "visual-change"
    INSERT_EXIT = "insert-exit"
    INSERT_REST = "insert-rest"
    INSERT_CLEAR = "insert-clear"
    INSERT_BACKSPACE = "insert-backspace"
    INSERT_DELETE = "insert-delete"
    INSERT_BARLINE = "insert-barline"
    INSERT_DOT = "insert-dot"
    INSERT_PREFIX = "insert-prefix"
    INSERT_LEFT = "insert-left"
    INSERT_RIGHT = "insert-right"
    INSERT_UP = "insert-up"
    INSERT_DOWN = "insert-down"
    PASTE_BARS_BEFORE = "paste-bars-before"
    PROMPT_CANCEL = "prompt-cancel"
    PROMPT_SUBMIT = "prompt-submit"
    PROMPT_BACKSPACE = "prompt-backspace"
    PROMPT_COMPLETE = "prompt-complete"
    PROMPT_HISTORY_PREV = "prompt-history-prev"
    PROMPT_HISTORY_NEXT = "prompt-history-next"
    PAGE_CLOSE = "page-close"
    PAGE_UP = "page-up"
    PAGE_DOWN = "page-down"
    PLUGIN_CLOSE = "plugin-close"
    PLUGIN_BACK = "plugin-back"
    PLUGIN_UP = "plugin-up"
    PLUGIN_DOWN = "plugin-down"
    PLUGIN_TOP = "plugin-top"
    PLUGIN_BOTTOM = "plugin-bottom"
    PLUGIN_OPEN = "plugin-open"
    PLUGIN_DOWNLOAD = "plugin-download"
    PLUGIN_DOWNLOAD_TREE = "plugin-download-tree"
    PLUGIN_FILTER = "plugin-filter"
    PLUGIN_HELP = "plugin-help"


@dataclass(frozen=True)
class ActionSpec:
    group: ActionGroup
    help: str
    mutates: bool = False
    takes_char: bool = False
    # A char-argument action normally drops a pending count; finds consume it.
    keeps_count: bool = False


def _spec(
    group: ActionGroup,
    text: str,
    *,
    mutates: bool = False,
    takes_char: bool = False,
    keeps_count: bool = False,
) -> ActionSpec:
    return ActionSpec(group, text, mutates=mutates, takes_char=takes_char, keeps_count=keeps_count)


_G = ActionGroup
ACTION_SPECS: Mapping[Action, ActionSpec] = MappingProxyType(
    {
        Action.QUIT: _spec(_G.SESSION, "quit (press again to discard changes)"),
        Action.COMMAND: _spec(_G.SESSION, "command prompt"),
        Action.GOTO_BAR: _spec(_G.SESSION, "go to bar number"),
        Action.HELP: _spec(_G.SESSION, "this help page"),
        Action.HELP_PAGER: _spec(_G.SESSION, "this help in less"),
        Action.INFO: _spec(_G.SESSION, "file and score info"),
        Action.PLUGINS: _spec(_G.SESSION, "plugin browser"),
        Action.RELOAD: _spec(_G.SESSION, "reload unmodified file"),
        Action.MOVE_LEFT: _spec(_G.MOVE, "left"),
        Action.MOVE_RIGHT: _spec(_G.MOVE, "right"),
        Action.MOVE_UP: _spec(_G.MOVE, "up a course (viewer: previous staff)"),
        Action.MOVE_DOWN: _spec(_G.MOVE, "down a course (viewer: next staff)"),
        Action.ROW_PREV: _spec(_G.MOVE, "previous rendered row (viewer: system)"),
        Action.ROW_NEXT: _spec(_G.MOVE, "next rendered row (viewer: system)"),
        Action.BAR_PREV: _spec(_G.MOVE, "previous bar"),
        Action.BAR_NEXT: _spec(_G.MOVE, "next bar"),
        Action.BAR_HOME: _spec(_G.MOVE, "start of bar (no count pending)"),
        Action.BAR_START: _spec(_G.MOVE, "start of bar"),
        Action.BAR_END: _spec(_G.MOVE, "end of bar"),
        Action.ROW_FIRST_NOTE: _spec(_G.MOVE, "first note in row"),
        Action.FIRST_BAR: _spec(_G.MOVE, "first bar"),
        Action.LAST_BAR: _spec(_G.MOVE, "last bar"),
        Action.SCROLL_UP: _spec(_G.VIEW, "scroll up a page"),
        Action.SCROLL_DOWN: _spec(_G.VIEW, "scroll down a page"),
        Action.SECTION_PREV: _spec(_G.VIEW, "previous section or page"),
        Action.SECTION_NEXT: _spec(_G.VIEW, "next section or page"),
        Action.VISUAL: _spec(_G.VISUAL, "select cells"),
        Action.VISUAL_LINE: _spec(_G.VISUAL, "select whole rows"),
        Action.INSERT: _spec(_G.EDIT, "insert mode", mutates=True),
        Action.REPLACE_ONCE: _spec(_G.EDIT, "replace one cell", mutates=True),
        Action.REPLACE_MODE: _spec(_G.EDIT, "replace mode", mutates=True),
        Action.DELETE_NOTE: _spec(_G.EDIT, "delete note ([count])", mutates=True),
        Action.UNDO: _spec(_G.EDIT, "undo", mutates=True),
        Action.REDO: _spec(_G.EDIT, "redo", mutates=True),
        Action.ADD_BASS_COURSE: _spec(_G.EDIT, "add configured bass course", mutates=True),
        Action.BAR_AFTER: _spec(_G.BARS, "add bar after", mutates=True),
        Action.BAR_BEFORE: _spec(_G.BARS, "add bar before", mutates=True),
        Action.BAR_DELETE: _spec(_G.BARS, "delete bar", mutates=True),
        Action.DELETE_BARS: _spec(_G.BARS, "cut [count] bars", mutates=True),
        Action.YANK_BARS: _spec(_G.BARS, "copy [count] bars"),
        Action.PASTE_BARS: _spec(_G.BARS, "paste bars after", mutates=True),
        Action.FIND_FORWARD: _spec(_G.FIND, "find glyph forward", takes_char=True, keeps_count=True),
        Action.FIND_BACKWARD: _spec(_G.FIND, "find glyph backward", takes_char=True, keeps_count=True),
        Action.TILL_FORWARD: _spec(_G.FIND, "till glyph forward", takes_char=True, keeps_count=True),
        Action.TILL_BACKWARD: _spec(_G.FIND, "till glyph backward", takes_char=True, keeps_count=True),
        Action.FIND_REPEAT: _spec(_G.FIND, "repeat find"),
        Action.FIND_REPEAT_REVERSE: _spec(_G.FIND, "repeat find reversed"),
        Action.WORD_SEARCH_FORWARD: _spec(_G.FIND, "search glyph under cursor forward"),
        Action.WORD_SEARCH_BACKWARD: _spec(_G.FIND, "search glyph under cursor backward"),
        Action.WORD_SEARCH_NEXT: _spec(_G.FIND, "next match"),
        Action.WORD_SEARCH_PREV: _spec(_G.FIND, "previous match"),
        Action.MATCH_JUMP: _spec(_G.FIND, "jump to matching span end"),
        Action.MARK_SET: _spec(_G.FIND, "set mark", takes_char=True),
        Action.MARK_JUMP: _spec(_G.FIND, "jump to mark", takes_char=True),
        Action.PLAY: _spec(_G.MEDIA, "play or stop"),
        Action.VISUAL_EXIT: _spec(_G.VISUAL, "leave selection"),
        Action.VISUAL_COMMAND: _spec(_G.VISUAL, "command prompt"),
        Action.VISUAL_YANK: _spec(_G.VISUAL, "copy selection"),
        Action.VISUAL_PLAY: _spec(_G.VISUAL, "loop selected bars"),
        Action.VISUAL_DELETE: _spec(_G.VISUAL, "delete selection", mutates=True),
        Action.VISUAL_CHANGE: _spec(_G.VISUAL, "delete selection and insert", mutates=True),
        Action.INSERT_EXIT: _spec(_G.INSERT, "back to normal mode"),
        Action.INSERT_REST: _spec(_G.INSERT, "rest", mutates=True),
        Action.INSERT_CLEAR: _spec(_G.INSERT, "clear cell", mutates=True),
        Action.INSERT_BACKSPACE: _spec(_G.INSERT, "clear cell and move left", mutates=True),
        Action.INSERT_DELETE: _spec(_G.INSERT, "clear cell and move right", mutates=True),
        Action.INSERT_BARLINE: _spec(_G.INSERT, "thin barline", mutates=True),
        Action.INSERT_DOT: _spec(_G.INSERT, "toggle dot", mutates=True),
        Action.INSERT_PREFIX: _spec(_G.INSERT, "prefix: ;1..;7 duration, ,10..,24 Italian fret"),
        Action.INSERT_LEFT: _spec(_G.INSERT, "left"),
        Action.INSERT_RIGHT: _spec(_G.INSERT, "right"),
        Action.INSERT_UP: _spec(_G.INSERT, "up a course"),
        Action.INSERT_DOWN: _spec(_G.INSERT, "down a course"),
        Action.PASTE_BARS_BEFORE: _spec(_G.BARS, "paste bars before", mutates=True),
        Action.PROMPT_CANCEL: _spec(_G.PROMPT, "cancel"),
        Action.PROMPT_SUBMIT: _spec(_G.PROMPT, "run"),
        Action.PROMPT_BACKSPACE: _spec(_G.PROMPT, "delete character"),
        Action.PROMPT_COMPLETE: _spec(_G.PROMPT, "complete command or path"),
        Action.PROMPT_HISTORY_PREV: _spec(_G.PROMPT, "previous history entry"),
        Action.PROMPT_HISTORY_NEXT: _spec(_G.PROMPT, "next history entry"),
        Action.PAGE_CLOSE: _spec(_G.PAGE, "close page"),
        Action.PAGE_UP: _spec(_G.PAGE, "scroll up"),
        Action.PAGE_DOWN: _spec(_G.PAGE, "scroll down"),
        Action.PLUGIN_CLOSE: _spec(_G.PLUGIN, "close browser (or go up a level)"),
        Action.PLUGIN_BACK: _spec(_G.PLUGIN, "up a level"),
        Action.PLUGIN_UP: _spec(_G.PLUGIN, "previous item"),
        Action.PLUGIN_DOWN: _spec(_G.PLUGIN, "next item"),
        Action.PLUGIN_TOP: _spec(_G.PLUGIN, "first item"),
        Action.PLUGIN_BOTTOM: _spec(_G.PLUGIN, "last item"),
        Action.PLUGIN_OPEN: _spec(_G.PLUGIN, "open item"),
        Action.PLUGIN_DOWNLOAD: _spec(_G.PLUGIN, "download item"),
        Action.PLUGIN_DOWNLOAD_TREE: _spec(_G.PLUGIN, "download folder recursively"),
        Action.PLUGIN_FILTER: _spec(_G.PLUGIN, "search items (Enter jumps, Esc cancels)"),
        Action.PLUGIN_HELP: _spec(_G.PLUGIN, "plugin help in less"),
    },
)


@dataclass(frozen=True)
class Binding:
    keys: tuple[str, ...]
    action: Action
    style: KeyStyle | None = None
    scope: Scope = Scope.ANY
    arrows: bool = False


def _key_names(text: str) -> tuple[str, ...]:
    """Split `gg`, `^R`, `<PgUp>` or `g<Esc>` into key names; a lone `^` is a key."""
    key_names: list[str] = []
    index = 0
    while index < len(text):
        if text[index] == "<" and ">" in text[index + 1 :]:
            end = text.index(">", index)
            key_names.append(text[index : end + 1])
            index = end + 1
        elif text[index] == "^" and index + 1 < len(text) and text[index + 1].isalpha():
            key_names.append(text[index : index + 2])
            index += 2
        else:
            key_names.append(text[index])
            index += 1
    return tuple(key_names)


def _bind(
    text: str,
    action: Action,
    *,
    style: KeyStyle | None = None,
    scope: Scope = Scope.ANY,
    arrows: bool = False,
) -> Binding:
    return Binding(_key_names(text), action, style, scope, arrows)


_A = Action
_VIM = KeyStyle.VIM
_CASUAL = KeyStyle.CASUAL
_MOTION_BINDINGS: tuple[Binding, ...] = (
    _bind("h", _A.MOVE_LEFT, style=_VIM),
    _bind("^B", _A.MOVE_LEFT, style=_VIM),
    _bind("l", _A.MOVE_RIGHT, style=_VIM),
    _bind("^F", _A.MOVE_RIGHT, style=_VIM),
    _bind("k", _A.MOVE_UP, style=_VIM),
    _bind("^P", _A.MOVE_UP, style=_VIM),
    _bind("j", _A.MOVE_DOWN, style=_VIM),
    _bind("^N", _A.MOVE_DOWN, style=_VIM),
    _bind("a", _A.MOVE_LEFT, style=_CASUAL),
    _bind("d", _A.MOVE_RIGHT, style=_CASUAL),
    _bind("w", _A.MOVE_UP, style=_CASUAL),
    _bind("s", _A.MOVE_DOWN, style=_CASUAL),
    _bind("<Left>", _A.MOVE_LEFT, arrows=True),
    _bind("<Right>", _A.MOVE_RIGHT, arrows=True),
    _bind("<Up>", _A.MOVE_UP, arrows=True),
    _bind("<Down>", _A.MOVE_DOWN, arrows=True),
    _bind("K", _A.ROW_PREV, style=_VIM),
    _bind("{", _A.ROW_PREV, style=_VIM),
    _bind("J", _A.ROW_NEXT, style=_VIM),
    _bind("}", _A.ROW_NEXT, style=_VIM),
    _bind("W", _A.ROW_PREV, style=_CASUAL),
    _bind("S", _A.ROW_NEXT, style=_CASUAL),
    _bind("<PgUp>", _A.SCROLL_UP),
    _bind("<PgDn>", _A.SCROLL_DOWN),
    _bind("^U", _A.SCROLL_UP, style=_VIM),
    _bind("^D", _A.SCROLL_DOWN, style=_VIM),
    _bind("b", _A.BAR_PREV, style=_VIM),
    _bind("w", _A.BAR_NEXT, style=_VIM),
    _bind(",", _A.BAR_PREV, style=_CASUAL),
    _bind(".", _A.BAR_NEXT, style=_CASUAL),
    _bind("<Home>", _A.BAR_START, style=_CASUAL),
    _bind("e", _A.BAR_END, style=_VIM),
    _bind("$", _A.BAR_END, style=_VIM),
    _bind("<End>", _A.BAR_END, style=_CASUAL),
    _bind("G", _A.LAST_BAR),
)

_NORMAL_BINDINGS: tuple[Binding, ...] = (
    _bind("q", _A.QUIT),
    _bind("Q", _A.QUIT),
    _bind("^C", _A.QUIT),
    _bind(":", _A.COMMAND),
    _bind("/", _A.GOTO_BAR),
    _bind("<F1>", _A.HELP),
    _bind("gh", _A.HELP),
    _bind("?", _A.HELP_PAGER),
    _bind("I", _A.INFO),
    _bind("gi", _A.INFO),
    _bind("gp", _A.PLUGINS),
    _bind("gr", _A.RELOAD),
    *_MOTION_BINDINGS,
    _bind("0", _A.BAR_HOME),
    _bind("^", _A.ROW_FIRST_NOTE),
    _bind("gg", _A.FIRST_BAR),
    _bind("[", _A.SECTION_PREV, scope=Scope.READ_ONLY),
    _bind("]", _A.SECTION_NEXT, scope=Scope.READ_ONLY),
    _bind("v", _A.VISUAL),
    _bind("V", _A.VISUAL_LINE),
    _bind("i", _A.INSERT),
    _bind("<Enter>", _A.INSERT),
    _bind("r", _A.REPLACE_ONCE),
    _bind("R", _A.REPLACE_MODE),
    _bind("x", _A.DELETE_NOTE),
    _bind("u", _A.UNDO),
    _bind("^Z", _A.UNDO, style=_CASUAL),
    _bind("^R", _A.REDO),
    _bind("^Y", _A.REDO, style=_CASUAL),
    _bind("gb", _A.ADD_BASS_COURSE),
    _bind("o", _A.BAR_AFTER),
    _bind("+", _A.BAR_AFTER),
    _bind("<Ins>", _A.BAR_AFTER, style=_CASUAL),
    _bind("O", _A.BAR_BEFORE),
    _bind("X", _A.BAR_DELETE),
    _bind("-", _A.BAR_DELETE),
    _bind("<Del>", _A.BAR_DELETE, style=_CASUAL),
    _bind("dd", _A.DELETE_BARS, style=_VIM),
    _bind("yy", _A.YANK_BARS),
    _bind("p", _A.PASTE_BARS),
    _bind("P", _A.PASTE_BARS_BEFORE),
    _bind("f", _A.FIND_FORWARD),
    _bind("F", _A.FIND_BACKWARD),
    _bind("t", _A.TILL_FORWARD),
    _bind("T", _A.TILL_BACKWARD),
    _bind(";", _A.FIND_REPEAT),
    _bind(",", _A.FIND_REPEAT_REVERSE, style=_VIM),
    _bind("*", _A.WORD_SEARCH_FORWARD),
    _bind("#", _A.WORD_SEARCH_BACKWARD),
    _bind("n", _A.WORD_SEARCH_NEXT),
    _bind("N", _A.WORD_SEARCH_PREV),
    _bind("%", _A.MATCH_JUMP),
    _bind("m", _A.MARK_SET),
    _bind("'", _A.MARK_JUMP),
    _bind("`", _A.MARK_JUMP),
    _bind("M", _A.PLAY),
)

_VISUAL_BINDINGS: tuple[Binding, ...] = (
    _bind("<Esc>", _A.VISUAL_EXIT),
    _bind("<Exit>", _A.VISUAL_EXIT),
    _bind(":", _A.VISUAL_COMMAND),
    _bind("v", _A.VISUAL),
    _bind("V", _A.VISUAL_LINE),
    *_MOTION_BINDINGS,
    _bind("y", _A.VISUAL_YANK),
    _bind("Y", _A.VISUAL_YANK),
    _bind("M", _A.VISUAL_PLAY),
    _bind("d", _A.VISUAL_DELETE, style=_VIM),
    _bind("D", _A.VISUAL_DELETE),
    _bind("x", _A.VISUAL_DELETE),
    _bind("X", _A.VISUAL_DELETE),
    _bind("<Del>", _A.VISUAL_DELETE),
    _bind("c", _A.VISUAL_CHANGE),
    _bind("C", _A.VISUAL_CHANGE),
)

# Letters and digits are frets or durations in insert mode, so these bindings
# use only symbols, named keys and Ctrl chords.
_INSERT_BINDINGS: tuple[Binding, ...] = (
    _bind("<Esc>", _A.INSERT_EXIT),
    _bind("<Exit>", _A.INSERT_EXIT),
    _bind("^C", _A.QUIT),
    _bind("z", _A.INSERT_REST),
    _bind("<Space>", _A.INSERT_CLEAR),
    _bind("<Backspace>", _A.INSERT_BACKSPACE),
    _bind("<Del>", _A.INSERT_DELETE),
    _bind("|", _A.INSERT_BARLINE),
    _bind(".", _A.INSERT_DOT),
    _bind(";", _A.INSERT_PREFIX),
    _bind(",", _A.INSERT_PREFIX),
    _bind("<Left>", _A.INSERT_LEFT),
    _bind("<Right>", _A.INSERT_RIGHT),
    _bind("<Up>", _A.INSERT_UP),
    _bind("<Down>", _A.INSERT_DOWN),
)

_PROMPT_EDIT_BINDINGS: tuple[Binding, ...] = (
    _bind("<Esc>", _A.PROMPT_CANCEL),
    _bind("^C", _A.PROMPT_CANCEL),
    _bind("<Enter>", _A.PROMPT_SUBMIT),
    _bind("<Backspace>", _A.PROMPT_BACKSPACE),
    _bind("<Up>", _A.PROMPT_HISTORY_PREV),
    _bind("<Down>", _A.PROMPT_HISTORY_NEXT),
)

_COMMAND_BINDINGS: tuple[Binding, ...] = (
    *_PROMPT_EDIT_BINDINGS,
    _bind("<Tab>", _A.PROMPT_COMPLETE),
    _bind("^A", _A.PROMPT_COMPLETE),
)

_PAGE_BINDINGS: tuple[Binding, ...] = (
    _bind("q", _A.PAGE_CLOSE),
    _bind("Q", _A.PAGE_CLOSE),
    _bind("<Esc>", _A.PAGE_CLOSE),
    _bind("<Exit>", _A.PAGE_CLOSE),
    _bind("^C", _A.PAGE_CLOSE),
    _bind("k", _A.PAGE_UP),
    _bind("<Up>", _A.PAGE_UP),
    _bind("j", _A.PAGE_DOWN),
    _bind("<Down>", _A.PAGE_DOWN),
)

# The browser is a list, so it keeps vim letters and arrows in every key style.
_PLUGIN_BINDINGS: tuple[Binding, ...] = (
    _bind("q", _A.PLUGIN_CLOSE),
    _bind("Q", _A.PLUGIN_CLOSE),
    _bind("b", _A.PLUGIN_CLOSE),
    _bind("<Esc>", _A.PLUGIN_CLOSE),
    _bind("<Exit>", _A.PLUGIN_CLOSE),
    _bind("^C", _A.PLUGIN_CLOSE),
    _bind("h", _A.PLUGIN_BACK),
    _bind("<Left>", _A.PLUGIN_BACK),
    _bind("k", _A.PLUGIN_UP),
    _bind("<Up>", _A.PLUGIN_UP),
    _bind("j", _A.PLUGIN_DOWN),
    _bind("<Down>", _A.PLUGIN_DOWN),
    _bind("gg", _A.PLUGIN_TOP),
    _bind("G", _A.PLUGIN_BOTTOM),
    _bind("l", _A.PLUGIN_OPEN),
    _bind("<Enter>", _A.PLUGIN_OPEN),
    _bind("d", _A.PLUGIN_DOWNLOAD),
    _bind("D", _A.PLUGIN_DOWNLOAD_TREE),
    _bind("/", _A.PLUGIN_FILTER),
    _bind("?", _A.PLUGIN_HELP),
)

_TABLES: Mapping[Mode, tuple[Binding, ...]] = MappingProxyType(
    {
        Mode.NORMAL: _NORMAL_BINDINGS,
        Mode.VISUAL: _VISUAL_BINDINGS,
        Mode.INSERT: _INSERT_BINDINGS,
        Mode.COMMAND: _COMMAND_BINDINGS,
        Mode.SEARCH: _PROMPT_EDIT_BINDINGS,
        Mode.HELP: _PAGE_BINDINGS,
        Mode.PLUGIN: _PLUGIN_BINDINGS,
    },
)


def _table_mode(mode: Mode | str) -> Mode:
    mode = Mode(mode)
    if mode in VISUAL_MODES:
        return Mode.VISUAL
    if mode in INSERT_MODES:
        return Mode.INSERT
    if mode in OVERLAY_MODES:
        return Mode.HELP
    if mode in _TABLES:
        return mode
    return Mode.NORMAL


@dataclass(frozen=True)
class KeyProfile:
    style: KeyStyle
    arrows: bool
    read_only: bool

    @property
    def label(self) -> str:
        return f"{self.style.value}{'+arrows' if self.arrows else ''}"


def key_profile(state: EditorState) -> KeyProfile:
    style = KeyStyle.CASUAL if is_casual(state) else KeyStyle.VIM
    return KeyProfile(style, allow_arrows(state), bool(state.read_only))


def _binding_active(binding: Binding, profile: KeyProfile) -> bool:
    if binding.style is not None and binding.style is not profile.style:
        return False
    if binding.arrows and not profile.arrows:
        return False
    if binding.scope is Scope.EDITABLE:
        return not profile.read_only
    if binding.scope is Scope.READ_ONLY:
        return profile.read_only
    return True


def active_bindings(profile: KeyProfile, mode: Mode | str) -> tuple[Binding, ...]:
    return tuple(binding for binding in _TABLES[_table_mode(mode)] if _binding_active(binding, profile))


# Named key -> (KeyCodes field or None, fixed codes that terminals also send).
_NAMED_KEYS: Mapping[str, tuple[str | None, tuple[int, ...]]] = MappingProxyType(
    {
        "<Left>": ("left", ()),
        "<Right>": ("right", ()),
        "<Up>": ("up", ()),
        "<Down>": ("down", ()),
        "<F1>": ("f1", ()),
        "<Ins>": ("ic", ()),
        "<Del>": ("dc", ()),
        "<Exit>": ("exit", ()),
        "<PgUp>": ("ppage", ()),
        "<PgDn>": ("npage", ()),
        "<Home>": ("home", ()),
        "<End>": ("end", ()),
        "<Enter>": ("enter", (10, 13)),
        "<Tab>": ("tab", (9,)),
        "<Backspace>": ("backspace", (127, 8)),
        "<Esc>": (None, (27,)),
        "<Space>": (None, (32,)),
    },
)


def key_codes(key_name: str, keycodes: KeyCodes) -> tuple[int, ...]:
    """Return every terminal code that produces `key_name`."""
    if key_name in _NAMED_KEYS:
        field, fixed = _NAMED_KEYS[key_name]
        codes = (getattr(keycodes, field),) if field else ()
        return tuple(dict.fromkeys((*codes, *fixed)))
    if key_name.startswith("^") and len(key_name) == len("^X"):
        return (ord(key_name[1].upper()) & 31,)
    return (ord(key_name),)


def key_label(key_name: str) -> str:
    if key_name.startswith("<") and key_name.endswith(">"):
        return key_name[1:-1]
    if key_name.startswith("^") and len(key_name) == len("^X"):
        return f"Ctrl-{key_name[1].upper()}"
    return key_name


@dataclass(frozen=True)
class ResolvedKeymap:
    actions: Mapping[KeySequence, Action]
    prefixes: frozenset[KeySequence]

    def lookup(self, sequence: KeySequence) -> Action | None:
        return self.actions.get(sequence)

    def is_prefix(self, sequence: KeySequence) -> bool:
        return sequence in self.prefixes

    def keys_for(self, action: Action) -> tuple[int, ...]:
        """Single keys bound to `action`, in table order."""
        return tuple(seq[0] for seq, bound in self.actions.items() if bound is action and len(seq) == 1)

    def first_keys_for(self, action: Action) -> tuple[int, ...]:
        """First keys of the multi-key sequences bound to `action` (for list widgets with `gg`)."""
        return tuple(dict.fromkeys(seq[0] for seq, bound in self.actions.items() if bound is action and len(seq) > 1))


@lru_cache(maxsize=32)
def _resolve(profile: KeyProfile, mode: Mode, keycodes: KeyCodes) -> ResolvedKeymap:
    actions: dict[KeySequence, Action] = {}
    prefixes: set[KeySequence] = set()
    for binding in active_bindings(profile, mode):
        for sequence in product(*(key_codes(key_name, keycodes) for key_name in binding.keys)):
            # The first binding wins, so table order is the documented precedence.
            actions.setdefault(sequence, binding.action)
            prefixes.update(sequence[:length] for length in range(1, len(sequence)))
    return ResolvedKeymap(MappingProxyType(actions), frozenset(prefixes))


def keymap_for(state: EditorState, mode: Mode | str) -> ResolvedKeymap:
    return _resolve(key_profile(state), _table_mode(mode), state.keycodes)


# curses' KEY_EXIT duplicates Esc on some terminals; it is bound but not advertised.
_HIDDEN_KEY = "<Exit>"


@dataclass(frozen=True)
class HelpRow:
    group: ActionGroup
    keys: str
    text: str


def help_rows(profile: KeyProfile, mode: Mode | str) -> tuple[HelpRow, ...]:
    """Describe every active binding, one row per action in table order."""
    keys_by_action: dict[Action, list[str]] = {}
    for binding in active_bindings(profile, mode):
        spec = ACTION_SPECS[binding.action]
        if spec.mutates and profile.read_only:
            continue
        labels = keys_by_action.setdefault(binding.action, [])
        if _HIDDEN_KEY in binding.keys:
            continue
        label = "".join(key_label(key_name) for key_name in binding.keys) + ("{c}" if spec.takes_char else "")
        if label not in labels:
            labels.append(label)
    return tuple(
        HelpRow(ACTION_SPECS[action].group, " ".join(labels), ACTION_SPECS[action].help)
        for action, labels in keys_by_action.items()
    )
