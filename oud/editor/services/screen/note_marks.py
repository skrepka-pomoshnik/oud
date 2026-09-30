"""Slurs and ties drawn from the marks stored on notes.

The renderer draws slurs and ties from column spans inside one bar. Notes carry
their own marks (a hammer-on starts on a note, a tie names both ends), so the
spans are derived here for the bars that have any; editor-side spans are added
by the caller. A mark that leaves its bar is kept in the score but not drawn.
"""

from __future__ import annotations

from petrucci.core.model import Bar
from petrucci.rendering.primitives.utils import chord_positions

Span = tuple[int, int, int]
SLURRED_TECHNIQUES = frozenset({"hammer-on", "pull-off"})
TIE_STARTS = frozenset({"start", "continue"})
_DEFAULT_DURATION = 4


def _has_marks(bar: Bar) -> bool:
    return any(note.tie in TIE_STARTS or note.technique in SLURRED_TECHNIQUES for c in bar.chords for note in c.notes)


def _pair_spans(index: int, bar: Bar, columns: list[int]) -> tuple[list[Span], list[Span]]:
    ties: list[Span] = []
    slurs: list[Span] = []
    for position, (chord, following) in enumerate(zip(bar.chords, bar.chords[1:], strict=False)):
        if position + 1 >= len(columns):
            break
        span = (index, columns[position], columns[position + 1])
        for note in chord.notes:
            target = next((other for other in following.notes if other.string == note.string), None)
            if target is None:
                continue
            if note.technique in SLURRED_TECHNIQUES and span not in slurs:
                slurs.append(span)
            if note.tie in TIE_STARTS and target.fret == note.fret and span not in ties:
                ties.append(span)
    return ties, slurs


def derived_spans(bars: list[Bar], bar_width: int) -> tuple[list[Span], list[Span]]:
    """(ties, slurs) as ``(bar, start column, end column)`` for pairs of chords in the same bar."""

    ties: list[Span] = []
    slurs: list[Span] = []
    for index, bar in enumerate(bars):
        if not _has_marks(bar):
            continue
        columns = [column for column, _denom, _dot in chord_positions(bar, bar_width, _DEFAULT_DURATION)]
        bar_ties, bar_slurs = _pair_spans(index, bar, columns)
        ties.extend(bar_ties)
        slurs.extend(bar_slurs)
    return ties, slurs
