from __future__ import annotations

import os
from pathlib import Path

from editor.keymap import command_bindings, search_bindings
from editor.state import EditorState
from tui.commands import command_names, no_space_commands, path_commands


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
        len(state.command_history), state.command_history_index + 1,
    )
    if state.command_history_index >= len(state.command_history):
        state.command_history_index = None
        return ""
    return state.command_history[state.command_history_index]


def complete_command(state: EditorState) -> bool:  # noqa: PLR0911, C901, PLR0912
    cmdline = state.cmdline
    commands = command_names()
    if " " not in cmdline:
        matches = [cmd for cmd in commands if cmd.startswith(cmdline)]
        if not matches:
            return True
        if len(matches) == 1:
            match = matches[0]
            state.cmdline = match + (" " if match not in no_space_commands() else "")
            return True
        state.message = "Matches: " + " ".join(matches)
        return True

    cmd, rest = cmdline.split(" ", 1)
    if cmd not in path_commands():
        return True
    if rest.rstrip().endswith(os.sep + ".") or rest.strip() in (".", "./"):
        return True
    expanded = Path(rest).expanduser()
    base_dir = expanded.parent
    base_prefix = expanded.name
    if base_prefix.startswith("."):
        return True
    try:
        entries = sorted(base_dir.iterdir())
    except OSError:
        return True
    matches: list[str] = []
    display_matches: list[str] = []
    for entry in entries:
        if entry.name.startswith("."):
            continue
        if not entry.name.startswith(base_prefix):
            continue
        path = base_dir / entry.name
        matches.append(str(path))
        display_matches.append(str(path) + os.sep if path.is_dir() else str(path))
    if not matches:
        return True
    if len(matches) == 1:
        path = matches[0]
        if Path(path).is_dir():
            path = path + os.sep
        state.cmdline = f"{cmd} {path}"
        return True
    common = os.path.commonprefix(matches)
    if common and common != str(expanded):
        state.cmdline = f"{cmd} {common}"
        return True
    state.message = "Matches: " + " ".join(display_matches[:8])
    return True


def handle_command(state: EditorState, key: int, apply_command) -> bool:  # noqa: PLR0911, C901
    bindings = command_bindings(state)
    if key in bindings.escape:
        state.mode = "normal"
        state.cmdline = ""
        state.command_history_index = None
        return True
    if key in bindings.tab:
        return complete_command(state)
    if key in bindings.backspace:
        state.cmdline = state.cmdline[:-1]
        return True
    if key in bindings.history_up:
        prev = history_prev(state)
        if prev is not None:
            state.cmdline = prev
        return True
    if key in bindings.history_down:
        nxt = history_next(state)
        if nxt is not None:
            state.cmdline = nxt
        return True
    if key in bindings.enter:
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
    bindings = search_bindings(state)
    if key in bindings.escape:
        state.mode = "normal"
        state.searchline = ""
        return True
    if key in bindings.backspace:
        state.searchline = state.searchline[:-1]
        return True
    if key in bindings.enter:
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
