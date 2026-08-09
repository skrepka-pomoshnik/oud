"""Public composition facade for canonical score layout and terminal painting."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import NoReturn

from petrucci.framebuffer import Frame
from petrucci.layout import (
    LayoutMetrics,
    LayoutViewport,
    NotationLayoutPolicy,
    ScoreLayout,
    layout_score,
)
from petrucci.score import NotationScore
from petrucci.score_cues import PitchCue, paint_pitch_cues
from petrucci.terminal import GlyphMode, SemanticFrame, TerminalNoteheads, paint_score


@dataclass(frozen=True, slots=True)
class ScoreTypesetOptions:
    width: int = 80
    height: int = 24
    system_offset: int = 0
    x_offset: int = 0
    y_offset: int = 0
    layout_width: int | None = None
    glyph_mode: GlyphMode = GlyphMode.PRETTY
    noteheads: TerminalNoteheads | None = None
    metrics: LayoutMetrics = field(default_factory=LayoutMetrics)
    policy: NotationLayoutPolicy = field(default_factory=NotationLayoutPolicy)
    pitch_cues: tuple[PitchCue, ...] = ()

    def __post_init__(self) -> None:
        viewport = self.viewport
        layout_width = self.resolved_layout_width
        if layout_width < viewport.width:
            _type_fail("score layout width must not be smaller than the paint viewport")
        if viewport.x_offset >= layout_width:
            _type_fail("score horizontal offset must stay inside the layout width")

    @property
    def resolved_layout_width(self) -> int:
        return self.layout_width if self.layout_width is not None else self.width

    @property
    def viewport(self) -> LayoutViewport:
        return LayoutViewport(
            width=self.width,
            height=self.height,
            system_offset=self.system_offset,
            x_offset=self.x_offset,
            y_offset=self.y_offset,
        )

    @property
    def layout_viewport(self) -> LayoutViewport:
        return LayoutViewport(width=self.resolved_layout_width, height=self.height)


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
) -> ScoreTypesetResult:
    """Lay out and paint a canonical score without Oud editor state."""

    active = options or ScoreTypesetOptions()
    layout = layout_score(
        score,
        viewport=active.layout_viewport,
        metrics=active.metrics,
        policy=active.policy,
    )
    return typeset_layout(layout, options=active, score=score)


def typeset_layout(
    layout: ScoreLayout,
    *,
    options: ScoreTypesetOptions | None = None,
    score: NotationScore | None = None,
) -> ScoreTypesetResult:
    """Paint an existing layout, allowing a host to select a system without relayout."""

    active = options or ScoreTypesetOptions(width=layout.width)
    if active.x_offset >= layout.width:
        _type_fail("score horizontal offset must stay inside the existing layout")
    semantic_frame = paint_score(
        layout,
        viewport=active.viewport,
        glyph_mode=active.glyph_mode,
        noteheads=active.noteheads,
    )
    if active.pitch_cues:
        if score is None:
            _type_fail("score is required when painting pitch cues on an existing layout")
        semantic_frame = paint_pitch_cues(
            semantic_frame,
            score=score,
            layout=layout,
            cues=active.pitch_cues,
            viewport=active.viewport,
            glyph_mode=active.glyph_mode,
        )
    return ScoreTypesetResult(layout=layout, semantic_frame=semantic_frame)


def _type_fail(message: str) -> NoReturn:
    raise TypeError(message)


__all__ = ["ScoreTypesetOptions", "ScoreTypesetResult", "typeset_layout", "typeset_score"]
