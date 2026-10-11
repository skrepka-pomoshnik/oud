"""System breaks recorded in the layout tail of FT3 tablature records.

**Confirmed (2026-10-12, 193 corpus files whose bar counts match their reference PDFs).** After its objects a record
holds a layout tail: a two-byte object count, a four-byte float that Fronimo stores for the *system* the bar sits
in, then one float per object. Every bar of a system carries the same value, so a change between two consecutive
tablature records marks a system break. Of 2087 breaks in the reference PDFs 1886 are found and 8 are false; the
rest are neighbouring systems that store the same value, which the tail cannot separate.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from itertools import pairwise

from petrucci.core.model import Bar

_OBJECT_COUNT_AT = 28
_FIRST_OBJECT_AT = 30
_ITEM_COUNT_SIZE = 2
_OBJECT_HEADER_SIZE = 4
_NOTE_SIZE = 5
_TAIL_COUNT_SIZE = 2
_SYSTEM_VALUE_SIZE = 4
# Scores with sung text store a different value for almost every bar (that value is not a system value there);
# a system holds several bars, so a file where fewer pairs share a value is left without breaks.
_MIN_SHARED_PAIRS = 0.5


def system_value(record: bytes) -> bytes | None:
    """The tail's per-system value, or None when the record's objects do not frame up to a full tail."""

    objects = int.from_bytes(record[_OBJECT_COUNT_AT : _OBJECT_COUNT_AT + 2], "little") + 1
    cursor = _FIRST_OBJECT_AT
    for _ in range(objects):
        if cursor + _ITEM_COUNT_SIZE > len(record):
            return None
        items = int.from_bytes(record[cursor : cursor + _ITEM_COUNT_SIZE], "little")
        if items < 1:
            return None
        cursor += _ITEM_COUNT_SIZE + _OBJECT_HEADER_SIZE + _NOTE_SIZE * (items - 1)
    start = cursor + _TAIL_COUNT_SIZE
    if start + _SYSTEM_VALUE_SIZE > len(record):
        return None
    return record[start : start + _SYSTEM_VALUE_SIZE]


def apply_system_breaks(records: Sequence[bytes], bars: Sequence[Bar], is_tablature: Callable[[Bar], bool]) -> None:
    """Mark the last bar of each system, judged by the value change between consecutive tablature bars."""

    values: list[tuple[int, bytes]] = []
    for index, (record, bar) in enumerate(zip(records, bars, strict=False)):
        value = system_value(record) if is_tablature(bar) else None
        if value is not None:
            values.append((index, value))
    pairs = list(pairwise(values))
    if not pairs or sum(a[1] == b[1] for a, b in pairs) < _MIN_SHARED_PAIRS * len(pairs):
        return
    for (index, value), (_, following) in pairs:
        if value != following:
            bars[index].system_break = True
