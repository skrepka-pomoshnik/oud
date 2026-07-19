from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from petrucci import (
    ElementRole,
    EventKind,
    LayoutViewport,
    LyricSyllable,
    NotationEvent,
    NotationLayoutPolicy,
    NotationMeasure,
    NotationScore,
    NotationSpan,
    NotationStaff,
    ScoreTypesetOptions,
    SpanKind,
    TimeSignature,
    layout_score,
    pitch_from_midi,
    typeset_layout,
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


def test_external_consumer_decorates_event_cells_without_glyph_parsing() -> None:
    events = (
        ConsumerFlowEvent("repeat-1", 60, Fraction(0), Fraction(1, 4)),
        ConsumerFlowEvent("repeat-2", 60, Fraction(1, 4), Fraction(1, 4)),
        ConsumerFlowEvent("rest", None, Fraction(1, 2), Fraction(1, 4)),
    )
    score = _adapt_flow(events)

    result = typeset_score(score, options=ScoreTypesetOptions(width=60, height=22))

    first_onset = result.layout.onset_for("repeat-1")
    second_onset = result.layout.onset_for("repeat-2")
    assert first_onset is not None
    assert second_onset is not None
    assert first_onset.x != second_onset.x
    caller_states = {"repeat-1": "accepted", "repeat-2": "rejected", "rest": "waiting"}
    decorated = {cell: caller_states[event_id] for event_id in caller_states for cell in result.cells_for(event_id)}
    assert {decorated[cell] for cell in result.cells_for("repeat-1")} == {"accepted"}
    assert {decorated[cell] for cell in result.cells_for("repeat-2")} == {"rejected"}
    assert {decorated[cell] for cell in result.cells_for("rest")} == {"waiting"}


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
        )
        assert result.cells_for(target.id)


def test_external_score_flow_follows_repeated_notes_rests_results_and_lyrics() -> None:
    repeated_first = NotationEvent(
        "flow-c-1",
        Fraction(3, 4),
        Fraction(1, 4),
        EventKind.NOTE,
        (pitch_from_midi(60),),
    )
    rest = NotationEvent("flow-rest", Fraction(0), Fraction(1, 4), EventKind.REST)
    repeated_second = NotationEvent(
        "flow-c-2",
        Fraction(0),
        Fraction(1, 4),
        EventKind.NOTE,
        (pitch_from_midi(60),),
    )
    middle = NotationEvent(
        "flow-e",
        Fraction(1, 4),
        Fraction(1, 4),
        EventKind.NOTE,
        (pitch_from_midi(64),),
    )
    final = NotationEvent(
        "flow-g",
        Fraction(0),
        Fraction(1, 2),
        EventKind.NOTE,
        (pitch_from_midi(67),),
    )
    ordered = (rest, repeated_first, repeated_second, middle, final)
    score = NotationScore(
        "flow-acceptance",
        (
            NotationStaff(
                "flow-staff",
                (
                    NotationMeasure("flow-measure-1", 1, (rest, repeated_first), forced_break_after=True),
                    NotationMeasure("flow-measure-2", 2, (repeated_second, middle), forced_break_after=True),
                    NotationMeasure("flow-measure-3", 3, (final,)),
                ),
                lyrics=(
                    LyricSyllable("flow-lyric-1", repeated_first.id, "same"),
                    LyricSyllable("flow-lyric-2", repeated_second.id, "pitch"),
                    LyricSyllable("flow-lyric-3", middle.id, "then"),
                    LyricSyllable("flow-lyric-4", final.id, "sing"),
                ),
                spans=(NotationSpan("flow-tie", SpanKind.TIE, repeated_first.id, repeated_second.id),),
            ),
        ),
    )
    policy = NotationLayoutPolicy(
        show_title=False,
        show_measure_numbers=False,
        show_stems=False,
        show_barlines=False,
        show_pitch_labels=True,
    )

    for width in (48, 80):
        layout = layout_score(score, viewport=LayoutViewport(width=width, height=18), policy=policy)
        assert layout.location_for(repeated_first.id) != layout.location_for(repeated_second.id)
        for target in ordered:
            location = layout.location_for(target.id)
            assert location is not None
            result = typeset_score(
                score,
                options=ScoreTypesetOptions(
                    width=width,
                    height=18,
                    system_offset=location.system_index,
                    policy=policy,
                ),
            )

            target_cells = result.cells_for(target.id)
            assert target_cells
            assert result.layout.system_for_event(target.id) is result.layout.systems[location.system_index]
            if target.kind is EventKind.NOTE:
                target_roles = {result.semantic_frame.roles[y][x] for y, x in target_cells}
                assert ElementRole.PITCH_LABEL in target_roles
        tied_page = typeset_score(
            score,
            options=ScoreTypesetOptions(width=width, height=18, system_offset=1, policy=policy),
        )
        assert tied_page.cells_for("flow-tie")


def test_external_consumer_moves_horizontal_viewport_without_relayout() -> None:
    events = tuple(
        ConsumerFlowEvent(f"event-{index}", 60 + index % 8, Fraction(index, 32), Fraction(1, 32)) for index in range(24)
    )
    score = _adapt_flow(events)
    layout = layout_score(score, viewport=LayoutViewport(width=160, height=18))
    assert layout_score(score, viewport=LayoutViewport(width=160, height=18, x_offset=20)) is layout
    target = layout.onset_for("event-16")
    assert target is not None

    left = typeset_layout(
        layout,
        options=ScoreTypesetOptions(width=40, height=18, layout_width=160),
    )
    shifted = typeset_layout(
        layout,
        options=ScoreTypesetOptions(
            width=40,
            height=18,
            x_offset=max(0, target.x - 20),
            layout_width=160,
        ),
    )

    assert left.layout is layout
    assert shifted.layout is layout
    assert shifted.cells_for("event-16")
    assert all(0 <= column < 40 for _row, column in shifted.cells_for("event-16"))
