from __future__ import annotations

import shutil
import subprocess
import sys

from oud.editor.command_misc_ops import (
    cmd_col,
    cmd_cursor,
    cmd_verify,
    cmd_vocal,
    parse_time_signature,
    row_first_note_col,
    tuning_preset_value,
)
from oud.editor.command_notation_ops import (
    cmd_arpeggio,
    cmd_barline,
    cmd_dynamic,
    cmd_ending,
    cmd_fermata,
    cmd_repeat,
    cmd_separee,
    cmd_time,
    cmd_tuplet,
    set_annotation,
    set_barline,
    set_dynamic,
    set_ending,
    set_fermata,
    set_highlight,
    set_hold,
    set_ornament,
    set_repeat,
    set_slur,
    set_tie,
)
from oud.editor.file_ops import cmd_source as _cmd_source
from oud.editor.file_ops import cmd_write as _cmd_write
from oud.editor.file_ops import cmd_write_ascii as _cmd_write_ascii
from oud.editor.file_ops import cmd_write_ascii_default as _cmd_write_ascii_default
from oud.editor.file_ops import cmd_write_default as _cmd_write_default
from oud.editor.load_ops import cmd_open as _cmd_open
from oud.editor.media_ops import cmd_lilypond as _cmd_lilypond
from oud.editor.media_ops import cmd_midi as _cmd_midi
from oud.editor.media_ops import cmd_midicmd as _cmd_midicmd
from oud.editor.media_ops import cmd_midicmd_default as _cmd_midicmd_default
from oud.editor.media_ops import cmd_musicxml as _cmd_musicxml
from oud.editor.media_ops import cmd_play as _cmd_play
from oud.editor.media_ops import print_pdf as _print_pdf
from oud.editor.messages import NO_PATH
from oud.editor.score_ops import cmd_bar, cmd_chord, cmd_stave, paste_bar, yank_bar
from oud.editor.settings_ops import apply_set_command as _apply_set_command
from oud.editor.settings_ops import convert_overrides as _convert_overrides
from oud.editor.state import EditorState
from oud.editor.tool_ops import cmd_info as _cmd_info
from oud.editor.tool_ops import cmd_notes as _cmd_notes
from oud.editor.tool_ops import cmd_plugins as _cmd_plugins
from oud.editor.tool_ops import cmd_tool as _cmd_tool
from oud.editor.transform_ops import cmd_courseshift, cmd_retune, cmd_transpose
from oud.exports.lilypond import export_lilypond, print_lilypond_pdf
from oud.exports.midi import _midi_command, export_midi
from oud.exports.musicxml import export_musicxml, export_mxl
from oud.importers.ft3 import build_durations, load_ft3
from oud.importers.tab import load_tab, load_tab_data
from oud.settings import save_settings

__all__ = [
    "apply_set_command",
    "cmd_arpeggio",
    "cmd_ascii",
    "cmd_bar",
    "cmd_barline",
    "cmd_chord",
    "cmd_col",
    "cmd_convert",
    "cmd_courseshift",
    "cmd_cursor",
    "cmd_dynamic",
    "cmd_ending",
    "cmd_fermata",
    "cmd_info",
    "cmd_lilypond",
    "cmd_midi",
    "cmd_midicmd",
    "cmd_midicmd_default",
    "cmd_musicxml",
    "cmd_notes",
    "cmd_open",
    "cmd_pause",
    "cmd_pdf",
    "cmd_play",
    "cmd_plugins",
    "cmd_repeat",
    "cmd_retune",
    "cmd_separee",
    "cmd_source",
    "cmd_stave",
    "cmd_time",
    "cmd_tool",
    "cmd_transpose",
    "cmd_tuplet",
    "cmd_verify",
    "cmd_vocal",
    "cmd_write",
    "cmd_write_ascii",
    "cmd_write_ascii_default",
    "cmd_write_default",
    "convert_overrides",
    "parse_time_signature",
    "paste_bar",
    "print_pdf",
    "row_first_note_col",
    "set_annotation",
    "set_barline",
    "set_dynamic",
    "set_ending",
    "set_fermata",
    "set_highlight",
    "set_hold",
    "set_ornament",
    "set_repeat",
    "set_slur",
    "set_tie",
    "tuning_preset_value",
    "yank_bar",
]


def cmd_open(state: EditorState, args: str) -> None:
    _cmd_open(
        state,
        args,
        no_path_msg=NO_PATH,
        load_tab_data_fn=load_tab_data,
        load_tab_fn=load_tab,
        load_ft3_fn=load_ft3,
        build_durations_fn=build_durations,
    )


def cmd_notes(state: EditorState, _args: str = "") -> None:
    _cmd_notes(state)


def cmd_convert(state: EditorState, args: str, config_path: str) -> None:
    target = args.strip()
    if target not in ("french", "italian"):
        state.message = "Convert target must be french or italian"
        return
    convert_overrides(state, target)
    state.settings["style"] = target
    save_settings(config_path, state.settings)
    state.message = f"Converted to {target}"


def cmd_ascii(state: EditorState, args: str) -> None:
    value = args.strip()
    if value not in ("on", "off"):
        state.message = "Ascii must be on/off"
        return
    state.ascii_preview = value == "on"
    state.message = f"Ascii preview {value}"


def cmd_midi(state: EditorState, args: str, config_path: str) -> None:
    _cmd_midi(state, args, config_path, export_midi_fn=export_midi, save_fn=save_settings)


def cmd_lilypond(state: EditorState, args: str, config_path: str) -> None:
    _cmd_lilypond(
        state,
        args,
        config_path,
        export_lilypond_fn=export_lilypond,
        save_fn=save_settings,
    )


def cmd_musicxml(state: EditorState, args: str, config_path: str) -> None:
    _cmd_musicxml(
        state,
        args,
        config_path,
        export_musicxml_fn=export_musicxml,
        export_mxl_fn=export_mxl,
        save_fn=save_settings,
    )


def cmd_pdf(state: EditorState, _args: str, config_path: str) -> None:
    _ = (_args, config_path)
    _print_pdf(
        state,
        export_lilypond_fn=export_lilypond,
        print_lilypond_pdf_fn=print_lilypond_pdf,
    )


def cmd_play(state: EditorState, args: str, config_path: str) -> None:
    from oud.editor.midi_control import start_midi  # noqa: PLC0415

    _cmd_play(
        state,
        args,
        config_path,
        start_midi_fn=start_midi,
        save_fn=save_settings,
    )


def cmd_pause(state: EditorState) -> None:
    from oud.editor.midi_control import pause_midi  # noqa: PLC0415

    pause_midi(state)


def apply_set_command(state: EditorState, args: str, config_path: str) -> None:
    _apply_set_command(state, args, config_path, save_fn=save_settings)


def cmd_set(state: EditorState, args: str, config_path: str) -> None:
    apply_set_command(state, args.strip(), config_path)


def convert_overrides(state: EditorState, target_style: str) -> None:
    _convert_overrides(state, target_style)


def cmd_midicmd(state: EditorState, target: str) -> None:
    _cmd_midicmd(
        state,
        target,
        midi_command_fn=_midi_command,
        which_fn=shutil.which,
        platform=sys.platform,
    )


def cmd_midicmd_default(state: EditorState, args: str) -> None:
    _cmd_midicmd_default(state, args, cmd_midicmd_fn=cmd_midicmd)


def cmd_source(state: EditorState, target: str) -> None:
    _cmd_source(state, target, which_fn=shutil.which, run_fn=subprocess.run)


def show_help(state: EditorState) -> None:
    from oud.editor.command_misc_ops import show_help as _show_help  # noqa: PLC0415

    _show_help(state, which_fn=shutil.which, run_fn=subprocess.run)


def cmd_info(state: EditorState) -> None:
    _cmd_info(state)


def cmd_plugins(state: EditorState) -> None:
    _cmd_plugins(state)


def cmd_tool(state: EditorState, action: str, config_path: str) -> None:
    _cmd_tool(state, action, config_path, save_fn=save_settings)


def cmd_write(state: EditorState, path: str) -> bool:
    return _cmd_write(state, path)


def cmd_write_default(state: EditorState, args: str, *, prompt_command: str = "w") -> bool:
    return _cmd_write_default(state, args, prompt_command=prompt_command)


def cmd_write_ascii(state: EditorState, path: str) -> None:
    _cmd_write_ascii(state, path)


def cmd_write_ascii_default(state: EditorState, args: str) -> None:
    _cmd_write_ascii_default(state, args)


def print_pdf(state: EditorState) -> None:
    _print_pdf(
        state,
        export_lilypond_fn=export_lilypond,
        print_lilypond_pdf_fn=print_lilypond_pdf,
    )
