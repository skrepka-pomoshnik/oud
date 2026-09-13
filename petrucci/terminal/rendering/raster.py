"""Musical shapes drawn entirely on a shared, clipped braille lattice."""

from __future__ import annotations

from petrucci.engraving.layout.engine import ElementRole, LayoutElement
from petrucci.terminal.canvas.dots import DOT_COLUMNS, DotCanvas
from petrucci.terminal.rendering.raster_grid import PITCH_STEP, RasterGrid
from petrucci.terminal.rendering.raster_symbols import accidental, clef, meter, notehead, rest


def paint_geometry(
    canvas: DotCanvas,
    element: LayoutElement,
    *,
    x_offset: int,
    y_offset: int,
    priority: int,
    grid: RasterGrid | None = None,
) -> bool:
    """Return false for textual annotations or an unsupported symbol spelling."""
    painters = {
        ElementRole.STAFF: _rule,
        ElementRole.LEDGER_LINE: _rule,
        ElementRole.STEM: _rule,
        ElementRole.BEAM: _rule,
        ElementRole.BARLINE: _barline,
        ElementRole.FLAG: _flag,
        ElementRole.SLUR: _curve,
        ElementRole.TIE: _curve,
        ElementRole.GLISSANDO: _curve,
        ElementRole.DOT: _dot,
        ElementRole.NOTEHEAD: notehead,
        ElementRole.CLEF: clef,
        ElementRole.REST: rest,
        ElementRole.ACCIDENTAL: accidental,
        ElementRole.KEY_SIGNATURE: accidental,
        ElementRole.TIME_SIGNATURE: meter,
    }
    painter = painters.get(element.key.role)
    if painter is None or not _supported(element):
        return False
    x = grid.x(element.rect.x) if grid is not None else (element.rect.x - x_offset) * DOT_COLUMNS
    y = grid.y(element.rect.y) if grid is not None else (element.rect.y - y_offset) * PITCH_STEP + 2
    if grid is not None and element.key.role is ElementRole.TIE:
        y = grid.tie_y(element)
    painter(canvas, element, x, y, priority)
    return True


def _supported(element: LayoutElement) -> bool:
    if element.key.role is ElementRole.TIME_SIGNATURE:
        top, separator, bottom = element.value.partition("/")
        return bool(separator and top.isascii() and top.isdigit() and bottom.isascii() and bottom.isdigit())
    if element.key.role is ElementRole.CLEF:
        return element.value in {"treble", "bass"}
    return not (element.key.role is ElementRole.ACCIDENTAL and ":" in element.value)


def _rule(canvas: DotCanvas, element: LayoutElement, x: int, y: int, priority: int) -> None:
    if element.key.role is ElementRole.STEM:
        x += int(element.value == "down")
        canvas.vertical(x, y, y + (element.rect.height - 1) * PITCH_STEP, element, priority)
        return
    right = x + element.rect.width * DOT_COLUMNS - 1
    canvas.horizontal(x, right, y, element, priority)
    if element.key.role is ElementRole.BEAM:
        canvas.horizontal(x, right, y + 1, element, priority)


def _barline(canvas: DotCanvas, element: LayoutElement, x: int, y: int, priority: int) -> None:
    bottom = y + (element.rect.height - 1) * PITCH_STEP
    canvas.vertical(x, y, bottom, element, priority)
    if element.value != "regular":
        canvas.vertical(x - 2, y, bottom, element, priority)
    if element.value in {"final", "repeat-start", "repeat-end", "repeat-both"}:
        canvas.vertical(x + 1, y, bottom, element, priority)
    repeat_sides = {"repeat-start": (3,), "repeat-end": (-4,), "repeat-both": (-4, 3)}
    for dx in repeat_sides.get(element.value, ()):
        for dy in (-2, 2):
            canvas.pixel(x + dx, (y + bottom) // 2 + dy, element, priority)


def _flag(canvas: DotCanvas, element: LayoutElement, x: int, y: int, priority: int) -> None:
    direction = 1 if element.value == "up" else -1
    for dx, dy in ((0, 0), (1, 1), (2, 2), (2, 3), (1, 4)):
        canvas.pixel(x + dx, y + direction * dy, element, priority)


def _curve(canvas: DotCanvas, element: LayoutElement, x: int, y: int, priority: int) -> None:
    extent = max(1, element.rect.width * DOT_COLUMNS - 1)
    depth = min(3, max(1, extent // 4))
    for pixel_x in range(max(0, x), min(canvas.width, x + extent + 1)):
        offset = pixel_x - x
        if element.key.role is ElementRole.GLISSANDO:
            pixel_y = y + 1 - offset * 3 // extent
        else:
            arch = (4 * depth * offset * (extent - offset) + extent * extent // 2) // (extent * extent)
            pixel_y = y + arch if element.key.role is ElementRole.TIE else y - arch
        canvas.pixel(pixel_x, pixel_y, element, priority)


def _dot(canvas: DotCanvas, element: LayoutElement, x: int, y: int, priority: int) -> None:
    for offset in range(min(element.rect.width, canvas.width)):
        canvas.pixel(x + offset * DOT_COLUMNS + 1, y - 1, element, priority)
