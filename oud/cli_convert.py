"""Non-interactive conversion command with explicit stream and file contracts."""

from __future__ import annotations

import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

from oud.command_io import (
    OutputExistsError,
    atomic_export,
    atomic_write_text,
    ensure_output_available,
    publish_existing,
)
from oud.editor.services.io.loading import load_piece_data
from oud.exports.export_tab import export_ascii, export_tab
from oud.exports.lilypond import lilypond_text, print_lilypond_pdf
from oud.exports.midi import export_midi
from oud.exports.musicxml import export_mxl, musicxml_text
from oud.importers.tab import parse_tab_text_data
from oud.settings import DEFAULT_SETTINGS, load_settings
from petrucci.model import Piece

EXIT_USAGE = 2
EXIT_INPUT = 3
EXIT_OUTPUT = 4
EXIT_TOOL = 5
EXIT_INTERRUPTED = 130

FORMAT_ALIASES = {
    "ascii": "ascii",
    "lilypond": "lilypond",
    "ly": "lilypond",
    "midi": "midi",
    "mid": "midi",
    "musicxml": "musicxml",
    "mxl": "mxl",
    "pdf": "pdf",
    "tab": "tab",
    "xml": "musicxml",
}
SUFFIX_FORMATS = {
    ".ascii": "ascii",
    ".ly": "lilypond",
    ".mid": "midi",
    ".midi": "midi",
    ".musicxml": "musicxml",
    ".mxl": "mxl",
    ".pdf": "pdf",
    ".tab": "tab",
    ".txt": "ascii",
    ".xml": "musicxml",
}
STREAM_FORMATS = frozenset({"ascii", "lilypond", "musicxml", "tab"})


class ConversionError(ValueError):
    def __init__(self, status: int, message: str) -> None:
        self.status = status
        super().__init__(message)


@dataclass(frozen=True, slots=True)
class ConversionContext:
    settings: dict[str, str]
    bar_width: int
    piece: Piece
    overrides: dict[tuple[int, int, int], str]
    durations: dict[tuple[int, int, int], int]
    dotted: set[tuple[int, int]]


@dataclass(frozen=True, slots=True)
class ConvertOptions:
    overwrite: bool = False
    input_format: str | None = None
    output_format: str | None = None


@dataclass(frozen=True, slots=True)
class CommandStreams:
    stdin: TextIO | None = None
    stdout: TextIO | None = None
    stderr: TextIO | None = None


def _error(status: int, message: str) -> ConversionError:
    return ConversionError(status, message)


def load_export_context(
    path: str,
    config_path: str,
    *,
    input_format: str | None = None,
    stdin: TextIO | None = None,
) -> ConversionContext:
    settings = load_settings(config_path)
    if path == "-":
        piece, overrides, durations, dotted, parsed_bar_width = _read_stdin(
            input_format,
            stdin or sys.stdin,
        )
    else:
        if input_format is not None:
            raise _error(EXIT_USAGE, "--input-format is only valid when input is -")
        piece, overrides, durations, dotted, parsed_bar_width = load_piece_data(path)
    _validate_piece(piece, path)
    bar_width = parsed_bar_width or _default_bar_width(settings)
    return ConversionContext(settings, bar_width, piece, overrides, durations, dotted)


def _read_stdin(
    input_format: str | None,
    stream: TextIO,
) -> tuple[
    Piece,
    dict[tuple[int, int, int], str],
    dict[tuple[int, int, int], int],
    set[tuple[int, int]],
    int | None,
]:
    if input_format != "tab":
        raise _error(EXIT_USAGE, "stdin requires --input-format tab")
    parsed = parse_tab_text_data(stream.read())
    if parsed is None:
        raise _error(EXIT_INPUT, "stdin does not contain a recoverable TAB score")
    return parsed.piece, parsed.overrides, parsed.durations, parsed.dotted, parsed.bar_width


def _validate_piece(piece: Piece, path: str) -> None:
    if piece.import_warnings:
        details = "; ".join(piece.import_warnings)
        raise _error(EXIT_INPUT, f"cannot convert {path}: {details}")
    if not piece.bars:
        raise _error(EXIT_INPUT, f"cannot convert {path}: input contains no score bars")


def _default_bar_width(settings: dict[str, str]) -> int:
    try:
        value = int(settings.get("spacing", DEFAULT_SETTINGS["spacing"]))
    except ValueError:
        value = int(DEFAULT_SETTINGS["spacing"])
    return max(4, value)


def resolve_output_format(path: str, explicit: str | None) -> str:
    if explicit is not None:
        resolved = FORMAT_ALIASES.get(explicit)
        if resolved is None:
            raise _error(EXIT_USAGE, f"unsupported --format value: {explicit}")
        inferred = SUFFIX_FORMATS.get(Path(path).suffix.lower()) if path != "-" else None
        if inferred is not None and inferred != resolved:
            raise _error(EXIT_USAGE, f"--format {explicit} conflicts with output suffix {Path(path).suffix}")
        return resolved
    if path == "-":
        raise _error(EXIT_USAGE, "stdout output requires --format")
    resolved = SUFFIX_FORMATS.get(Path(path).suffix.lower())
    if resolved is None:
        raise _error(EXIT_USAGE, f"unsupported output format: {path}")
    return resolved


def convert_command(
    path_in: str,
    path_out: str,
    config_path: str,
    *,
    options: ConvertOptions | None = None,
    streams: CommandStreams | None = None,
) -> int:
    options = options or ConvertOptions()
    streams = streams or CommandStreams()
    out = streams.stdout or sys.stdout
    err = streams.stderr or sys.stderr
    try:
        _execute_convert(
            path_in,
            path_out,
            config_path,
            options=options,
            stdin=streams.stdin,
            stdout=out,
        )
        status = 0
    except ConversionError as exc:
        print(f"oud: {exc}", file=err)
        status = exc.status
    except OutputExistsError as exc:
        print(f"oud: {exc}", file=err)
        status = EXIT_OUTPUT
    except BrokenPipeError:
        status = 0
    except KeyboardInterrupt:
        print("oud: interrupted", file=err)
        status = EXIT_INTERRUPTED
    except OSError as exc:
        print(f"oud: output failed: {exc}", file=err)
        status = EXIT_OUTPUT
    except ValueError as exc:
        print(f"oud: conversion failed: {exc}", file=err)
        status = EXIT_INPUT
    return status


def _execute_convert(
    path_in: str,
    path_out: str,
    config_path: str,
    *,
    options: ConvertOptions,
    stdin: TextIO | None,
    stdout: TextIO,
) -> None:
    resolved_format = resolve_output_format(path_out, options.output_format)
    context = load_export_context(
        path_in,
        config_path,
        input_format=options.input_format,
        stdin=stdin,
    )
    if path_out == "-":
        _write_stdout(resolved_format, context, stdout)
        return
    _write_file(resolved_format, Path(path_out), context, overwrite=options.overwrite)
    print(f"Wrote {path_out}", file=stdout)


def _write_stdout(output_format: str, context: ConversionContext, stream: TextIO) -> None:
    if output_format not in STREAM_FORMATS:
        raise _error(EXIT_USAGE, f"{output_format} output cannot be streamed to stdout")
    stream.write(_render_text(output_format, context))


def _render_text(output_format: str, context: ConversionContext) -> str:
    if output_format == "tab":
        return export_tab(
            context.piece,
            context.overrides,
            context.durations,
            context.bar_width,
            settings=context.settings,
            dotted=context.dotted,
        )
    if output_format == "ascii":
        return export_ascii(
            context.piece,
            context.overrides,
            context.durations,
            context.bar_width,
            settings=context.settings,
        )
    if output_format == "lilypond":
        return lilypond_text(
            context.piece,
            context.overrides,
            context.durations,
            context.bar_width,
            settings=context.settings,
        )
    return musicxml_text(
        context.piece,
        context.overrides,
        context.durations,
        context.bar_width,
        settings=context.settings,
        dotted=context.dotted,
    )


def _write_file(
    output_format: str,
    target: Path,
    context: ConversionContext,
    *,
    overwrite: bool,
) -> None:
    if output_format in STREAM_FORMATS:
        atomic_write_text(target, _render_text(output_format, context), overwrite=overwrite)
        return
    if output_format == "mxl":
        atomic_export(target, lambda path: _export_mxl(path, context), overwrite=overwrite)
        return
    if output_format == "midi":
        atomic_export(target, lambda path: _export_midi(path, context), overwrite=overwrite)
        return
    _write_pdf(target, context, overwrite=overwrite)


def _export_mxl(path: str, context: ConversionContext) -> str:
    return export_mxl(
        path,
        context.piece,
        context.overrides,
        context.durations,
        context.bar_width,
        settings=context.settings,
        dotted=context.dotted,
    )


def _export_midi(path: str, context: ConversionContext) -> str:
    bpm_text = context.settings.get("tempo", "90")
    bpm = int(bpm_text) if bpm_text.isdigit() else 90
    return export_midi(
        path,
        context.piece,
        context.overrides,
        context.durations,
        context.bar_width,
        settings=context.settings,
        bpm=bpm,
        dotted=context.dotted,
    )


def _write_pdf(target: Path, context: ConversionContext, *, overwrite: bool) -> None:
    ensure_output_available(target, overwrite=overwrite)
    lilypond_source = target.with_suffix(".ly")
    ensure_output_available(lilypond_source, overwrite=overwrite)
    atomic_write_text(lilypond_source, _render_text("lilypond", context), overwrite=overwrite)
    with tempfile.TemporaryDirectory(prefix=f".{target.stem}.", dir=target.parent) as directory:
        output_base = Path(directory) / target.stem
        message = print_lilypond_pdf(str(lilypond_source), str(output_base))
        if not message.startswith("Printed "):
            raise _error(EXIT_TOOL, message)
        generated = output_base.with_suffix(".pdf")
        if not generated.is_file():
            raise _error(EXIT_TOOL, f"LilyPond reported success but did not create {generated}")
        publish_existing(generated, target, overwrite=overwrite)


__all__ = [
    "EXIT_INPUT",
    "EXIT_INTERRUPTED",
    "EXIT_OUTPUT",
    "EXIT_TOOL",
    "EXIT_USAGE",
    "FORMAT_ALIASES",
    "CommandStreams",
    "ConversionContext",
    "ConversionError",
    "ConvertOptions",
    "convert_command",
    "load_export_context",
    "resolve_output_format",
]
