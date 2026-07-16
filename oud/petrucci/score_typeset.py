"""Public composition facade for canonical score layout and terminal painting."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import NoReturn

from oud.petrucci.feedback_layout import with_feedback_annotations
from oud.petrucci.framebuffer import Frame
from oud.petrucci.layout import (
    LayoutMetrics,
    LayoutViewport,
    NotationLayoutPolicy,
    ScoreLayout,
    layout_score,
)
from oud.petrucci.score import NotationScore
from oud.petrucci.terminal import EventOverlay, GlyphMode, SemanticFrame, paint_score


@dataclass(frozen=True, slots=True)
class ScoreTypesetOptions:
    width: int = 80
    height: int = 24
    system_offset: int = 0
    glyph_mode: GlyphMode = GlyphMode.PRETTY
    metrics: LayoutMetrics = field(default_factory=LayoutMetrics)
    policy: NotationLayoutPolicy = field(default_factory=NotationLayoutPolicy)

    def __post_init__(self) -> None:
        if not isinstance(self.glyph_mode, GlyphMode):
            _type_fail("glyph mode must be a GlyphMode")
        if not isinstance(self.metrics, LayoutMetrics):
            _type_fail("score typeset metrics must be LayoutMetrics")
        if not isinstance(self.policy, NotationLayoutPolicy):
            _type_fail("score typeset policy must be NotationLayoutPolicy")
        LayoutViewport(width=self.width, height=self.height, system_offset=self.system_offset)

    @property
    def viewport(self) -> LayoutViewport:
        return LayoutViewport(width=self.width, height=self.height, system_offset=self.system_offset)


@dataclass(frozen=True, slots=True)
class ScoreTypesetResult:
    layout: ScoreLayout
    semantic_frame: SemanticFrame

    @property
    def frame(self) -> Frame:
        return self.semantic_frame.frame

    @property
    def lines(self) -> tuple[str, ...]:
        return self.semantic_frame.lines

    @property
    def text(self) -> str:
        return self.semantic_frame.text

    def cells_for(self, element_id: str) -> tuple[tuple[int, int], ...]:
        return self.semantic_frame.cells_for(element_id)


def typeset_score(
    score: NotationScore,
    *,
    options: ScoreTypesetOptions | None = None,
    overlays: Mapping[str, EventOverlay] | None = None,
) -> ScoreTypesetResult:
    """Lay out and paint a canonical score without Oud editor state."""

    if options is not None and not isinstance(options, ScoreTypesetOptions):
        _type_fail("score typeset options must be ScoreTypesetOptions")
    active = options or ScoreTypesetOptions()
    if overlays is not None and any(not isinstance(overlay, EventOverlay) for overlay in overlays.values()):
        _type_fail("score overlays must contain EventOverlay values")
    viewport = active.viewport
    annotations = {event_id: text for event_id, overlay in (overlays or {}).items() if (text := overlay.feedback_text)}
    layout = layout_score(
        score,
        viewport=viewport,
        metrics=active.metrics,
        policy=active.policy,
        feedback_event_ids=frozenset(annotations),
    )
    layout = with_feedback_annotations(layout, annotations)
    semantic_frame = paint_score(
        layout,
        viewport=viewport,
        glyph_mode=active.glyph_mode,
        overlays=overlays,
    )
    return ScoreTypesetResult(layout=layout, semantic_frame=semantic_frame)


def _type_fail(message: str) -> NoReturn:
    raise TypeError(message)


__all__ = ["ScoreTypesetOptions", "ScoreTypesetResult", "typeset_score"]
