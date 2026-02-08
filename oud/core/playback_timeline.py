from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PlaybackCursor:
    start: float
    end: float
    bar: int
    col: int

    def contains(self, elapsed: float) -> bool:
        return self.start <= elapsed <= self.end

    def __iter__(self):
        yield self.start
        yield self.end
        yield self.bar
        yield self.col


TimelineEntry = PlaybackCursor | tuple[float, float, int, int]


def cursor_from_entry(entry: TimelineEntry) -> PlaybackCursor:
    if isinstance(entry, PlaybackCursor):
        return entry
    start, end, bar, col = entry
    return PlaybackCursor(start=start, end=end, bar=bar, col=col)

