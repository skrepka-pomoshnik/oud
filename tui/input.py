from __future__ import annotations

import curses
import os

from editor.state import EditorState


def history_prev(state: EditorState) -> str | None:
    if not state.command_history:
        return None
    if state.command_history_index is None:
        state.command_history_index = len(state.command_history) - 1
    else:
        state.command_history_index = max(0, state.command_history_index - 1)
    return state.command_history[state.command_history_index]


def history_next(state: EditorState) -> str | None:
    if not state.command_history:
        return None
    if state.command_history_index is None:
        return ""
    state.command_history_index = min(
        len(state.command_history), state.command_history_index + 1
    )
    if state.command_history_index >= len(state.command_history):
        state.command_history_index = None
        return ""
    return state.command_history[state.command_history_index]


def complete_command(state: EditorState) -> bool:  # noqa: PLR0911
    cmdline = state.cmdline
    commands = [
        "e",
        "w",
        "wa",
        "ascii",
        "midi",
        "play",
        "lilypond",
        "pdf",
        "print",
        "set",
        "convert",
        "time",
        "timesig",
        "verify",
        "title",
        "author",
        "composer",
        "subtitle",
        "footnote",
        "header",
        "undo",
        "redo",
        "orn",
        "annot",
        "highlight",
        "midicmd",
        "source",
        "bar",
        "chord",
        "stave",
        "slur",
        "tie",
        "hold",
        "barline",
        "repeat",
        "tool",
        "q",
        "quit",
    ]
    if " " not in cmdline:
        matches = [cmd for cmd in commands if cmd.startswith(cmdline)]
        if not matches:
            return True
        if len(matches) == 1:
            match = matches[0]
            state.cmdline = match + (" " if match not in ("q", "quit") else "")
            return True
        state.message = "Matches: " + " ".join(matches)
        return True

    cmd, rest = cmdline.split(" ", 1)
    if cmd not in ("e", "w", "wa", "midi", "lilypond"):
        return True
    expanded = os.path.expanduser(rest)
    base_dir = os.path.dirname(expanded) or "."
    base_prefix = os.path.basename(expanded)
    try:
        entries = sorted(os.listdir(base_dir))
    except OSError:
        return True
    matches: list[str] = []
    display_matches: list[str] = []
    for entry in entries:
        if not entry.startswith(base_prefix):
            continue
        path = os.path.join(base_dir, entry)
        matches.append(path)
        display_matches.append(path + os.sep if os.path.isdir(path) else path)
    if not matches:
        return True
    if len(matches) == 1:
        path = matches[0]
        if os.path.isdir(path):
            path = path + os.sep
        state.cmdline = f"{cmd} {path}"
        return True
    common = os.path.commonprefix(matches)
    if common and common != expanded:
        state.cmdline = f"{cmd} {common}"
        return True
    state.message = "Matches: " + " ".join(display_matches[:8])
    return True


def handle_command(state: EditorState, key: int, apply_command) -> bool:  # noqa: PLR0911
    if key in (27,):  # ESC
        state.mode = "normal"
        state.cmdline = ""
        state.command_history_index = None
        return True
    key_tab = getattr(curses, "KEY_TAB", 9)
    if key in (key_tab, 9):
        return complete_command(state)
    if key in (curses.KEY_BACKSPACE, 127, 8):
        state.cmdline = state.cmdline[:-1]
        return True
    if key == curses.KEY_UP:
        prev = history_prev(state)
        if prev is not None:
            state.cmdline = prev
        return True
    if key == curses.KEY_DOWN:
        nxt = history_next(state)
        if nxt is not None:
            state.cmdline = nxt
        return True
    if key in (curses.KEY_ENTER, 10, 13):
        cmd = state.cmdline
        state.cmdline = ""
        state.mode = "normal"
        state.command_history_index = None
        if cmd:
            state.command_history.append(cmd)
        apply_command(state, cmd)
        return True
    if 32 <= key <= 126:
        state.cmdline += chr(key)
    return True


def parse_search(text: str) -> int | None:
    text = text.strip()
    if not text:
        return None
    if not text.isdigit():
        return None
    value = int(text)
    if value <= 0:
        return None
    return value - 1


def handle_search(state: EditorState, key: int) -> bool:
    if key in (27,):  # ESC
        state.mode = "normal"
        state.searchline = ""
        return True
    if key in (curses.KEY_BACKSPACE, 127, 8):
        state.searchline = state.searchline[:-1]
        return True
    if key in (curses.KEY_ENTER, 10, 13):
        target = parse_search(state.searchline)
        state.searchline = ""
        state.mode = "normal"
        if target is None:
            state.message = "Invalid bar"
            return True
        state.cursor_bar = max(0, min(target, len(state.piece.bars) - 1))
        state.cursor_col = 0
        return True
    if 32 <= key <= 126:
        state.searchline += chr(key)
    return True
