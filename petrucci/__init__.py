"""Petrucci: reusable ASCII tablature and staff-note typesetting."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from petrucci.core.flow import (
    FlowAdapterError,
    FlowBeamPolicy,
    FlowEvent,
    FlowEventMap,
    FlowMeasure,
    FlowScore,
    FlowScoreOptions,
    FlowSegmentMap,
    adapt_flow_events,
    adapt_flow_measures,
)
from petrucci.engraving.layout.engine import (
    ElementKey,
    ElementRole,
    EventLocation,
    LayoutCollision,
    LayoutElement,
    LayoutError,
    LayoutMetrics,
    LayoutViewport,
    NotationLayoutPolicy,
    OnsetPosition,
    Rect,
    ScoreLayout,
    ScoreSystem,
    StaffRows,
    clear_layout_cache,
    layout_collisions,
    layout_score,
)
from petrucci.core.model import (
    Bar,
    Chord,
    ImportedBarContent,
    ImportedScore,
    ImportedSourceRecord,
    ImportedStaff,
    ImportedTextRow,
    LyricEvent,
    MelodyEvent,
    Note,
    Piece,
)
from petrucci.input.note.operations import apply_note_input, resolve_input_pitch
from petrucci.input.note.types import (
    AddLyric,
    AddSlur,
    AddTie,
    ChangeDuration,
    DeleteEvent,
    EnterNote,
    EnterRest,
    EventInputStyle,
    InputPitch,
    NotatedDuration,
    NoteInputChange,
    NoteInputChangeKind,
    NoteInputContext,
    NoteInputError,
    NoteInputOperation,
    NoteInputResult,
    NoteInputTransaction,
    RemoveLyric,
    RemoveSlur,
    RemoveTie,
    ReplacePitch,
    ScorePosition,
)
from petrucci.adapters.piece import PieceAdapterError, notation_score_from_piece, written_pitch_from_token
from petrucci.core.score import (
    AccidentalDisplay,
    BarlineKind,
    BeamKind,
    Clef,
    EventKind,
    KeySignature,
    LyricLine,
    LyricSyllable,
    NotationEvent,
    NotationMeasure,
    NotationScore,
    NotationSpan,
    NotationStaff,
    OrnamentKind,
    PitchStep,
    ScoreValidationError,
    SpanKind,
    StemDirection,
    Syllabic,
    TimeSignature,
    TupletRatio,
    WrittenPitch,
    duration_notation,
    pitch_from_midi,
)
from petrucci.engraving.cues import PitchCue, PitchCueError, paint_pitch_cues
from petrucci.input.tablature.input import CellKey, editor_event_columns, editor_fret_at
from petrucci.input.tablature.mutation import (
    EditableTablature,
    TabCellDelta,
    TabChordDelta,
    TabDotDelta,
    TabEdit,
    TabEditIntent,
    TabEditTransaction,
    TabMutation,
    TabMutationError,
    TabMutationResult,
    TabPosition,
    TabRhythmDelta,
    apply_tab_mutation,
    clear_tab_cell,
    clear_tab_note,
    set_tab_cell,
    set_tab_duration,
)

if TYPE_CHECKING:
    from petrucci.engraving.score_typeset import ScoreTypesetOptions, ScoreTypesetResult
    from petrucci.terminal.api import GlyphMode, SemanticFrame, TerminalNoteheads
    from petrucci.engraving.typeset import TypesetOptions, TypesetResult

__all__ = [
    "AccidentalDisplay",
    "AddLyric",
    "AddSlur",
    "AddTie",
    "Bar",
    "BarlineKind",
    "BeamKind",
    "CellKey",
    "ChangeDuration",
    "Chord",
    "Clef",
    "DeleteEvent",
    "EditableTablature",
    "ElementKey",
    "ElementRole",
    "EnterNote",
    "EnterRest",
    "EventInputStyle",
    "EventKind",
    "EventLocation",
    "FlowAdapterError",
    "FlowBeamPolicy",
    "FlowEvent",
    "FlowEventMap",
    "FlowMeasure",
    "FlowScore",
    "FlowScoreOptions",
    "FlowSegmentMap",
    "GlyphMode",
    "ImportedBarContent",
    "ImportedScore",
    "ImportedSourceRecord",
    "ImportedStaff",
    "ImportedTextRow",
    "InputPitch",
    "KeySignature",
    "LayoutCollision",
    "LayoutElement",
    "LayoutError",
    "LayoutMetrics",
    "LayoutViewport",
    "LyricEvent",
    "LyricLine",
    "LyricSyllable",
    "MelodyEvent",
    "NotatedDuration",
    "NotationEvent",
    "NotationLayoutPolicy",
    "NotationMeasure",
    "NotationScore",
    "NotationSpan",
    "NotationStaff",
    "Note",
    "NoteInputChange",
    "NoteInputChangeKind",
    "NoteInputContext",
    "NoteInputError",
    "NoteInputOperation",
    "NoteInputResult",
    "NoteInputTransaction",
    "OnsetPosition",
    "OrnamentKind",
    "Piece",
    "PieceAdapterError",
    "PitchCue",
    "PitchCueError",
    "PitchStep",
    "Rect",
    "RemoveLyric",
    "RemoveSlur",
    "RemoveTie",
    "ReplacePitch",
    "ScoreLayout",
    "ScorePosition",
    "ScoreSystem",
    "ScoreTypesetOptions",
    "ScoreTypesetResult",
    "ScoreValidationError",
    "SemanticFrame",
    "SpanKind",
    "StaffRows",
    "StemDirection",
    "Syllabic",
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
    "TerminalNoteheads",
    "TimeSignature",
    "TupletRatio",
    "TypesetOptions",
    "TypesetResult",
    "WrittenPitch",
    "adapt_flow_events",
    "adapt_flow_measures",
    "apply_note_input",
    "apply_tab_mutation",
    "clear_layout_cache",
    "clear_tab_cell",
    "clear_tab_note",
    "duration_notation",
    "editor_event_columns",
    "editor_fret_at",
    "layout_collisions",
    "layout_score",
    "notation_score_from_piece",
    "paint_pitch_cues",
    "paint_score",
    "pitch_from_midi",
    "resolve_input_pitch",
    "set_tab_cell",
    "set_tab_duration",
    "typeset_layout",
    "typeset_piece",
    "typeset_score",
    "typeset_text",
    "written_pitch_from_token",
]


def __getattr__(name: str) -> Any:
    if name in {"TypesetOptions", "TypesetResult"}:
        from petrucci.engraving import typeset  # noqa: PLC0415

        return getattr(typeset, name)
    if name in {"ScoreTypesetOptions", "ScoreTypesetResult"}:
        from petrucci.engraving import score_typeset  # noqa: PLC0415

        return getattr(score_typeset, name)
    if name in {"GlyphMode", "SemanticFrame", "TerminalNoteheads"}:
        from petrucci.terminal import api as terminal  # noqa: PLC0415

        return getattr(terminal, name)
    raise AttributeError(name)


def typeset_piece(*args, **kwargs):
    from petrucci.engraving.typeset import typeset_piece as _typeset_piece  # noqa: PLC0415

    return _typeset_piece(*args, **kwargs)


def typeset_text(*args, **kwargs):
    from petrucci.engraving.typeset import typeset_text as _typeset_text  # noqa: PLC0415

    return _typeset_text(*args, **kwargs)


def typeset_score(
    score: NotationScore,
    *,
    options: ScoreTypesetOptions | None = None,
) -> ScoreTypesetResult:
    from petrucci.engraving.score_typeset import typeset_score as _typeset_score  # noqa: PLC0415

    return _typeset_score(score, options=options)


def typeset_layout(
    layout: ScoreLayout,
    *,
    options: ScoreTypesetOptions | None = None,
    score: NotationScore | None = None,
) -> ScoreTypesetResult:
    from petrucci.engraving.score_typeset import typeset_layout as _typeset_layout  # noqa: PLC0415

    return _typeset_layout(layout, options=options, score=score)


def paint_score(
    layout: ScoreLayout,
    *,
    viewport: LayoutViewport | None = None,
    glyph_mode: GlyphMode | None = None,
    noteheads: TerminalNoteheads | None = None,
) -> SemanticFrame:
    from petrucci.terminal.api import paint_score as _paint_score  # noqa: PLC0415

    if glyph_mode is None:
        return _paint_score(layout, viewport=viewport, noteheads=noteheads)
    return _paint_score(layout, viewport=viewport, glyph_mode=glyph_mode, noteheads=noteheads)
