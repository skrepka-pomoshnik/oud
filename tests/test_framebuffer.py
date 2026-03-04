import unicodedata

from oud.ui.adapter import CursesError, Screen
from oud.ui.framebuffer import Frame, draw_frame_rows


def _display_cols(text: str) -> int:
    return sum(1 for ch in text if not unicodedata.combining(ch))


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
        assert x + _display_cols(text) <= self._width
        self.calls.append((y, x, text))

    def erase(self) -> None:
        return None

    def refresh(self) -> None:
        return None


class _AttrScreen(_StrictScreen):
    def __init__(self, height: int, width: int, base_attr: int) -> None:
        super().__init__(height, width)
        self.base_attr = base_attr
        self.attr_calls: list[int] = []

    def addstr(self, y: int, x: int, text: str, attr: int = 0) -> None:
        self.attr_calls.append(attr | self.base_attr)
        super().addstr(y, x, text, attr)


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
        if y == self._height - 1 and x + _display_cols(text) >= self._width:
            raise CursesError("ERR")
        super().addstr(y, x, text, attr)


def test_draw_frame_rows_ignores_curses_errors() -> None:
    screen = _CursesLikeScreen(height=2, width=6)
    frame = Frame(
        lines=["123456", "abcdef"],
        attrs=[(0,) * 6, (0,) * 6],
    )
    draw_frame_rows(screen, frame, {0, 1})


def test_draw_frame_rows_combining_mark_rows_preserve_width() -> None:
    screen = _StrictScreen(height=1, width=6)
    frame = Frame(
        lines=["a\u0323bcdef"],
        attrs=[(0,) * 6],
    )
    draw_frame_rows(screen, frame, {0})
    assert screen.calls
    # One display row worth of text should be drawn without truncation/shear.
    drawn = "".join(text for (_y, _x, text) in screen.calls)
    assert "f" in drawn


def test_draw_frame_rows_screen_base_attr_applies_to_plain_rows() -> None:
    screen = _AttrScreen(height=1, width=4, base_attr=16)
    frame = Frame(lines=["abcd"], attrs=[(0, 0, 0, 0)])
    draw_frame_rows(screen, frame, {0})
    assert screen.attr_calls == [16]
