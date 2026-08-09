from __future__ import annotations

import curses
from dataclasses import dataclass, field
from typing import cast

import pytest

from oud.presentation.ui.adapter import CursesError, CursesScreen
from petrucci.terminal.canvas.screen import A_BOLD, A_DIM, A_REVERSE, A_UNDERLINE


@dataclass
class _Window:
    writes: list[tuple[int, int, str, int]] = field(default_factory=list)
    fail: bool = False

    def addstr(self, y: int, x: int, text: str, attr: int) -> None:
        if self.fail:
            raise curses.error
        self.writes.append((y, x, text, attr))

    def getmaxyx(self) -> tuple[int, int]:
        return (24, 80)

    def erase(self) -> None:
        return None

    def refresh(self) -> None:
        return None


def test_curses_screen_translates_portable_text_attributes() -> None:
    window = _Window()
    base_attr = 1 << 24
    screen = CursesScreen(cast(curses.window, window), base_attr=base_attr)

    screen.addstr(2, 3, "score", A_BOLD | A_REVERSE | A_DIM | A_UNDERLINE)

    assert window.writes == [
        (2, 3, "score", base_attr | curses.A_BOLD | curses.A_REVERSE | curses.A_DIM | curses.A_UNDERLINE),
    ]


def test_curses_screen_exposes_backend_write_failure_as_portable_error() -> None:
    screen = CursesScreen(cast(curses.window, _Window(fail=True)))

    with pytest.raises(CursesError):
        screen.addstr(0, 0, "score")
