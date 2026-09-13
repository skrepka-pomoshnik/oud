from __future__ import annotations

from typing import cast

import pytest

from petrucci import ElementKey, ElementRole, GlyphMode, LayoutElement, Rect, ScoreTypesetOptions, typeset_score
from petrucci.terminal.api import SemanticFrame
from petrucci.terminal.canvas.dots import DotCanvas
from petrucci.terminal.canvas.framebuffer import Frame
from petrucci.terminal.rendering.ansi import INK, PAPER, AnsiPalette, PaletteError, colour_score
from petrucci.terminal.rendering.raster import paint_geometry
from scripts.notation_preview import example_score


def _semantic_frame(roles: tuple[ElementRole | None, ...], ids: tuple[str | None, ...]) -> SemanticFrame:
    frame = Frame(lines=["x" * len(roles)], attrs=[(0,) * len(roles)])
    return SemanticFrame(frame=frame, roles=(roles,), element_ids=(ids,))


def test_palette_routes_staff_notes_marks_spans_and_text() -> None:
    palette = PAPER
    assert palette.foreground(ElementRole.STAFF) == palette.staff
    assert palette.foreground(ElementRole.LEDGER_LINE) == palette.staff
    assert palette.foreground(ElementRole.BARLINE) == palette.staff
    assert palette.foreground(ElementRole.ACCIDENTAL) == palette.marks
    assert palette.foreground(ElementRole.KEY_SIGNATURE) == palette.marks
    assert palette.foreground(ElementRole.ORNAMENT) == palette.marks
    assert palette.foreground(ElementRole.TIE) == palette.spans
    assert palette.foreground(ElementRole.SLUR) == palette.spans
    assert palette.foreground(ElementRole.GLISSANDO) == palette.spans
    assert palette.foreground(ElementRole.NOTEHEAD) == palette.notes
    assert palette.foreground(ElementRole.REST) == palette.notes
    assert palette.foreground(None) == palette.text
    assert palette.foreground(ElementRole.NOTEHEAD, active=True) == palette.active


def test_palette_rejects_invalid_rgb_shape_or_channel() -> None:
    with pytest.raises(PaletteError):
        AnsiPalette(
            background=(0, 0, 256),
            staff=INK.staff,
            notes=INK.notes,
            marks=INK.marks,
            spans=INK.spans,
            text=INK.text,
            active=INK.active,
        )
    with pytest.raises(PaletteError):
        AnsiPalette(
            background=cast("tuple[int, int, int]", (0, 0)),
            staff=INK.staff,
            notes=INK.notes,
            marks=INK.marks,
            spans=INK.spans,
            text=INK.text,
            active=INK.active,
        )


def test_colour_score_uses_semantic_colours_and_active_ids() -> None:
    frame = _semantic_frame((ElementRole.STAFF, ElementRole.NOTEHEAD), ("staff", "event"))
    output = colour_score(frame, palette=INK, active_ids=("event",))

    assert "48;2;17;28;39" in output
    assert "38;2;82;102;119" in output
    assert "38;2;255;111;97" in output
    assert output.endswith("\x1b[0m\n")


def test_colour_score_replaces_control_characters_with_spaces() -> None:
    frame = SemanticFrame(
        frame=Frame(lines=["a\x1b"], attrs=[(0, 0)]),
        roles=((None, None),),
        element_ids=((None, None),),
    )

    output = colour_score(frame)

    assert "\x1b" not in output.replace("\x1b[", "")


def test_block_canvas_emits_half_and_full_blocks() -> None:
    canvas = DotCanvas(1, 3, blocks=True)
    element = LayoutElement(ElementKey("block", ElementRole.STAFF), Rect(0, 0))
    canvas.pixel(0, 0, element, 1)
    canvas.pixel(1, 1, element, 1)
    canvas.pixel(2, 0, element, 1)
    canvas.pixel(2, 1, element, 1)

    assert [cell.glyph for cell in canvas.cells()] == ["▀", "▄", "█"]


def test_block_preview_is_terminal_width_and_contains_no_braille() -> None:
    result = typeset_score(
        example_score(), options=ScoreTypesetOptions(width=96, height=32, glyph_mode=GlyphMode.BLOCK)
    )

    assert all(len(line) == 96 for line in result.lines)
    assert any(char in result.text for char in "▀▄█")
    assert not any(0x2800 <= ord(char) <= 0x28FF for char in result.text)
    assert all(result.cells_for(event_id) for event_id in result.layout.event_ids)


@pytest.mark.parametrize("value", ("regular", "final", "repeat-start", "repeat-end", "repeat-both"))
def test_block_barline_variants_are_drawn_on_the_shared_grid(value: str) -> None:
    canvas = DotCanvas(12, 8, blocks=True)
    element = LayoutElement(ElementKey("bar", ElementRole.BARLINE), Rect(3, 2, 1, 5), value)

    assert paint_geometry(canvas, element, x_offset=0, y_offset=0, priority=25)
    assert tuple(canvas.cells())


@pytest.mark.parametrize(
    "role,value",
    (
        (ElementRole.CLEF, "unknown"),
        (ElementRole.ACCIDENTAL, "1:courtesy"),
        (ElementRole.TIME_SIGNATURE, "invalid"),
        (ElementRole.TUPLET, "3"),
    ),
)
def test_unsupported_advanced_symbols_fall_back_to_the_glyph_painter(role: ElementRole, value: str) -> None:
    canvas = DotCanvas(8, 8, blocks=True)
    element = LayoutElement(ElementKey("unsupported", role), Rect(2, 2, 3, 2), value)

    assert not paint_geometry(canvas, element, x_offset=0, y_offset=0, priority=40)
    assert tuple(canvas.cells()) == ()


@pytest.mark.parametrize(
    "role,values",
    (
        (ElementRole.ACCIDENTAL, ("sharp", "flat", "natural", "2", "-2", "0")),
        (ElementRole.REST, ("whole", "half", "breve", "eighth", "sixteenth", "32")),
        (ElementRole.TIME_SIGNATURE, ("3/4", "6/8")),
    ),
)
def test_advanced_symbol_variants_are_multirow_and_owned(role: ElementRole, values: tuple[str, ...]) -> None:
    for value in values:
        canvas = DotCanvas(20, 12, blocks=True)
        element = LayoutElement(ElementKey(value, role), Rect(4, 8, 4, 2), value)

        assert paint_geometry(canvas, element, x_offset=0, y_offset=0, priority=40)
        cells = tuple(canvas.cells())
        assert cells
        assert all(cell.element.key.source_id == value for cell in cells)
