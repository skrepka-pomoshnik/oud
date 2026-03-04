from __future__ import annotations

import shutil
import subprocess
import sys

from oud.core.ft3 import build_durations, load_ft3
from oud.core.tab_parser import load_tab, load_tab_data
from oud.editor.command_misc_ops import cmd_col as _cmd_col
from oud.editor.command_misc_ops import cmd_cursor as _cmd_cursor
from oud.editor.command_misc_ops import cmd_verify as _cmd_verify
from oud.editor.command_misc_ops import cmd_vocal as _cmd_vocal
from oud.editor.command_misc_ops import parse_time_signature as _parse_time_signature
from oud.editor.command_misc_ops import row_first_note_col as _row_first_note_col
from oud.editor.command_misc_ops import tuning_preset_value as _tuning_preset_value
from oud.editor.command_notation_ops import cmd_arpeggio as _cmd_arpeggio
from oud.editor.command_notation_ops import cmd_barline as _cmd_barline
from oud.editor.command_notation_ops import cmd_dynamic as _cmd_dynamic
from oud.editor.command_notation_ops import cmd_fermata as _cmd_fermata
from oud.editor.command_notation_ops import cmd_repeat as _cmd_repeat
from oud.editor.command_notation_ops import cmd_separee as _cmd_separee
from oud.editor.command_notation_ops import cmd_time as _cmd_time
from oud.editor.command_notation_ops import cmd_tuplet as _cmd_tuplet
from oud.editor.command_notation_ops import set_annotation as _set_annotation
from oud.editor.command_notation_ops import set_barline as _set_barline
from oud.editor.command_notation_ops import set_dynamic as _set_dynamic
from oud.editor.command_notation_ops import set_fermata as _set_fermata
from oud.editor.command_notation_ops import set_highlight as _set_highlight
from oud.editor.command_notation_ops import set_hold as _set_hold
from oud.editor.command_notation_ops import set_ornament as _set_ornament
from oud.editor.command_notation_ops import set_repeat as _set_repeat
from oud.editor.command_notation_ops import set_slur as _set_slur
from oud.editor.command_notation_ops import set_tie as _set_tie
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
from oud.editor.score_ops import cmd_bar as _cmd_bar
from oud.editor.score_ops import cmd_chord as _cmd_chord
from oud.editor.score_ops import cmd_stave as _cmd_stave
from oud.editor.score_ops import paste_bar as _paste_bar
from oud.editor.score_ops import yank_bar as _yank_bar
from oud.editor.settings_ops import apply_set_command as _apply_set_command
from oud.editor.settings_ops import convert_overrides as _convert_overrides
from oud.editor.state import EditorState
from oud.editor.tool_ops import cmd_info as _cmd_info
from oud.editor.tool_ops import cmd_plugins as _cmd_plugins
from oud.editor.tool_ops import cmd_tool as _cmd_tool
from oud.editor.transform_ops import cmd_courseshift as _cmd_courseshift
from oud.editor.transform_ops import cmd_retune as _cmd_retune
from oud.editor.transform_ops import cmd_transpose as _cmd_transpose
from oud.exports.lilypond import export_lilypond, print_lilypond_pdf
from oud.exports.midi import _midi_command, export_midi
from oud.exports.musicxml import export_musicxml, export_mxl
from oud.settings import save_settings


def row_first_note_col(state: EditorState) -> int:
    return _row_first_note_col(state)


def tuning_preset_value(value: str) -> str | None:
    return _tuning_preset_value(value)


def parse_time_signature(text: str) -> tuple[int, int] | None:
    return _parse_time_signature(text)


def yank_bar(state: EditorState, index: int, *, count: int = 1) -> None:
    _yank_bar(state, index, count=count)


def paste_bar(state: EditorState, index: int, *, count: int = 1) -> None:
    _paste_bar(state, index, count=count)


def cmd_bar(state: EditorState, args: str) -> None:
    _cmd_bar(state, args)


def cmd_stave(state: EditorState, args: str) -> None:
    _cmd_stave(state, args)


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


def cmd_col(state: EditorState, args: str) -> None:
    _cmd_col(state, args)


def cmd_cursor(state: EditorState, args: str) -> None:
    _cmd_cursor(state, args)


def cmd_verify(state: EditorState, args: str = "") -> None:
    _cmd_verify(state, args)


def cmd_vocal(state: EditorState, args: str) -> None:
    _cmd_vocal(state, args)


def cmd_info(state: EditorState) -> None:
    _cmd_info(state)


def cmd_plugins(state: EditorState) -> None:
    _cmd_plugins(state)


def cmd_tool(state: EditorState, action: str, config_path: str) -> None:
    _cmd_tool(state, action, config_path, save_fn=save_settings)


def cmd_transpose(state: EditorState, value: str) -> None:
    _cmd_transpose(state, value)


def cmd_retune(state: EditorState, value: str) -> None:
    _cmd_retune(state, value)


def cmd_courseshift(state: EditorState, value: str) -> None:
    _cmd_courseshift(state, value)


def cmd_write(state: EditorState, path: str) -> None:
    _cmd_write(state, path)


def cmd_write_default(state: EditorState, args: str) -> None:
    _cmd_write_default(state, args)


def cmd_write_ascii(state: EditorState, path: str) -> None:
    _cmd_write_ascii(state, path)


def cmd_write_ascii_default(state: EditorState, args: str) -> None:
    _cmd_write_ascii_default(state, args)


def cmd_chord(state: EditorState, args: str) -> None:
    _cmd_chord(state, args)


def cmd_time(state: EditorState, value: str) -> None:
    _cmd_time(state, value)


def cmd_barline(state: EditorState, value: str) -> None:
    _cmd_barline(state, value)


def cmd_repeat(state: EditorState, value: str) -> None:
    _cmd_repeat(state, value)


def cmd_dynamic(state: EditorState, value: str) -> None:
    _cmd_dynamic(state, value)


def cmd_fermata(state: EditorState, value: str) -> None:
    _cmd_fermata(state, value)


def cmd_arpeggio(state: EditorState, value: str) -> None:
    _cmd_arpeggio(state, value)


def cmd_separee(state: EditorState, value: str) -> None:
    _cmd_separee(state, value)


def cmd_tuplet(state: EditorState, value: str) -> None:
    _cmd_tuplet(state, value)


def set_ornament(state: EditorState, value: str) -> None:
    _set_ornament(state, value)


def set_annotation(state: EditorState, value: str) -> None:
    _set_annotation(state, value)


def set_highlight(state: EditorState, value: str) -> None:
    _set_highlight(state, value)


def set_barline(state: EditorState, value: str) -> None:
    _set_barline(state, value)


def set_repeat(state: EditorState, value: str) -> None:
    _set_repeat(state, value)


def set_dynamic(state: EditorState, value: str) -> None:
    _set_dynamic(state, value)


def set_fermata(state: EditorState, value: str) -> None:
    _set_fermata(state, value)


def set_slur(state: EditorState, value: str) -> None:
    _set_slur(state, value)


def set_tie(state: EditorState, value: str) -> None:
    _set_tie(state, value)


def set_hold(state: EditorState, value: str) -> None:
    _set_hold(state, value)


def print_pdf(state: EditorState) -> None:
    _print_pdf(
        state,
        export_lilypond_fn=export_lilypond,
        print_lilypond_pdf_fn=print_lilypond_pdf,
    )
