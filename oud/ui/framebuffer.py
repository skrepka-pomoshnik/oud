from __future__ import annotations

from dataclasses import dataclass

from oud.ui.adapter import CursesError, Screen


@dataclass(frozen=True)
class Frame:
    lines: list[str]
    attrs: list[tuple[int, ...]]


class FrameBuffer(Screen):
    def __init__(self, height: int, width: int) -> None:
        self._height = height
        self._width = width
        self._chars: list[list[str]] = [
            [" " for _ in range(width)] for _ in range(height)
        ]
        self._attrs: list[list[int]] = [
            [0 for _ in range(width)] for _ in range(height)
        ]

    def getmaxyx(self) -> tuple[int, int]:
        return self._height, self._width

    def addstr(self, y: int, x: int, text: str, attr: int = 0) -> None:
        if y < 0 or y >= self._height or x >= self._width:
            return
        if x < 0:
            text = text[-x:]
            x = 0
        max_len = max(0, self._width - x)
        for idx, ch in enumerate(text[:max_len]):
            self._chars[y][x + idx] = ch
            self._attrs[y][x + idx] = attr

    def erase(self) -> None:
        for y in range(self._height):
            for x in range(self._width):
                self._chars[y][x] = " "
                self._attrs[y][x] = 0

    def refresh(self) -> None:  # pragma: no cover - no-op for buffer
        return None

    def snapshot(self) -> Frame:
        lines: list[str] = []
        attrs: list[tuple[int, ...]] = []
        for y in range(self._height):
            lines.append("".join(self._chars[y]))
            attrs.append(tuple(self._attrs[y]))
        return Frame(lines=lines, attrs=attrs)


def frame_diff_rows(prev: Frame | None, curr: Frame) -> set[int]:
    if prev is None:
        return set(range(len(curr.lines)))
    rows: set[int] = set()
    for idx, (line, attrs) in enumerate(zip(curr.lines, curr.attrs, strict=False)):
        if idx >= len(prev.lines):
            rows.add(idx)
            continue
        if line != prev.lines[idx] or attrs != prev.attrs[idx]:
            rows.add(idx)
    return rows


def iter_attr_runs(text: str, attrs: tuple[int, ...]) -> list[tuple[str, int]]:
    if not text:
        return []
    runs: list[tuple[str, int]] = []
    current_attr = attrs[0] if attrs else 0
    current_text = [text[0]]
    for ch, attr in zip(text[1:], attrs[1:], strict=False):
        if attr == current_attr:
            current_text.append(ch)
            continue
        runs.append(("".join(current_text), current_attr))
        current_attr = attr
        current_text = [ch]
    runs.append(("".join(current_text), current_attr))
    return runs


def draw_frame_rows(screen: Screen, frame: Frame, rows: set[int]) -> None:  # noqa: C901
    height, width = screen.getmaxyx()
    for row in sorted(rows):
        if row < 0 or row >= height:
            continue
        text = frame.lines[row]
        attrs = frame.attrs[row]
        if width <= 0:
            continue
        if len(text) > width:
            text = text[:width]
            attrs = attrs[:width]
        x = 0
        for chunk_text, attr in iter_attr_runs(text, attrs):
            if x >= width:
                break
            if not chunk_text:
                continue
            if x + len(chunk_text) > width:
                clipped = chunk_text[: max(0, width - x)]
                if not clipped:
                    break
                chunk_out = clipped
            else:
                chunk_out = chunk_text
            try:
                screen.addstr(row, x, chunk_out, attr)
            except CursesError:
                break
            x += len(chunk_out)
