from __future__ import annotations

from collections.abc import Sequence
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
PlaybackEvent = tuple[int, int, int, int]


def cursor_from_entry(entry: TimelineEntry) -> PlaybackCursor:
    if isinstance(entry, PlaybackCursor):
        return entry
    start, end, bar, col = entry
    return PlaybackCursor(start=start, end=end, bar=bar, col=col)


def build_timeline_from_events(
    events: list[PlaybackEvent],
    *,
    sec_per_tick: float,
) -> list[PlaybackCursor]:
    timeline: list[PlaybackCursor] = []
    for bar, start_tick, duration_ticks, col in events:
        start = start_tick * sec_per_tick
        end = (start_tick + duration_ticks) * sec_per_tick
        timeline.append(PlaybackCursor(start=start, end=end, bar=bar, col=col))
    return timeline


def cursor_at_time(
    timeline: Sequence[TimelineEntry],
    elapsed: float,
    *,
    start_index: int = 0,
) -> tuple[int, PlaybackCursor | None]:
    if not timeline:
        return 0, None
    idx = max(0, min(start_index, len(timeline) - 1))
    while idx + 1 < len(timeline) and elapsed >= cursor_from_entry(timeline[idx + 1]).start:
        idx += 1
    while idx > 0 and elapsed < cursor_from_entry(timeline[idx]).start:
        idx -= 1
    cursor = cursor_from_entry(timeline[idx])
    if cursor.contains(elapsed):
        return idx, cursor
    return idx, None
