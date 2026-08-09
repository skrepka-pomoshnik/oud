from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from oud.editor.commands.handlers.settings import (
    is_bool_set_token,
    set_key_names,
    set_preset_names,
    set_value_options,
)
from oud.editor.core.state import EditorState
from oud.presentation.tui.commands import command_names, no_space_commands, path_commands

Completion = tuple[str, str | None]


def _complete_command_name(cmdline: str, commands: list[str]) -> Completion:
    if cmdline in commands and cmdline not in no_space_commands():
        return cmdline + " ", None
    matches = [cmd for cmd in commands if cmd.startswith(cmdline)]
    if not matches:
        return cmdline, None
    if len(matches) == 1:
        match = matches[0]
        return match + (" " if match not in no_space_commands() else ""), None
    return cmdline, "Matches: " + " ".join(matches)


def _complete_set_value(cmd: str, key: str, value_prefix: str, cmdline: str) -> Completion:
    if not key:
        return cmdline, None
    options = [option for option in set_value_options(key) if option.startswith(value_prefix)]
    if not options:
        return cmdline, None
    if len(options) == 1:
        return f"{cmd} {key}={options[0]}", None
    common = os.path.commonprefix(options)
    if common and common != value_prefix:
        return f"{cmd} {key}={common}", None
    return cmdline, "Options: " + " ".join(options)


def _complete_set_token(cmd: str, token: str, cmdline: str, keys: list[str], presets: list[str]) -> Completion:
    matches = sorted(key for key in keys if key.startswith(token))
    matches.extend(name for name in presets if name.startswith(token))
    if not matches:
        return cmdline, None
    if len(matches) != 1:
        return cmdline, "Options: " + " ".join(matches)
    match = matches[0]
    if match in presets or is_bool_set_token(match):
        return f"{cmd} {match} ", None
    return f"{cmd} {match}=", None


def _complete_set(cmd: str, rest: str, cmdline: str) -> Completion:
    keys = sorted(set(set_key_names()))
    presets = list(set_preset_names())
    token = rest.strip()
    if not token:
        return cmdline, "Options: " + " ".join(sorted(keys + presets))
    if "=" in token:
        key, value_prefix = token.split("=", 1)
        return _complete_set_value(cmd, key, value_prefix, cmdline)
    return _complete_set_token(cmd, token, cmdline, keys, presets)


def _path_completion_base(rest: str) -> tuple[Path, str, Path] | None:
    if rest.rstrip().endswith(os.sep + ".") or rest.strip() in (".", "./"):
        return None
    expanded = Path(rest).expanduser()
    if rest.endswith(os.sep) and expanded.is_dir():
        return expanded, "", expanded
    if expanded.name.startswith("."):
        return None
    return expanded.parent, expanded.name, expanded


def _path_entries(base_dir: Path) -> list[Path]:
    entries: list[Path] = []
    for entry in sorted(base_dir.iterdir()):
        if entry.name.startswith("."):
            continue
        if entry.is_file() and not entry.name.lower().endswith((".tab", ".ft3", ".ft3.gz")):
            continue
        entries.append(entry)
    return entries


def _fzf_filter(candidates: list[str], query: str) -> tuple[list[str] | None, str | None]:
    executable = shutil.which("fzf")
    if executable is None:
        return None, "fzf is not installed; using prefix completion"
    try:
        result = subprocess.run(  # noqa: S603 - resolved executable receives fixed non-interactive arguments
            [executable, "--filter", query],
            input="\n".join(candidates),
            capture_output=True,
            check=False,
            text=True,
            timeout=2,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None, "fzf failed; using prefix completion"
    if result.returncode not in (0, 1):
        return None, "fzf failed; using prefix completion"
    known = set(candidates)
    return [line for line in result.stdout.splitlines() if line in known], None


def _matching_path_entries(
    state: EditorState,
    entries: list[Path],
    prefix: str,
) -> tuple[list[Path], str | None]:
    if state.settings.get("completion", "prefix") != "fzf":
        return [entry for entry in entries if entry.name.startswith(prefix)], None
    ranked, diagnostic = _fzf_filter([entry.name for entry in entries], prefix)
    if ranked is None:
        return [entry for entry in entries if entry.name.startswith(prefix)], diagnostic
    by_name = {entry.name: entry for entry in entries}
    return [by_name[name] for name in ranked], diagnostic


def _completion_message(entries: list[Path], diagnostic: str | None) -> str:
    display = [str(entry) + os.sep if entry.is_dir() else str(entry) for entry in entries]
    matches = "Matches: " + " ".join(display)
    return f"{diagnostic}; {matches}" if diagnostic else matches


def _complete_path_entries(
    state: EditorState,
    cmd: str,
    cmdline: str,
    *,
    expanded: Path,
    entries: list[Path],
    diagnostic: str | None,
) -> Completion:
    if not entries:
        return cmdline, diagnostic
    if len(entries) == 1:
        suffix = os.sep if entries[0].is_dir() else ""
        return f"{cmd} {entries[0]}{suffix}", diagnostic
    if state.settings.get("completion", "prefix") == "fzf":
        return cmdline, _completion_message(entries, diagnostic)
    common = os.path.commonprefix([str(entry) for entry in entries])
    if common and common != str(expanded):
        completed = f"{cmd} {common}"
        if completed != cmdline:
            return completed, diagnostic
    return cmdline, _completion_message(entries, diagnostic)


def _complete_path(state: EditorState, cmd: str, rest: str, cmdline: str) -> Completion:
    base = _path_completion_base(rest)
    if base is None:
        return cmdline, None
    base_dir, base_prefix, expanded = base
    try:
        entries, diagnostic = _matching_path_entries(state, _path_entries(base_dir), base_prefix)
    except OSError:
        return cmdline, None
    return _complete_path_entries(
        state,
        cmd,
        cmdline,
        expanded=expanded,
        entries=entries,
        diagnostic=diagnostic,
    )


def complete_command_text(state: EditorState, cmdline: str) -> Completion:
    commands = command_names()
    if " " not in cmdline:
        return _complete_command_name(cmdline, commands)
    cmd, rest = cmdline.split(" ", 1)
    if cmd == "set":
        return _complete_set(cmd, rest, cmdline)
    if cmd in path_commands():
        return _complete_path(state, cmd, rest, cmdline)
    return cmdline, None
