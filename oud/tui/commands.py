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
    cmd_musicxml,
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
    cmd_col as _cmd_col,
)
from oud.editor.command_ops import (
    cmd_cursor as _cmd_cursor,
)
from oud.editor.command_ops import (
    cmd_ending as _cmd_ending,
)
from oud.editor.command_ops import (
    cmd_info as _cmd_info,
)
from oud.editor.command_ops import (
    cmd_notes as _cmd_notes,
)
from oud.editor.command_ops import (
    cmd_open as _cmd_open,
)
from oud.editor.command_ops import (
    cmd_pause as _cmd_pause,
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
from oud.editor.command_ops import (
    cmd_vocal as _cmd_vocal,
)
from oud.editor.command_ops import (
    show_help as _show_help,
)
from oud.editor.commands import (
    cmd_author,
    cmd_composer,
    cmd_footnote,
    cmd_header_template,
    cmd_subtitle,
    cmd_title,
)
from oud.editor.messages import READ_ONLY_VIEWER, UNSAVED_QUIT_CMD, MessageLevel
from oud.editor.state import EditorState

READ_ONLY_BLOCKED_COMMANDS = frozenset(
    {
        "w",
        "write",
        "set",
        "convert",
        "time",
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
        "bar",
        "chord",
        "stave",
        "slur",
        "tie",
        "hold",
        "barline",
        "repeat",
        "ending",
        "dynamic",
        "fermata",
        "arpeggio",
        "separee",
        "tuplet",
        "transpose",
        "retune",
        "courseshift",
        "tool",
        "vocal",
    },
)


def _readonly_block_message(state: EditorState) -> None:
    state.message = f"{READ_ONLY_VIEWER}: command disabled"


def _tuning_preset(value: str) -> str | None:
    return tuning_preset_value(value)


def _parse_time_sig_value(text: str) -> tuple[int, int] | None:
    return parse_time_signature(text)


def cmd_open(state: EditorState, args: str) -> None:
    _cmd_open(state, args)


def cmd_set(state: EditorState, args: str, config_path: str) -> None:
    apply_set_command(state, args.strip(), config_path)


def cmd_dark(state: EditorState, _args: str, config_path: str) -> None:
    apply_set_command(state, "theme=dark", config_path)


def cmd_light(state: EditorState, _args: str, config_path: str) -> None:
    apply_set_command(state, "theme=light", config_path)


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


def cmd_help(state: EditorState, _args: str) -> None:
    _show_help(state)


def cmd_info(state: EditorState, _args: str) -> None:
    _cmd_info(state)


def cmd_ack(state: EditorState, _args: str) -> None:
    state.persistent_notice = ""
    state.persistent_notice_level = MessageLevel.INFO
    state.message = "Notice acknowledged"


def cmd_notes(state: EditorState, _args: str) -> None:
    _cmd_notes(state)


def cmd_plugins(state: EditorState, _args: str) -> None:
    _cmd_plugins(state)


def cmd_bar(state: EditorState, args: str) -> None:
    _cmd_bar(state, args)


def cmd_stave(state: EditorState, args: str) -> None:
    _cmd_stave(state, args)


def cmd_col(state: EditorState, args: str) -> None:
    _cmd_col(state, args)


def cmd_cursor(state: EditorState, args: str) -> None:
    _cmd_cursor(state, args)


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


def cmd_ending(state: EditorState, args: str) -> None:
    _cmd_ending(state, args.strip())


def cmd_dynamic(state: EditorState, args: str) -> None:
    from oud.editor.command_ops import cmd_dynamic as _cmd_dynamic_local

    _cmd_dynamic_local(state, args.strip())


def cmd_fermata(state: EditorState, args: str) -> None:
    from oud.editor.command_ops import cmd_fermata as _cmd_fermata_local

    _cmd_fermata_local(state, args.strip())


def cmd_arpeggio(state: EditorState, args: str) -> None:
    from oud.editor.command_ops import cmd_arpeggio as _cmd_arpeggio_local

    _cmd_arpeggio_local(state, args.strip())


def cmd_separee(state: EditorState, args: str) -> None:
    from oud.editor.command_ops import cmd_separee as _cmd_separee_local

    _cmd_separee_local(state, args.strip())


def cmd_tuplet(state: EditorState, args: str) -> None:
    from oud.editor.command_ops import cmd_tuplet as _cmd_tuplet_local

    _cmd_tuplet_local(state, args.strip())


def cmd_transpose(state: EditorState, args: str) -> None:
    from oud.editor.command_ops import cmd_transpose as _cmd_transpose_local

    _cmd_transpose_local(state, args.strip())


def cmd_retune(state: EditorState, args: str) -> None:
    from oud.editor.command_ops import cmd_retune as _cmd_retune_local

    _cmd_retune_local(state, args.strip())


def cmd_courseshift(state: EditorState, args: str) -> None:
    from oud.editor.command_ops import cmd_courseshift as _cmd_courseshift_local

    _cmd_courseshift_local(state, args.strip())


def cmd_tool(state: EditorState, args: str, config_path: str) -> None:
    _cmd_tool(state, args, config_path)


def cmd_time(state: EditorState, args: str) -> None:
    _cmd_time(state, args)


def cmd_verify(state: EditorState, _args: str) -> None:
    _cmd_verify(state, _args)


def cmd_vocal(state: EditorState, args: str) -> None:
    _cmd_vocal(state, args)


def cmd_pause(state: EditorState, _args: str) -> None:
    _cmd_pause(state)


def cmd_undo(state: EditorState, _args: str, config_path: str) -> None:
    from oud.editor.undo_ops import undo

    undo(state, config_path=config_path)


def cmd_redo(state: EditorState, _args: str, config_path: str) -> None:
    from oud.editor.undo_ops import redo

    redo(state, config_path=config_path)


def cmd_write(state: EditorState, args: str) -> bool:
    return cmd_write_default(state, args)


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


def apply_command(state: EditorState, cmdline: str, config_path: str) -> None:  # noqa: C901
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
    if state.read_only and cmd in ("wq", "x"):
        _readonly_block_message(state)
        return
    if state.read_only and cmd in READ_ONLY_BLOCKED_COMMANDS:
        _readonly_block_message(state)
        return
    handler = _command_map().get(cmd)
    if handler is None:
        if cmd in ("wq", "x"):
            wrote = cmd_write_default(state, args, prompt_command=cmd)
            if wrote:
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


def _no_config(func: Callable[[EditorState, str], object]) -> Callable[[EditorState, str, str], None]:
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
        CommandSpec("write", _no_config(cmd_write), takes_path=True),
        CommandSpec("ascii", _no_config(cmd_ascii)),
        CommandSpec("midi", _with_config(cmd_midi), takes_path=True),
        CommandSpec("play", _with_config(cmd_play)),
        CommandSpec("pause", _no_config(cmd_pause)),
        CommandSpec("lilypond", _with_config(cmd_lilypond), takes_path=True),
        CommandSpec("musicxml", _with_config(cmd_musicxml), takes_path=True),
        CommandSpec("pdf", _with_config(cmd_pdf), takes_path=True),
        CommandSpec("print", _with_config(cmd_pdf), takes_path=True),
        CommandSpec("set", _with_config(cmd_set)),
        CommandSpec("dark", _with_config(cmd_dark)),
        CommandSpec("light", _with_config(cmd_light)),
        CommandSpec("convert", _with_config(cmd_convert)),
        CommandSpec("time", _no_config(cmd_time)),
        CommandSpec("verify", _no_config(cmd_verify)),
        CommandSpec("vocal", _no_config(cmd_vocal)),
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
        CommandSpec("help", _no_config(cmd_help)),
        CommandSpec("info", _no_config(cmd_info)),
        CommandSpec("ack", _no_config(cmd_ack)),
        CommandSpec("notes", _no_config(cmd_notes)),
        CommandSpec("plugins", _no_config(cmd_plugins)),
        CommandSpec("bar", _no_config(cmd_bar)),
        CommandSpec("cursor", _no_config(cmd_cursor)),
        CommandSpec("col", _no_config(cmd_col)),
        CommandSpec("chord", _no_config(cmd_chord)),
        CommandSpec("stave", _no_config(cmd_stave)),
        CommandSpec("slur", _no_config(cmd_slur)),
        CommandSpec("tie", _no_config(cmd_tie)),
        CommandSpec("hold", _no_config(cmd_hold)),
        CommandSpec("barline", _no_config(cmd_barline)),
        CommandSpec("repeat", _no_config(cmd_repeat)),
        CommandSpec("ending", _no_config(cmd_ending)),
        CommandSpec("dynamic", _no_config(cmd_dynamic)),
        CommandSpec("fermata", _no_config(cmd_fermata)),
        CommandSpec("arpeggio", _no_config(cmd_arpeggio)),
        CommandSpec("separee", _no_config(cmd_separee)),
        CommandSpec("tuplet", _no_config(cmd_tuplet)),
        CommandSpec("transpose", _no_config(cmd_transpose)),
        CommandSpec("retune", _no_config(cmd_retune)),
        CommandSpec("courseshift", _no_config(cmd_courseshift)),
        CommandSpec("tool", _with_config(cmd_tool)),
    )


@lru_cache(maxsize=1)
def _command_map() -> dict[str, Callable[[EditorState, str, str], None]]:
    return {spec.name: spec.handler for spec in _command_specs()}


def command_names() -> list[str]:
    return [spec.name for spec in _command_specs()] + ["q", "quit", "wq", "x"]


def path_commands() -> set[str]:
    return {spec.name for spec in _command_specs() if spec.takes_path} | {"wq", "x"}


def no_space_commands() -> set[str]:
    return {"q", "quit"}
