"""Petrucci: reusable ASCII tablature and staff-note typesetting."""

from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from oud.petrucci.layout import (
    ElementKey,
    ElementRole,
    EventLocation,
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
    layout_score,
)
from oud.petrucci.model import (
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
from oud.petrucci.oud_adapter import OudScoreAdapterError, notation_score_from_piece, written_pitch_from_token
from oud.petrucci.score import (
    AccidentalDisplay,
    BarlineKind,
    BeamKind,
    Clef,
    EventKind,
    KeySignature,
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

if TYPE_CHECKING:
    from oud.petrucci.score_typeset import ScoreTypesetOptions, ScoreTypesetResult
    from oud.petrucci.terminal import CellStyle, EventOverlay, GlyphMode, OverlayRole, SemanticFrame
    from oud.petrucci.typeset import TypesetOptions, TypesetResult

__all__ = [
    "AccidentalDisplay",
    "Bar",
    "BarlineKind",
    "BeamKind",
    "CellStyle",
    "Chord",
    "Clef",
    "ElementKey",
    "ElementRole",
    "EventKind",
    "EventLocation",
    "EventOverlay",
    "GlyphMode",
    "ImportedBarContent",
    "ImportedScore",
    "ImportedSourceRecord",
    "ImportedStaff",
    "ImportedTextRow",
    "KeySignature",
    "LayoutElement",
    "LayoutError",
    "LayoutMetrics",
    "LayoutViewport",
    "LyricEvent",
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
    "OudScoreAdapterError",
    "OverlayRole",
    "Piece",
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
    "clear_layout_cache",
    "layout_score",
    "notation_score_from_piece",
    "paint_score",
    "pitch_from_midi",
    "typeset_piece",
    "typeset_score",
    "typeset_text",
    "written_pitch_from_token",
]


def __getattr__(name: str) -> Any:
    if name in {"TypesetOptions", "TypesetResult"}:
        from oud.petrucci import typeset  # noqa: PLC0415

        return getattr(typeset, name)
    if name in {"ScoreTypesetOptions", "ScoreTypesetResult"}:
        from oud.petrucci import score_typeset  # noqa: PLC0415

        return getattr(score_typeset, name)
    if name in {"CellStyle", "EventOverlay", "GlyphMode", "OverlayRole", "SemanticFrame"}:
        from oud.petrucci import terminal  # noqa: PLC0415

        return getattr(terminal, name)
    raise AttributeError(name)


def typeset_piece(*args, **kwargs):
    from oud.petrucci.typeset import typeset_piece as _typeset_piece  # noqa: PLC0415

    return _typeset_piece(*args, **kwargs)


def typeset_text(*args, **kwargs):
    from oud.petrucci.typeset import typeset_text as _typeset_text  # noqa: PLC0415

    return _typeset_text(*args, **kwargs)


def typeset_score(
    score: NotationScore,
    *,
    options: ScoreTypesetOptions | None = None,
    overlays: Mapping[str, EventOverlay] | None = None,
) -> ScoreTypesetResult:
    from oud.petrucci.score_typeset import typeset_score as _typeset_score  # noqa: PLC0415

    return _typeset_score(score, options=options, overlays=overlays)


def paint_score(
    layout: ScoreLayout,
    *,
    viewport: LayoutViewport | None = None,
    glyph_mode: GlyphMode | None = None,
    overlays: Mapping[str, EventOverlay] | None = None,
) -> SemanticFrame:
    from oud.petrucci.terminal import paint_score as _paint_score  # noqa: PLC0415

    if glyph_mode is None:
        return _paint_score(layout, viewport=viewport, overlays=overlays)
    return _paint_score(layout, viewport=viewport, glyph_mode=glyph_mode, overlays=overlays)
