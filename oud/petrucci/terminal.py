"""Display-safe terminal painting for semantic Petrucci score layouts."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from math import isfinite
from numbers import Real
from typing import NoReturn

from oud.petrucci.display import clip_display, display_width, split_display_clusters
from oud.petrucci.framebuffer import Frame
from oud.petrucci.layout import ElementRole, LayoutElement, LayoutViewport, ScoreLayout
from oud.petrucci.screen import A_BOLD, A_DIM, A_REVERSE, A_UNDERLINE


class GlyphMode(StrEnum):
    PRETTY = "pretty"
    SAFE = "safe"


class OverlayRole(StrEnum):
    CURRENT = "current"
    PENDING = "pending"
    HIT = "hit"
    MISSED = "missed"
    UNCERTAIN = "uncertain"


class CellStyle(StrEnum):
    NORMAL = "normal"
    DIM = "dim"
    CURRENT = "current"
    PENDING = "pending"
    HIT = "hit"
    MISSED = "missed"
    UNCERTAIN = "uncertain"


@dataclass(frozen=True, slots=True)
class EventOverlay:
    role: OverlayRole
    pitch_error_cents: float | None = None
    timing_error_ms: float | None = None
    confidence: float | None = None
    annotation: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.role, OverlayRole):
            _fail("event overlay role must be an OverlayRole")
        _validate_optional_number(self.pitch_error_cents, "pitch error")
        _validate_optional_number(self.timing_error_ms, "timing error")
        _validate_optional_number(self.confidence, "confidence")
        if self.confidence is not None and not 0.0 <= self.confidence <= 1.0:
            _fail("event overlay confidence must be between zero and one")
        if self.annotation is not None and not isinstance(self.annotation, str):
            _fail("event overlay annotation must be a string")

    @property
    def feedback_text(self) -> str:
        parts = [self.annotation] if self.annotation else []
        if self.pitch_error_cents is not None:
            parts.append(f"{self.pitch_error_cents:+g}c")
        if self.timing_error_ms is not None:
            parts.append(f"{self.timing_error_ms:+g}ms")
        if self.confidence is not None:
            parts.append(f"{self.confidence:.0%}")
        return " ".join(parts)


@dataclass(frozen=True, slots=True)
class SemanticFrame:
    frame: Frame
    roles: tuple[tuple[ElementRole | None, ...], ...]
    element_ids: tuple[tuple[str | None, ...], ...]
    styles: tuple[tuple[CellStyle, ...], ...]

    @property
    def lines(self) -> tuple[str, ...]:
        return tuple(self.frame.lines)

    @property
    def text(self) -> str:
        lines = [line.rstrip() for line in self.frame.lines]
        while lines and not lines[-1]:
            lines.pop()
        return "\n".join(lines) + ("\n" if lines else "")

    def cells_for(self, element_id: str) -> tuple[tuple[int, int], ...]:
        return tuple(
            (y, x)
            for y, row in enumerate(self.element_ids)
            for x, source_id in enumerate(row)
            if source_id == element_id
        )


@dataclass(frozen=True, slots=True)
class _GlyphInventory:
    staff: str
    ledger: str
    stem: str
    flag_up: str
    flag_down: str
    beam: str
    tie_left: str
    tie_fill: str
    tie_right: str
    slur_left: str
    slur_fill: str
    slur_right: str
    continuation_left: str
    continuation_right: str
    barline: str
    double_barline: str
    final_barline: str
    repeat_start_barline: str
    repeat_end_barline: str
    repeat_both_barline: str
    ending_left: str
    ending_fill: str
    treble_clef: str
    bass_clef: str
    sharp: str
    flat: str
    natural: str
    filled_notehead: str
    open_notehead: str
    dot: str
    whole_rest: str
    half_rest: str
    quarter_rest: str
    eighth_rest: str
    sixteenth_rest: str
    thirty_second_rest: str
    sixty_fourth_rest: str
    fermata: str
    ornament_plus: str
    clip: str


_PRETTY = _GlyphInventory(
    staff="─",
    ledger="─",
    stem="│",
    flag_up="╲",
    flag_down="/",
    beam="━",
    tie_left="╰",
    tie_fill="─",
    tie_right="╯",
    slur_left="╭",
    slur_fill="─",
    slur_right="╮",
    continuation_left="<",
    continuation_right=">",
    barline="│",
    double_barline="║",
    final_barline="┃",
    repeat_start_barline="╞",
    repeat_end_barline="╡",
    repeat_both_barline="╪",
    ending_left="┌",
    ending_fill="─",
    treble_clef="𝄞",
    bass_clef="𝄢",
    sharp="♯",
    flat="♭",
    natural="♮",
    filled_notehead="●",
    open_notehead="○",
    dot="·",
    whole_rest="𝄻",
    half_rest="𝄼",
    quarter_rest="𝄽",
    eighth_rest="𝄾",
    sixteenth_rest="𝄿",
    thirty_second_rest="𝅀",
    sixty_fourth_rest="𝅁",
    fermata="𝄐",
    ornament_plus="+",
    clip="»",
)

_SAFE = _GlyphInventory(
    staff="-",
    ledger="-",
    stem="|",
    flag_up="\\",
    flag_down="/",
    beam="=",
    tie_left="\\",
    tie_fill="_",
    tie_right="/",
    slur_left="/",
    slur_fill="-",
    slur_right="\\",
    continuation_left="<",
    continuation_right=">",
    barline="|",
    double_barline="|",
    final_barline="|",
    repeat_start_barline="{",
    repeat_end_barline="}",
    repeat_both_barline=":",
    ending_left="[",
    ending_fill="-",
    treble_clef="G",
    bass_clef="F",
    sharp="#",
    flat="b",
    natural="n",
    filled_notehead="o",
    open_notehead="O",
    dot=".",
    whole_rest="R",
    half_rest="r",
    quarter_rest="r",
    eighth_rest="e",
    sixteenth_rest="s",
    thirty_second_rest="t",
    sixty_fourth_rest="x",
    fermata="^",
    ornament_plus="+",
    clip=">",
)


class _SemanticCanvas:
    def __init__(self, height: int, width: int) -> None:
        self.height = height
        self.width = width
        self.chars = [[" " for _ in range(width)] for _ in range(height)]
        self.roles: list[list[ElementRole | None]] = [[None for _ in range(width)] for _ in range(height)]
        self.ids: list[list[str | None]] = [[None for _ in range(width)] for _ in range(height)]
        self.styles = [[CellStyle.NORMAL for _ in range(width)] for _ in range(height)]
        self.priorities = [[-1 for _ in range(width)] for _ in range(height)]

    def write(
        self,
        y: int,
        x: int,
        text: str,
        *,
        role: ElementRole,
        source_id: str,
        style: CellStyle,
        priority: int,
    ) -> None:
        if y < 0 or y >= self.height or x >= self.width:
            return
        cursor = x
        for cluster in split_display_clusters(text):
            if cursor + cluster.width <= 0:
                cursor += cluster.width
                continue
            if cursor < 0 or cursor + cluster.width > self.width:
                break
            if any(self.priorities[y][cell_x] > priority for cell_x in range(cursor, cursor + cluster.width)):
                cursor += cluster.width
                continue
            self.chars[y][cursor] = cluster.text
            for continuation_x in range(cursor + 1, cursor + cluster.width):
                self.chars[y][continuation_x] = ""
            for cell_x in range(cursor, cursor + cluster.width):
                self.roles[y][cell_x] = role
                self.ids[y][cell_x] = source_id
                self.styles[y][cell_x] = style
                self.priorities[y][cell_x] = priority
            cursor += cluster.width

    def snapshot(self) -> SemanticFrame:
        lines = ["".join(row) for row in self.chars]
        attrs = [tuple(_style_attr(style) for style in row) for row in self.styles]
        return SemanticFrame(
            frame=Frame(lines=lines, attrs=attrs),
            roles=tuple(tuple(row) for row in self.roles),
            element_ids=tuple(tuple(row) for row in self.ids),
            styles=tuple(tuple(row) for row in self.styles),
        )


def paint_score(
    layout: ScoreLayout,
    *,
    viewport: LayoutViewport | None = None,
    glyph_mode: GlyphMode = GlyphMode.PRETTY,
    overlays: Mapping[str, EventOverlay] | None = None,
) -> SemanticFrame:
    """Paint a semantic layout into a fixed terminal frame."""

    active_viewport = viewport or LayoutViewport(width=layout.width)
    if not isinstance(glyph_mode, GlyphMode):
        _fail("glyph mode must be a GlyphMode")
    if active_viewport.width != layout.width:
        _fail("paint viewport width must match the score layout width")
    if active_viewport.system_offset >= len(layout.systems) and layout.systems:
        _fail("paint system offset is outside the score layout")
    canvas = _SemanticCanvas(active_viewport.height, active_viewport.width)
    overlay_map = _validated_overlays(layout, overlays)
    if not layout.systems:
        return canvas.snapshot()
    scroll_y = layout.systems[active_viewport.system_offset].rect.y
    glyphs = _PRETTY if glyph_mode is GlyphMode.PRETTY else _SAFE
    for system in layout.systems[active_viewport.system_offset :]:
        if system.rect.y - scroll_y >= active_viewport.height:
            break
        for element in sorted(system.elements, key=lambda item: _priority(item.key.role)):
            _paint_element(canvas, element, y_offset=scroll_y, glyphs=glyphs, overlays=overlay_map)
    return canvas.snapshot()


def _validated_overlays(
    layout: ScoreLayout,
    overlays: Mapping[str, EventOverlay] | None,
) -> Mapping[str, EventOverlay]:
    overlay_map = overlays or {}
    if any(not isinstance(event_id, str) or not event_id for event_id in overlay_map):
        _fail("overlay event IDs must be non-empty strings")
    if any(not isinstance(overlay, EventOverlay) for overlay in overlay_map.values()):
        _fail("overlay values must be EventOverlay instances")
    unknown_overlays = set(overlay_map) - set(layout.event_ids)
    if unknown_overlays:
        unknown = ", ".join(sorted(unknown_overlays))
        _fail(f"overlays reference unknown event IDs: {unknown}")
    return overlay_map


def _paint_element(
    canvas: _SemanticCanvas,
    element: LayoutElement,
    *,
    y_offset: int,
    glyphs: _GlyphInventory,
    overlays: Mapping[str, EventOverlay],
) -> None:
    role = element.key.role
    y = element.rect.y - y_offset
    style = _element_style(element, overlays)
    if role in {ElementRole.STEM, ElementRole.BARLINE}:
        text = _vertical_glyph(element, glyphs)
        for row in range(element.rect.height):
            _write(canvas, element, y=y + row, text=text, style=style)
        return
    if role is ElementRole.TIME_SIGNATURE:
        _paint_time_signature(canvas, element, y=y, style=style)
        return
    if role is ElementRole.ENDING:
        _write(canvas, element, y=y, text=_ending_text(element, glyphs), style=style)
        return
    if role in {ElementRole.TIE, ElementRole.SLUR}:
        _write(canvas, element, y=y, text=_span_text(element, glyphs), style=style)
        return
    text = _element_text(element, glyphs)
    if not text:
        return
    if role in {
        ElementRole.STAFF,
        ElementRole.LEDGER_LINE,
        ElementRole.BEAM,
    }:
        text = text * element.rect.width
    text = clip_display(text, element.rect.width)
    _write(canvas, element, y=y, text=text, style=style)


def _write(
    canvas: _SemanticCanvas,
    element: LayoutElement,
    *,
    y: int,
    text: str,
    style: CellStyle,
) -> None:
    canvas.write(
        y,
        element.rect.x,
        text,
        role=element.key.role,
        source_id=element.key.source_id,
        style=style,
        priority=_priority(element.key.role),
    )


def _paint_time_signature(
    canvas: _SemanticCanvas,
    element: LayoutElement,
    *,
    y: int,
    style: CellStyle,
) -> None:
    numerator, separator, denominator = element.value.partition("/")
    if not separator:
        _write(canvas, element, y=y, text=element.value, style=style)
        return
    width = element.rect.width
    top_x = element.rect.x + max(0, (width - display_width(numerator)) // 2)
    bottom_x = element.rect.x + max(0, (width - display_width(denominator)) // 2)
    canvas.write(
        y,
        top_x,
        clip_display(numerator, width),
        role=element.key.role,
        source_id=element.key.source_id,
        style=style,
        priority=_priority(element.key.role),
    )
    canvas.write(
        y + 1,
        bottom_x,
        clip_display(denominator, width),
        role=element.key.role,
        source_id=element.key.source_id,
        style=style,
        priority=_priority(element.key.role),
    )


def _element_text(element: LayoutElement, glyphs: _GlyphInventory) -> str:
    role = element.key.role
    literal_roles = {
        ElementRole.TITLE,
        ElementRole.COMPOSER,
        ElementRole.STAFF_LABEL,
        ElementRole.MEASURE_NUMBER,
        ElementRole.LYRIC,
        ElementRole.DYNAMIC,
        ElementRole.PITCH_LABEL,
        ElementRole.FEEDBACK,
    }
    if role in literal_roles:
        return element.value
    return _notation_symbol(element, glyphs)


def _notation_symbol(element: LayoutElement, glyphs: _GlyphInventory) -> str:
    fixed = {
        ElementRole.STAFF: glyphs.staff,
        ElementRole.LEDGER_LINE: glyphs.ledger,
        ElementRole.BEAM: glyphs.beam,
        ElementRole.FERMATA: glyphs.fermata,
        ElementRole.ORNAMENT: glyphs.ornament_plus,
        ElementRole.LYRIC_EXTENDER: "__",
        ElementRole.LYRIC_HYPHEN: "-",
        ElementRole.CLIP_MARKER: glyphs.clip,
    }
    if element.key.role in fixed:
        return fixed[element.key.role]
    return _valued_notation_symbol(element, glyphs)


def _span_text(element: LayoutElement, glyphs: _GlyphInventory) -> str:
    if element.key.role is ElementRole.SLUR:
        left, fill, right = glyphs.slur_left, glyphs.slur_fill, glyphs.slur_right
    else:
        left, fill, right = glyphs.tie_left, glyphs.tie_fill, glyphs.tie_right
    if element.value in {"end", "continue"}:
        left = glyphs.continuation_left
    if element.value in {"start", "continue"}:
        right = glyphs.continuation_right
    if element.rect.width == 1:
        if element.value == "start":
            return right
        if element.value in {"end", "continue"}:
            return left
        return fill
    return left + (fill * max(0, element.rect.width - 2)) + right


def _ending_text(element: LayoutElement, glyphs: _GlyphInventory) -> str:
    prefix = f"{glyphs.ending_left}{element.value}."
    return prefix + (glyphs.ending_fill * max(0, element.rect.width - display_width(prefix)))


def _valued_notation_symbol(element: LayoutElement, glyphs: _GlyphInventory) -> str:
    role = element.key.role
    if role is ElementRole.CLEF:
        text = _clef_text(element.value, glyphs)
    elif role is ElementRole.FLAG:
        text = glyphs.flag_up if element.value == "up" else glyphs.flag_down
    elif role is ElementRole.KEY_SIGNATURE:
        text = _key_signature_text(element.value, glyphs)
    elif role is ElementRole.NOTEHEAD:
        text = glyphs.open_notehead if element.value in {"1", "2"} else glyphs.filled_notehead
    elif role is ElementRole.REST:
        text = _rest_text(element.value, glyphs)
    elif role is ElementRole.ACCIDENTAL:
        text = _accidental_text(element.value, glyphs)
    elif role is ElementRole.DOT:
        text = glyphs.dot * max(1, int(element.value or "1"))
    else:
        text = element.value
    return text


def _clef_text(value: str, glyphs: _GlyphInventory) -> str:
    return glyphs.treble_clef if value == "treble" else glyphs.bass_clef


def _vertical_glyph(element: LayoutElement, glyphs: _GlyphInventory) -> str:
    if element.key.role is ElementRole.STEM:
        return glyphs.stem
    return {
        "double": glyphs.double_barline,
        "final": glyphs.final_barline,
        "repeat-start": glyphs.repeat_start_barline,
        "repeat-end": glyphs.repeat_end_barline,
        "repeat-both": glyphs.repeat_both_barline,
    }.get(element.value, glyphs.barline)


def _key_signature_text(value: str, glyphs: _GlyphInventory) -> str:
    if value == "sharp":
        return glyphs.sharp
    if value == "flat":
        return glyphs.flat
    if value == "natural":
        return glyphs.natural
    fifths = int(value or "0")
    if fifths > 0:
        return glyphs.sharp + (str(fifths) if fifths > 1 else "")
    if fifths < 0:
        return glyphs.flat + (str(abs(fifths)) if fifths < -1 else "")
    return ""


def _rest_text(value: str, glyphs: _GlyphInventory) -> str:
    denominator = int(value or "4")
    if denominator <= 1:
        return glyphs.whole_rest
    return {
        2: glyphs.half_rest,
        4: glyphs.quarter_rest,
        8: glyphs.eighth_rest,
        16: glyphs.sixteenth_rest,
        32: glyphs.thirty_second_rest,
    }.get(denominator, glyphs.sixty_fourth_rest)


def _accidental_text(value: str, glyphs: _GlyphInventory) -> str:
    alter_text, separator, display = (value or "0").partition(":")
    alter = int(alter_text)
    if alter > 0:
        text = glyphs.sharp * alter
    elif alter < 0:
        text = glyphs.flat * abs(alter)
    else:
        text = glyphs.natural
    return f"({text})" if separator and display == "courtesy" else text


def _element_style(element: LayoutElement, overlays: Mapping[str, EventOverlay]) -> CellStyle:
    overlay = overlays.get(element.key.source_id)
    if overlay is not None:
        return _overlay_style(overlay.role)
    if element.key.role in {ElementRole.MEASURE_NUMBER, ElementRole.STAFF_LABEL}:
        return CellStyle.DIM
    return CellStyle.NORMAL


def _overlay_style(role: OverlayRole) -> CellStyle:
    return {
        OverlayRole.CURRENT: CellStyle.CURRENT,
        OverlayRole.PENDING: CellStyle.PENDING,
        OverlayRole.HIT: CellStyle.HIT,
        OverlayRole.MISSED: CellStyle.MISSED,
        OverlayRole.UNCERTAIN: CellStyle.UNCERTAIN,
    }[role]


def _style_attr(style: CellStyle) -> int:
    return {
        CellStyle.NORMAL: 0,
        CellStyle.DIM: A_DIM,
        CellStyle.CURRENT: A_REVERSE,
        CellStyle.PENDING: A_DIM,
        CellStyle.HIT: A_BOLD,
        CellStyle.MISSED: A_DIM | A_UNDERLINE,
        CellStyle.UNCERTAIN: A_UNDERLINE,
    }[style]


def _priority(role: ElementRole) -> int:
    return {
        ElementRole.STAFF: 10,
        ElementRole.LEDGER_LINE: 15,
        ElementRole.STEM: 20,
        ElementRole.FLAG: 28,
        ElementRole.BARLINE: 25,
        ElementRole.ENDING: 32,
        ElementRole.BEAM: 30,
        ElementRole.TIE: 32,
        ElementRole.SLUR: 32,
        ElementRole.CLEF: 40,
        ElementRole.KEY_SIGNATURE: 40,
        ElementRole.TIME_SIGNATURE: 40,
        ElementRole.ACCIDENTAL: 45,
        ElementRole.DOT: 48,
        ElementRole.EDITORIAL_BRACKET: 49,
        ElementRole.NOTEHEAD: 50,
        ElementRole.REST: 50,
        ElementRole.FERMATA: 52,
        ElementRole.ORNAMENT: 52,
        ElementRole.CLIP_MARKER: 55,
        ElementRole.FEEDBACK: 60,
    }.get(role, 35)


def _fail(message: str) -> NoReturn:
    raise ValueError(message)


def _validate_optional_number(value: float | None, label: str) -> None:
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, Real) or not isfinite(float(value)):
        _fail(f"event overlay {label} must be a finite number")


__all__ = [
    "CellStyle",
    "EventOverlay",
    "GlyphMode",
    "OverlayRole",
    "SemanticFrame",
    "paint_score",
]
