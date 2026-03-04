from __future__ import annotations

import curses
from dataclasses import dataclass
from functools import lru_cache
from typing import Protocol


class Screen(Protocol):
    def getmaxyx(self) -> tuple[int, int]:
        ...

    def addstr(self, y: int, x: int, text: str, attr: int = 0) -> None:
        ...

    def erase(self) -> None:
        ...

    def refresh(self) -> None:
        ...


A_BOLD = curses.A_BOLD
A_REVERSE = curses.A_REVERSE
CursesError = curses.error
_HIGH_CONTRAST_PAIR = 1


@lru_cache(maxsize=1)
def _init_high_contrast_colors() -> None:
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(_HIGH_CONTRAST_PAIR, curses.COLOR_WHITE, -1)


def contrast_attr(mode: str) -> int:
    if mode != "high":
        return 0
    try:
        has_colors = curses.has_colors()
    except CursesError:
        return 0
    if has_colors:
        try:
            _init_high_contrast_colors()
            return curses.color_pair(_HIGH_CONTRAST_PAIR)
        except CursesError:
            return curses.A_BOLD
    return curses.A_BOLD


@dataclass(frozen=True)
class CursesScreen:
    stdscr: curses.window
    base_attr: int = 0

    def getmaxyx(self) -> tuple[int, int]:
        return self.stdscr.getmaxyx()

    def addstr(self, y: int, x: int, text: str, attr: int = 0) -> None:
        self.stdscr.addstr(y, x, text, attr | self.base_attr)

    def erase(self) -> None:
        self.stdscr.erase()

    def refresh(self) -> None:
        self.stdscr.refresh()
