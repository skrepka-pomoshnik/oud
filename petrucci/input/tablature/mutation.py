"""Tablature edits at exact onsets.

A bar's events are its ordered ``Chord`` list; a chord without notes is a rest.
An event's onset is the sum of the written durations before it, in whole notes
from the start of the bar. Edits address events by onset, never by display
column, and a transaction is applied atomically.
"""

from __future__ import annotations

import copy
from collections.abc import Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from fractions import Fraction
from typing import NoReturn

from petrucci.core.model import Bar, Chord, Note
from petrucci.core.music.time import parse_time_signature_value

DENOMINATORS = (1, 2, 4, 8, 16, 32, 64, 128)
# Chord.note_type encodes a written denominator as log2(denominator) + 2.
_NOTE_TYPES = {denominator: index + 2 for index, denominator in enumerate(DENOMINATORS)}
_DENOMINATORS = {note_type: denominator for denominator, note_type in _NOTE_TYPES.items()}
# Imported chords with an unknown note type are read as quarters, as the renderer does.
_UNKNOWN_NOTE_TYPE_DENOMINATOR = 4
FRENCH_FRET_LETTERS = "abcdefghiklmnopqrst"
STYLES = ("french", "italian")


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
    """The event at the onset becomes a single note on the course."""
    CHORD = "chord"
    """Set the course's note in the event at the onset; other courses stay."""
    REST = "rest"
    """The event at the onset becomes a rest."""
    DELETE = "delete"
    """Remove the course's note, or the whole event when no course is given.

    An event left without notes is removed, and later events move earlier.
    """
    DURATION = "duration"
    """Change the written duration of the event at the onset."""


@dataclass(frozen=True, slots=True)
class TabDuration:
    """A written duration: a power-of-two denominator and an optional dot."""

    denominator: int = 4
    dotted: bool = False

    def __post_init__(self) -> None:
        if self.denominator not in DENOMINATORS:
            _reject("invalid-duration", "duration must be a power-of-two denominator from 1 through 128")

    @property
    def whole_notes(self) -> Fraction:
        value = Fraction(1, self.denominator)
        return value * Fraction(3, 2) if self.dotted else value

    @classmethod
    def of(cls, chord: Chord) -> TabDuration:
        denominator = _DENOMINATORS.get(chord.note_type, _UNKNOWN_NOTE_TYPE_DENOMINATOR)
        return cls(denominator, chord.dotted)


@dataclass(frozen=True, slots=True)
class TabPosition:
    """An event address: bar index, onset in whole notes, and an optional 1-based course."""

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
    """One edit. ``duration=None`` keeps an existing event's duration.

    ``insert`` places a new note or rest before the event at the onset instead of
    replacing it; later events move by the new event's duration.
    """

    position: TabPosition
    intent: TabEditIntent
    fret: int | None = None
    duration: TabDuration | None = None
    insert: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.intent, TabEditIntent):
            _reject("invalid-operation", "tablature intent must be a TabEditIntent")
        self._validate_fret()
        if self.intent in {TabEditIntent.REST, TabEditIntent.DURATION} and self.position.course is not None:
            _reject("invalid-operation", f"{self.intent.value} addresses a whole event, not a course")
        if self.intent is TabEditIntent.DURATION and self.duration is None:
            _reject("invalid-operation", "duration change requires a duration")
        if self.insert and self.intent not in {TabEditIntent.NOTE, TabEditIntent.REST}:
            _reject("invalid-operation", "only notes and rests can be inserted")

    def _validate_fret(self) -> None:
        needs_note = self.intent in {TabEditIntent.NOTE, TabEditIntent.CHORD}
        if needs_note and (self.position.course is None or self.fret is None):
            _reject("invalid-operation", "note and chord entry require a course and fret")
        if not needs_note and self.fret is not None:
            _reject("invalid-operation", f"{self.intent.value} does not take a fret")
        if self.fret is not None and self.fret < 0:
            _reject("invalid-fret", "fret must be non-negative")


@dataclass(frozen=True, slots=True)
class TabEditTransaction:
    operations: tuple[TabEdit, ...]

    def __post_init__(self) -> None:
        if not self.operations:
            _reject("empty-transaction", "tablature transaction must contain at least one operation")


@dataclass(slots=True)
class TabDocument:
    """Bars edited in place; ``default_meter`` applies until a bar states its own."""

    bars: Sequence[Bar]
    strings: int
    style: str = "french"
    default_meter: str | None = None

    def __post_init__(self) -> None:
        if self.strings <= 0:
            _reject("invalid-document", "tablature must contain at least one course")
        if self.style not in STYLES:
            _reject("invalid-document", "tablature style must be french or italian")


@dataclass(frozen=True, slots=True)
class TabChordDelta:
    bar_index: int
    before: tuple[Chord, ...]
    after: tuple[Chord, ...]


@dataclass(frozen=True, slots=True)
class TabMutationResult:
    """One delta per bar the transaction changed, in bar order."""

    changes: tuple[TabChordDelta, ...] = field(default_factory=tuple)

    @property
    def changed(self) -> bool:
        return bool(self.changes)


def event_onsets(bar: Bar) -> tuple[Fraction, ...]:
    """Onset of every event in ``bar``, in whole notes."""

    onsets: list[Fraction] = []
    total = Fraction(0)
    for chord in bar.chords:
        onsets.append(total)
        total += TabDuration.of(chord).whole_notes
    return tuple(onsets)


def bar_content_length(bar: Bar) -> Fraction:
    return sum((TabDuration.of(chord).whole_notes for chord in bar.chords), Fraction(0))


def bar_meter_length(document: TabDocument, bar_index: int) -> Fraction | None:
    """Length of the bar's effective meter in whole notes, or ``None`` when unknown."""

    meter = document.default_meter
    for bar in document.bars[: bar_index + 1]:
        meter = bar.time_sig or meter
    parsed = parse_time_signature_value(meter) if meter else None
    if parsed is None:
        return None
    beats, unit = parsed
    return Fraction(beats, unit)


def apply_tab_mutation(document: TabDocument, transaction: TabEditTransaction) -> TabMutationResult:
    """Apply every edit or none; the error names the rejected operation."""

    snapshots: dict[int, list[Chord]] = {}
    for index, operation in enumerate(transaction.operations):
        try:
            _apply(document, operation, snapshots)
        except TabMutationError as exc:
            for bar_index, chords in snapshots.items():
                document.bars[bar_index].chords = chords
            raise exc.at_operation(index) from exc
    changes = (
        TabChordDelta(bar_index, tuple(before), tuple(copy.deepcopy(document.bars[bar_index].chords)))
        for bar_index, before in sorted(snapshots.items())
    )
    return TabMutationResult(tuple(delta for delta in changes if delta.before != delta.after))


def _apply(document: TabDocument, operation: TabEdit, snapshots: dict[int, list[Chord]]) -> None:
    position = operation.position
    if position.bar_index >= len(document.bars):
        _reject("invalid-position", "bar index is outside the document")
    if position.course is not None and position.course > document.strings:
        _reject("invalid-position", "course exceeds the document course count")
    if operation.fret is not None and document.style == "french" and operation.fret >= len(FRENCH_FRET_LETTERS):
        _reject("invalid-fret", "fret cannot be represented in French tablature")
    bar = document.bars[position.bar_index]
    if position.bar_index not in snapshots:
        snapshots[position.bar_index] = copy.deepcopy(bar.chords)
    length_before = bar_content_length(bar)
    _EDITORS[operation.intent](bar, operation)
    _check_meter(document, position.bar_index, length_before)


def _check_meter(document: TabDocument, bar_index: int, length_before: Fraction) -> None:
    meter = bar_meter_length(document, bar_index)
    length = bar_content_length(document.bars[bar_index])
    # A bar that already overflowed its meter (imported source) may still be edited
    # as long as the edit does not lengthen it further.
    if meter is not None and length > meter and length > length_before:
        _reject("bar-overflow", "edit makes the bar longer than its meter")


def _event_index(bar: Bar, onset: Fraction) -> int:
    """Index of the event at ``onset``; ``len(bar.chords)`` is the append slot."""

    for index, event_onset in enumerate(event_onsets(bar)):
        if event_onset == onset:
            return index
        if event_onset > onset:
            _reject("not-an-onset", "onset falls inside an event")
    if onset == bar_content_length(bar):
        return len(bar.chords)
    if onset < bar_content_length(bar):
        _reject("not-an-onset", "onset falls inside an event")
    _reject("beyond-content", "onset is past the end of the bar's events")


def _existing_event(bar: Bar, onset: Fraction) -> Chord:
    index = _event_index(bar, onset)
    if index == len(bar.chords):
        _reject("no-event", "no event starts at the onset")
    return bar.chords[index]


def _new_chord(operation: TabEdit, notes: list[Note]) -> Chord:
    if operation.duration is None:
        _reject("missing-duration", "a new event needs a duration")
    duration = operation.duration
    return Chord(note_type=_NOTE_TYPES[duration.denominator], dotted=duration.dotted, grid=None, notes=notes)


def _set_duration(chord: Chord, duration: TabDuration | None) -> None:
    if duration is None or duration == TabDuration.of(chord):
        return
    chord.note_type = _NOTE_TYPES[duration.denominator]
    chord.dotted = duration.dotted
    # The source flag marker described the old duration.
    chord.grid = None


def _place(bar: Bar, operation: TabEdit, notes: list[Note]) -> None:
    index = _event_index(bar, operation.position.onset)
    if operation.insert or index == len(bar.chords):
        bar.chords.insert(index, _new_chord(operation, notes))
        return
    chord = bar.chords[index]
    chord.notes = notes
    _set_duration(chord, operation.duration)


def _edit_note(bar: Bar, operation: TabEdit) -> None:
    assert operation.position.course is not None and operation.fret is not None
    _place(bar, operation, [Note(string=operation.position.course, fret=operation.fret, raw_pos=0)])


def _edit_rest(bar: Bar, operation: TabEdit) -> None:
    _place(bar, operation, [])


def _edit_chord(bar: Bar, operation: TabEdit) -> None:
    course, fret = operation.position.course, operation.fret
    assert course is not None and fret is not None
    index = _event_index(bar, operation.position.onset)
    if index == len(bar.chords):
        bar.chords.append(_new_chord(operation, [Note(string=course, fret=fret, raw_pos=0)]))
        return
    chord = bar.chords[index]
    existing = next((note for note in chord.notes if note.string == course), None)
    if existing is None:
        chord.notes.append(Note(string=course, fret=fret, raw_pos=0))
    else:
        # Keep the note's fingerings and ornaments; only the fret changes.
        existing.fret = fret
    _set_duration(chord, operation.duration)


def _edit_delete(bar: Bar, operation: TabEdit) -> None:
    index = _event_index(bar, operation.position.onset)
    if index == len(bar.chords):
        _reject("no-event", "no event starts at the onset")
    course = operation.position.course
    chord = bar.chords[index]
    if course is None:
        bar.chords.pop(index)
        return
    remaining = [note for note in chord.notes if note.string != course]
    if len(remaining) == len(chord.notes):
        return
    if remaining:
        chord.notes = remaining
    else:
        bar.chords.pop(index)


def _edit_duration(bar: Bar, operation: TabEdit) -> None:
    _set_duration(_existing_event(bar, operation.position.onset), operation.duration)


_EDITORS = {
    TabEditIntent.NOTE: _edit_note,
    TabEditIntent.CHORD: _edit_chord,
    TabEditIntent.REST: _edit_rest,
    TabEditIntent.DELETE: _edit_delete,
    TabEditIntent.DURATION: _edit_duration,
}


__all__ = [
    "DENOMINATORS",
    "TabChordDelta",
    "TabDocument",
    "TabDuration",
    "TabEdit",
    "TabEditIntent",
    "TabEditTransaction",
    "TabMutationError",
    "TabMutationResult",
    "TabPosition",
    "apply_tab_mutation",
    "bar_content_length",
    "bar_meter_length",
    "event_onsets",
]
