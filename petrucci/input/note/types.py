"""Public, source-independent contracts for standard-note entry."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import StrEnum
from fractions import Fraction
from typing import NoReturn, TypeAlias

from petrucci.core.score import (
    AccidentalDisplay,
    BeamKind,
    NotationScore,
    OrnamentKind,
    PitchStep,
    StemDirection,
    Syllabic,
    TupletRatio,
    WrittenPitch,
)


class NoteInputError(ValueError):
    """A rejected note-input transaction with a stable machine-readable code."""

    def __init__(self, code: str, message: str, *, operation_index: int | None = None) -> None:
        self.code = code
        self.operation_index = operation_index
        prefix = f"operation {operation_index}: " if operation_index is not None else ""
        super().__init__(f"{prefix}{message}")

    def at_operation(self, index: int) -> NoteInputError:
        if self.operation_index is not None:
            return self
        return NoteInputError(self.code, str(self), operation_index=index)


def _reject(code: str, message: str) -> NoReturn:
    raise NoteInputError(code, message)


@dataclass(frozen=True, slots=True)
class ScorePosition:
    staff_id: str
    measure_id: str
    onset: Fraction
    voice: int = 0

    def __post_init__(self) -> None:
        if not self.staff_id.strip():
            _reject("invalid-position", "staff ID must be non-empty")
        if not self.measure_id.strip():
            _reject("invalid-position", "measure ID must be non-empty")
        if not isinstance(self.onset, Fraction) or self.onset < 0:
            _reject("invalid-position", "onset must be a non-negative Fraction")
        if self.voice < 0:
            _reject("invalid-position", "voice must be non-negative")


@dataclass(frozen=True, slots=True)
class NotatedDuration:
    """A written duration; performed duration includes dots and tuplet scaling."""

    denominator: int = 4
    dots: int = 0
    tuplet_actual: int | None = None
    tuplet_normal: int | None = None

    def __post_init__(self) -> None:
        if self.denominator not in {1, 2, 4, 8, 16, 32, 64, 128}:
            _reject(
                "invalid-duration",
                "duration denominator must be one of 1, 2, 4, 8, 16, 32, 64, or 128",
            )
        if not 0 <= self.dots <= 4:
            _reject("invalid-duration", "duration dots must be between 0 and 4")
        values = (self.tuplet_actual, self.tuplet_normal)
        if (values[0] is None) != (values[1] is None):
            _reject("invalid-duration", "tuplet actual and normal values must be provided together")
        if any(value is not None and value <= 0 for value in values):
            _reject("invalid-duration", "tuplet values must be positive")

    @property
    def duration(self) -> Fraction:
        base = Fraction(1, self.denominator)
        value = sum((base / (2**dot) for dot in range(self.dots + 1)), start=Fraction())
        if self.tuplet_actual is not None and self.tuplet_normal is not None:
            value *= Fraction(self.tuplet_normal, self.tuplet_actual)
        return value

    @property
    def tuplet(self) -> TupletRatio | None:
        if self.tuplet_actual is None or self.tuplet_normal is None:
            return None
        return TupletRatio(self.tuplet_actual, self.tuplet_normal)

    def halved(self) -> NotatedDuration:
        """Return the next shorter base duration, preserving dots and tuplet ratio."""

        if self.denominator == 128:
            _reject("duration-boundary", "128th duration cannot be halved")
        return replace(self, denominator=self.denominator * 2)

    def doubled(self) -> NotatedDuration:
        """Return the next longer base duration, preserving dots and tuplet ratio."""

        if self.denominator == 1:
            _reject("duration-boundary", "whole duration cannot be doubled")
        return replace(self, denominator=self.denominator // 2)


@dataclass(frozen=True, slots=True)
class InputPitch:
    """A pitch spelling; omitted octave resolves nearest to the current anchor."""

    step: PitchStep
    octave: int | None = None
    alter: int = 0
    accidental: AccidentalDisplay = AccidentalDisplay.AUTO

    def __post_init__(self) -> None:
        if not isinstance(self.step, PitchStep):
            _reject("invalid-pitch", "pitch step must be a PitchStep")
        if self.octave is not None and not -1 <= self.octave <= 9:
            _reject("invalid-pitch", "pitch octave must be between -1 and 9")
        if not -2 <= self.alter <= 2:
            _reject("invalid-pitch", "pitch alteration must be between -2 and 2")
        if not isinstance(self.accidental, AccidentalDisplay):
            _reject("invalid-pitch", "accidental display must be an AccidentalDisplay")


@dataclass(frozen=True, slots=True)
class EventInputStyle:
    stem: StemDirection = StemDirection.AUTO
    beam: BeamKind = BeamKind.NONE
    fermata: bool = False
    dynamic: str | None = None
    ornament: OrnamentKind | None = None
    editorial_brackets: bool = False
    grace: bool = False


@dataclass(frozen=True, slots=True)
class NoteInputContext:
    duration: NotatedDuration = field(default_factory=NotatedDuration)
    pitch_anchor: WrittenPitch = field(default_factory=lambda: WrittenPitch(PitchStep.C, 4))


@dataclass(frozen=True, slots=True)
class EnterNote:
    position: ScorePosition
    pitch: InputPitch | WrittenPitch
    duration: NotatedDuration | None = None
    event_id: str | None = None
    chord: bool = False
    replace_event_id: str | None = None
    tie_from_previous: bool = False
    style: EventInputStyle | None = None

    def __post_init__(self) -> None:
        if self.chord and self.replace_event_id is not None:
            _reject("invalid-operation", "chord entry and event replacement are mutually exclusive")
        if self.event_id is not None and (self.chord or self.replace_event_id is not None):
            _reject("invalid-operation", "event ID is only valid when inserting a new event")


@dataclass(frozen=True, slots=True)
class EnterRest:
    position: ScorePosition
    duration: NotatedDuration | None = None
    event_id: str | None = None
    replace_event_id: str | None = None
    style: EventInputStyle | None = None

    def __post_init__(self) -> None:
        if self.event_id is not None and self.replace_event_id is not None:
            _reject("invalid-operation", "event ID is only valid when inserting a new rest")


@dataclass(frozen=True, slots=True)
class ReplacePitch:
    position: ScorePosition
    event_id: str
    pitch: InputPitch | WrittenPitch
    pitch_index: int = 0


@dataclass(frozen=True, slots=True)
class ChangeDuration:
    position: ScorePosition
    event_id: str
    duration: NotatedDuration


@dataclass(frozen=True, slots=True)
class DeleteEvent:
    position: ScorePosition
    event_id: str


@dataclass(frozen=True, slots=True)
class AddTie:
    start_event_id: str
    end_event_id: str
    span_id: str | None = None


@dataclass(frozen=True, slots=True)
class RemoveTie:
    span_id: str


@dataclass(frozen=True, slots=True)
class AddSlur:
    start_event_id: str
    end_event_id: str
    span_id: str | None = None


@dataclass(frozen=True, slots=True)
class RemoveSlur:
    span_id: str


@dataclass(frozen=True, slots=True)
class AddLyric:
    event_id: str
    text: str
    verse: int = 0
    syllabic: Syllabic = Syllabic.SINGLE
    extender: bool = False
    lyric_id: str | None = None


@dataclass(frozen=True, slots=True)
class RemoveLyric:
    lyric_id: str


NoteInputOperation: TypeAlias = (
    EnterNote
    | EnterRest
    | ReplacePitch
    | ChangeDuration
    | DeleteEvent
    | AddTie
    | RemoveTie
    | AddSlur
    | RemoveSlur
    | AddLyric
    | RemoveLyric
)


@dataclass(frozen=True, slots=True)
class NoteInputTransaction:
    operations: tuple[NoteInputOperation, ...]
    context: NoteInputContext = field(default_factory=NoteInputContext)

    def __post_init__(self) -> None:
        if not self.operations:
            _reject("empty-transaction", "note-input transaction must contain at least one operation")


class NoteInputChangeKind(StrEnum):
    INSERT_EVENT = "insert-event"
    STACK_PITCH = "stack-pitch"
    REPLACE_EVENT = "replace-event"
    REPLACE_PITCH = "replace-pitch"
    CHANGE_DURATION = "change-duration"
    DELETE_EVENT = "delete-event"
    ADD_TIE = "add-tie"
    REMOVE_TIE = "remove-tie"
    ADD_SLUR = "add-slur"
    REMOVE_SLUR = "remove-slur"
    ADD_LYRIC = "add-lyric"
    REMOVE_LYRIC = "remove-lyric"


@dataclass(frozen=True, slots=True)
class NoteInputChange:
    kind: NoteInputChangeKind
    element_id: str
    staff_id: str
    measure_id: str | None = None


@dataclass(frozen=True, slots=True)
class NoteInputResult:
    score: NotationScore
    context: NoteInputContext
    changes: tuple[NoteInputChange, ...]


__all__ = [
    "AddLyric",
    "AddSlur",
    "AddTie",
    "ChangeDuration",
    "DeleteEvent",
    "EnterNote",
    "EnterRest",
    "EventInputStyle",
    "InputPitch",
    "NotatedDuration",
    "NoteInputChange",
    "NoteInputChangeKind",
    "NoteInputContext",
    "NoteInputError",
    "NoteInputOperation",
    "NoteInputResult",
    "NoteInputTransaction",
    "RemoveLyric",
    "RemoveSlur",
    "RemoveTie",
    "ReplacePitch",
    "ScorePosition",
]
