"""Guitar-style rhythm rows: stems, beams joining runs of short notes, and flags on lone ones.

The row against the staff holds a stem ``|`` for every note that has one (half
notes and shorter, dots as ``.`` after the stem). The row under it holds the beams: ``_`` joins
eighths, ``=`` joins sixteenths and shorter, and a note that stands alone gets its flags to the
right of its stem. A run is broken at every beat (a quarter of a whole note counted from the
bar's first note) and by any note longer than an eighth.
"""

from __future__ import annotations

from fractions import Fraction
from itertools import pairwise

Position = tuple[int, int, bool]

_PLAIN_STEM_DENOMINATOR = 4
_SIXTEENTH = 16
_BEAT = Fraction(1, 4)
_COMPOUND_UNIT = 8
_COMPOUND_BEAT = 3
_DOT_FACTOR = Fraction(3, 2)
_SINGLE_BEAM = "_"
_DOUBLE_BEAM = "="
_DOT = "."
_MIN_TUPLET_BEAM = 3  # columns between the first and last stem that fit a digit


def beat_length(beats: int, unit: int) -> Fraction:
    """Length a beam may span: three eighths in 6/8, 9/8 and 12/8 (and 3/8), else a quarter note."""

    if unit == _COMPOUND_UNIT and beats % _COMPOUND_BEAT == 0:
        return Fraction(_COMPOUND_BEAT, _COMPOUND_UNIT)
    return _BEAT


def beam_level(denom: int) -> int:
    """Beams a note carries: none up to a quarter, one for an eighth, two for a sixteenth and shorter."""

    if denom <= _PLAIN_STEM_DENOMINATOR:
        return 0
    return 1 if denom < _SIXTEENTH else 2


def _duration(denom: int, dotted: bool, ratio: Fraction = Fraction(1)) -> Fraction:
    return Fraction(1, max(1, denom)) * (_DOT_FACTOR if dotted else 1) * ratio


def beam_groups(
    positions: list[Position],
    ratios: list[Fraction] | None = None,
    beat: Fraction = _BEAT,
) -> list[list[Position]]:
    """Runs of beamed notes, one per beat, in the order of their columns.

    ``ratios`` gives the length factor of each position (2/3 for a triplet member), so a triplet of
    eighths, which fills one beat, stays in one run.
    """

    ordered = sorted(zip(positions, ratios or [Fraction(1)] * len(positions), strict=True), key=lambda item: item[0][0])
    groups: list[list[Position]] = []
    run: list[Position] = []
    run_beat: int | None = None
    onset = Fraction(0)
    for position, ratio in ordered:
        _col, denom, dotted = position
        beat_index = int(onset // beat)
        if beam_level(denom) == 0 or beat_index != run_beat:
            if run:
                groups.append(run)
            run, run_beat = [], None
        if beam_level(denom) > 0:
            run.append(position)
            run_beat = beat_index
        onset += _duration(denom, dotted, ratio)
    if run:
        groups.append(run)
    return groups


def _beam_char(level: int) -> str:
    return _DOUBLE_BEAM if level >= 2 else _SINGLE_BEAM  # noqa: PLR2004 - two beams is the double beam


def _draw_beam(row: list[str], group: list[Position]) -> None:
    for (col, denom, _dot), (next_col, next_denom, _next_dot) in pairwise(group):
        char = _beam_char(min(beam_level(denom), beam_level(next_denom)))
        for at in range(col, next_col):
            row[at] = char
    last_col, last_denom, _dot = group[-1]
    previous_denom = group[-2][1] if len(group) > 1 else last_denom
    row[last_col] = _beam_char(min(beam_level(last_denom), beam_level(previous_denom)))


def _draw_flags(row: list[str], position: Position) -> None:
    col, denom, _dot = position
    level = beam_level(denom)
    if level and col + 1 < len(row):
        row[col + 1] = _beam_char(level)


def _draw_stems(stems: list[str], positions: list[Position]) -> None:
    width = len(stems)
    for col, denom, dotted in positions:
        if not 0 <= col < width:
            continue
        stems[col] = "|" if denom > 1 else " "
        if dotted and col + 1 < width and stems[col + 1] == " ":
            stems[col + 1] = _DOT


def _label_tuplet(beams: list[str], group: list[Position], actual: int) -> None:
    """Put the tuplet number in the middle of the beam when the beam is long enough to hold it."""

    first, last = group[0][0], group[-1][0]
    middle = (first + last) // 2
    if last - first >= _MIN_TUPLET_BEAM and 0 <= middle < len(beams):
        beams[middle] = str(actual)[-1]


def guitar_rows(
    positions: list[Position],
    width: int,
    ratios: list[Fraction] | None = None,
    tuplets: list[int] | None = None,
    beat: Fraction = _BEAT,
) -> tuple[list[str], list[str]]:
    """(beam row, stem row) for notes at ``(column, denominator, dotted)``.

    ``ratios`` are the notes' length factors, ``tuplets`` their tuplet numbers (0 for none) and ``beat``
    the length a beam may span (a quarter note, or three eighths in 6/8).
    """

    stems = [" "] * width
    beams = [" "] * width
    _draw_stems(stems, positions)
    beamed: set[int] = set()
    numbers = dict(zip((position[0] for position in positions), tuplets or [0] * len(positions), strict=True))
    for group in beam_groups(positions, ratios, beat):
        inside = [position for position in group if 0 <= position[0] < width]
        if len(inside) > 1:
            _draw_beam(beams, inside)
            beamed.update(position[0] for position in inside)
            shared = {numbers.get(position[0], 0) for position in inside}
            if len(shared) == 1 and (number := shared.pop()):
                _label_tuplet(beams, inside, number)
    for position in positions:
        if position[0] not in beamed and 0 <= position[0] < width:
            _draw_flags(beams, position)
    return beams, stems
