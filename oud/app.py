from __future__ import annotations

import curses
import sys

from oud.editor.actions import handle_insert, handle_normal
from oud.tui.commands import apply_command
from oud.tui.loop import run_loop

CONFIG_PATH = "config.toml"


def _main(stdscr, path: str | None) -> int:
    return run_loop(
        stdscr,
        path,
        config_path=CONFIG_PATH,
        handle_insert=handle_insert,
        handle_normal=handle_normal,
        apply_command=apply_command,
    )


def main() -> int:
    path = sys.argv[1] if len(sys.argv) > 1 else None
    return curses.wrapper(_main, path)


if __name__ == "__main__":
    raise SystemExit(main())
