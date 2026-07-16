from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from oud.petrucci import (
    CellStyle,
    EventKind,
    EventOverlay,
    LayoutViewport,
    NotationEvent,
    NotationMeasure,
    NotationScore,
    NotationStaff,
    OverlayRole,
    ScoreTypesetOptions,
    TimeSignature,
    layout_score,
    pitch_from_midi,
    typeset_score,
)


@dataclass(frozen=True)
class ConsumerFlowEvent:
    id: str
    midi: int | None
    onset: Fraction
    duration: Fraction


def _adapt_flow(events: tuple[ConsumerFlowEvent, ...]) -> NotationScore:
    notation_events = tuple(
        NotationEvent(
            id=event.id,
            onset=event.onset,
            duration=event.duration,
            kind=EventKind.REST if event.midi is None else EventKind.NOTE,
            pitches=() if event.midi is None else (pitch_from_midi(event.midi),),
        )
        for event in events
    )
    return NotationScore(
        id="consumer-score",
        staffs=(
            NotationStaff(
                id="consumer-staff",
                measures=(
                    NotationMeasure(
                        id="consumer-measure",
                        number=1,
                        events=notation_events,
                        time_signature=TimeSignature(),
                    ),
                ),
            ),
        ),
    )


def test_external_consumer_attaches_feedback_without_oud_models_or_glyph_parsing() -> None:
    events = (
        ConsumerFlowEvent("repeat-1", 60, Fraction(0), Fraction(1, 4)),
        ConsumerFlowEvent("repeat-2", 60, Fraction(1, 4), Fraction(1, 4)),
        ConsumerFlowEvent("rest", None, Fraction(1, 2), Fraction(1, 4)),
    )
    score = _adapt_flow(events)

    result = typeset_score(
        score,
        options=ScoreTypesetOptions(width=60, height=22),
        overlays={
            "repeat-1": EventOverlay(OverlayRole.HIT),
            "repeat-2": EventOverlay(OverlayRole.MISSED),
            "rest": EventOverlay(OverlayRole.PENDING),
        },
    )

    first_onset = result.layout.onset_for("repeat-1")
    second_onset = result.layout.onset_for("repeat-2")
    assert first_onset is not None
    assert second_onset is not None
    assert first_onset.x != second_onset.x
    assert {result.semantic_frame.styles[y][x] for y, x in result.cells_for("repeat-1")} == {CellStyle.HIT}
    assert {result.semantic_frame.styles[y][x] for y, x in result.cells_for("repeat-2")} == {CellStyle.MISSED}
    assert {result.semantic_frame.styles[y][x] for y, x in result.cells_for("rest")} == {CellStyle.PENDING}


def test_external_consumer_can_follow_an_event_across_systems_and_resize() -> None:
    first = NotationEvent(
        "first-system",
        Fraction(0),
        Fraction(1, 4),
        EventKind.NOTE,
        (pitch_from_midi(60),),
    )
    target = NotationEvent(
        "target-system",
        Fraction(0),
        Fraction(1, 4),
        EventKind.NOTE,
        (pitch_from_midi(62),),
    )
    score = NotationScore(
        "follow-score",
        (
            NotationStaff(
                "follow-staff",
                (
                    NotationMeasure("follow-1", 1, (first,), forced_break_after=True),
                    NotationMeasure("follow-2", 2, (target,)),
                ),
            ),
        ),
    )

    for width in (40, 72):
        layout = layout_score(score, viewport=LayoutViewport(width=width, height=18))
        location = layout.location_for(target.id)
        assert location is not None
        assert layout.system_for_event(target.id) is layout.systems[location.system_index]

        result = typeset_score(
            score,
            options=ScoreTypesetOptions(width=width, height=18, system_offset=location.system_index),
            overlays={target.id: EventOverlay(OverlayRole.CURRENT)},
        )
        assert result.cells_for(target.id)
        assert {result.semantic_frame.styles[y][x] for y, x in result.cells_for(target.id)} == {
            CellStyle.CURRENT,
        }
