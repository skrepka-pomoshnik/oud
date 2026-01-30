# ruff: noqa: PLC0415
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache

from oud.editor.command_ops import (
    apply_set_command,
    cmd_ascii,
    cmd_convert,
    cmd_lilypond,
    cmd_midi,
    cmd_midicmd_default,
    cmd_pdf,
    cmd_play,
    cmd_write_ascii_default,
    cmd_write_default,
    parse_time_signature,
    tuning_preset_value,
)
from oud.editor.command_ops import (
    cmd_bar as _cmd_bar,
)
from oud.editor.command_ops import (
    cmd_barline as _cmd_barline,
)
from oud.editor.command_ops import (
    cmd_chord as _cmd_chord,
)
from oud.editor.command_ops import (
    cmd_info as _cmd_info,
)
from oud.editor.command_ops import (
    cmd_open as _cmd_open,
)
from oud.editor.command_ops import (
    cmd_plugins as _cmd_plugins,
)
from oud.editor.command_ops import (
    cmd_repeat as _cmd_repeat,
)
from oud.editor.command_ops import (
    cmd_source as _cmd_source,
)
from oud.editor.command_ops import (
    cmd_stave as _cmd_stave,
)
from oud.editor.command_ops import (
    cmd_time as _cmd_time,
)
from oud.editor.command_ops import (
    cmd_tool as _cmd_tool,
)
from oud.editor.command_ops import (
    cmd_verify as _cmd_verify,
)
from oud.editor.commands import (
    cmd_author,
    cmd_composer,
    cmd_footnote,
    cmd_header_template,
    cmd_subtitle,
    cmd_title,
)
from oud.editor.messages import UNSAVED_QUIT_CMD
from oud.editor.state import EditorState


def _tuning_preset(value: str) -> str | None:
    return tuning_preset_value(value)


def _parse_time_sig_value(text: str) -> tuple[int, int] | None:
    return parse_time_signature(text)


def cmd_open(state: EditorState, args: str) -> None:
    _cmd_open(state, args)


def cmd_set(state: EditorState, args: str, config_path: str) -> None:
    apply_set_command(state, args.strip(), config_path)


def cmd_orn(state: EditorState, args: str) -> None:
    _set_ornament(state, args.strip())


def cmd_annot(state: EditorState, args: str) -> None:
    _set_annotation(state, args.strip())


def cmd_highlight(state: EditorState, args: str) -> None:
    _set_highlight(state, args.strip())


def cmd_chord(state: EditorState, args: str) -> None:
    _cmd_chord(state, args)


def cmd_midicmd(state: EditorState, _args: str) -> None:
    cmd_midicmd_default(state, _args)


def cmd_source(state: EditorState, args: str) -> None:
    _cmd_source(state, args)


def cmd_info(state: EditorState, _args: str) -> None:
    _cmd_info(state)


def cmd_plugins(state: EditorState, _args: str) -> None:
    _cmd_plugins(state)


def cmd_bar(state: EditorState, args: str) -> None:
    _cmd_bar(state, args)


def cmd_stave(state: EditorState, args: str) -> None:
    _cmd_stave(state, args)


def cmd_slur(state: EditorState, args: str) -> None:
    _set_slur(state, args.strip())


def cmd_tie(state: EditorState, args: str) -> None:
    _set_tie(state, args.strip())


def cmd_hold(state: EditorState, args: str) -> None:
    _set_hold(state, args.strip())


def cmd_barline(state: EditorState, args: str) -> None:
    _cmd_barline(state, args.strip())


def cmd_repeat(state: EditorState, args: str) -> None:
    _cmd_repeat(state, args.strip())


def cmd_tool(state: EditorState, args: str, config_path: str) -> None:
    _cmd_tool(state, args, config_path)


def cmd_time(state: EditorState, args: str) -> None:
    _cmd_time(state, args)


def cmd_verify(state: EditorState, _args: str) -> None:
    _cmd_verify(state)


def cmd_undo(state: EditorState, _args: str, config_path: str) -> None:
    from oud.editor.undo_ops import undo

    undo(state, config_path=config_path)


def cmd_redo(state: EditorState, _args: str, config_path: str) -> None:
    from oud.editor.undo_ops import redo

    redo(state, config_path=config_path)


def cmd_write(state: EditorState, args: str) -> None:
    cmd_write_default(state, args)


def cmd_write_ascii(state: EditorState, args: str) -> None:
    cmd_write_ascii_default(state, args)


def _set_ornament(state: EditorState, value: str) -> None:
    from oud.editor.command_ops import set_ornament

    set_ornament(state, value)


def _set_annotation(state: EditorState, value: str) -> None:
    from oud.editor.command_ops import set_annotation

    set_annotation(state, value)


def _set_highlight(state: EditorState, value: str) -> None:
    from oud.editor.command_ops import set_highlight

    set_highlight(state, value)


def _set_slur(state: EditorState, value: str) -> None:
    from oud.editor.command_ops import set_slur

    set_slur(state, value)


def _set_tie(state: EditorState, value: str) -> None:
    from oud.editor.command_ops import set_tie

    set_tie(state, value)


def _set_hold(state: EditorState, value: str) -> None:
    from oud.editor.command_ops import set_hold

    set_hold(state, value)


def _set_barline(state: EditorState, value: str) -> None:
    from oud.editor.command_ops import set_barline

    set_barline(state, value)


def _set_repeat(state: EditorState, value: str) -> None:
    from oud.editor.command_ops import set_repeat

    set_repeat(state, value)


def apply_command(state: EditorState, cmdline: str, config_path: str) -> None:
    cmdline = cmdline.strip()
    if not cmdline:
        return
    if cmdline in ("q", "quit"):
        if state.modified and not state.pending_quit:
            state.pending_quit = True
            state.message = UNSAVED_QUIT_CMD
            return
        raise SystemExit(0)
    if cmdline in ("q!", "quit!"):
        raise SystemExit(0)
    cmd, *rest = cmdline.split(maxsplit=1)
    args = rest[0] if rest else ""
    handler = _command_map().get(cmd)
    if handler is None:
        if cmd in ("wq", "x"):
            cmd_write(state, args)
            if state.message.startswith("Wrote "):
                raise SystemExit(0)
            return
        state.message = f"Unknown command: {cmdline}"
        return
    handler(state, args, config_path)


@dataclass(frozen=True)
class CommandSpec:
    name: str
    handler: Callable[[EditorState, str, str], None]
    takes_path: bool = False


def _no_config(func: Callable[[EditorState, str], None]) -> Callable[[EditorState, str, str], None]:
    def _handler(state: EditorState, args: str, _config_path: str) -> None:
        func(state, args)

    return _handler


def _with_config(
    func: Callable[[EditorState, str, str], None],
) -> Callable[[EditorState, str, str], None]:
    def _handler(state: EditorState, args: str, config_path: str) -> None:
        func(state, args, config_path)

    return _handler


@lru_cache(maxsize=1)
def _command_specs() -> tuple[CommandSpec, ...]:
    return (
        CommandSpec("e", _no_config(cmd_open), takes_path=True),
        CommandSpec("w", _no_config(cmd_write), takes_path=True),
        CommandSpec("wa", _no_config(cmd_write_ascii), takes_path=True),
        CommandSpec("wascii", _no_config(cmd_write_ascii), takes_path=True),
        CommandSpec("writeascii", _no_config(cmd_write_ascii), takes_path=True),
        CommandSpec("saveascii", _no_config(cmd_write_ascii), takes_path=True),
        CommandSpec("write", _no_config(cmd_write), takes_path=True),
        CommandSpec("ascii", _no_config(cmd_ascii)),
        CommandSpec("midi", _with_config(cmd_midi), takes_path=True),
        CommandSpec("play", _with_config(cmd_play)),
        CommandSpec("lilypond", _with_config(cmd_lilypond), takes_path=True),
        CommandSpec("pdf", _with_config(cmd_pdf), takes_path=True),
        CommandSpec("print", _with_config(cmd_pdf), takes_path=True),
        CommandSpec("set", _with_config(cmd_set)),
        CommandSpec("convert", _with_config(cmd_convert)),
        CommandSpec("time", _no_config(cmd_time)),
        CommandSpec("timesig", _no_config(cmd_time)),
        CommandSpec("verify", _no_config(cmd_verify)),
        CommandSpec("title", _no_config(cmd_title)),
        CommandSpec("author", _no_config(cmd_author)),
        CommandSpec("composer", _no_config(cmd_composer)),
        CommandSpec("subtitle", _no_config(cmd_subtitle)),
        CommandSpec("footnote", _no_config(cmd_footnote)),
        CommandSpec("header", _no_config(cmd_header_template)),
        CommandSpec("undo", _with_config(cmd_undo)),
        CommandSpec("redo", _with_config(cmd_redo)),
        CommandSpec("orn", _no_config(cmd_orn)),
        CommandSpec("annot", _no_config(cmd_annot)),
        CommandSpec("highlight", _no_config(cmd_highlight)),
        CommandSpec("midicmd", _no_config(cmd_midicmd)),
        CommandSpec("source", _no_config(cmd_source)),
        CommandSpec("info", _no_config(cmd_info)),
        CommandSpec("plugins", _no_config(cmd_plugins)),
        CommandSpec("bar", _no_config(cmd_bar)),
        CommandSpec("chord", _no_config(cmd_chord)),
        CommandSpec("stave", _no_config(cmd_stave)),
        CommandSpec("slur", _no_config(cmd_slur)),
        CommandSpec("tie", _no_config(cmd_tie)),
        CommandSpec("hold", _no_config(cmd_hold)),
        CommandSpec("barline", _no_config(cmd_barline)),
        CommandSpec("repeat", _no_config(cmd_repeat)),
        CommandSpec("tool", _with_config(cmd_tool)),
    )


@lru_cache(maxsize=1)
def _command_map() -> dict[str, Callable[[EditorState, str, str], None]]:
    return {spec.name: spec.handler for spec in _command_specs()}


def command_names() -> list[str]:
    return [spec.name for spec in _command_specs()] + ["q", "quit"]


def path_commands() -> set[str]:
    return {spec.name for spec in _command_specs() if spec.takes_path}


def no_space_commands() -> set[str]:
    return {"q", "quit"}
