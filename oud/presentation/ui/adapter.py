from __future__ import annotations

import contextlib
import curses
from dataclasses import dataclass

from petrucci.terminal.canvas.screen import A_BOLD, A_DIM, A_REVERSE, A_UNDERLINE, CursesError, Screen

__all__ = [
    "A_BOLD",
    "A_DIM",
    "A_REVERSE",
    "A_UNDERLINE",
    "CursesError",
    "CursesScreen",
    "Screen",
    "apply_theme_background",
    "contrast_attr",
    "theme_attr",
]

_THEME_PAIRS = {"dark": 1, "light": 2}
_initialized_theme_pairs: set[str] = set()


def contrast_attr(mode: str) -> int:
    # Bold on the terminal's default colors stays readable on both dark and
    # light themes; forcing a foreground color (e.g. white) does not.
    return curses.A_BOLD if mode == "high" else 0


def theme_attr(theme: str) -> int:
    """Color attribute for an explicit dark/light theme; 0 follows the terminal."""
    pair = _THEME_PAIRS.get(theme)
    if pair is None:
        return 0
    try:
        if not curses.has_colors():
            return 0
        if theme not in _initialized_theme_pairs:
            curses.start_color()
            curses.use_default_colors()
            if theme == "dark":
                curses.init_pair(pair, curses.COLOR_WHITE, curses.COLOR_BLACK)
            else:
                curses.init_pair(pair, curses.COLOR_BLACK, curses.COLOR_WHITE)
            _initialized_theme_pairs.add(theme)
        return curses.color_pair(pair)
    except curses.error:
        return 0


def apply_theme_background(stdscr: curses.window, attr: int) -> None:
    """Paint the window background so themed colors cover untouched cells."""
    bkgd = getattr(stdscr, "bkgd", None)
    if bkgd is None:
        return
    with contextlib.suppress(curses.error):
        bkgd(" ", attr)


def _curses_text_attr(attr: int) -> int:
    portable_mask = A_BOLD | A_REVERSE | A_DIM | A_UNDERLINE
    backend_attr = attr & ~portable_mask
    for portable, native in (
        (A_BOLD, curses.A_BOLD),
        (A_REVERSE, curses.A_REVERSE),
        (A_DIM, curses.A_DIM),
        (A_UNDERLINE, curses.A_UNDERLINE),
    ):
        if attr & portable:
            backend_attr |= native
    return backend_attr


@dataclass(frozen=True)
class CursesScreen:
    stdscr: curses.window
    base_attr: int = 0

    def getmaxyx(self) -> tuple[int, int]:
        return self.stdscr.getmaxyx()

    def addstr(self, y: int, x: int, text: str, attr: int = 0) -> None:
        try:
            self.stdscr.addstr(y, x, text, _curses_text_attr(attr) | self.base_attr)
        except curses.error as exc:
            raise CursesError(str(exc)) from exc

    def erase(self) -> None:
        self.stdscr.erase()

    def refresh(self) -> None:
        self.stdscr.refresh()
