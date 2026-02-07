from __future__ import annotations

import argparse

from oud.core.ft3 import load_ft3
from oud.core.tab_parser import load_tab
from oud.editor.load_ops import load_piece_data
from oud.exports.export_tab import export_ascii
from oud.settings import DEFAULT_SETTINGS, load_settings


def main() -> int:
    parser = argparse.ArgumentParser(description="Minimal FT3/TAB reader")
    parser.add_argument("path", help="Path to .ft3, .ft3.gz, or .tab")
    parser.add_argument("--ascii", action="store_true", help="Render ASCII tablature")
    parser.add_argument("--config", default="config.toml", help="Path to config TOML")
    args = parser.parse_args()

    if args.ascii:
        piece, overrides, durations, _dotted, parsed_bar_width = load_piece_data(args.path)
        settings = load_settings(args.config)
        try:
            default_width = int(settings.get("spacing", DEFAULT_SETTINGS["spacing"]))
        except ValueError:
            default_width = int(DEFAULT_SETTINGS["spacing"])
        bar_width = parsed_bar_width or max(4, default_width)
        print(
            export_ascii(
                piece,
                overrides,
                durations,
                bar_width,
                settings=settings,
            ),
            end="",
        )
        return 0

    piece = load_tab(args.path) if args.path.lower().endswith(".tab") else load_ft3(args.path)
    print(f"Title: {piece.title}")
    print(f"Author: {piece.author}")
    print(f"Composer: {piece.composer}")
    print(f"Bars: {len(piece.bars)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
