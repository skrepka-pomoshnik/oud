from __future__ import annotations

from typing import Protocol

A_BOLD = 1 << 0
A_REVERSE = 1 << 1
A_DIM = 1 << 2
A_UNDERLINE = 1 << 3


class CursesError(Exception):
    """Portable screen-write failure raised by the curses adapter."""


class Screen(Protocol):
    """Minimal character-cell target required by the Petrucci renderer."""

    def getmaxyx(self) -> tuple[int, int]: ...

    def addstr(self, y: int, x: int, text: str, attr: int = 0) -> None: ...

    def erase(self) -> None: ...

    def refresh(self) -> None: ...
