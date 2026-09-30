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
_DOT_FACTOR = Fraction(3, 2)
_SINGLE_BEAM = "_"
_DOUBLE_BEAM = "="
_DOT = "."


def beam_level(denom: int) -> int:
    """Beams a note carries: none up to a quarter, one for an eighth, two for a sixteenth and shorter."""

    if denom <= _PLAIN_STEM_DENOMINATOR:
        return 0
    return 1 if denom < _SIXTEENTH else 2


def _duration(denom: int, dotted: bool) -> Fraction:
    return Fraction(1, max(1, denom)) * (_DOT_FACTOR if dotted else 1)


def beam_groups(positions: list[Position]) -> list[list[Position]]:
    """Runs of beamed notes, one per beat, in the order of their columns."""

    groups: list[list[Position]] = []
    run: list[Position] = []
    run_beat: int | None = None
    onset = Fraction(0)
    for position in sorted(positions, key=lambda item: item[0]):
        _col, denom, dotted = position
        beat = int(onset // _BEAT)
        if beam_level(denom) == 0 or beat != run_beat:
            if run:
                groups.append(run)
            run, run_beat = [], None
        if beam_level(denom) > 0:
            run.append(position)
            run_beat = beat
        onset += _duration(denom, dotted)
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


def guitar_rows(positions: list[Position], width: int) -> tuple[list[str], list[str]]:
    """(beam row, stem row) for notes at ``(column, denominator, dotted)``."""

    stems = [" "] * width
    beams = [" "] * width
    _draw_stems(stems, positions)
    beamed: set[int] = set()
    for group in beam_groups(positions):
        inside = [position for position in group if 0 <= position[0] < width]
        if len(inside) > 1:
            _draw_beam(beams, inside)
            beamed.update(position[0] for position in inside)
    for position in positions:
        if position[0] not in beamed and 0 <= position[0] < width:
            _draw_flags(beams, position)
    return beams, stems
