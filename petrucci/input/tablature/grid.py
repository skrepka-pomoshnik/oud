"""The editor's column grid of tablature cells.

The editor still types into sparse maps keyed by ``(bar, string, column)`` on a
fixed ``bar_width`` grid. These primitives edit that grid and the bar chords it
overlays. They are retired when editing moves to exact onsets; new code uses
``petrucci.input.tablature.mutation``.
"""

from __future__ import annotations

from collections.abc import MutableMapping, MutableSet, Sequence
from dataclasses import dataclass
from typing import NoReturn

from petrucci.core.model import Bar, Chord, Note
from petrucci.input.tablature.input import CellKey
from petrucci.input.tablature.mutation import TabChordDelta, TabMutationError
from petrucci.rendering.primitives.utils import chord_slot_positions

DotKey = tuple[int, int]


def _reject(code: str, message: str) -> NoReturn:
    raise TabMutationError(code, message)


@dataclass(slots=True)
class EditableTablature:
    bars: Sequence[Bar]
    strings: int
    bar_width: int
    cells: MutableMapping[CellKey, str]
    durations: MutableMapping[CellKey, int]
    dotted: MutableSet[DotKey]
    style: str = "french"

    def __post_init__(self) -> None:
        if self.strings <= 0:
            _reject("invalid-document", "tablature must contain at least one course")
        if self.bar_width <= 0:
            _reject("invalid-document", "tablature bar width must be positive")
        if self.style not in {"french", "italian"}:
            _reject("invalid-document", "tablature style must be french or italian")


@dataclass(frozen=True, slots=True)
class TabCellDelta:
    key: CellKey
    before: str | None
    after: str | None


@dataclass(frozen=True, slots=True)
class TabMutation:
    cells: tuple[TabCellDelta, ...] = ()
    chords: tuple[TabChordDelta, ...] = ()

    @property
    def changed(self) -> bool:
        return bool(self.cells or self.chords)


def chord_index_at_col(bar: Bar, bar_width: int, col: int, *, exact: bool = False) -> int | None:
    if not bar.chords:
        return None
    positions = chord_slot_positions(bar, bar_width, 4)
    for index, (position, _denom, _dot) in enumerate(positions):
        if position == col:
            return index
    if positions:
        if exact:
            return None
        return min(enumerate(positions), key=lambda item: abs(item[1][0] - col))[0]
    if len(bar.chords) == 1:
        return 0
    step = max(1, bar_width // len(bar.chords))
    return min(len(bar.chords) - 1, max(0, col) // step)


def set_chord_note(bar: Bar, bar_width: int, col: int, string: int, fret: int | None) -> bool:
    index = chord_index_at_col(bar, bar_width, col, exact=fret is None)
    if index is None:
        return False
    chord = bar.chords[index]
    for note in chord.notes:
        if note.string != string:
            continue
        if fret is None:
            chord.notes = [item for item in chord.notes if item.string != string]
            if not chord.notes:
                bar.chords.pop(index)
        else:
            note.fret = fret
        return True
    if fret is not None:
        chord.notes.append(Note(string=string, fret=fret, raw_pos=0))
        return True
    return False


def insert_chord(bar: Bar, bar_width: int, col: int) -> None:
    note_type = bar.chords[-1].note_type if bar.chords else 4
    dotted = bar.chords[-1].dotted if bar.chords else False
    index = chord_index_at_col(bar, bar_width, col)
    chord = Chord(note_type=note_type, dotted=dotted, grid=None)
    if index is None:
        bar.chords.append(chord)
    else:
        bar.chords.insert(index, chord)


def delete_chord(bar: Bar, bar_width: int, col: int) -> bool:
    if col < 0 or col >= bar_width:
        return False
    index = chord_index_at_col(bar, bar_width, col, exact=True)
    if index is None:
        return False
    bar.chords.pop(index)
    return True


def set_tab_cell(document: EditableTablature, key: CellKey, value: str) -> TabMutation:
    _validate_cell_key(document, key)
    if not isinstance(value, str) or not value:
        _reject("invalid-cell", "tablature cell value must be a non-empty string")
    before = document.cells.get(key)
    document.cells[key] = value
    return TabMutation(cells=(TabCellDelta(key, before, value),))


def _validate_cell_key(document: EditableTablature, key: CellKey) -> None:
    bar_index, string_index, column = key
    if not 0 <= bar_index < len(document.bars):
        _reject("invalid-position", "bar index is outside the document")
    if not 0 <= string_index < document.strings:
        _reject("invalid-position", "string index is outside the document")
    if not 0 <= column < document.bar_width:
        _reject("invalid-position", "column is outside the bar")


__all__ = [
    "EditableTablature",
    "TabCellDelta",
    "TabMutation",
    "chord_index_at_col",
    "delete_chord",
    "insert_chord",
    "set_chord_note",
    "set_tab_cell",
]
