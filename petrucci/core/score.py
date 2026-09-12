"""Canonical, source-independent input for Petrucci score layout."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
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
    TRILL = "trill"
    TURN = "turn"
    MORDENT = "mordent"
    INVERTED_MORDENT = "inverted-mordent"


class SpanKind(StrEnum):
    TIE = "tie"
    SLUR = "slur"
    GLISSANDO = "glissando"


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
        minimum_pitch_octave = -1
        maximum_pitch_octave = 9
        minimum_pitch_alter = -2
        maximum_pitch_alter = 2
        if not isinstance(self.step, PitchStep):
            _fail("pitch step must be a PitchStep")
        if not minimum_pitch_octave <= self.octave <= maximum_pitch_octave:
            _fail("pitch octave must be between -1 and 9")
        if not minimum_pitch_alter <= self.alter <= maximum_pitch_alter:
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
        minimum_key_fifths = -7
        maximum_key_fifths = 7
        if not minimum_key_fifths <= self.fifths <= maximum_key_fifths:
            _fail("key-signature fifths must be between -7 and 7")


@dataclass(frozen=True, slots=True)
class TupletRatio:
    actual: int
    normal: int

    def __post_init__(self) -> None:
        if self.actual <= 0 or self.normal <= 0:
            _fail("tuplet values must be positive")


@dataclass(frozen=True, slots=True)
class ProportionRatio:
    numerator: int
    denominator: int

    def __post_init__(self) -> None:
        if self.numerator <= 0 or self.denominator <= 0:
            _fail("proportion values must be positive")


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
    editorial_brackets: bool = False
    grace: bool = False
    harmonic: bool = False
    fingering: str | None = None

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
        _validate_event_options(self)
        _validate_editorial_brackets(self)
        _validate_event_ornament(self)


def _validate_event_options(event: NotationEvent) -> None:
    if event.voice < 0:
        _fail("event voice must be non-negative")
    if not isinstance(event.stem, StemDirection):
        _fail("event stem must be a StemDirection")
    if not isinstance(event.beam, BeamKind):
        _fail("event beam must be a BeamKind")
    if event.tuplet is not None and not isinstance(event.tuplet, TupletRatio):
        _fail("event tuplet must be a TupletRatio")
    if not isinstance(event.grace, bool):
        _fail("event grace must be a bool")
    if event.kind is EventKind.REST and event.grace:
        _fail(f"rest event {event.id!r} cannot be a grace note")
    _validate_event_techniques(event)


def _validate_event_techniques(event: NotationEvent) -> None:
    if not isinstance(event.harmonic, bool):
        _fail("event harmonic must be a bool")
    if event.kind is EventKind.REST and (event.harmonic or event.fingering is not None):
        _fail(f"rest event {event.id!r} cannot have a harmonic or fingering")
    if event.fingering is not None and (not isinstance(event.fingering, str) or not event.fingering.strip()):
        _fail("event fingering must contain visible text")


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
class LyricLine:
    """Source lyric text whose notation onset is not encoded."""

    id: str
    measure_id: str
    text: str
    verse: int = 0

    def __post_init__(self) -> None:
        _validate_id(self.id, "lyric line")
        _validate_id(self.measure_id, "lyric-line measure reference")
        if not self.text.strip():
            _fail(f"lyric line {self.id!r} must contain text")
        if self.verse < 0:
            _fail("lyric-line verse must be non-negative")


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
    irregular: bool = False
    proportion: ProportionRatio | None = None
    duration: Fraction | None = None

    def __post_init__(self) -> None:
        _validate_id(self.id, "measure")
        if self.number < 0:
            _fail("measure number must be non-negative")
        if any(not isinstance(event, NotationEvent) for event in self.events):
            _fail("measure events must be NotationEvent values")
        _validate_measure_context(self)
        _validate_ending_numbers(self.ending_numbers)
        if not isinstance(self.irregular, bool):
            _fail("measure irregular must be a bool")
        if self.proportion is not None and not isinstance(self.proportion, ProportionRatio):
            _fail("measure proportion must be a ProportionRatio")
        if self.duration is not None:
            _validate_fraction(self.duration, "measure duration", allow_zero=False)


@dataclass(frozen=True, slots=True)
class NotationStaff:
    id: str
    measures: tuple[NotationMeasure, ...]
    clef: Clef = Clef.TREBLE
    label: str | None = None
    lyrics: tuple[LyricSyllable, ...] = ()
    spans: tuple[NotationSpan, ...] = ()
    lyric_lines: tuple[LyricLine, ...] = ()
    _measure_states: tuple[tuple[Clef, TimeSignature, KeySignature], ...] = field(
        init=False,
        repr=False,
        compare=False,
    )

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
        if any(not isinstance(line, LyricLine) for line in self.lyric_lines):
            _fail("staff lyric lines must be LyricLine values")
        object.__setattr__(self, "_measure_states", _effective_measure_states(self))

    def measure_state(self, measure_index: int) -> tuple[Clef, TimeSignature, KeySignature]:
        """Return the effective clef, meter, and key at one measure in constant time."""

        return self._measure_states[measure_index]


def _effective_measure_states(staff: NotationStaff) -> tuple[tuple[Clef, TimeSignature, KeySignature], ...]:
    clef = staff.clef
    time = TimeSignature()
    key = KeySignature()
    states: list[tuple[Clef, TimeSignature, KeySignature]] = []
    for measure in staff.measures:
        clef = measure.clef or clef
        time = measure.time_signature or time
        key = measure.key_signature or key
        states.append((clef, time, key))
    return tuple(states)


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
    reference_durations = _staff_measure_durations(score.staffs[0])
    if any(_staff_measure_durations(staff) != reference_durations for staff in score.staffs[1:]):
        _fail("aligned staffs must have matching measure durations")


def iter_score_events(score: NotationScore) -> Iterator[NotationEvent]:
    for staff in score.staffs:
        for measure in staff.measures:
            yield from measure.events


def duration_notation(duration: Fraction) -> tuple[int, int] | None:
    """Return (denominator, dots) for whole through 128th durations."""

    if not isinstance(duration, Fraction) or duration <= 0:
        return None
    for denominator in (1, 2, 4, 8, 16, 32, 64, 128):
        base = Fraction(1, denominator)
        value = base
        addition = base
        for dots in range(5):
            if value == duration:
                return denominator, dots
            addition /= 2
            value += addition
    return None


class DurationBase(StrEnum):
    """Named written values independent of reciprocal-denominator notation."""

    BREVE = "breve"
    WHOLE = "whole"
    HALF = "half"
    QUARTER = "quarter"
    EIGHTH = "eighth"
    SIXTEENTH = "sixteenth"
    THIRTY_SECOND = "thirty-second"
    SIXTY_FOURTH = "sixty-fourth"
    ONE_HUNDRED_TWENTY_EIGHTH = "one-hundred-twenty-eighth"


@dataclass(frozen=True, slots=True)
class DurationSpelling:
    """A written rhythmic value and its augmentation dots."""

    base: DurationBase
    dots: int = 0


_DURATION_BASES = (
    (DurationBase.BREVE, Fraction(2)),
    (DurationBase.WHOLE, Fraction(1)),
    (DurationBase.HALF, Fraction(1, 2)),
    (DurationBase.QUARTER, Fraction(1, 4)),
    (DurationBase.EIGHTH, Fraction(1, 8)),
    (DurationBase.SIXTEENTH, Fraction(1, 16)),
    (DurationBase.THIRTY_SECOND, Fraction(1, 32)),
    (DurationBase.SIXTY_FOURTH, Fraction(1, 64)),
    (DurationBase.ONE_HUNDRED_TWENTY_EIGHTH, Fraction(1, 128)),
)


def spell_duration(duration: Fraction) -> DurationSpelling | None:
    """Spell an exact duration from breve through 128th with up to four dots."""

    if not isinstance(duration, Fraction) or duration <= 0:
        return None
    for base, base_duration in _DURATION_BASES:
        value = base_duration
        addition = base_duration
        for dots in range(5):
            if value == duration:
                return DurationSpelling(base, dots)
            addition /= 2
            value += addition
    return None


def pitch_from_midi(midi: int, *, prefer_sharps: bool = True) -> WrittenPitch:
    """Create a deterministic written pitch when a consumer only has MIDI."""

    midi_min = 0
    midi_max = 127
    if not midi_min <= midi <= midi_max:
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


def _validate_measure_context(measure: NotationMeasure) -> None:
    if measure.time_signature is not None and not isinstance(measure.time_signature, TimeSignature):
        _fail("measure time signature must be a TimeSignature")
    if measure.key_signature is not None and not isinstance(measure.key_signature, KeySignature):
        _fail("measure key signature must be a KeySignature")
    if measure.clef is not None and not isinstance(measure.clef, Clef):
        _fail("measure clef must be a Clef")
    if not isinstance(measure.barline, BarlineKind):
        _fail("measure barline must be a BarlineKind")


def _validate_ending_numbers(ending_numbers: tuple[int, ...]) -> None:
    if any(number <= 0 for number in ending_numbers):
        _fail("measure ending numbers must be positive")
    if tuple(sorted(set(ending_numbers))) != ending_numbers:
        _fail("measure ending numbers must be sorted and unique")


def _validate_staff(staff: NotationStaff, seen: set[str]) -> None:
    event_order, measure_ids = _validate_staff_measures(staff.measures, seen)
    _validate_staff_lyrics(staff.lyrics, event_order, seen)
    _validate_staff_lyric_lines(staff.lyric_lines, measure_ids, seen)
    _validate_staff_spans(staff.spans, event_order, seen)


def _validate_staff_measures(
    measures: tuple[NotationMeasure, ...],
    seen: set[str],
) -> tuple[dict[str, int], set[str]]:
    event_order: dict[str, int] = {}
    measure_ids: set[str] = set()
    current_time = TimeSignature()
    for measure in measures:
        _claim_id(measure.id, "measure", seen)
        measure_ids.add(measure.id)
        if measure.time_signature is not None:
            current_time = measure.time_signature
        _validate_measure(measure, measure.duration or current_time.duration, seen, event_order)
    return event_order, measure_ids


def _validate_staff_lyrics(
    lyrics: tuple[LyricSyllable, ...],
    event_order: dict[str, int],
    seen: set[str],
) -> None:
    for lyric in lyrics:
        _claim_id(lyric.id, "lyric", seen)
        if lyric.event_id not in event_order:
            _fail(f"lyric {lyric.id!r} references unknown event {lyric.event_id!r}")


def _validate_staff_lyric_lines(
    lyric_lines: tuple[LyricLine, ...],
    measure_ids: set[str],
    seen: set[str],
) -> None:
    for line in lyric_lines:
        _claim_id(line.id, "lyric line", seen)
        if line.measure_id not in measure_ids:
            _fail(f"lyric line {line.id!r} references unknown measure {line.measure_id!r}")


def _validate_staff_spans(
    spans: tuple[NotationSpan, ...],
    event_order: dict[str, int],
    seen: set[str],
) -> None:
    for span in spans:
        _claim_id(span.id, "span", seen)
        _validate_span_references(span, event_order)


def _validate_measure(
    measure: NotationMeasure,
    capacity: Fraction,
    seen: set[str],
    event_order: dict[str, int],
) -> None:
    for event in measure.events:
        _claim_id(event.id, "event", seen)
        event_order[event.id] = len(event_order)
        if (measure.duration is not None or not measure.irregular) and event.onset + event.duration > capacity:
            _fail(f"event {event.id!r} ends after measure {measure.id!r} capacity {capacity}")


def _staff_measure_durations(staff: NotationStaff) -> tuple[Fraction, ...]:
    meter = TimeSignature()
    durations: list[Fraction] = []
    for measure in staff.measures:
        meter = measure.time_signature or meter
        durations.append(measure.duration or meter.duration)
    return tuple(durations)


def _validate_span_references(span: NotationSpan, event_order: dict[str, int]) -> None:
    if span.start_event_id not in event_order:
        _fail(f"span {span.id!r} references unknown start event {span.start_event_id!r}")
    if span.end_event_id not in event_order:
        _fail(f"span {span.id!r} references unknown end event {span.end_event_id!r}")
    if event_order[span.end_event_id] <= event_order[span.start_event_id]:
        _fail(f"span {span.id!r} must end after its start event")


def _validate_event_ornament(event: NotationEvent) -> None:
    if event.ornament is not None and not isinstance(event.ornament, OrnamentKind):
        _fail("event ornament must be an OrnamentKind")
    if event.kind is EventKind.REST and event.ornament is not None:
        _fail(f"rest event {event.id!r} cannot contain an ornament")


def _validate_editorial_brackets(event: NotationEvent) -> None:
    if not isinstance(event.editorial_brackets, bool):
        _fail("event editorial_brackets must be a bool")
    if event.kind is EventKind.REST and event.editorial_brackets:
        _fail(f"rest event {event.id!r} cannot have editorial brackets")


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
