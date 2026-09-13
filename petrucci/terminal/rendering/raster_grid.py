"""Explicit compact projection from layout coordinates to terminal dots."""

from __future__ import annotations

from bisect import bisect_left

from petrucci.engraving.layout.engine import ElementRole, LayoutElement, LayoutViewport, ScoreLayout
from petrucci.terminal.canvas.dots import DOT_COLUMNS, DOT_ROWS

PITCH_STEP = 2
TOP_CLEARANCE = 8
_TEXT_ROLES = frozenset(
    {
        ElementRole.TITLE,
        ElementRole.COMPOSER,
        ElementRole.MEASURE_NUMBER,
        ElementRole.ENDING,
        ElementRole.LYRIC,
        ElementRole.LYRIC_LINE,
        ElementRole.LYRIC_HYPHEN,
        ElementRole.LYRIC_EXTENDER,
        ElementRole.DYNAMIC,
        ElementRole.PITCH_LABEL,
        ElementRole.TUPLET,
        ElementRole.FINGERING,
        ElementRole.PROPORTION,
    }
)


class RasterGrid:
    """Keep pitch spacing compact without collapsing adjacent text baselines.

    Viewport offsets are terminal cells. Block mode uses one column and two
    pixel rows per cell; braille uses two columns and four dot rows per cell.
    """

    def __init__(self, layout: ScoreLayout, viewport: LayoutViewport, *, blocks: bool = False) -> None:
        self.columns_per_cell = 1 if blocks else DOT_COLUMNS
        self.rows_per_cell = 2 if blocks else DOT_ROWS
        self.x_offset = viewport.x_offset * self.columns_per_cell
        # Staff labels share staff rows and must not stretch the pitch lattice.
        self.text_rows = sorted({e.rect.y for e in layout.elements if e.key.role in _TEXT_ROLES})
        self.heads: dict[str, list[LayoutElement]] = {}
        for element in layout.elements:
            if element.key.role is ElementRole.NOTEHEAD:
                self.heads.setdefault(element.key.source_id, []).append(element)
        self.origin = 0
        system_y = layout.systems[viewport.system_offset].rect.y
        self.origin = self.y(system_y) - TOP_CLEARANCE + viewport.y_offset * self.rows_per_cell

    def x(self, column: int) -> int:
        return column * DOT_COLUMNS - self.x_offset

    def y(self, row: int) -> int:
        text_space = (self.rows_per_cell - PITCH_STEP) * bisect_left(self.text_rows, row)
        return row * PITCH_STEP + text_space + TOP_CLEARANCE - self.origin

    def tie_y(self, element: LayoutElement) -> int:
        """Anchor simple complete ties to notes; keep complex ties in their lanes."""
        fallback = self.y(element.rect.y)
        if element.anchor_ids is None or element.continuation:
            return fallback
        start, end = (self.heads.get(event_id, []) for event_id in element.anchor_ids)
        if len(start) != 1 or len(end) != 1 or start[0].rect.y != end[0].rect.y:
            return fallback
        return self.y(start[0].rect.y) + 3
