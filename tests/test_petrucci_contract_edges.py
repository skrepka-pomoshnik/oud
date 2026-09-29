from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from fractions import Fraction

import pytest

from petrucci.core.flow import (
    FlowAdapterError,
    FlowEvent,
    FlowMeasure,
    FlowScoreOptions,
    adapt_flow_events,
    adapt_flow_measures,
)
from petrucci.core.model import Bar
from petrucci.core.score import (
    EventKind,
    KeySignature,
    LyricLine,
    LyricSyllable,
    NotationEvent,
    NotationMeasure,
    NotationScore,
    NotationSpan,
    NotationStaff,
    PitchStep,
    ProportionRatio,
    ScoreValidationError,
    SpanKind,
    TimeSignature,
    TupletRatio,
    WrittenPitch,
    duration_notation,
    pitch_from_midi,
)
from petrucci.engraving.cues import PitchCue, PitchCueError, paint_pitch_cues
from petrucci.engraving.layout.engine import (
    ElementKey,
    ElementRole,
    EventLocation,
    LayoutElement,
    LayoutError,
    LayoutMetrics,
    LayoutViewport,
    OnsetPosition,
    Rect,
    ScoreLayout,
    ScoreSystem,
    StaffRows,
    layout_collisions,
)
from petrucci.input.note.types import (
    EnterNote,
    EnterRest,
    InputPitch,
    NotatedDuration,
    NoteInputError,
    NoteInputTransaction,
    ScorePosition,
)
from petrucci.input.tablature.grid import (
    EditableTablature,
    chord_index_at_col,
    delete_chord,
    insert_chord,
    set_chord_note,
    set_tab_cell,
)
from petrucci.input.tablature.mutation import (
    TabDocument,
    TabDuration,
    TabEdit,
    TabEditIntent,
    TabEditTransaction,
    TabMutationError,
    TabPosition,
)
from petrucci.terminal.api import GlyphMode, SemanticFrame
from petrucci.terminal.canvas.framebuffer import Frame


def _rejects(error: type[Exception], factory: Callable[[], object], match: str | None = None) -> None:
    with pytest.raises(error, match=match):
        factory()


def _note(event_id: str = "note", onset: Fraction = Fraction()) -> NotationEvent:
    return NotationEvent(event_id, onset, Fraction(1, 4), EventKind.NOTE, (WrittenPitch(PitchStep.C, 4),))


def _staff(*measures: NotationMeasure, staff_id: str = "staff") -> NotationStaff:
    return NotationStaff(staff_id, measures or (NotationMeasure("measure", 1, (_note(),)),))


def test_score_value_contracts_reject_unrepresentable_music() -> None:
    cases: tuple[tuple[Callable[[], object], str], ...] = (
        (lambda: WrittenPitch(PitchStep.C, -2), "octave"),
        (lambda: WrittenPitch(PitchStep.C, 4, 3), "alteration"),
        (lambda: TimeSignature(0, 4), "beats"),
        (lambda: TimeSignature(4, 3), "power of two"),
        (lambda: KeySignature(8), "fifths"),
        (lambda: TupletRatio(0, 2), "tuplet"),
        (lambda: ProportionRatio(1, 0), "proportion"),
        (
            lambda: NotationEvent(
                "duplicate",
                Fraction(),
                Fraction(1, 4),
                EventKind.NOTE,
                (WrittenPitch(PitchStep.C, 4), WrittenPitch(PitchStep.C, 4)),
            ),
            "duplicate",
        ),
        (lambda: replace(_note(), voice=-1), "voice"),
        (lambda: NotationEvent("grace-rest", Fraction(), Fraction(1, 4), EventKind.REST, grace=True), "grace"),
        (lambda: NotationEvent("harmonic-rest", Fraction(), Fraction(1, 4), EventKind.REST, harmonic=True), "harmonic"),
        (lambda: replace(_note(), fingering="  "), "fingering"),
        (lambda: LyricSyllable("lyric", "note", ""), "text or an extender"),
        (lambda: LyricSyllable("lyric", "note", "la", verse=-1), "verse"),
        (lambda: LyricLine("line", "measure", "  "), "contain text"),
        (lambda: LyricLine("line", "measure", "text", verse=-1), "verse"),
        (lambda: NotationMeasure("measure", -1), "number"),
        (lambda: NotationStaff("staff", ()), "at least one measure"),
        (lambda: NotationScore("score", ()), "at least one staff"),
        (lambda: pitch_from_midi(128), "MIDI"),
        (lambda: NotationEvent("zero", Fraction(), Fraction(), EventKind.REST), "positive"),
        (lambda: NotationEvent("negative", Fraction(-1), Fraction(1, 4), EventKind.REST), "non-negative"),
        (lambda: NotationEvent(" ", Fraction(), Fraction(1, 4), EventKind.REST), "non-empty"),
    )
    for factory, message in cases:
        _rejects(ScoreValidationError, factory, message)
    assert duration_notation(Fraction()) is None


def test_score_reference_contracts_reject_ambiguous_structure() -> None:
    first = NotationMeasure("m1", 1, (_note("a"),))
    second = NotationMeasure("m2", 2, (_note("b"),))
    _rejects(
        ScoreValidationError,
        lambda: NotationScore("score", (_staff(first, second, staff_id="one"), _staff(first, staff_id="two"))),
        "same number",
    )
    _rejects(
        ScoreValidationError,
        lambda: NotationScore(
            "score",
            (NotationStaff("staff", (first,), lyric_lines=(LyricLine("line", "missing", "text"),)),),
        ),
        "unknown measure",
    )

    unknown_start = NotationSpan("span", SpanKind.TIE, "missing", "a")
    unknown_end = NotationSpan("span", SpanKind.TIE, "a", "missing")
    reversed_span = NotationSpan("span", SpanKind.TIE, "b", "a")
    for span, message in ((unknown_start, "start"), (unknown_end, "end"), (reversed_span, "after")):
        _rejects(
            ScoreValidationError,
            lambda span=span: NotationScore(
                "score",
                (
                    NotationStaff(
                        "staff",
                        (NotationMeasure("measure", 1, (_note("a"), _note("b", Fraction(1, 4)))),),
                        spans=(span,),
                    ),
                ),
            ),
            message,
        )
    _rejects(
        ScoreValidationError,
        lambda: NotationEvent("rest", Fraction(), Fraction(1, 4), EventKind.REST, editorial_brackets=True),
        "editorial brackets",
    )


def test_flow_contracts_reject_invalid_identity_timing_and_pitch_content() -> None:
    cases: tuple[tuple[Callable[[], object], str], ...] = (
        (lambda: FlowScoreOptions(score_id=""), "score ID"),
        (lambda: adapt_flow_events(()), "empty"),
        (lambda: FlowEvent("", Fraction(), Fraction(1), (60,)), "non-empty"),
        (lambda: FlowEvent("voice", Fraction(), Fraction(1), (60,), voice=-1), "voice"),
        (lambda: FlowEvent("lyric", Fraction(), Fraction(1), (60,), lyric=""), "lyric"),
        (lambda: FlowEvent("duplicate", Fraction(), Fraction(1), (60, 60)), "duplicate MIDI"),
        (lambda: FlowEvent("range", Fraction(), Fraction(1), (128,)), "between 0 and 127"),
        (
            lambda: FlowEvent(
                "written",
                Fraction(),
                Fraction(1),
                written_pitches=(WrittenPitch(PitchStep.C, 4), WrittenPitch(PitchStep.C, 4)),
            ),
            "duplicate written",
        ),
        (lambda: FlowEvent("negative", Fraction(-1), Fraction(1), (60,)), "non-negative"),
        (lambda: FlowEvent("zero", Fraction(), Fraction(), (60,)), "positive"),
        (lambda: adapt_flow_measures(()), "empty"),
        (lambda: FlowMeasure("", ()), "non-empty"),
        (lambda: FlowMeasure("number", (), number=-1), "number"),
        (lambda: FlowMeasure("capacity", (), beat_capacity=Fraction()), "positive"),
        (lambda: adapt_flow_measures((FlowMeasure("same", ()), FlowMeasure("same", ()))), "unique"),
    )
    for factory, message in cases:
        _rejects(FlowAdapterError, factory, message)


def _rows() -> StaffRows:
    return StaffRows(
        staff_id="staff",
        top=0,
        measure_number_row=None,
        ending_row=None,
        slur_rows=(),
        tuplet_rows=(),
        grace_row=None,
        ornament_row=None,
        fermata_row=None,
        notation_top=1,
        line_rows=(1, 3, 5, 7, 9),
        notation_bottom=9,
        tie_rows=(),
        dynamic_row=None,
        pitch_label_row=None,
        lyric_rows=(),
        bottom=10,
    )


def test_layout_value_and_lane_contracts_reject_invalid_geometry() -> None:
    cases: tuple[Callable[[], object], ...] = (
        lambda: Rect(-1, 0),
        lambda: Rect(0, 0, 0, 1),
        lambda: ElementKey("", ElementRole.NOTEHEAD),
        lambda: ElementKey("note", ElementRole.NOTEHEAD, -1),
        lambda: LayoutViewport(width=0),
        lambda: LayoutViewport(system_offset=-1),
        lambda: LayoutViewport(x_offset=-1),
        lambda: LayoutViewport(y_offset=-1),
        lambda: LayoutMetrics(event_gap=0),
        lambda: LayoutMetrics(left_padding=-1),
        lambda: replace(_rows(), line_rows=(3, 1, 5, 7, 9)),
        lambda: replace(_rows(), notation_top=2),
        lambda: replace(_rows(), notation_bottom=8),
        lambda: replace(_rows(), measure_number_row=1),
        lambda: replace(_rows(), tie_rows=(9,)),
        lambda: replace(_rows(), measure_number_row=0, slur_rows=(0,)),
    )
    for factory in cases:
        _rejects(LayoutError, factory)


def _layout(
    *,
    event_ids: tuple[str, ...] = ("event",),
    locations: tuple[EventLocation, ...] | None = None,
    onsets: tuple[OnsetPosition, ...] | None = None,
    elements: tuple[LayoutElement, ...] = (),
    clipped_event_ids: tuple[str, ...] = (),
) -> ScoreLayout:
    system = ScoreSystem(0, 0, 0, Rect(0, 0, 10, 5), (), (), elements, bool(clipped_event_ids), clipped_event_ids)
    return ScoreLayout(
        "score",
        10,
        5,
        event_ids,
        locations if locations is not None else (EventLocation("event", "staff", "measure", 0),),
        (system,),
        onsets if onsets is not None else (OnsetPosition("event", "staff", "measure", 0, 1),),
    )


def test_score_layout_references_bounds_and_collision_scan_are_enforced() -> None:
    cases: tuple[Callable[[], object], ...] = (
        lambda: _layout(event_ids=("event", "event")),
        lambda: _layout(onsets=(OnsetPosition("missing", "staff", "measure", 0, 1),)),
        lambda: _layout(locations=()),
        lambda: _layout(locations=(EventLocation("event", "staff", "measure", 1),)),
        lambda: _layout(elements=(LayoutElement(ElementKey("wide", ElementRole.NOTEHEAD), Rect(9, 0, 2, 1)),)),
        lambda: _layout(elements=(LayoutElement(ElementKey("low", ElementRole.NOTEHEAD), Rect(0, 4, 1, 2)),)),
        lambda: _layout(clipped_event_ids=("missing",)),
    )
    for factory in cases:
        _rejects(LayoutError, factory)

    elements = (
        LayoutElement(ElementKey("left", ElementRole.NOTEHEAD), Rect(2, 2)),
        LayoutElement(ElementKey("right", ElementRole.NOTEHEAD), Rect(2, 2)),
        LayoutElement(ElementKey("label", ElementRole.TITLE), Rect(2, 2)),
    )
    collisions = layout_collisions(_layout(elements=elements))
    assert [(item.left.source_id, item.right.source_id) for item in collisions] == [("left", "right")]


def _tab(*, style: str = "french") -> EditableTablature:
    return EditableTablature([Bar()], 6, 12, {}, {}, set(), style)


def test_tablature_contract_edges_preserve_atomic_mutation_state() -> None:
    base_error = TabMutationError("bad", "failure", operation_index=1)
    assert base_error.at_operation(2) is base_error
    cases: tuple[Callable[[], object], ...] = (
        lambda: TabPosition(-1, Fraction()),
        lambda: TabPosition(0, Fraction(-1)),
        lambda: TabPosition(0, Fraction(), 0),
        lambda: TabDuration(3),
        lambda: TabEdit(TabPosition(0, Fraction()), TabEditIntent.NOTE),
        lambda: TabEdit(TabPosition(0, Fraction(), 1), TabEditIntent.NOTE, fret=-1),
        lambda: TabEdit(TabPosition(0, Fraction(), 1), TabEditIntent.REST),
        lambda: TabEdit(TabPosition(0, Fraction()), TabEditIntent.REST, fret=1),
        lambda: TabEdit(TabPosition(0, Fraction()), TabEditIntent.DURATION),
        lambda: TabEdit(TabPosition(0, Fraction(), 1), TabEditIntent.DELETE, insert=True),
        lambda: TabEditTransaction(()),
        lambda: TabDocument([Bar()], 0),
        lambda: TabDocument([Bar()], 6, "german"),
        lambda: EditableTablature([Bar()], 0, 12, {}, {}, set()),
        lambda: EditableTablature([Bar()], 6, 0, {}, {}, set()),
        lambda: EditableTablature([Bar()], 6, 12, {}, {}, set(), "german"),
        lambda: set_tab_cell(_tab(), (0, 0, 0), ""),
        lambda: set_tab_cell(_tab(), (1, 0, 0), "a"),
        lambda: set_tab_cell(_tab(), (0, 6, 0), "a"),
        lambda: set_tab_cell(_tab(), (0, 0, 12), "a"),
    )
    for factory in cases:
        _rejects(TabMutationError, factory)


def test_tablature_chord_edges_report_only_real_changes() -> None:
    empty = Bar()
    assert chord_index_at_col(empty, 12, 0) is None
    assert not delete_chord(empty, 12, -1)
    insert_chord(empty, 12, 0)
    assert len(empty.chords) == 1
    assert not set_chord_note(empty, 12, 0, 1, None)
    assert set_chord_note(empty, 12, 0, 1, 3)
    assert set_chord_note(empty, 12, 0, 1, 5)
    assert set_chord_note(empty, 12, 0, 1, None)
    assert empty.chords == []
    assert not delete_chord(empty, 12, 0)


def test_note_input_value_contracts_expose_stable_error_codes() -> None:
    error = NoteInputError("bad", "failure", operation_index=2)
    assert error.at_operation(3) is error
    position = ScorePosition("staff", "measure", Fraction())
    cases: tuple[Callable[[], object], ...] = (
        lambda: ScorePosition("", "measure", Fraction()),
        lambda: ScorePosition("staff", "", Fraction()),
        lambda: ScorePosition("staff", "measure", Fraction(-1)),
        lambda: ScorePosition("staff", "measure", Fraction(), voice=-1),
        lambda: NotatedDuration(3),
        lambda: NotatedDuration(4, dots=5),
        lambda: NotatedDuration(4, tuplet_actual=3),
        lambda: NotatedDuration(4, tuplet_actual=0, tuplet_normal=2),
        lambda: InputPitch(PitchStep.C, octave=10),
        lambda: InputPitch(PitchStep.C, alter=3),
        lambda: EnterNote(position, InputPitch(PitchStep.C), chord=True, replace_event_id="event"),
        lambda: EnterNote(position, InputPitch(PitchStep.C), event_id="new", chord=True),
        lambda: EnterRest(position, event_id="new", replace_event_id="old"),
        lambda: NoteInputTransaction(()),
        lambda: NotatedDuration(128).halved(),
        lambda: NotatedDuration(1).doubled(),
    )
    for factory in cases:
        _rejects(NoteInputError, factory)
    triplet = NotatedDuration(8, dots=1, tuplet_actual=3, tuplet_normal=2)
    assert triplet.duration == Fraction(1, 8)
    assert triplet.tuplet == TupletRatio(3, 2)


def _semantic_frame(width: int = 10, height: int = 5) -> SemanticFrame:
    return SemanticFrame(
        frame=Frame([" " * width for _ in range(height)], [(0,) * width for _ in range(height)]),
        roles=tuple((None,) * width for _ in range(height)),
        element_ids=tuple((None,) * width for _ in range(height)),
    )


def test_pitch_cue_contracts_reject_incomplete_or_unknown_anchors() -> None:
    pitch = WrittenPitch(PitchStep.C, 4)
    cases: tuple[Callable[[], object], ...] = (
        lambda: PitchCue("", pitch, event_id="event"),
        lambda: PitchCue("cue", pitch),
        lambda: PitchCue("cue", pitch, staff_id="staff", measure_id="measure"),
        lambda: PitchCue("cue", pitch, staff_id="staff", measure_id="measure", onset=Fraction(-1)),
    )
    for factory in cases:
        _rejects(PitchCueError, factory)

    score = NotationScore("score", (_staff(NotationMeasure("measure", 1, (_note("event"),))),))
    layout = _layout()
    frame = _semantic_frame()
    viewport = LayoutViewport(width=10, height=5)
    cue = PitchCue("cue", pitch, event_id="event")
    _rejects(
        PitchCueError,
        lambda: paint_pitch_cues(
            frame,
            score=replace(score, id="other"),
            layout=layout,
            cues=(cue,),
            viewport=viewport,
            glyph_mode=GlyphMode.SAFE,
        ),
        "IDs must match",
    )
    _rejects(
        PitchCueError,
        lambda: paint_pitch_cues(
            frame,
            score=score,
            layout=layout,
            cues=(cue, cue),
            viewport=viewport,
            glyph_mode=GlyphMode.SAFE,
        ),
        "unique",
    )
    colliding = PitchCue("event", pitch, event_id="event")
    _rejects(
        PitchCueError,
        lambda: paint_pitch_cues(
            frame,
            score=score,
            layout=layout,
            cues=(colliding,),
            viewport=viewport,
            glyph_mode=GlyphMode.SAFE,
        ),
        "collide",
    )
    unknown = PitchCue("cue", pitch, event_id="missing")
    _rejects(
        PitchCueError,
        lambda: paint_pitch_cues(
            frame,
            score=score,
            layout=layout,
            cues=(unknown,),
            viewport=viewport,
            glyph_mode=GlyphMode.SAFE,
        ),
        "unknown event",
    )
