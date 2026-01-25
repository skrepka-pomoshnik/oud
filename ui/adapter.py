from __future__ import annotations

import curses
from dataclasses import dataclass
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


@dataclass(frozen=True)
class CursesScreen:
    stdscr: curses.window

    def getmaxyx(self) -> tuple[int, int]:
        return self.stdscr.getmaxyx()

    def addstr(self, y: int, x: int, text: str, attr: int = 0) -> None:
        self.stdscr.addstr(y, x, text, attr)

    def erase(self) -> None:
        self.stdscr.erase()

    def refresh(self) -> None:
        self.stdscr.refresh()
