from __future__ import annotations

import os
from pathlib import Path

from oud.editor.insert_session import set_mode
from oud.editor.keymap import command_bindings, search_bindings
from oud.editor.prompt_state import (
    command_history_commit,
    command_history_reset_nav,
    search_history_commit,
    search_history_reset_nav,
)
from oud.editor.prompt_state import (
    command_history_next as command_history_next_state,
)
from oud.editor.prompt_state import (
    command_history_prev as command_history_prev_state,
)
from oud.editor.settings_ops import (
    is_bool_set_token,
    set_key_names,
    set_preset_names,
    set_value_options,
)
from oud.editor.state import EditorState
from oud.tui.commands import command_names, no_space_commands, path_commands
from oud.tui.prompt import PromptBindings, update_prompt


def _prompt_bindings(bindings) -> PromptBindings:
    return PromptBindings(
        escape=bindings.escape,
        backspace=bindings.backspace,
        enter=bindings.enter,
        tab=getattr(bindings, "tab", ()),
        history_up=getattr(bindings, "history_up", ()),
        history_down=getattr(bindings, "history_down", ()),
    )


def history_prev(state: EditorState) -> str | None:
    return command_history_prev_state(state)


def history_next(state: EditorState) -> str | None:
    return command_history_next_state(state)


def complete_command_text(  # noqa: PLR0911, C901, PLR0912
    _state: EditorState,
    cmdline: str,
) -> tuple[str, str | None]:
    commands = command_names()
    if " " not in cmdline:
        if cmdline in commands and cmdline not in no_space_commands():
            return cmdline + " ", None
        matches = [cmd for cmd in commands if cmd.startswith(cmdline)]
        if not matches:
            return cmdline, None
        if len(matches) == 1:
            match = matches[0]
            return match + (" " if match not in no_space_commands() else ""), None
        return cmdline, "Matches: " + " ".join(matches)

    cmd, rest = cmdline.split(" ", 1)
    if cmd == "set":
        keys = sorted(set(set_key_names()))
        presets = list(set_preset_names())
        token = rest.strip()
        if not token:
            options = sorted(keys + presets)
            return cmdline, "Options: " + " ".join(options[:8])
        if "=" in token:
            key, value_prefix = token.split("=", 1)
            if not key:
                return cmdline, None
            options = [opt for opt in set_value_options(key) if opt.startswith(value_prefix)]
            if not options:
                return cmdline, None
            if len(options) == 1:
                return f"{cmd} {key}={options[0]}", None
            common = os.path.commonprefix(options)
            if common and common != value_prefix:
                return f"{cmd} {key}={common}", None
            return cmdline, "Options: " + " ".join(options[:8])
        matches = sorted([key for key in keys if key.startswith(token)])
        matches.extend([name for name in presets if name.startswith(token)])
        if not matches:
            return cmdline, None
        if len(matches) == 1:
            match = matches[0]
            if match in presets:
                return f"{cmd} {match} ", None
            if is_bool_set_token(match):
                return f"{cmd} {match} ", None
            return f"{cmd} {match}=", None
        return cmdline, "Options: " + " ".join(matches[:8])
    if cmd not in path_commands():
        return cmdline, None
    if rest.rstrip().endswith(os.sep + ".") or rest.strip() in (".", "./"):
        return cmdline, None
    expanded = Path(rest).expanduser()
    if rest.endswith(os.sep) and expanded.is_dir():
        base_dir = expanded
        base_prefix = ""
    else:
        base_dir = expanded.parent
        base_prefix = expanded.name
    if base_prefix.startswith("."):
        return cmdline, None
    try:
        entries = sorted(base_dir.iterdir())
    except OSError:
        return cmdline, None
    matches: list[str] = []
    display_matches: list[str] = []
    for entry in entries:
        if entry.name.startswith("."):
            continue
        if not entry.name.startswith(base_prefix):
            continue
        path = base_dir / entry.name
        if path.is_file():
            name = entry.name.lower()
            if not name.endswith((".tab", ".ft3", ".ft3.gz")):
                continue
        matches.append(str(path))
        display_matches.append(str(path) + os.sep if path.is_dir() else str(path))
    if not matches:
        return cmdline, None
    if len(matches) == 1:
        path = matches[0]
        if Path(path).is_dir():
            path = path + os.sep
        return f"{cmd} {path}", None
    common = os.path.commonprefix(matches)
    if common and common != str(expanded):
        new_cmdline = f"{cmd} {common}"
        if new_cmdline != cmdline:
            return new_cmdline, None
    return cmdline, "Matches: " + " ".join(display_matches[:8])


def complete_command(state: EditorState) -> bool:
    new_text, message = complete_command_text(state, state.cmdline)
    state.cmdline = new_text
    if message:
        state.message = message
    return True


def handle_command(state: EditorState, key: int, apply_command) -> bool:
    bindings = command_bindings(state)
    prompt_bindings = _prompt_bindings(bindings)

    def _complete(text: str) -> tuple[str, str | None]:
        return complete_command_text(state, text)

    result = update_prompt(
        state.cmdline,
        key,
        prompt_bindings,
        history=state.command_history,
        history_index=state.command_history_index,
        on_complete=_complete if key in bindings.tab else None,
    )
    if result.message:
        state.message = result.message
    state.cmdline = result.text
    state.command_history_index = result.history_index
    if result.cancel:
        set_mode(state, "normal")
        state.cmdline = ""
        command_history_reset_nav(state)
        return True
    if result.submit:
        cmd = state.cmdline
        state.cmdline = ""
        set_mode(state, "normal")
        command_history_commit(state, cmd)
        apply_command(state, cmd)
        return True
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
    prompt_bindings = _prompt_bindings(bindings)
    result = update_prompt(
        state.searchline,
        key,
        prompt_bindings,
        history=state.search_history,
        history_index=state.search_history_index,
    )
    state.searchline = result.text
    state.search_history_index = result.history_index
    if result.cancel:
        set_mode(state, "normal")
        state.searchline = ""
        search_history_reset_nav(state)
        return True
    if result.submit:
        search_text = state.searchline
        target = parse_search(search_text)
        state.searchline = ""
        set_mode(state, "normal")
        search_history_commit(state, search_text)
        if target is None:
            state.message = "Invalid bar"
            return True
        state.cursor_bar = max(0, min(target, len(state.piece.bars) - 1))
        state.cursor_col = 0
        return True
    return True
