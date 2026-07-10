from __future__ import annotations

from typing import Protocol

try:
    import curses as _curses
except ImportError:  # pragma: no cover - curses exists on supported oud platforms
    A_BOLD = 1
    A_REVERSE = 2

    class CursesError(Exception):
        pass

else:
    A_BOLD = _curses.A_BOLD
    A_REVERSE = _curses.A_REVERSE
    CursesError = _curses.error


class Screen(Protocol):
    """Minimal character-cell target required by the Petrucci renderer."""

    def getmaxyx(self) -> tuple[int, int]:
        ...

    def addstr(self, y: int, x: int, text: str, attr: int = 0) -> None:
        ...

    def erase(self) -> None:
        ...

    def refresh(self) -> None:
        ...
