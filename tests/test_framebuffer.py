from oud.ui.adapter import CursesError, Screen
from oud.ui.framebuffer import Frame, draw_frame_rows


class _StrictScreen(Screen):
    def __init__(self, height: int, width: int) -> None:
        self._height = height
        self._width = width
        self.calls: list[tuple[int, int, str]] = []

    def getmaxyx(self) -> tuple[int, int]:
        return (self._height, self._width)

    def addstr(self, y: int, x: int, text: str, attr: int = 0) -> None:
        _ = attr
        assert 0 <= y < self._height
        assert 0 <= x < self._width
        assert x + len(text) <= self._width
        self.calls.append((y, x, text))

    def erase(self) -> None:
        return None

    def refresh(self) -> None:
        return None


def test_draw_frame_rows_clamps_to_width() -> None:
    screen = _StrictScreen(height=2, width=6)
    frame = Frame(
        lines=["123456789", "abcdefghi"],
        attrs=[(0,) * 9, (0,) * 9],
    )
    draw_frame_rows(screen, frame, {0, 1})
    assert screen.calls
    for _y, _x, text in screen.calls:
        assert len(text) <= 6


class _CursesLikeScreen(_StrictScreen):
    def addstr(self, y: int, x: int, text: str, attr: int = 0) -> None:
        _ = attr
        if y == self._height - 1 and x + len(text) >= self._width:
            raise CursesError("ERR")
        super().addstr(y, x, text, attr)


def test_draw_frame_rows_ignores_curses_errors() -> None:
    screen = _CursesLikeScreen(height=2, width=6)
    frame = Frame(
        lines=["123456", "abcdef"],
        attrs=[(0,) * 6, (0,) * 6],
    )
    draw_frame_rows(screen, frame, {0, 1})
