"""Public, source-independent tablature mutation contracts."""

from __future__ import annotations

import copy
from collections.abc import MutableMapping, MutableSet, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from fractions import Fraction
from typing import NoReturn

from petrucci.model import Bar, Chord, Note
from petrucci.render_utils import chord_slot_positions
from petrucci.tab_input import CellKey

DotKey = tuple[int, int]


class TabMutationError(ValueError):
    """A rejected tablature transaction with a stable machine-readable code."""

    def __init__(self, code: str, message: str, *, operation_index: int | None = None) -> None:
        self.code = code
        self.operation_index = operation_index
        prefix = f"operation {operation_index}: " if operation_index is not None else ""
        super().__init__(f"{prefix}{message}")

    def at_operation(self, index: int) -> TabMutationError:
        if self.operation_index is not None:
            return self
        return TabMutationError(self.code, str(self), operation_index=index)


def _reject(code: str, message: str) -> NoReturn:
    raise TabMutationError(code, message)


class TabEditIntent(StrEnum):
    NOTE = "note"
    CHORD = "chord"
    REST = "rest"
    DELETE = "delete"


@dataclass(frozen=True, slots=True)
class TabPosition:
    bar_index: int
    onset: Fraction
    course: int | None = None

    def __post_init__(self) -> None:
        if self.bar_index < 0:
            _reject("invalid-position", "bar index must be non-negative")
        if not isinstance(self.onset, Fraction) or self.onset < 0:
            _reject("invalid-position", "onset must be a non-negative Fraction")
        if self.course is not None and self.course <= 0:
            _reject("invalid-position", "course must be positive")


@dataclass(frozen=True, slots=True)
class TabEdit:
    position: TabPosition
    intent: TabEditIntent
    fret: int | None = None
    duration: int = 4

    def __post_init__(self) -> None:
        if not isinstance(self.intent, TabEditIntent):
            _reject("invalid-operation", "tablature intent must be a TabEditIntent")
        if self.duration not in {1, 2, 4, 8, 16, 32, 64, 128}:
            _reject("invalid-duration", "duration must be a power-of-two denominator from 1 through 128")
        needs_note = self.intent in {TabEditIntent.NOTE, TabEditIntent.CHORD}
        if needs_note and (self.position.course is None or self.fret is None):
            _reject("invalid-operation", "note and chord entry require a course and fret")
        if self.fret is not None and self.fret < 0:
            _reject("invalid-fret", "fret must be non-negative")
        if self.intent is TabEditIntent.REST and (self.position.course is not None or self.fret is not None):
            _reject("invalid-operation", "rest entry cannot specify a course or fret")


@dataclass(frozen=True, slots=True)
class TabEditTransaction:
    operations: tuple[TabEdit, ...]

    def __post_init__(self) -> None:
        if not self.operations:
            _reject("empty-transaction", "tablature transaction must contain at least one operation")


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
class TabChordDelta:
    bar_index: int
    before: tuple[Chord, ...]
    after: tuple[Chord, ...]


@dataclass(frozen=True, slots=True)
class TabMutation:
    cells: tuple[TabCellDelta, ...] = ()
    rhythms: tuple[TabRhythmDelta, ...] = ()
    dots: tuple[TabDotDelta, ...] = ()
    chords: tuple[TabChordDelta, ...] = ()

    @property
    def changed(self) -> bool:
        return bool(self.cells or self.rhythms or self.dots or self.chords)


@dataclass(frozen=True, slots=True)
class TabMutationResult:
    changes: tuple[TabMutation, ...] = field(default_factory=tuple)

    @property
    def changed(self) -> bool:
        return any(change.changed for change in self.changes)


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


def apply_tab_mutation(document: EditableTablature, transaction: TabEditTransaction) -> TabMutationResult:
    cell_snapshot = dict(document.cells)
    duration_snapshot = dict(document.durations)
    dotted_snapshot = set(document.dotted)
    chord_snapshots = [copy.deepcopy(bar.chords) for bar in document.bars]
    changes: list[TabMutation] = []
    for index, operation in enumerate(transaction.operations):
        try:
            changes.extend(_apply_tab_edit(document, operation))
        except TabMutationError as exc:
            _restore_document(document, cell_snapshot, duration_snapshot, dotted_snapshot, chord_snapshots)
            raise exc.at_operation(index) from exc
    return TabMutationResult(tuple(changes))


def _restore_document(
    document: EditableTablature,
    cells: dict[CellKey, str],
    durations: dict[CellKey, int],
    dotted: set[DotKey],
    chords: list[list[Chord]],
) -> None:
    document.cells.clear()
    document.cells.update(cells)
    document.durations.clear()
    document.durations.update(durations)
    document.dotted.clear()
    for key in dotted:
        document.dotted.add(key)
    for bar, bar_chords in zip(document.bars, chords, strict=True):
        bar.chords = bar_chords


def _apply_tab_edit(document: EditableTablature, operation: TabEdit) -> tuple[TabMutation, ...]:
    column = _column_for_onset(document, operation.position)
    if operation.intent is TabEditIntent.DELETE:
        return _delete_at_position(document, operation.position, column)
    if operation.intent is TabEditIntent.REST:
        changes = list(_clear_column(document, operation.position.bar_index, column))
        changes.append(set_tab_duration(document, (operation.position.bar_index, 0, column), operation.duration))
        return tuple(changes)
    return _enter_fret(document, operation, column)


def _enter_fret(document: EditableTablature, operation: TabEdit, column: int) -> tuple[TabMutation, ...]:
    course, fret = _required_fret_input(document, operation)
    changes: list[TabMutation] = []
    if operation.intent is TabEditIntent.NOTE:
        changes.extend(_clear_column(document, operation.position.bar_index, column))
    else:
        replaced = clear_tab_note(document, (operation.position.bar_index, course - 1, column))
        if replaced.changed:
            changes.append(replaced)
    symbols = _fret_symbols(document.style, fret)
    if column + len(symbols) > document.bar_width:
        _reject("bar-overflow", "fret representation extends beyond the bar")
    for offset, symbol in enumerate(symbols):
        key = (operation.position.bar_index, course - 1, column + offset)
        changes.append(set_tab_cell(document, key, symbol))
    if not _rhythm_snapshot(document, operation.position.bar_index, column):
        key = (operation.position.bar_index, course - 1, column)
        changes.append(set_tab_duration(document, key, operation.duration))
    return tuple(changes)


def _required_fret_input(document: EditableTablature, operation: TabEdit) -> tuple[int, int]:
    course = operation.position.course
    fret = operation.fret
    if course is None or fret is None:
        _reject("invalid-operation", "fret entry requires a course and fret")
    if course > document.strings:
        _reject("invalid-position", "course exceeds the document course count")
    return course, fret


def _delete_at_position(document: EditableTablature, position: TabPosition, column: int) -> tuple[TabMutation, ...]:
    if position.course is None:
        return _clear_column(document, position.bar_index, column)
    if position.course > document.strings:
        _reject("invalid-position", "course exceeds the document course count")
    return (clear_tab_note(document, (position.bar_index, position.course - 1, column)),)


def _clear_column(document: EditableTablature, bar_index: int, column: int) -> tuple[TabMutation, ...]:
    changes = [clear_tab_note(document, (bar_index, string, column)) for string in range(document.strings)]
    return tuple(change for change in changes if change.changed)


def _column_for_onset(document: EditableTablature, position: TabPosition) -> int:
    if position.bar_index >= len(document.bars):
        _reject("invalid-position", "bar index is outside the document")
    scaled = position.onset * document.bar_width
    if scaled.denominator != 1:
        _reject("unrepresentable-onset", "onset does not map to the document grid")
    column = int(scaled)
    if not 0 <= column < document.bar_width:
        _reject("invalid-position", "onset is outside the bar")
    return column


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
    "TabChordDelta",
    "TabDotDelta",
    "TabEdit",
    "TabEditIntent",
    "TabEditTransaction",
    "TabMutation",
    "TabMutationError",
    "TabMutationResult",
    "TabPosition",
    "TabRhythmDelta",
    "apply_tab_mutation",
    "clear_tab_cell",
    "clear_tab_note",
    "set_tab_cell",
    "set_tab_duration",
]
