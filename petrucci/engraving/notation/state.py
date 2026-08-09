from __future__ import annotations

from itertools import pairwise

from petrucci.engraving.layout.engine import ElementKey, ElementRole, LayoutElement, Rect, StaffRows
from petrucci.engraving.notation.types import _ScoreState
from petrucci.core.score import (
    AccidentalDisplay,
    Clef,
    KeySignature,
    NotationScore,
    NotationStaff,
    PitchStep,
    TimeSignature,
    WrittenPitch,
)


def _state_at(staff: NotationStaff, measure_index: int) -> _ScoreState:
    clef = staff.clef
    time = TimeSignature()
    key = KeySignature()
    for measure in staff.measures[: measure_index + 1]:
        clef = measure.clef or clef
        time = measure.time_signature or time
        key = measure.key_signature or key
    return _ScoreState(clef=clef, time=time, key=key)


def _visible_accidentals(staff: NotationStaff, measure_index: int) -> dict[str, frozenset[WrittenPitch]]:
    defaults = _key_signature_alters(_state_at(staff, measure_index).key)
    active: dict[tuple[PitchStep, int], int] = {}
    visible: dict[str, frozenset[WrittenPitch]] = {}
    events = sorted(staff.measures[measure_index].events, key=lambda event: (event.onset, event.voice, event.id))
    for event in events:
        event_visible: set[WrittenPitch] = set()
        for pitch in sorted(event.pitches, key=_diatonic_number):
            key = (pitch.step, pitch.octave)
            current = active.get(key, defaults.get(pitch.step, 0))
            if pitch.accidental is not AccidentalDisplay.AUTO or pitch.alter != current:
                event_visible.add(pitch)
            active[key] = pitch.alter
        visible[event.id] = frozenset(event_visible)
    return visible


def _key_signature_alters(key: KeySignature) -> dict[PitchStep, int]:
    order = (
        (PitchStep.F, PitchStep.C, PitchStep.G, PitchStep.D, PitchStep.A, PitchStep.E, PitchStep.B)
        if key.fifths >= 0
        else (PitchStep.B, PitchStep.E, PitchStep.A, PitchStep.D, PitchStep.G, PitchStep.C, PitchStep.F)
    )
    alter = 1 if key.fifths >= 0 else -1
    return dict.fromkeys(order[: abs(key.fifths)], alter)


def _maximum_key_signature_width(score: NotationScore) -> int:
    return max(
        (
            abs(_state_at(staff, measure_index).key.fifths)
            for staff in score.staffs
            for measure_index in range(len(staff.measures))
        ),
        default=0,
    )


def _key_signature_elements(
    source_id: str,
    *,
    fifths: int,
    clef: Clef,
    x: int,
    rows: StaffRows,
    index_offset: int = 0,
) -> tuple[LayoutElement, ...]:
    if fifths == 0:
        return ()
    positions = _key_signature_positions(clef=clef, sharp=fifths > 0)
    value = "sharp" if fifths > 0 else "flat"
    return tuple(
        LayoutElement(
            ElementKey(source_id, ElementRole.KEY_SIGNATURE, index_offset + index),
            Rect(x + index, rows.line_rows[-1] - position),
            value,
        )
        for index, position in enumerate(positions[: abs(fifths)])
    )


def _key_signature_positions(*, clef: Clef, sharp: bool) -> tuple[int, ...]:
    treble = (8, 5, 9, 6, 3, 7, 4) if sharp else (4, 7, 3, 6, 2, 5, 1)
    if clef is Clef.TREBLE:
        return treble
    return tuple(position - 2 for position in treble)


def _staff_position(pitch: WrittenPitch, *, clef: Clef) -> int:
    bottom = WrittenPitch(PitchStep.E, 4) if clef is Clef.TREBLE else WrittenPitch(PitchStep.G, 2)
    return _diatonic_number(pitch) - _diatonic_number(bottom)


def _diatonic_number(pitch: WrittenPitch) -> int:
    steps = {
        PitchStep.C: 0,
        PitchStep.D: 1,
        PitchStep.E: 2,
        PitchStep.F: 3,
        PitchStep.G: 4,
        PitchStep.A: 5,
        PitchStep.B: 6,
    }
    return (pitch.octave * 7) + steps[pitch.step]


def _chord_has_second(pitches: tuple[WrittenPitch, ...]) -> bool:
    positions = sorted(_diatonic_number(pitch) for pitch in pitches)
    return any(right - left == 1 for left, right in pairwise(positions))


def _chord_offsets(positions: list[int]) -> tuple[int, ...]:
    offsets: list[int] = []
    previous: int | None = None
    previous_offset = 0
    for position in positions:
        offset = 1 - previous_offset if previous is not None and position - previous == 1 else 0
        offsets.append(offset)
        previous = position
        previous_offset = offset
    return tuple(offsets)


def _slot_id(index: int) -> str:
    return f"measure-slot:{index}"


def _slot_index(value: str) -> int:
    return int(value.rsplit(":", 1)[1])
