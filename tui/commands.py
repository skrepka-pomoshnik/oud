# ruff: noqa: PLC0415
from __future__ import annotations

import copy
import shutil
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from editor.command_ops import (
    apply_set_command,
    convert_overrides,
    parse_time_signature,
    tuning_preset_value,
)
from editor.command_ops import (
    cmd_bar as _cmd_bar,
)
from editor.command_ops import (
    cmd_open as _cmd_open,
)
from editor.command_ops import (
    cmd_stave as _cmd_stave,
)
from editor.command_ops import (
    cmd_time as _cmd_time,
)
from editor.commands import (
    cmd_author,
    cmd_composer,
    cmd_footnote,
    cmd_header_template,
    cmd_subtitle,
    cmd_title,
)
from editor.edit_ops import record_action
from editor.ops import delete_chord, insert_chord
from editor.plugin_ops import enter_plugin_mode
from editor.state import EditorState, UndoAction
from editor.verify_ops import verify_bar
from exports.export_tab import export_ascii, export_tab_to_file
from exports.lilypond import export_lilypond, print_lilypond_pdf
from exports.midi import _midi_command, export_midi, play_midi
from settings import save_settings


def _tuning_preset(value: str) -> str | None:
    return tuning_preset_value(value)


def _parse_time_sig_value(text: str) -> tuple[int, int] | None:
    return parse_time_signature(text)


def start_midi(state: EditorState, start_bar: int | None = None, path: str | None = None) -> None:
    if state.midi_proc is not None and state.midi_proc.poll() is None:
        state.midi_proc.terminate()
        state.midi_proc = None
    if path is None:
        base = Path(state.path) if state.path else Path("out")
        path = str(base.with_suffix(".mid"))
    start_bar = state.cursor_bar if start_bar is None else start_bar
    try:
        bpm = int(state.settings.get("tempo", "90") or "90")
    except ValueError:
        bpm = 90
    state.message = export_midi(
        path,
        state.piece,
        state.overrides,
        state.durations,
        state.bar_width,
        settings=state.settings,
        bpm=bpm,
        start_bar=start_bar,
        dotted=state.dotted,
    )
    soundfont = state.settings.get("soundfont", "") or None
    state.message, state.midi_proc = play_midi(path, soundfont=soundfont)


def cmd_open(state: EditorState, args: str) -> None:
    _cmd_open(state, args)


def cmd_set(state: EditorState, args: str, config_path: str) -> None:
    apply_set_command(state, args.strip(), config_path)


def cmd_convert(state: EditorState, args: str, config_path: str) -> None:
    target = args.strip()
    if target not in ("french", "italian"):
        state.message = "Convert target must be french or italian"
        return
    convert_overrides(state, target)
    state.settings["style"] = target
    save_settings(config_path, state.settings)


def cmd_ascii(state: EditorState, args: str) -> None:
    value = args.strip()
    if value not in ("on", "off"):
        state.message = "Ascii must be on/off"
        return
    state.ascii_preview = value == "on"
    state.message = f"Ascii preview {value}"


def cmd_midi(state: EditorState, args: str, config_path: str) -> None:
    target = args.strip()
    if target:
        path = target
    else:
        base = Path(state.path) if state.path else Path("out")
        path = str(base.with_suffix(".mid"))
    state.message = export_midi(
        path,
        state.piece,
        state.overrides,
        state.durations,
        state.bar_width,
        settings=state.settings,
        dotted=state.dotted,
    )
    save_settings(config_path, state.settings)


def cmd_lilypond(state: EditorState, args: str, config_path: str) -> None:
    target = args.strip()
    if target:
        path = target
    else:
        base = Path(state.path) if state.path else Path("out")
        path = str(base.with_suffix(".ly"))
    state.message = export_lilypond(
        path,
        state.piece,
        state.overrides,
        state.durations,
        state.bar_width,
        settings=state.settings,
    )
    save_settings(config_path, state.settings)


def cmd_pdf(state: EditorState, _args: str, config_path: str) -> None:
    cmd_lilypond(state, "", config_path)
    state.message = print_lilypond_pdf(state.path or "out.ly")


def cmd_play(state: EditorState, args: str, config_path: str) -> None:
    parts = args.split()
    start = int(parts[0]) - 1 if parts and parts[0].isdigit() else None
    tempo = parts[1] if len(parts) > 1 else None
    if tempo:
        state.settings["tempo"] = tempo
    start_midi(state, start_bar=start)
    save_settings(config_path, state.settings)


def cmd_orn(state: EditorState, args: str) -> None:
    _set_ornament(state, args.strip())


def cmd_annot(state: EditorState, args: str) -> None:
    _set_annotation(state, args.strip())


def cmd_highlight(state: EditorState, args: str) -> None:
    _set_highlight(state, args.strip())


def cmd_chord(state: EditorState, args: str) -> None:
    value = args.strip()
    if value in ("ins", "insert"):
        bar = state.piece.bars[state.cursor_bar]
        prev = copy.deepcopy(bar.chords)
        insert_chord(bar, state.bar_width, state.cursor_col)
        record_action(
            state,
            UndoAction(
                kind="chords",
                data={"bar": state.cursor_bar, "prev": prev, "new": bar.chords},
            ),
        )
        return
    if value in ("del", "delete", "remove"):
        bar = state.piece.bars[state.cursor_bar]
        prev = copy.deepcopy(bar.chords)
        if delete_chord(bar, state.bar_width, state.cursor_col):
            record_action(
                state,
                UndoAction(
                    kind="chords",
                    data={"bar": state.cursor_bar, "prev": prev, "new": bar.chords},
                ),
            )
        return
    state.message = "Chord action: insert/delete"


def cmd_midicmd(state: EditorState, _args: str) -> None:
    path = state.path or "out.mid"
    soundfont = state.settings.get("soundfont", "") or None
    cmd = _midi_command(
        path=path,
        soundfont=soundfont,
        platform=sys.platform,
        fluidsynth=shutil.which("fluidsynth"),
        timidity=shutil.which("timidity"),
        opener=shutil.which("open") if sys.platform == "darwin" else None,
    )
    state.message = " ".join(cmd) if cmd else "No MIDI player"


def cmd_source(state: EditorState, args: str) -> None:
    target = args.strip() or state.path
    if not target:
        state.message = "No source path"
        return
    viewer = shutil.which("less")
    if not viewer:
        state.message = "Missing less"
        return
    subprocess.run([viewer, target], check=False)  # noqa: S603


def cmd_info(state: EditorState, _args: str) -> None:
    state.mode = "info"
    state.info_offset = 0


def cmd_plugins(state: EditorState, _args: str) -> None:
    enter_plugin_mode(state)


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
    value = args.strip()
    if value not in ("thin", "thick", "double", "hidden", "pale"):
        state.message = "Barline must be thin/thick/double/hidden/pale"
        return
    _set_barline(state, value)


def cmd_repeat(state: EditorState, args: str) -> None:
    value = args.strip()
    if value not in ("none", "start", "end", "dots"):
        state.message = "Repeat must be none/start/end/dots"
        return
    _set_repeat(state, value)


def cmd_tool(state: EditorState, args: str, config_path: str) -> None:
    action = args.strip() or "reflow"
    if action == "reflow":
        prev = set(state.stave_breaks)
        state.stave_breaks.clear()
        record_action(
            state,
            UndoAction(
                kind="stave-breaks",
                data={"prev": prev, "new": set(state.stave_breaks)},
            ),
        )
        state.message = "Reflowed (breaks cleared)"
        return
    if action == "gridflags":
        current = state.settings.get("flagstyle", "standard")
        next_value = "board" if current != "board" else "standard"
        state.settings["flagstyle"] = next_value
        save_settings(config_path, state.settings)
        state.message = f"Flagstyle {next_value}"
        return
    if action == "comments":
        prev = dict(state.annotations)
        state.annotations.clear()
        record_action(
            state,
            UndoAction(
                kind="annotations-all",
                data={"prev": prev, "new": dict(state.annotations)},
            ),
        )
        state.message = "Annotations cleared"
        return
    state.message = "Tool: reflow|gridflags|comments"


def cmd_time(state: EditorState, args: str) -> None:
    _cmd_time(state, args)


def cmd_verify(state: EditorState, _args: str) -> None:
    state.message = verify_bar(state, state.cursor_bar)


def cmd_undo(state: EditorState, _args: str, config_path: str) -> None:
    from editor.undo_ops import undo

    undo(state, config_path=config_path)


def cmd_redo(state: EditorState, _args: str, config_path: str) -> None:
    from editor.undo_ops import redo

    redo(state, config_path=config_path)


def cmd_write(state: EditorState, args: str) -> None:
    path = args.strip()
    if not path and state.path:
        path = state.path if state.path.endswith(".tab") else state.path + ".tab"
    if not path:
        state.message = "No path for write"
        return
    export_tab_to_file(
        path,
        state.piece,
        state.overrides,
        state.durations,
        state.bar_width,
        settings=state.settings,
        dotted=state.dotted,
        ornaments=state.ornaments,
        annotations=state.annotations,
        slurs=state.slurs,
        ties=state.ties,
        holds=state.holds,
    )
    state.modified = False
    state.message = f"Wrote {path}"


def cmd_write_ascii(state: EditorState, args: str) -> None:
    path = args.strip()
    if not path and state.path:
        path = state.path if state.path.endswith(".txt") else state.path + ".txt"
    if not path:
        state.message = "No path for wa"
        return
    content = export_ascii(
        state.piece,
        state.overrides,
        state.durations,
        state.bar_width,
        settings=state.settings,
        ornaments=state.ornaments,
        annotations=state.annotations,
        slurs=state.slurs,
        ties=state.ties,
        holds=state.holds,
    )
    with Path(path).open("w", encoding="utf-8") as f:
        f.write(content)
    state.modified = False
    state.message = f"Wrote {path}"


def _set_ornament(state: EditorState, value: str) -> None:
    from editor.command_ops import set_ornament

    set_ornament(state, value)


def _set_annotation(state: EditorState, value: str) -> None:
    from editor.command_ops import set_annotation

    set_annotation(state, value)


def _set_highlight(state: EditorState, value: str) -> None:
    from editor.command_ops import set_highlight

    set_highlight(state, value)


def _set_slur(state: EditorState, value: str) -> None:
    from editor.command_ops import set_slur

    set_slur(state, value)


def _set_tie(state: EditorState, value: str) -> None:
    from editor.command_ops import set_tie

    set_tie(state, value)


def _set_hold(state: EditorState, value: str) -> None:
    from editor.command_ops import set_hold

    set_hold(state, value)


def _set_barline(state: EditorState, value: str) -> None:
    from editor.command_ops import set_barline

    set_barline(state, value)


def _set_repeat(state: EditorState, value: str) -> None:
    from editor.command_ops import set_repeat

    set_repeat(state, value)


def apply_command(state: EditorState, cmdline: str, config_path: str) -> None:
    cmdline = cmdline.strip()
    if not cmdline:
        return
    if cmdline in ("q", "quit"):
        if state.modified and not state.pending_quit:
            state.pending_quit = True
            state.message = "Unsaved changes. Use :q! to quit or :w to save."
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
