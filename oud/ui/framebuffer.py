from __future__ import annotations

import unicodedata
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
    row_ops: dict[int, list[tuple[int, int, str, int]]] = {}
    for y, x, text, attr in ops:
        if y in rows:
            row_ops.setdefault(y, []).append((y, x, text, attr))
    for row in rows:
        if row < 0 or row >= len(base_frame.lines):
            continue
        chars = _split_display_clusters(base_frame.lines[row])
        attrs = list(base_frame.attrs[row])
        for _y, x, text, attr in row_ops.get(row, []):
            for idx, cluster in enumerate(_split_display_clusters(text)):
                target_x = x + idx
                if target_x < 0 or target_x >= len(chars):
                    continue
                chars[target_x] = cluster
                attrs[target_x] = attr
        next_lines[row] = "".join(chars)
        next_attrs[row] = tuple(attrs)
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


def draw_frame_rows(screen: Screen, frame: Frame, rows: set[int]) -> None:  # noqa: C901
    height, width = screen.getmaxyx()
    for row in sorted(rows):
        if row < 0 or row >= height:
            continue
        text = frame.lines[row]
        attrs = frame.attrs[row]
        if width <= 0:
            continue
        if len(attrs) > width:
            attrs = attrs[:width]
        elif len(attrs) < width:
            attrs = attrs + (0,) * (width - len(attrs))
        x = 0
        for chunk_text, attr in iter_attr_runs(text, attrs):
            if x >= width:
                break
            if not chunk_text:
                continue
            chunk_cols = len(_split_display_clusters(chunk_text))
            if x + chunk_cols > width:
                clipped = _clip_display_cols(chunk_text, max(0, width - x))
                if not clipped:
                    break
                chunk_out = clipped
                chunk_cols = len(_split_display_clusters(chunk_out))
            else:
                chunk_out = chunk_text
            try:
                screen.addstr(row, x, chunk_out, attr)
            except CursesError:
                break
            x += chunk_cols
