from __future__ import annotations

import pytest

from petrucci import ElementKey, ElementRole, LayoutElement, Rect
from petrucci.terminal.canvas.dots import DotCanvas
from petrucci.terminal.rendering.raster import paint_geometry


def test_subcell_strokes_merge_and_keep_foreground_identity() -> None:
    canvas = DotCanvas(2, 3)
    staff = LayoutElement(ElementKey("staff", ElementRole.STAFF), Rect(0, 0, 3))
    stem = LayoutElement(ElementKey("note", ElementRole.STEM), Rect(1, 0), "up")
    canvas.horizontal(-(10**9), 10**9, 2, staff, 10)
    canvas.vertical(2, -(10**9), 10**9, stem, 20)
    canvas.horizontal(0, 5, 2, staff, 10)
    cells = {(cell.row, cell.column): cell for cell in canvas.cells()}

    assert cells[0, 0].glyph == chr(0x2800 + 0x24)
    assert cells[0, 1].glyph == chr(0x2800 + 0x67)
    assert cells[1, 1].glyph == chr(0x2800 + 0x47)
    assert cells[0, 1].element.key.source_id == "note"
    assert cells[0, 1].priority == 20
    assert len(cells) == 4


def test_subcell_primitives_clip_outside_the_viewport() -> None:
    canvas = DotCanvas(1, 1)
    element = LayoutElement(ElementKey("note", ElementRole.DOT), Rect(0, 0))
    for x, y in ((-1, 0), (2, 0), (0, -1), (0, 4)):
        canvas.pixel(x, y, element, 1)
    canvas.horizontal(0, 1, 4, element, 1)
    canvas.vertical(2, 0, 3, element, 1)
    assert tuple(canvas.cells()) == ()
    canvas.pixel(0, 0, element, 1)
    canvas.pixel(1, 3, element, 1)
    assert [cell.glyph for cell in canvas.cells()] == ["⢁"]


@pytest.mark.parametrize("role", (ElementRole.TIE, ElementRole.SLUR, ElementRole.GLISSANDO))
@pytest.mark.parametrize("value", ("", "start", "end", "continue"))
def test_raster_spans_preserve_clipped_continuation_ownership(role: ElementRole, value: str) -> None:
    canvas = DotCanvas(4, 8)
    element = LayoutElement(ElementKey("span", role), Rect(0, 1, 8), value)
    assert paint_geometry(canvas, element, x_offset=0, y_offset=0, priority=32)
    cells = tuple(canvas.cells())
    assert cells
    assert all(cell.element.key.source_id == "span" for cell in cells)
    assert {cell.column for cell in cells} == set(range(8))


@pytest.mark.parametrize("direction", ("up", "down"))
def test_raster_flags_follow_stem_direction(direction: str) -> None:
    canvas = DotCanvas(4, 4)
    flag = LayoutElement(ElementKey("flag", ElementRole.FLAG), Rect(1, 1, 2), direction)
    assert paint_geometry(canvas, flag, x_offset=0, y_offset=0, priority=28)
    rows = {cell.row for cell in canvas.cells()}
    assert rows == ({1, 2} if direction == "up" else {0, 1})


def test_raster_giant_span_work_is_limited_to_visible_columns() -> None:
    canvas = DotCanvas(4, 8)
    element = LayoutElement(ElementKey("long", ElementRole.TIE), Rect(0, 1, 10**9))
    assert paint_geometry(canvas, element, x_offset=10**8, y_offset=0, priority=32)
    assert len(tuple(canvas.cells())) == 8


def _pixels(canvas: DotCanvas) -> set[tuple[int, int]]:
    bits = ((1, 8), (2, 16), (4, 32), (64, 128))
    return {
        (cell.column * 2 + dx, cell.row * 4 + dy)
        for cell in canvas.cells()
        for dy, row in enumerate(bits)
        for dx, bit in enumerate(row)
        if (ord(cell.glyph) - 0x2800) & bit
    }


@pytest.mark.parametrize("value", ("half", "quarter"))
def test_notehead_masks_distinguish_open_and_filled_ink(value: str) -> None:
    canvas = DotCanvas(4, 6)
    head = LayoutElement(ElementKey("note", ElementRole.NOTEHEAD), Rect(2, 2), value)
    assert paint_geometry(canvas, head, x_offset=0, y_offset=0, priority=50)
    outline = {(4, 5), (5, 5), (3, 6), (6, 6), (4, 7), (5, 7)}
    filled = {(6, 5), (4, 6), (5, 6), (3, 7)}
    assert _pixels(canvas) == outline | (filled if value == "quarter" else set())


def test_open_head_knocks_out_staff_without_erasing_adjacent_staff_pixels() -> None:
    canvas = DotCanvas(4, 6)
    staff = LayoutElement(ElementKey("staff", ElementRole.STAFF), Rect(0, 2, 6))
    head = LayoutElement(ElementKey("note", ElementRole.NOTEHEAD), Rect(2, 2), "half")
    paint_geometry(canvas, staff, x_offset=0, y_offset=0, priority=10)
    paint_geometry(canvas, head, x_offset=0, y_offset=0, priority=50)
    ink = _pixels(canvas)
    assert (4, 6) not in ink and (5, 6) not in ink
    assert {(2, 6), (3, 6), (6, 6), (7, 6)} <= ink


@pytest.mark.parametrize("role,value", ((ElementRole.CLEF, "treble"), (ElementRole.REST, "quarter")))
def test_musical_masks_have_multiple_rows_and_source_identity(role: ElementRole, value: str) -> None:
    canvas = DotCanvas(12, 10)
    element = LayoutElement(ElementKey("symbol", role), Rect(3, 8), value)
    assert paint_geometry(canvas, element, x_offset=0, y_offset=0, priority=50)
    rows = {y for _x, y in _pixels(canvas)}
    assert max(rows) - min(rows) + 1 == (21 if role is ElementRole.CLEF else 9)
    assert all(cell.element.key.source_id == "symbol" for cell in canvas.cells())


def test_dot_knockout_is_clipped_and_preserves_higher_priority_ink() -> None:
    canvas = DotCanvas(1, 1)
    element = LayoutElement(ElementKey("note", ElementRole.NOTEHEAD), Rect(0, 0))
    canvas.pixel(0, 0, element, 50)
    canvas.clear(-(10**9), -(10**9), 2 * 10**9, 2 * 10**9, 10)
    assert _pixels(canvas) == {(0, 0)}
    canvas.clear(-(10**9), -(10**9), 2 * 10**9, 2 * 10**9, 50)
    assert tuple(canvas.cells()) == ()
