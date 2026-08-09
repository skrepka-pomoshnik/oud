from __future__ import annotations

from fractions import Fraction
from typing import Iterable, Protocol

from oud.exports.lilypond.common import _normalized_time_sig_or_none
from petrucci.rendering.primitives.utils import note_type_to_denom


class TimedItem(Protocol):
    note_type: int | None
    dotted: bool


def notated_duration(note_type: int | None, dotted: bool) -> Fraction:
    denominator = note_type_to_denom(note_type or 4) or 4
    value = Fraction(1, denominator)
    return value * Fraction(3, 2) if dotted else value


def timed_items_duration(items: Iterable[TimedItem], *, fallback: Fraction = Fraction()) -> Fraction:
    duration = sum((notated_duration(item.note_type, item.dotted) for item in items), Fraction())
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
