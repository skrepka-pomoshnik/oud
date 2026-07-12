from __future__ import annotations

from typing import Protocol

try:
    import curses as _curses
except ImportError:  # pragma: no cover - curses exists on supported oud platforms
    A_BOLD = 1
    A_REVERSE = 2
    A_DIM = 4
    A_UNDERLINE = 8

    class CursesError(Exception):
        pass

else:
    A_BOLD = _curses.A_BOLD
    A_REVERSE = _curses.A_REVERSE
    A_DIM = _curses.A_DIM
    A_UNDERLINE = _curses.A_UNDERLINE
    CursesError = _curses.error


class Screen(Protocol):
    """Minimal character-cell target required by the Petrucci renderer."""

    def getmaxyx(self) -> tuple[int, int]: ...

    def addstr(self, y: int, x: int, text: str, attr: int = 0) -> None: ...

    def erase(self) -> None: ...

    def refresh(self) -> None: ...
