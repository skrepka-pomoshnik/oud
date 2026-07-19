"""Petrucci: reusable ASCII tablature and staff-note typesetting."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from petrucci.flow import (
    FlowAdapterError,
    FlowEvent,
    FlowEventMap,
    FlowScore,
    FlowScoreOptions,
    adapt_flow_events,
)
from petrucci.layout import (
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
from petrucci.model import (
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
from petrucci.piece_adapter import PieceAdapterError, notation_score_from_piece, written_pitch_from_token
from petrucci.score import (
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
    pitch_from_midi,
)
from petrucci.tab_input import CellKey, editor_event_columns, editor_fret_at

if TYPE_CHECKING:
    from petrucci.score_typeset import ScoreTypesetOptions, ScoreTypesetResult
    from petrucci.terminal import GlyphMode, SemanticFrame
    from petrucci.typeset import TypesetOptions, TypesetResult

__all__ = [
    "AccidentalDisplay",
    "Bar",
    "BarlineKind",
    "BeamKind",
    "CellKey",
    "Chord",
    "Clef",
    "ElementKey",
    "ElementRole",
    "EventKind",
    "EventLocation",
    "FlowAdapterError",
    "FlowEvent",
    "FlowEventMap",
    "FlowScore",
    "FlowScoreOptions",
    "GlyphMode",
    "ImportedBarContent",
    "ImportedScore",
    "ImportedSourceRecord",
    "ImportedStaff",
    "ImportedTextRow",
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
    "NotationEvent",
    "NotationLayoutPolicy",
    "NotationMeasure",
    "NotationScore",
    "NotationSpan",
    "NotationStaff",
    "Note",
    "OnsetPosition",
    "OrnamentKind",
    "Piece",
    "PieceAdapterError",
    "PitchStep",
    "Rect",
    "ScoreLayout",
    "ScoreSystem",
    "ScoreTypesetOptions",
    "ScoreTypesetResult",
    "ScoreValidationError",
    "SemanticFrame",
    "SpanKind",
    "StaffRows",
    "StemDirection",
    "Syllabic",
    "TimeSignature",
    "TupletRatio",
    "TypesetOptions",
    "TypesetResult",
    "WrittenPitch",
    "adapt_flow_events",
    "clear_layout_cache",
    "editor_event_columns",
    "editor_fret_at",
    "layout_collisions",
    "layout_score",
    "notation_score_from_piece",
    "paint_score",
    "pitch_from_midi",
    "typeset_layout",
    "typeset_piece",
    "typeset_score",
    "typeset_text",
    "written_pitch_from_token",
]


def __getattr__(name: str) -> Any:
    if name in {"TypesetOptions", "TypesetResult"}:
        from petrucci import typeset  # noqa: PLC0415

        return getattr(typeset, name)
    if name in {"ScoreTypesetOptions", "ScoreTypesetResult"}:
        from petrucci import score_typeset  # noqa: PLC0415

        return getattr(score_typeset, name)
    if name in {"GlyphMode", "SemanticFrame"}:
        from petrucci import terminal  # noqa: PLC0415

        return getattr(terminal, name)
    raise AttributeError(name)


def typeset_piece(*args, **kwargs):
    from petrucci.typeset import typeset_piece as _typeset_piece  # noqa: PLC0415

    return _typeset_piece(*args, **kwargs)


def typeset_text(*args, **kwargs):
    from petrucci.typeset import typeset_text as _typeset_text  # noqa: PLC0415

    return _typeset_text(*args, **kwargs)


def typeset_score(
    score: NotationScore,
    *,
    options: ScoreTypesetOptions | None = None,
) -> ScoreTypesetResult:
    from petrucci.score_typeset import typeset_score as _typeset_score  # noqa: PLC0415

    return _typeset_score(score, options=options)


def typeset_layout(
    layout: ScoreLayout,
    *,
    options: ScoreTypesetOptions | None = None,
) -> ScoreTypesetResult:
    from petrucci.score_typeset import typeset_layout as _typeset_layout  # noqa: PLC0415

    return _typeset_layout(layout, options=options)


def paint_score(
    layout: ScoreLayout,
    *,
    viewport: LayoutViewport | None = None,
    glyph_mode: GlyphMode | None = None,
) -> SemanticFrame:
    from petrucci.terminal import paint_score as _paint_score  # noqa: PLC0415

    if glyph_mode is None:
        return _paint_score(layout, viewport=viewport)
    return _paint_score(layout, viewport=viewport, glyph_mode=glyph_mode)
