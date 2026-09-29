"""The editor's column grid of tablature cells.

The editor still types into sparse maps keyed by ``(bar, string, column)`` on a
fixed ``bar_width`` grid. These primitives edit that grid and the bar chords it
overlays. They are retired when editing moves to exact onsets; new code uses
``petrucci.input.tablature.mutation``.
"""

from __future__ import annotations

import copy
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
class TabRhythmDelta:
    bar_index: int
    column: int
    before: tuple[tuple[CellKey, int], ...]
    after: tuple[tuple[CellKey, int], ...]


@dataclass(frozen=True, slots=True)
class TabDotDelta:
    key: DotKey
    before: bool
    after: bool


@dataclass(frozen=True, slots=True)
class TabMutation:
    cells: tuple[TabCellDelta, ...] = ()
    rhythms: tuple[TabRhythmDelta, ...] = ()
    dots: tuple[TabDotDelta, ...] = ()
    chords: tuple[TabChordDelta, ...] = ()

    @property
    def changed(self) -> bool:
        return bool(self.cells or self.rhythms or self.dots or self.chords)


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


def set_tab_duration(document: EditableTablature, key: CellKey, duration: int) -> TabMutation:
    _validate_cell_key(document, key)
    if duration not in {1, 2, 4, 8, 16, 32, 64, 128}:
        _reject("invalid-duration", "duration must be a power-of-two denominator from 1 through 128")
    bar_index, _string, column = key
    before = _rhythm_snapshot(document, bar_index, column)
    document.durations[key] = duration
    after = _rhythm_snapshot(document, bar_index, column)
    return TabMutation(rhythms=(TabRhythmDelta(bar_index, column, before, after),))


def clear_tab_cell(document: EditableTablature, key: CellKey) -> TabMutation:
    _validate_cell_key(document, key)
    onset_key = _tab_onset_key(document, key)
    chord = _clear_chord_note(document, onset_key)
    cells = _clear_encoded_cells(document, onset_key)
    rhythm = _clear_rhythm(document, onset_key[0], onset_key[2])
    dot = _clear_dot(document, onset_key[0], onset_key[2])
    return TabMutation(
        cells=cells,
        rhythms=(rhythm,) if rhythm else (),
        dots=(dot,) if dot else (),
        chords=(chord,) if chord else (),
    )


def clear_tab_note(document: EditableTablature, key: CellKey) -> TabMutation:
    _validate_cell_key(document, key)
    onset_key = _tab_onset_key(document, key)
    chord = _clear_chord_note(document, onset_key)
    cells = _clear_encoded_cells(document, onset_key)
    rhythm = None
    dot = None
    if not _column_has_notes(document, onset_key[0], onset_key[2]):
        rhythm = _clear_rhythm(document, onset_key[0], onset_key[2])
        dot = _clear_dot(document, onset_key[0], onset_key[2])
    return TabMutation(
        cells=cells,
        rhythms=(rhythm,) if rhythm else (),
        dots=(dot,) if dot else (),
        chords=(chord,) if chord else (),
    )


def enter_grid_fret(
    document: EditableTablature,
    key: CellKey,
    fret: int,
    *,
    duration: int,
) -> tuple[TabMutation, ...]:
    """Write one fret into the grid, replacing that course's note at the column."""

    _validate_cell_key(document, key)
    if fret < 0:
        _reject("invalid-fret", "fret must be non-negative")
    bar_index, string_index, column = key
    changes: list[TabMutation] = []
    replaced = clear_tab_note(document, key)
    if replaced.changed:
        changes.append(replaced)
    symbols = _fret_symbols(document.style, fret)
    if column + len(symbols) > document.bar_width:
        _reject("bar-overflow", "fret representation extends beyond the bar")
    for offset, symbol in enumerate(symbols):
        changes.append(set_tab_cell(document, (bar_index, string_index, column + offset), symbol))
    if not _rhythm_snapshot(document, bar_index, column):
        changes.append(set_tab_duration(document, key, duration))
    return tuple(changes)


def _fret_symbols(style: str, fret: int) -> str:
    if style == "italian":
        return str(fret)
    letters = "abcdefghiklmnopqrst"
    if fret >= len(letters):
        _reject("invalid-fret", "fret cannot be represented in French tablature")
    return letters[fret]


def _validate_cell_key(document: EditableTablature, key: CellKey) -> None:
    bar_index, string_index, column = key
    if not 0 <= bar_index < len(document.bars):
        _reject("invalid-position", "bar index is outside the document")
    if not 0 <= string_index < document.strings:
        _reject("invalid-position", "string index is outside the document")
    if not 0 <= column < document.bar_width:
        _reject("invalid-position", "column is outside the bar")


def _rhythm_snapshot(document: EditableTablature, bar_index: int, column: int) -> tuple[tuple[CellKey, int], ...]:
    return tuple(
        sorted((key, value) for key, value in document.durations.items() if key[0] == bar_index and key[2] == column)
    )


def _tab_onset_key(document: EditableTablature, key: CellKey) -> CellKey:
    bar_index, string_index, column = key
    if document.style != "italian" or column <= 0 or key in document.durations:
        return key
    previous = (bar_index, string_index, column - 1)
    current_text = document.cells.get(key, "")
    previous_text = document.cells.get(previous, "")
    if current_text.isdigit() and previous_text.isdigit() and previous in document.durations:
        return previous
    return key


def _clear_encoded_cells(document: EditableTablature, key: CellKey) -> tuple[TabCellDelta, ...]:
    keys = [key]
    bar_index, string_index, column = key
    next_key = (bar_index, string_index, column + 1)
    text = document.cells.get(key, "")
    continuation = document.cells.get(next_key, "")
    if (
        document.style == "italian"
        and text.isdigit()
        and continuation.isdigit()
        and key in document.durations
        and next_key not in document.durations
    ):
        keys.append(next_key)
    return tuple(
        TabCellDelta(cell_key, document.cells.pop(cell_key), None) for cell_key in keys if cell_key in document.cells
    )


def _clear_rhythm(document: EditableTablature, bar_index: int, column: int) -> TabRhythmDelta | None:
    before = _rhythm_snapshot(document, bar_index, column)
    if not before:
        return None
    for key, _value in before:
        document.durations.pop(key, None)
    return TabRhythmDelta(bar_index, column, before, ())


def _clear_dot(document: EditableTablature, bar_index: int, column: int) -> TabDotDelta | None:
    key = (bar_index, column)
    if key not in document.dotted:
        return None
    document.dotted.discard(key)
    return TabDotDelta(key, True, False)


def _clear_chord_note(document: EditableTablature, key: CellKey) -> TabChordDelta | None:
    bar_index, string_index, column = key
    bar = document.bars[bar_index]
    if not bar.chords:
        return None
    before = tuple(copy.deepcopy(bar.chords))
    if not set_chord_note(bar, document.bar_width, column, string_index + 1, None):
        return None
    return TabChordDelta(bar_index, before, tuple(copy.deepcopy(bar.chords)))


def _column_has_notes(document: EditableTablature, bar_index: int, column: int) -> bool:
    if any(bar == bar_index and col == column for bar, _string, col in document.cells):
        return True
    bar = document.bars[bar_index]
    index = chord_index_at_col(bar, document.bar_width, column)
    return bool(index is not None and bar.chords[index].notes)


__all__ = [
    "EditableTablature",
    "TabCellDelta",
    "TabDotDelta",
    "TabMutation",
    "TabRhythmDelta",
    "chord_index_at_col",
    "clear_tab_cell",
    "clear_tab_note",
    "delete_chord",
    "enter_grid_fret",
    "insert_chord",
    "set_chord_note",
    "set_tab_cell",
    "set_tab_duration",
]
