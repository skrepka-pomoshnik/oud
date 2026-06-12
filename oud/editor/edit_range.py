from __future__ import annotations

from dataclasses import dataclass

from oud.core.model import Bar
from oud.editor.ops import chord_index_at_col
from oud.editor.state import EditorState


@dataclass(frozen=True)
class BarRange:
    """Half-open bar span [start, end) used by edit commands."""

    start: int
    end: int

    @classmethod
    def single(cls, index: int) -> BarRange:
        return cls(index, index + 1)

    @classmethod
    def from_bounds(cls, start: int, end: int) -> BarRange:
        if end < start:
            start, end = end, start
        return cls(start, end)

    @classmethod
    def from_start_count(cls, start: int, count: int) -> BarRange:
        width = max(0, count)
        return cls(start, start + width)

    def clamp(self, total_bars: int) -> BarRange:
        if total_bars <= 0:
            return BarRange(0, 0)
        start = max(0, min(self.start, total_bars))
        end = max(start, min(self.end, total_bars))
        return BarRange(start, end)

    @property
    def count(self) -> int:
        return max(0, self.end - self.start)

    @property
    def is_empty(self) -> bool:
        return self.count == 0

    def indices(self) -> range:
        return range(self.start, self.end)


@dataclass(frozen=True)
class ChordRange:
    """Half-open chord span [start, end) within a single bar."""

    bar_index: int
    start: int
    end: int

    @classmethod
    def single(cls, bar_index: int, chord_index: int) -> ChordRange:
        return cls(bar_index, chord_index, chord_index + 1)

    @classmethod
    def from_bounds(cls, bar_index: int, start: int, end: int) -> ChordRange:
        if end < start:
            start, end = end, start
        return cls(bar_index, start, end)

    @classmethod
    def from_start_count(cls, bar_index: int, start: int, count: int) -> ChordRange:
        width = max(0, count)
        return cls(bar_index, start, start + width)

    def clamp(self, chord_count: int) -> ChordRange:
        if chord_count <= 0:
            return ChordRange(self.bar_index, 0, 0)
        start = max(0, min(self.start, chord_count))
        end = max(start, min(self.end, chord_count))
        return ChordRange(self.bar_index, start, end)

    @property
    def count(self) -> int:
        return max(0, self.end - self.start)

    @property
    def is_empty(self) -> bool:
        return self.count == 0

    def indices(self) -> range:
        return range(self.start, self.end)


def chord_range_at_col(bar: Bar, bar_width: int, col: int, *, bar_index: int = 0) -> ChordRange:
    idx = chord_index_at_col(bar, bar_width, col, exact=True)
    if idx is None:
        return ChordRange(bar_index, 0, 0)
    return ChordRange.single(bar_index, idx).clamp(len(bar.chords))


def chord_range_at_col_count(
    bar: Bar,
    bar_width: int,
    col: int,
    *,
    count: int,
    bar_index: int = 0,
) -> ChordRange:
    idx = chord_index_at_col(bar, bar_width, col, exact=True)
    if idx is None:
        return ChordRange(bar_index, 0, 0)
    return ChordRange.from_start_count(bar_index, idx, max(1, count)).clamp(len(bar.chords))


def bar_range_from_cursor(state: EditorState, count: int = 1) -> BarRange:
    return BarRange.from_start_count(state.cursor_bar, max(1, count)).clamp(
        len(state.piece.bars),
    )


def deletable_bar_range_from_cursor(state: EditorState, count: int = 1) -> BarRange:
    bar_range = bar_range_from_cursor(state, count)
    total = len(state.piece.bars)
    if 1 < total <= bar_range.count:
        return BarRange.from_start_count(bar_range.start, total - 1).clamp(total)
    return bar_range
