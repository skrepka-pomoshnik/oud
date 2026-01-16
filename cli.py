from __future__ import annotations

import argparse

from ft3 import load_ft3
from tab_parser import load_tab


def main() -> int:
    parser = argparse.ArgumentParser(description="Minimal FT3 reader")
    parser.add_argument("path", help="Path to .ft3 or .ft3.gz")
    args = parser.parse_args()

    if args.path.lower().endswith(".tab"):
        piece = load_tab(args.path)
    else:
        piece = load_ft3(args.path)
    print(f"Title: {piece.title}")
    print(f"Author: {piece.author}")
    print(f"Composer: {piece.composer}")
    print(f"Bars: {len(piece.bars)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
