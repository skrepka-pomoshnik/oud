from __future__ import annotations

import unicodedata
from dataclasses import dataclass

from petrucci.terminal.canvas.screen import CursesError, Screen


@dataclass(frozen=True)
class Frame:
    lines: list[str]
    attrs: list[tuple[int, ...]]


class FrameBuffer(Screen):
    def __init__(self, height: int, width: int) -> None:
        self._height = height
        self._width = width
        self._chars: list[list[str]] = [[" " for _ in range(width)] for _ in range(height)]
        self._attrs: list[list[int]] = [[0 for _ in range(width)] for _ in range(height)]

    def getmaxyx(self) -> tuple[int, int]:
        return self._height, self._width

    def addstr(self, y: int, x: int, text: str, attr: int = 0) -> None:
        if y < 0 or y >= self._height or x >= self._width:
            return
        if x < 0:
            text = _drop_display_cols_left(text, -x)
            x = 0
        max_cols = max(0, self._width - x)
        clusters = _split_display_clusters(text)[:max_cols]
        for idx, cluster in enumerate(clusters):
            self._chars[y][x + idx] = cluster
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


def overlay_frame(
    frame: Frame,
    ops: list[tuple[int, int, str, int]],
) -> Frame:
    chars = [_split_display_clusters(line) for line in frame.lines]
    attrs = [list(row) for row in frame.attrs]
    for y, x, text, attr in ops:
        if y < 0 or y >= len(chars):
            continue
        clusters = _split_display_clusters(text)
        for idx, cluster in enumerate(clusters):
            target_x = x + idx
            if target_x < 0 or target_x >= len(chars[y]):
                continue
            chars[y][target_x] = cluster
            attrs[y][target_x] = attr
    return Frame(
        lines=["".join(row) for row in chars],
        attrs=[tuple(row) for row in attrs],
    )


def _dirty_row_ops(
    ops: list[tuple[int, int, str, int]],
    rows: set[int],
) -> dict[int, list[tuple[int, int, str, int]]]:
    grouped: dict[int, list[tuple[int, int, str, int]]] = {}
    for operation in ops:
        if operation[0] in rows:
            grouped.setdefault(operation[0], []).append(operation)
    return grouped


def _overlay_row(
    base_frame: Frame,
    row: int,
    ops: list[tuple[int, int, str, int]],
) -> tuple[str, tuple[int, ...]]:
    chars = _split_display_clusters(base_frame.lines[row])
    attrs = list(base_frame.attrs[row])
    for _y, x, text, attr in ops:
        for offset, cluster in enumerate(_split_display_clusters(text)):
            target_x = x + offset
            if 0 <= target_x < len(chars):
                chars[target_x] = cluster
                attrs[target_x] = attr
    return "".join(chars), tuple(attrs)


def overlay_dirty_rows(
    current_frame: Frame,
    *,
    base_frame: Frame,
    ops: list[tuple[int, int, str, int]],
    rows: set[int],
) -> Frame:
    if not rows:
        return current_frame
    next_lines = list(current_frame.lines)
    next_attrs = list(current_frame.attrs)
    row_ops = _dirty_row_ops(ops, rows)
    for row in rows:
        if row < 0 or row >= len(base_frame.lines):
            continue
        next_lines[row], next_attrs[row] = _overlay_row(base_frame, row, row_ops.get(row, []))
    return Frame(lines=next_lines, attrs=next_attrs)


def _split_display_clusters(text: str) -> list[str]:
    clusters: list[str] = []
    for ch in text:
        if unicodedata.combining(ch):
            if clusters:
                clusters[-1] += ch
            continue
        clusters.append(ch)
    return clusters


def _drop_display_cols_left(text: str, cols: int) -> str:
    if cols <= 0 or not text:
        return text
    clusters = _split_display_clusters(text)
    if cols >= len(clusters):
        return ""
    return "".join(clusters[cols:])


def _clip_display_cols(text: str, cols: int) -> str:
    if cols <= 0 or not text:
        return ""
    clusters = _split_display_clusters(text)
    if len(clusters) <= cols:
        return text
    return "".join(clusters[:cols])


def iter_attr_runs(text: str, attrs: tuple[int, ...]) -> list[tuple[str, int]]:
    if not text and not attrs:
        return []
    clusters = _split_display_clusters(text)
    if len(clusters) < len(attrs):
        clusters.extend([" "] * (len(attrs) - len(clusters)))
    elif len(clusters) > len(attrs):
        clusters = clusters[: len(attrs)]
    if not clusters:
        return []
    runs: list[tuple[str, int]] = []
    current_attr = attrs[0] if attrs else 0
    current_text = [clusters[0]]
    for ch, attr in zip(clusters[1:], attrs[1:], strict=False):
        if attr == current_attr:
            current_text.append(ch)
            continue
        runs.append(("".join(current_text), current_attr))
        current_attr = attr
        current_text = [ch]
    runs.append(("".join(current_text), current_attr))
    return runs


def _normalized_attrs(attrs: tuple[int, ...], width: int) -> tuple[int, ...]:
    if len(attrs) > width:
        return attrs[:width]
    if len(attrs) < width:
        return attrs + (0,) * (width - len(attrs))
    return attrs


def _draw_attr_run(
    screen: Screen,
    *,
    row: int,
    x: int,
    text: str,
    attr: int,
    width: int,
) -> int | None:
    chunk_columns = len(_split_display_clusters(text))
    if x + chunk_columns > width:
        output = _clip_display_cols(text, max(0, width - x))
        if not output:
            return None
        chunk_columns = len(_split_display_clusters(output))
    else:
        output = text
    try:
        screen.addstr(row, x, output, attr)
    except CursesError:
        return None
    return chunk_columns


def _draw_frame_row(screen: Screen, frame: Frame, row: int, width: int) -> None:
    if width <= 0:
        return
    attrs = _normalized_attrs(frame.attrs[row], width)
    x = 0
    for chunk_text, attr in iter_attr_runs(frame.lines[row], attrs):
        if x >= width:
            return
        if not chunk_text:
            continue
        consumed = _draw_attr_run(screen, row=row, x=x, text=chunk_text, attr=attr, width=width)
        if consumed is None:
            return
        x += consumed


def draw_frame_rows(screen: Screen, frame: Frame, rows: set[int]) -> None:
    height, width = screen.getmaxyx()
    for row in sorted(rows):
        if row < 0 or row >= height:
            continue
        _draw_frame_row(screen, frame, row, width)
