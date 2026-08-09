"""Display-safe terminal painting for semantic Petrucci score layouts."""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
from typing import NoReturn

from petrucci.display import clip_display, display_width, split_display_clusters
from petrucci.framebuffer import Frame
from petrucci.layout import ElementRole, LayoutElement, LayoutViewport, ScoreLayout
from petrucci.screen import A_DIM


class GlyphMode(StrEnum):
    PRETTY = "pretty"
    SAFE = "safe"


@dataclass(frozen=True, slots=True)
class TerminalNoteheads:
    """One-cell noteheads that override only the active inventory's note shapes."""

    filled: str = "o"
    open: str = "O"

    def __post_init__(self) -> None:
        for label, glyph in (("filled", self.filled), ("open", self.open)):
            if display_width(glyph) != 1 or len(split_display_clusters(glyph)) != 1:
                _fail(f"terminal {label} notehead must occupy exactly one terminal cell")


@dataclass(frozen=True, slots=True)
class SemanticFrame:
    frame: Frame
    roles: tuple[tuple[ElementRole | None, ...], ...]
    element_ids: tuple[tuple[str | None, ...], ...]

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
    one_hundred_twenty_eighth_rest: str
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
    one_hundred_twenty_eighth_rest="𝅂",
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
    one_hundred_twenty_eighth_rest="z",
    fermata="^",
    ornament_plus="+",
    clip=">",
)


class _SemanticCanvas:
    def __init__(self, height: int, width: int, *, x_offset: int = 0) -> None:
        self.height = height
        self.width = width
        self.x_offset = x_offset
        self.chars = [[" " for _ in range(width)] for _ in range(height)]
        self.roles: list[list[ElementRole | None]] = [[None for _ in range(width)] for _ in range(height)]
        self.ids: list[list[str | None]] = [[None for _ in range(width)] for _ in range(height)]
        self.priorities = [[-1 for _ in range(width)] for _ in range(height)]

    def write(
        self,
        y: int,
        x: int,
        text: str,
        *,
        role: ElementRole,
        source_id: str,
        priority: int,
    ) -> None:
        cursor = x - self.x_offset
        if y < 0 or y >= self.height or cursor >= self.width:
            return
        for cluster in split_display_clusters(text):
            next_cursor = self._write_cluster(
                y,
                cursor,
                cluster.text,
                cluster.width,
                role=role,
                source_id=source_id,
                priority=priority,
            )
            if next_cursor is None:
                break
            cursor = next_cursor

    def _write_cluster(
        self,
        y: int,
        cursor: int,
        text: str,
        width: int,
        *,
        role: ElementRole,
        source_id: str,
        priority: int,
    ) -> int | None:
        next_cursor = cursor + width
        if next_cursor <= 0:
            return next_cursor
        if cursor < 0 or next_cursor > self.width:
            return None
        if any(self.priorities[y][cell_x] > priority for cell_x in range(cursor, next_cursor)):
            return next_cursor
        self.chars[y][cursor] = text
        for continuation_x in range(cursor + 1, next_cursor):
            self.chars[y][continuation_x] = ""
        for cell_x in range(cursor, next_cursor):
            self.roles[y][cell_x] = role
            self.ids[y][cell_x] = source_id
            self.priorities[y][cell_x] = priority
        return next_cursor

    def snapshot(self) -> SemanticFrame:
        lines = ["".join(row) for row in self.chars]
        attrs = [tuple(_role_attr(role) for role in row) for row in self.roles]
        return SemanticFrame(
            frame=Frame(lines=lines, attrs=attrs),
            roles=tuple(tuple(row) for row in self.roles),
            element_ids=tuple(tuple(row) for row in self.ids),
        )


def paint_score(
    layout: ScoreLayout,
    *,
    viewport: LayoutViewport | None = None,
    glyph_mode: GlyphMode = GlyphMode.PRETTY,
    noteheads: TerminalNoteheads | None = None,
) -> SemanticFrame:
    """Paint a semantic layout into a fixed terminal frame."""

    active_viewport = viewport or LayoutViewport(width=layout.width)
    glyphs = _glyph_inventory(glyph_mode, noteheads)
    if active_viewport.system_offset >= len(layout.systems) and layout.systems:
        _fail("paint system offset is outside the score layout")
    canvas = _SemanticCanvas(
        active_viewport.height,
        active_viewport.width,
        x_offset=active_viewport.x_offset,
    )
    if not layout.systems:
        return canvas.snapshot()
    scroll_y = layout.systems[active_viewport.system_offset].rect.y + active_viewport.y_offset
    for system in layout.systems[active_viewport.system_offset :]:
        if system.rect.y - scroll_y >= active_viewport.height:
            break
        for element in sorted(system.elements, key=lambda item: _priority(item.key.role)):
            _paint_element(canvas, element, y_offset=scroll_y, glyphs=glyphs)
    return canvas.snapshot()


def _glyph_inventory(glyph_mode: GlyphMode, noteheads: TerminalNoteheads | None) -> _GlyphInventory:
    glyphs = _PRETTY if glyph_mode is GlyphMode.PRETTY else _SAFE
    if noteheads is None:
        return glyphs
    return replace(glyphs, filled_notehead=noteheads.filled, open_notehead=noteheads.open)


def _paint_special_element(
    canvas: _SemanticCanvas,
    element: LayoutElement,
    *,
    y: int,
    glyphs: _GlyphInventory,
) -> bool:
    role = element.key.role
    if role in {ElementRole.STEM, ElementRole.BARLINE}:
        text = _vertical_glyph(element, glyphs)
        for row in range(element.rect.height):
            _write(canvas, element, y=y + row, text=text)
        return True
    if role is ElementRole.TIME_SIGNATURE:
        _paint_time_signature(canvas, element, y=y)
        return True
    if role is ElementRole.ENDING:
        _write(canvas, element, y=y, text=_ending_text(element, glyphs))
        return True
    if role in {ElementRole.TIE, ElementRole.SLUR, ElementRole.GLISSANDO}:
        _write(canvas, element, y=y, text=_span_text(element, glyphs))
        return True
    return False


def _paint_element(
    canvas: _SemanticCanvas,
    element: LayoutElement,
    *,
    y_offset: int,
    glyphs: _GlyphInventory,
) -> None:
    role = element.key.role
    y = element.rect.y - y_offset
    if _paint_special_element(canvas, element, y=y, glyphs=glyphs):
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
    _write(canvas, element, y=y, text=text)


def _write(
    canvas: _SemanticCanvas,
    element: LayoutElement,
    *,
    y: int,
    text: str,
) -> None:
    canvas.write(
        y,
        element.rect.x,
        text,
        role=element.key.role,
        source_id=element.key.source_id,
        priority=_priority(element.key.role),
    )


def _paint_time_signature(
    canvas: _SemanticCanvas,
    element: LayoutElement,
    *,
    y: int,
) -> None:
    numerator, separator, denominator = element.value.partition("/")
    if not separator:
        _write(canvas, element, y=y, text=element.value)
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
        priority=_priority(element.key.role),
    )
    canvas.write(
        y + 1,
        bottom_x,
        clip_display(denominator, width),
        role=element.key.role,
        source_id=element.key.source_id,
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
        ElementRole.LYRIC_LINE,
        ElementRole.DYNAMIC,
        ElementRole.PITCH_LABEL,
        ElementRole.HARMONIC,
        ElementRole.FINGERING,
        ElementRole.PROPORTION,
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
        ElementRole.GRACE: "g",
        ElementRole.LYRIC_EXTENDER: "__",
        ElementRole.LYRIC_HYPHEN: "-",
        ElementRole.CLIP_MARKER: glyphs.clip,
    }
    if element.key.role in fixed:
        return fixed[element.key.role]
    return _valued_notation_symbol(element, glyphs)


def _span_text(element: LayoutElement, glyphs: _GlyphInventory) -> str:
    if element.key.role is ElementRole.GLISSANDO:
        return "/" * element.rect.width
    return _curved_span_text(element, glyphs)


def _curved_span_text(element: LayoutElement, glyphs: _GlyphInventory) -> str:
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
    staff_symbol = _valued_staff_symbol(element, glyphs)
    return staff_symbol if staff_symbol is not None else _valued_mark_symbol(element, glyphs)


def _valued_staff_symbol(element: LayoutElement, glyphs: _GlyphInventory) -> str | None:
    role = element.key.role
    if role is ElementRole.CLEF:
        return _clef_text(element.value, glyphs)
    if role is ElementRole.FLAG:
        return glyphs.flag_up if element.value == "up" else glyphs.flag_down
    if role is ElementRole.KEY_SIGNATURE:
        return _key_signature_text(element.value, glyphs)
    if role is ElementRole.NOTEHEAD:
        return glyphs.open_notehead if element.value in {"1", "2"} else glyphs.filled_notehead
    return None


def _valued_mark_symbol(element: LayoutElement, glyphs: _GlyphInventory) -> str:
    role = element.key.role
    if role is ElementRole.REST:
        return _rest_text(element.value, glyphs)
    if role is ElementRole.ORNAMENT:
        return _ornament_text(element.value, glyphs)
    if role is ElementRole.ACCIDENTAL:
        return _accidental_text(element.value, glyphs)
    if role is ElementRole.DOT:
        return glyphs.dot * max(1, int(element.value or "1"))
    return element.value


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
        64: glyphs.sixty_fourth_rest,
        128: glyphs.one_hundred_twenty_eighth_rest,
    }[denominator]


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


def _ornament_text(value: str, glyphs: _GlyphInventory) -> str:
    return {
        "plus": glyphs.ornament_plus,
        "trill": "t",
        "turn": "~",
        "mordent": "m",
        "inverted-mordent": "w",
    }.get(value, "?")


def _role_attr(role: ElementRole | None) -> int:
    return A_DIM if role in {ElementRole.MEASURE_NUMBER, ElementRole.STAFF_LABEL} else 0


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
        ElementRole.GLISSANDO: 32,
        ElementRole.CLEF: 40,
        ElementRole.KEY_SIGNATURE: 40,
        ElementRole.TIME_SIGNATURE: 40,
        ElementRole.ACCIDENTAL: 45,
        ElementRole.DOT: 48,
        ElementRole.EDITORIAL_BRACKET: 49,
        ElementRole.NOTEHEAD: 50,
        ElementRole.REST: 50,
        ElementRole.FERMATA: 52,
        ElementRole.GRACE: 52,
        ElementRole.ORNAMENT: 52,
        ElementRole.HARMONIC: 52,
        ElementRole.FINGERING: 52,
        ElementRole.PROPORTION: 40,
        ElementRole.CLIP_MARKER: 55,
    }.get(role, 35)


def _fail(message: str) -> NoReturn:
    raise ValueError(message)


__all__ = [
    "GlyphMode",
    "SemanticFrame",
    "TerminalNoteheads",
    "paint_score",
]
