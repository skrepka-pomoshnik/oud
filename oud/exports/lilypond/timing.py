from __future__ import annotations

from collections.abc import Iterable, Sequence
from fractions import Fraction
from typing import Protocol

from oud.exports.lilypond.common import _normalized_time_sig_or_none
from petrucci.rendering.primitives.utils import note_type_to_denom


class TimedItem(Protocol):
    @property
    def note_type(self) -> int | None: ...

    @property
    def dotted(self) -> bool: ...


def notated_duration(note_type: int | None, dotted: bool) -> Fraction:
    denominator = note_type_to_denom(note_type or 4) or 4
    value = Fraction(1, denominator)
    return value * Fraction(3, 2) if dotted else value


def tuplet_factor(item: object) -> Fraction:
    """``normal/actual`` of a tuplet member (2/3 in a triplet), else 1; chords have no tuplet fields."""

    actual = getattr(item, "tuplet_actual", None)
    normal = getattr(item, "tuplet_normal", None)
    return Fraction(normal, actual) if actual and normal else Fraction(1)


def timed_items_duration(items: Iterable[TimedItem], *, fallback: Fraction = Fraction()) -> Fraction:
    duration = sum((notated_duration(item.note_type, item.dotted) * tuplet_factor(item) for item in items), Fraction())
    return duration or fallback


def meter_duration(time_signature: str | None) -> Fraction:
    normalized = _normalized_time_sig_or_none(time_signature)
    if normalized is None or "/" not in normalized:
        return Fraction()
    numerator, denominator = normalized.split("/", 1)
    if not numerator.isdigit() or not denominator.isdigit() or int(denominator) == 0:
        return Fraction()
    return Fraction(int(numerator), int(denominator))


def duration_scale(target: Fraction, actual: Fraction) -> Fraction:
    if target <= 0 or actual <= 0:
        return Fraction(1)
    return target / actual


def tuplet_blocks(events: Sequence[object]) -> tuple[dict[int, tuple[int, int]], set[int]]:
    """Where ``\\tuplet`` blocks open and close: a block takes up to ``actual`` consecutive members of one ratio."""

    opens: dict[int, tuple[int, int]] = {}
    closes: set[int] = set()
    index = 0
    while index < len(events):
        ratio = (getattr(events[index], "tuplet_actual", None), getattr(events[index], "tuplet_normal", None))
        if not (ratio[0] and ratio[1]):
            index += 1
            continue
        size = 1
        while (
            size < ratio[0]
            and index + size < len(events)
            and (
                getattr(events[index + size], "tuplet_actual", None),
                getattr(events[index + size], "tuplet_normal", None),
            )
            == ratio
        ):
            size += 1
        opens[index] = (ratio[0], ratio[1])
        closes.add(index + size - 1)
        index += size
    return opens, closes
