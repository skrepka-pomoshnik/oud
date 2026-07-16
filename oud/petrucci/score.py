"""Canonical, source-independent input for Petrucci score layout."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from enum import StrEnum
from fractions import Fraction
from typing import NoReturn


class ScoreValidationError(ValueError):
    """Raised when a canonical notation score violates its public contract."""


def _fail(message: str) -> NoReturn:
    raise ScoreValidationError(message)


class PitchStep(StrEnum):
    C = "C"
    D = "D"
    E = "E"
    F = "F"
    G = "G"
    A = "A"
    B = "B"


class AccidentalDisplay(StrEnum):
    AUTO = "auto"
    EXPLICIT = "explicit"
    COURTESY = "courtesy"


class Clef(StrEnum):
    TREBLE = "treble"
    BASS = "bass"


class EventKind(StrEnum):
    NOTE = "note"
    REST = "rest"


class StemDirection(StrEnum):
    AUTO = "auto"
    UP = "up"
    DOWN = "down"


class BeamKind(StrEnum):
    NONE = "none"
    START = "start"
    CONTINUE = "continue"
    END = "end"
    PARTIAL_FORWARD = "partial-forward"
    PARTIAL_BACKWARD = "partial-backward"


class OrnamentKind(StrEnum):
    PLUS = "plus"


class SpanKind(StrEnum):
    TIE = "tie"
    SLUR = "slur"


class Syllabic(StrEnum):
    SINGLE = "single"
    BEGIN = "begin"
    MIDDLE = "middle"
    END = "end"


class BarlineKind(StrEnum):
    REGULAR = "regular"
    DOUBLE = "double"
    FINAL = "final"
    REPEAT_START = "repeat-start"
    REPEAT_END = "repeat-end"
    REPEAT_BOTH = "repeat-both"


@dataclass(frozen=True, slots=True)
class WrittenPitch:
    """A spelled pitch; octave follows scientific pitch notation (C4 = MIDI 60)."""

    step: PitchStep
    octave: int
    alter: int = 0
    accidental: AccidentalDisplay = AccidentalDisplay.AUTO

    def __post_init__(self) -> None:
        if not isinstance(self.step, PitchStep):
            _fail("pitch step must be a PitchStep")
        if not -1 <= self.octave <= 9:
            _fail("pitch octave must be between -1 and 9")
        if not -2 <= self.alter <= 2:
            _fail("pitch alteration must be between -2 and 2")
        if not isinstance(self.accidental, AccidentalDisplay):
            _fail("pitch accidental display must be an AccidentalDisplay")

    @property
    def midi(self) -> int:
        semitones = {
            PitchStep.C: 0,
            PitchStep.D: 2,
            PitchStep.E: 4,
            PitchStep.F: 5,
            PitchStep.G: 7,
            PitchStep.A: 9,
            PitchStep.B: 11,
        }
        return ((self.octave + 1) * 12) + semitones[self.step] + self.alter


@dataclass(frozen=True, slots=True)
class TimeSignature:
    beats: int = 4
    beat_unit: int = 4

    def __post_init__(self) -> None:
        if self.beats <= 0:
            _fail("time-signature beats must be positive")
        if self.beat_unit <= 0 or self.beat_unit & (self.beat_unit - 1):
            _fail("time-signature beat unit must be a positive power of two")

    @property
    def duration(self) -> Fraction:
        return Fraction(self.beats, self.beat_unit)


@dataclass(frozen=True, slots=True)
class KeySignature:
    fifths: int = 0

    def __post_init__(self) -> None:
        if not -7 <= self.fifths <= 7:
            _fail("key-signature fifths must be between -7 and 7")


@dataclass(frozen=True, slots=True)
class TupletRatio:
    actual: int
    normal: int

    def __post_init__(self) -> None:
        if self.actual <= 0 or self.normal <= 0:
            _fail("tuplet values must be positive")


@dataclass(frozen=True, slots=True)
class NotationEvent:
    id: str
    onset: Fraction
    duration: Fraction
    kind: EventKind
    pitches: tuple[WrittenPitch, ...] = ()
    voice: int = 0
    stem: StemDirection = StemDirection.AUTO
    beam: BeamKind = BeamKind.NONE
    tuplet: TupletRatio | None = None
    fermata: bool = False
    dynamic: str | None = None
    ornament: OrnamentKind | None = None

    def __post_init__(self) -> None:
        _validate_id(self.id, "event")
        _validate_fraction(self.onset, "event onset", allow_zero=True)
        _validate_fraction(self.duration, "event duration", allow_zero=False)
        if not isinstance(self.kind, EventKind):
            _fail("event kind must be an EventKind")
        if self.kind is EventKind.NOTE and not self.pitches:
            _fail(f"note event {self.id!r} must contain at least one pitch")
        if self.kind is EventKind.REST and self.pitches:
            _fail(f"rest event {self.id!r} cannot contain pitches")
        if any(not isinstance(pitch, WrittenPitch) for pitch in self.pitches):
            _fail(f"event {self.id!r} pitches must be WrittenPitch values")
        if len(set(self.pitches)) != len(self.pitches):
            _fail(f"event {self.id!r} contains a duplicate written pitch")
        if self.voice < 0:
            _fail("event voice must be non-negative")
        if not isinstance(self.stem, StemDirection):
            _fail("event stem must be a StemDirection")
        if not isinstance(self.beam, BeamKind):
            _fail("event beam must be a BeamKind")
        if self.tuplet is not None and not isinstance(self.tuplet, TupletRatio):
            _fail("event tuplet must be a TupletRatio")
        _validate_event_ornament(self)


@dataclass(frozen=True, slots=True)
class LyricSyllable:
    id: str
    event_id: str
    text: str
    verse: int = 0
    syllabic: Syllabic = Syllabic.SINGLE
    extender: bool = False

    def __post_init__(self) -> None:
        _validate_id(self.id, "lyric")
        _validate_id(self.event_id, "lyric event reference")
        if not self.text and not self.extender:
            _fail(f"lyric {self.id!r} must contain text or an extender")
        if self.verse < 0:
            _fail("lyric verse must be non-negative")
        if not isinstance(self.syllabic, Syllabic):
            _fail("lyric syllabic value must be a Syllabic")


@dataclass(frozen=True, slots=True)
class NotationSpan:
    id: str
    kind: SpanKind
    start_event_id: str
    end_event_id: str

    def __post_init__(self) -> None:
        _validate_id(self.id, "span")
        _validate_id(self.start_event_id, "span start reference")
        _validate_id(self.end_event_id, "span end reference")
        if not isinstance(self.kind, SpanKind):
            _fail("span kind must be a SpanKind")


@dataclass(frozen=True, slots=True)
class NotationMeasure:
    id: str
    number: int
    events: tuple[NotationEvent, ...] = ()
    time_signature: TimeSignature | None = None
    key_signature: KeySignature | None = None
    clef: Clef | None = None
    barline: BarlineKind = BarlineKind.REGULAR
    ending_numbers: tuple[int, ...] = ()
    forced_break_after: bool = False

    def __post_init__(self) -> None:
        _validate_id(self.id, "measure")
        if self.number < 0:
            _fail("measure number must be non-negative")
        if any(not isinstance(event, NotationEvent) for event in self.events):
            _fail("measure events must be NotationEvent values")
        if self.time_signature is not None and not isinstance(self.time_signature, TimeSignature):
            _fail("measure time signature must be a TimeSignature")
        if self.key_signature is not None and not isinstance(self.key_signature, KeySignature):
            _fail("measure key signature must be a KeySignature")
        if self.clef is not None and not isinstance(self.clef, Clef):
            _fail("measure clef must be a Clef")
        if not isinstance(self.barline, BarlineKind):
            _fail("measure barline must be a BarlineKind")
        if any(number <= 0 for number in self.ending_numbers):
            _fail("measure ending numbers must be positive")
        if tuple(sorted(set(self.ending_numbers))) != self.ending_numbers:
            _fail("measure ending numbers must be sorted and unique")


@dataclass(frozen=True, slots=True)
class NotationStaff:
    id: str
    measures: tuple[NotationMeasure, ...]
    clef: Clef = Clef.TREBLE
    label: str | None = None
    lyrics: tuple[LyricSyllable, ...] = ()
    spans: tuple[NotationSpan, ...] = ()

    def __post_init__(self) -> None:
        _validate_id(self.id, "staff")
        if not isinstance(self.clef, Clef):
            _fail("staff clef must be a Clef")
        if not self.measures:
            _fail(f"staff {self.id!r} must contain at least one measure")
        if any(not isinstance(measure, NotationMeasure) for measure in self.measures):
            _fail("staff measures must be NotationMeasure values")
        if any(not isinstance(lyric, LyricSyllable) for lyric in self.lyrics):
            _fail("staff lyrics must be LyricSyllable values")
        if any(not isinstance(span, NotationSpan) for span in self.spans):
            _fail("staff spans must be NotationSpan values")


@dataclass(frozen=True, slots=True)
class NotationScore:
    id: str
    staffs: tuple[NotationStaff, ...]
    title: str | None = None
    subtitle: str | None = None
    composer: str | None = None

    def __post_init__(self) -> None:
        _validate_id(self.id, "score")
        if not self.staffs:
            _fail("score must contain at least one staff")
        if any(not isinstance(staff, NotationStaff) for staff in self.staffs):
            _fail("score staffs must be NotationStaff values")
        validate_score(self)


def validate_score(score: NotationScore) -> None:
    """Validate IDs, references, timing, and aligned staff structure."""

    seen: set[str] = set()
    _claim_id(score.id, "score", seen)
    measure_count = len(score.staffs[0].measures)
    for staff in score.staffs:
        _claim_id(staff.id, "staff", seen)
        if len(staff.measures) != measure_count:
            _fail("all staffs must contain the same number of measures")
        _validate_staff(staff, seen)


def iter_score_events(score: NotationScore) -> Iterator[NotationEvent]:
    for staff in score.staffs:
        for measure in staff.measures:
            yield from measure.events


def duration_notation(duration: Fraction) -> tuple[int, int] | None:
    """Return (denominator, dots) for whole through 64th durations."""

    if not isinstance(duration, Fraction) or duration <= 0:
        return None
    for denominator in (1, 2, 4, 8, 16, 32, 64):
        base = Fraction(1, denominator)
        value = base
        addition = base
        for dots in range(3):
            if value == duration:
                return denominator, dots
            addition /= 2
            value += addition
    return None


def pitch_from_midi(midi: int, *, prefer_sharps: bool = True) -> WrittenPitch:
    """Create a deterministic written pitch when a consumer only has MIDI."""

    if not 0 <= midi <= 127:
        _fail("MIDI pitch must be between 0 and 127")
    sharp_spellings = (
        (PitchStep.C, 0),
        (PitchStep.C, 1),
        (PitchStep.D, 0),
        (PitchStep.D, 1),
        (PitchStep.E, 0),
        (PitchStep.F, 0),
        (PitchStep.F, 1),
        (PitchStep.G, 0),
        (PitchStep.G, 1),
        (PitchStep.A, 0),
        (PitchStep.A, 1),
        (PitchStep.B, 0),
    )
    flat_spellings = (
        (PitchStep.C, 0),
        (PitchStep.D, -1),
        (PitchStep.D, 0),
        (PitchStep.E, -1),
        (PitchStep.E, 0),
        (PitchStep.F, 0),
        (PitchStep.G, -1),
        (PitchStep.G, 0),
        (PitchStep.A, -1),
        (PitchStep.A, 0),
        (PitchStep.B, -1),
        (PitchStep.B, 0),
    )
    step, alter = (sharp_spellings if prefer_sharps else flat_spellings)[midi % 12]
    return WrittenPitch(step=step, octave=(midi // 12) - 1, alter=alter)


def _validate_staff(staff: NotationStaff, seen: set[str]) -> None:
    event_ids: set[str] = set()
    current_time = TimeSignature()
    for measure in staff.measures:
        _claim_id(measure.id, "measure", seen)
        if measure.time_signature is not None:
            current_time = measure.time_signature
        _validate_measure(measure, current_time.duration, seen, event_ids)
    for lyric in staff.lyrics:
        _claim_id(lyric.id, "lyric", seen)
        if lyric.event_id not in event_ids:
            _fail(f"lyric {lyric.id!r} references unknown event {lyric.event_id!r}")
    for span in staff.spans:
        _claim_id(span.id, "span", seen)
        _validate_span_references(span, event_ids)


def _validate_measure(
    measure: NotationMeasure,
    capacity: Fraction,
    seen: set[str],
    event_ids: set[str],
) -> None:
    for event in measure.events:
        _claim_id(event.id, "event", seen)
        event_ids.add(event.id)
        if event.onset + event.duration > capacity:
            _fail(f"event {event.id!r} ends after measure {measure.id!r} capacity {capacity}")


def _validate_span_references(span: NotationSpan, event_ids: set[str]) -> None:
    if span.start_event_id not in event_ids:
        _fail(f"span {span.id!r} references unknown start event {span.start_event_id!r}")
    if span.end_event_id not in event_ids:
        _fail(f"span {span.id!r} references unknown end event {span.end_event_id!r}")


def _validate_event_ornament(event: NotationEvent) -> None:
    if event.ornament is not None and not isinstance(event.ornament, OrnamentKind):
        _fail("event ornament must be an OrnamentKind")
    if event.kind is EventKind.REST and event.ornament is not None:
        _fail(f"rest event {event.id!r} cannot contain an ornament")


def _validate_fraction(value: Fraction, label: str, *, allow_zero: bool) -> None:
    if not isinstance(value, Fraction):
        _fail(f"{label} must be a Fraction")
    if value < 0 or (not allow_zero and value == 0):
        qualifier = "non-negative" if allow_zero else "positive"
        _fail(f"{label} must be {qualifier}")


def _validate_id(value: str, label: str) -> None:
    if not isinstance(value, str) or not value.strip():
        _fail(f"{label} ID must be a non-empty string")


def _claim_id(value: str, label: str, seen: set[str]) -> None:
    _validate_id(value, label)
    if value in seen:
        _fail(f"duplicate score element ID {value!r}")
    seen.add(value)
