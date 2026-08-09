from __future__ import annotations

import argparse
import curses
import shutil
import sys
from dataclasses import replace

from oud import __version__
from oud.cli_convert import (
    FORMAT_ALIASES,
    ConvertOptions,
    convert_command,
)
from oud.command_io import OutputExistsError, atomic_write_text
from oud.editor.interaction.dispatch.actions import handle_insert, handle_normal
from oud.editor.services.bootstrap import init_state
from oud.editor.services.io.files import render_ascii_snapshot
from oud.tui.commands import apply_command
from oud.tui.loop import run_loop

CONFIG_PATH = "config.toml"
COMMANDS = {"tui", "ascii", "convert"}
ERR_BARS_EMPTY = "empty bars range"
ERR_BARS_FORMAT = "bars must be N or START:END"
ERR_BARS_RANGE_FORMAT = "bars must be START:END"
ERR_BARS_POSITIVE = "bars are 1-based and must be > 0"
ERR_BARS_ORDER = "bar range start must be <= end"
ERR_BARS_PAST_END = "bar range starts past end of piece"
EXIT_INPUT = 3
EXIT_OUTPUT = 4
EXIT_INTERRUPTED = 130


class AsciiInputError(ValueError):
    def __init__(self, path: str, warnings: list[str] | tuple[str, ...]) -> None:
        super().__init__(f"cannot render {path}: {'; '.join(warnings)}")


def _main(stdscr, path: str | None, config_path: str, read_only: bool = False) -> int:
    return run_loop(
        stdscr,
        path,
        config_path=config_path,
        handle_insert=handle_insert,
        handle_normal=handle_normal,
        apply_command=apply_command,
        read_only=read_only,
    )


def _cmd_ascii(
    path: str,
    config_path: str,
    output: str | None,
    bars: str | None = None,
    *,
    overwrite: bool = False,
) -> int:
    if path == "-":
        print("oud: ascii stdin is unsupported; use convert - - --input-format tab --format ascii", file=sys.stderr)
        return 2
    if bars:
        _parse_bars_spec(bars, sys.maxsize)
    try:
        text = _ascii_text(path, config_path, bars)
        if output and output != "-":
            atomic_write_text(output, text, overwrite=overwrite)
            print(f"Wrote {output}")
        else:
            sys.stdout.write(text)
    except (AsciiInputError, OutputExistsError, KeyboardInterrupt, OSError) as exc:
        return _report_ascii_failure(exc)
    else:
        return 0


def _ascii_text(path: str, config_path: str, bars: str | None) -> str:
    state = init_state(path, config_path=config_path)
    warnings = getattr(getattr(state, "piece", None), "import_warnings", ())
    if warnings:
        raise AsciiInputError(path, warnings)
    _slice_for_ascii(state, bars)
    term = shutil.get_terminal_size((120, 40))
    state.screen_width = max(1, term.columns)
    state.screen_height = max(1, term.lines)
    return render_ascii_snapshot(state)


def _report_ascii_failure(exc: BaseException) -> int:
    if isinstance(exc, AsciiInputError):
        print(f"oud: {exc}", file=sys.stderr)
        return EXIT_INPUT
    if isinstance(exc, KeyboardInterrupt):
        print("oud: interrupted", file=sys.stderr)
        return EXIT_INTERRUPTED
    print(f"oud: ASCII output failed: {exc}", file=sys.stderr)
    return EXIT_OUTPUT


def _parse_bars_spec(spec: str, total: int) -> tuple[int, int]:  # noqa: C901
    text = spec.strip()
    if not text:
        raise ValueError(ERR_BARS_EMPTY)
    if ":" in text:
        left, right = text.split(":", 1)
        if not left.isdigit() or not right.isdigit():
            raise ValueError(ERR_BARS_RANGE_FORMAT)
        start = int(left)
        end = int(right)
    elif text.isdigit():
        start = int(text)
        end = start
    else:
        raise ValueError(ERR_BARS_FORMAT)
    if start <= 0 or end <= 0:
        raise ValueError(ERR_BARS_POSITIVE)
    if start > end:
        raise ValueError(ERR_BARS_ORDER)
    if start > total:
        raise ValueError(ERR_BARS_PAST_END)
    end = min(end, total)
    return start - 1, end


def _slice_for_ascii(state, bars_spec: str | None) -> None:
    if not bars_spec:
        return
    start, end = _parse_bars_spec(bars_spec, len(state.piece.bars))
    state.piece = replace(state.piece, bars=list(state.piece.bars[start:end]))

    def in_range(bar_idx: int) -> bool:
        return start <= bar_idx < end

    def remap_bar(bar_idx: int) -> int:
        return bar_idx - start

    state.overrides = {(remap_bar(b), s, c): v for (b, s, c), v in state.overrides.items() if in_range(b)}
    state.durations = {(remap_bar(b), s, c): v for (b, s, c), v in state.durations.items() if in_range(b)}
    state.dotted = {(remap_bar(b), c) for (b, c) in state.dotted if in_range(b)}
    state.annotations = {(remap_bar(b), c): v for (b, c), v in state.annotations.items() if in_range(b)}
    state.ornaments = {(remap_bar(b), c): v for (b, c), v in state.ornaments.items() if in_range(b)}

    def remap_spans(spans: list[tuple[int, int, int]]) -> list[tuple[int, int, int]]:
        out: list[tuple[int, int, int]] = []
        for b, c1, c2 in spans:
            if in_range(b):
                out.append((remap_bar(b), c1, c2))
        return out

    state.slurs = remap_spans(state.slurs)
    state.ties = remap_spans(state.ties)
    state.holds = remap_spans(state.holds)


def _cmd_convert(
    path_in: str,
    path_out: str,
    config_path: str,
    options: ConvertOptions | None = None,
) -> int:
    return convert_command(path_in, path_out, config_path, options=options)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="oud")
    parser.add_argument("--version", action="version", version=f"oud {__version__}")
    parser.add_argument(
        "--config",
        default=CONFIG_PATH,
        help="Path to config TOML",
    )
    parser.add_argument(
        "--readonly",
        dest="readonly_global",
        action="store_true",
        help="Open TUI in read-only viewer mode",
    )
    sub = parser.add_subparsers(dest="command", metavar="command")

    p_tui = sub.add_parser("tui", help="Open interactive editor")
    p_tui.add_argument("path", nargs="?", help="Optional file to open in TUI")
    p_tui.add_argument(
        "--readonly",
        dest="readonly_tui",
        action="store_true",
        help="Open in read-only viewer mode",
    )

    p_ascii = sub.add_parser("ascii", help="Render tablature as ASCII")
    p_ascii.add_argument("path", help="Input .ft3/.tab path")
    p_ascii.add_argument("-o", "--output", help="Write ASCII output to file")
    p_ascii.add_argument("-f", "--force", action="store_true", help="Replace an existing output file")
    p_ascii.add_argument(
        "--bars",
        help="Optional 1-based bar range (N or START:END)",
    )
    p_ascii.add_argument(
        "bars_expr",
        nargs="?",
        help=argparse.SUPPRESS,
    )

    p_convert = sub.add_parser("convert", help="Convert by output extension")
    p_convert.add_argument("input", help="Input .ft3/.tab path")
    p_convert.add_argument(
        "output",
        help="Output path, or - for a supported text stream",
    )
    p_convert.add_argument("-f", "--force", action="store_true", help="Replace existing output files")
    p_convert.add_argument(
        "--input-format",
        choices=("tab",),
        help="Input format required when input is -",
    )
    p_convert.add_argument(
        "--format",
        choices=tuple(sorted(FORMAT_ALIASES)),
        help="Output format; required when output is -",
    )
    return parser


def _first_positional_index(argv: list[str]) -> int | None:
    first_non_option = None
    skip_value = False
    for idx, arg in enumerate(argv):
        if skip_value:
            skip_value = False
            continue
        if arg == "--":
            break
        if arg == "--config":
            skip_value = True
            continue
        if not arg.startswith("-"):
            first_non_option = idx
            break
    return first_non_option


def _normalize_args(argv: list[str]) -> list[str]:
    if not argv:
        return ["tui"]
    if argv[0] in ("-h", "--help", "--version"):
        return argv
    if argv[0] in COMMANDS:
        return argv
    first_non_option = _first_positional_index(argv)
    if first_non_option is None:
        return argv
    if argv[first_non_option] in COMMANDS:
        return argv
    out = argv[:first_non_option]
    out.append("tui")
    out.extend(argv[first_non_option:])
    return out


def main(argv: list[str] | None = None) -> int:
    raw_args = list(sys.argv[1:] if argv is None else argv)
    args = _normalize_args(raw_args)
    parsed = _build_parser().parse_args(args)
    if parsed.command == "tui":
        read_only = bool(
            getattr(parsed, "readonly_global", False) or getattr(parsed, "readonly_tui", False),
        )
        return curses.wrapper(_main, parsed.path, parsed.config, read_only)
    if parsed.command == "ascii":
        try:
            bars = parsed.bars
            if bars is None and parsed.bars_expr:
                if parsed.bars_expr.startswith("bars="):
                    bars = parsed.bars_expr.split("=", 1)[1]
                else:
                    print(
                        "Invalid ascii argument; use --bars N or --bars START:END",
                        file=sys.stderr,
                    )
                    return 2
            return _cmd_ascii(parsed.path, parsed.config, parsed.output, bars, overwrite=parsed.force)
        except ValueError as exc:
            print(f"Invalid --bars: {exc}", file=sys.stderr)
            return 2
    if parsed.command == "convert":
        options = ConvertOptions(parsed.force, parsed.input_format, parsed.format)
        return _cmd_convert(parsed.input, parsed.output, parsed.config, options)
    _build_parser().print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
