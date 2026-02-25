from __future__ import annotations

import argparse
import curses
import shutil
import sys
from dataclasses import replace
from pathlib import Path

from oud import __version__
from oud.core.model import Piece
from oud.editor.actions import handle_insert, handle_normal
from oud.editor.file_ops import render_ascii_snapshot
from oud.editor.init import init_state
from oud.editor.load_ops import load_piece_data
from oud.exports.export_tab import export_tab_to_file
from oud.exports.lilypond import export_lilypond, print_lilypond_pdf
from oud.exports.midi import export_midi
from oud.exports.musicxml import export_musicxml, export_mxl
from oud.settings import DEFAULT_SETTINGS, load_settings
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


def _main(stdscr, path: str | None, config_path: str) -> int:
    return run_loop(
        stdscr,
        path,
        config_path=config_path,
        handle_insert=handle_insert,
        handle_normal=handle_normal,
        apply_command=apply_command,
    )


def _export_context(path: str, config_path: str) -> tuple[
    dict[str, str],
    int,
    Piece,
    dict[tuple[int, int, int], str],
    dict[tuple[int, int, int], int],
    set[tuple[int, int]],
]:
    settings = load_settings(config_path)
    piece, overrides, durations, dotted, parsed_bar_width = load_piece_data(path)
    try:
        default_width = int(settings.get("spacing", DEFAULT_SETTINGS["spacing"]))
    except ValueError:
        default_width = int(DEFAULT_SETTINGS["spacing"])
    bar_width = parsed_bar_width or max(4, default_width)
    return settings, bar_width, piece, overrides, durations, dotted


def _cmd_ascii(
    path: str,
    config_path: str,
    output: str | None,
    bars: str | None = None,
) -> int:
    state = init_state(path, config_path=config_path)
    _slice_for_ascii(state, bars)
    term = shutil.get_terminal_size((120, 40))
    state.screen_width = max(1, term.columns)
    state.screen_height = max(1, term.lines)
    text = render_ascii_snapshot(state)
    if output:
        Path(output).write_text(text, encoding="utf-8")
    else:
        print(text, end="")
    return 0


def _parse_bars_spec(spec: str, total: int) -> tuple[int, int]:
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

    state.overrides = {
        (remap_bar(b), s, c): v
        for (b, s, c), v in state.overrides.items()
        if in_range(b)
    }
    state.durations = {
        (remap_bar(b), s, c): v
        for (b, s, c), v in state.durations.items()
        if in_range(b)
    }
    state.dotted = {
        (remap_bar(b), c)
        for (b, c) in state.dotted
        if in_range(b)
    }
    state.annotations = {
        (remap_bar(b), c): v
        for (b, c), v in state.annotations.items()
        if in_range(b)
    }
    state.ornaments = {
        (remap_bar(b), c): v
        for (b, c), v in state.ornaments.items()
        if in_range(b)
    }

    def remap_spans(spans: list[tuple[int, int, int]]) -> list[tuple[int, int, int]]:
        out: list[tuple[int, int, int]] = []
        for b, c1, c2 in spans:
            if in_range(b):
                out.append((remap_bar(b), c1, c2))
        return out

    state.slurs = remap_spans(state.slurs)
    state.ties = remap_spans(state.ties)
    state.holds = remap_spans(state.holds)


def _cmd_convert(path_in: str, path_out: str, config_path: str) -> int:  # noqa: PLR0911
    settings, bar_width, piece, overrides, durations, dotted = _export_context(path_in, config_path)
    suffix = Path(path_out).suffix.lower()
    if suffix == ".tab":
        export_tab_to_file(
            path_out,
            piece,
            overrides,
            durations,
            bar_width,
            settings=settings,
            dotted=dotted,
        )
        print(f"Wrote {path_out}")
        return 0
    if suffix in {".txt", ".ascii"}:
        _cmd_ascii(path_in, config_path, path_out, None)
        print(f"Wrote {path_out}")
        return 0
    if suffix == ".ly":
        print(
            export_lilypond(
                path_out,
                piece,
                overrides,
                durations,
                bar_width,
                settings=settings,
            ),
        )
        return 0
    if suffix == ".pdf":
        ly_path = str(Path(path_out).with_suffix(".ly"))
        print(
            export_lilypond(
                ly_path,
                piece,
                overrides,
                durations,
                bar_width,
                settings=settings,
            ),
        )
        print(print_lilypond_pdf(ly_path, str(Path(path_out).with_suffix(""))))
        return 0
    if suffix in {".musicxml", ".xml"}:
        print(
            export_musicxml(
                path_out,
                piece,
                overrides,
                durations,
                bar_width,
                settings=settings,
                dotted=dotted,
            ),
        )
        return 0
    if suffix == ".mxl":
        print(
            export_mxl(
                path_out,
                piece,
                overrides,
                durations,
                bar_width,
                settings=settings,
                dotted=dotted,
            ),
        )
        return 0
    if suffix in {".mid", ".midi"}:
        bpm_text = settings.get("tempo", "90")
        bpm = int(bpm_text) if bpm_text.isdigit() else 90
        print(
            export_midi(
                path_out,
                piece,
                overrides,
                durations,
                bar_width,
                settings=settings,
                bpm=bpm,
                dotted=dotted,
            ),
        )
        return 0
    print(f"Unsupported output format: {path_out}", file=sys.stderr)
    return 2


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="oud")
    parser.add_argument("--version", action="version", version=f"oud {__version__}")
    parser.add_argument(
        "--config",
        default=CONFIG_PATH,
        help="Path to config TOML",
    )
    sub = parser.add_subparsers(dest="command", metavar="command")

    p_tui = sub.add_parser("tui", help="Open interactive editor")
    p_tui.add_argument("path", nargs="?", help="Optional file to open in TUI")

    p_ascii = sub.add_parser("ascii", help="Render tablature as ASCII")
    p_ascii.add_argument("path", help="Input .ft3/.tab path")
    p_ascii.add_argument("-o", "--output", help="Write ASCII output to file")
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
        help="Output path (.tab/.txt/.ascii/.ly/.mid/.musicxml/.xml/.mxl)",
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
        return curses.wrapper(_main, parsed.path, parsed.config)
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
            return _cmd_ascii(parsed.path, parsed.config, parsed.output, bars)
        except ValueError as exc:
            print(f"Invalid --bars: {exc}", file=sys.stderr)
            return 2
    if parsed.command == "convert":
        return _cmd_convert(parsed.input, parsed.output, parsed.config)
    _build_parser().print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
