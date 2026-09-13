"""Clipped braille pixels with cell-level musical identity."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

from petrucci.engraving.layout.engine import LayoutElement

DOT_COLUMNS = 2
DOT_ROWS = 4
_BITS = ((1, 8), (2, 16), (4, 32), (64, 128))
_BRAILLE_BASE = 0x2800
_HALF_BLOCKS = {1: "\u2580", 2: "\u2584", 3: "\u2588"}


@dataclass(frozen=True, slots=True)
class DotCell:
    row: int
    column: int
    glyph: str
    element: LayoutElement
    priority: int


class DotCanvas:
    """Keep raster storage and drawing work bounded by the visible viewport."""

    def __init__(self, height: int, width: int, *, blocks: bool = False) -> None:
        self.columns_per_cell = 1 if blocks else DOT_COLUMNS
        self.rows_per_cell = 2 if blocks else DOT_ROWS
        self.width = width * self.columns_per_cell
        self.height = height * self.rows_per_cell
        self.masks = [[0] * width for _ in range(height)]
        self.owners: list[list[tuple[int, LayoutElement] | None]] = [[None] * width for _ in range(height)]

    def pixel(self, x: int, y: int, element: LayoutElement, priority: int) -> None:
        if not (0 <= x < self.width and 0 <= y < self.height):
            return
        row, column = y // self.rows_per_cell, x // self.columns_per_cell
        bit = _BITS[y % self.rows_per_cell][x % self.columns_per_cell]
        self.masks[row][column] |= bit
        owner = self.owners[row][column]
        if owner is None or priority >= owner[0]:
            self.owners[row][column] = (priority, element)

    def horizontal(self, left: int, right: int, y: int, element: LayoutElement, priority: int) -> None:
        if 0 <= y < self.height:
            for x in range(max(0, left), min(self.width, right + 1)):
                self.pixel(x, y, element, priority)

    def vertical(self, x: int, top: int, bottom: int, element: LayoutElement, priority: int) -> None:
        if 0 <= x < self.width:
            for y in range(max(0, top), min(self.height, bottom + 1)):
                self.pixel(x, y, element, priority)

    def cells(self) -> Iterator[DotCell]:
        for row, owners in enumerate(self.owners):
            for column, owner in enumerate(owners):
                if owner is not None:
                    mask = self.masks[row][column]
                    glyph = _HALF_BLOCKS[mask] if self.columns_per_cell == 1 else chr(_BRAILLE_BASE + mask)
                    yield DotCell(row, column, glyph, owner[1], owner[0])

    def clear(self, x: int, y: int, width: int, height: int, priority: int) -> None:
        """Knock out lower-priority ink under a musical symbol, not whole cells."""
        for pixel_y in range(max(0, y), min(self.height, y + height)):
            for pixel_x in range(max(0, x), min(self.width, x + width)):
                row, column = pixel_y // self.rows_per_cell, pixel_x // self.columns_per_cell
                owner = self.owners[row][column]
                if owner is not None and owner[0] > priority:
                    continue
                self.masks[row][column] &= ~_BITS[pixel_y % self.rows_per_cell][pixel_x % self.columns_per_cell]
                if not self.masks[row][column]:
                    self.owners[row][column] = None
