"""Opt-in true-colour output for semantic score frames, without curses state."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from petrucci.engraving.layout.engine import ElementRole
from petrucci.terminal.api import SemanticFrame
from petrucci.terminal.display import split_display_clusters

RGB_CHANNELS = 3
MAX_RGB_CHANNEL = 255


class PaletteError(ValueError):
    """Raised when an ANSI palette contains invalid RGB values."""


@dataclass(frozen=True, slots=True)
class AnsiPalette:
    """RGB colours for complete terminal cells, not individual braille dots."""

    background: tuple[int, int, int]
    staff: tuple[int, int, int]
    notes: tuple[int, int, int]
    marks: tuple[int, int, int]
    spans: tuple[int, int, int]
    text: tuple[int, int, int]
    active: tuple[int, int, int]

    def __post_init__(self) -> None:
        colours = (self.background, self.staff, self.notes, self.marks, self.spans, self.text, self.active)
        if any(
            len(colour) != RGB_CHANNELS or any(not 0 <= channel <= MAX_RGB_CHANNEL for channel in colour)
            for colour in colours
        ):
            raise PaletteError

    def foreground(self, role: ElementRole | None, *, active: bool = False) -> tuple[int, int, int]:
        if active:
            return self.active
        if role in {ElementRole.STAFF, ElementRole.LEDGER_LINE, ElementRole.BARLINE}:
            return self.staff
        if role in {ElementRole.ACCIDENTAL, ElementRole.KEY_SIGNATURE, ElementRole.ORNAMENT}:
            return self.marks
        if role in {ElementRole.TIE, ElementRole.SLUR, ElementRole.GLISSANDO}:
            return self.spans
        if role in {
            ElementRole.NOTEHEAD,
            ElementRole.REST,
            ElementRole.STEM,
            ElementRole.FLAG,
            ElementRole.BEAM,
            ElementRole.DOT,
            ElementRole.CLEF,
            ElementRole.TIME_SIGNATURE,
        }:
            return self.notes
        return self.text


INK = AnsiPalette(
    background=(17, 28, 39),
    staff=(82, 102, 119),
    notes=(255, 242, 207),
    marks=(246, 185, 78),
    spans=(92, 214, 191),
    text=(190, 208, 219),
    active=(255, 111, 97),
)
PAPER = AnsiPalette(
    background=(250, 247, 239),
    staff=(174, 185, 189),
    notes=(23, 43, 56),
    marks=(170, 83, 0),
    spans=(20, 118, 105),
    text=(76, 94, 103),
    active=(177, 38, 57),
)


def colour_score(frame: SemanticFrame, *, palette: AnsiPalette = INK, active_ids: Iterable[str] = ()) -> str:
    """Serialize visible rows as ANSI true colour, resetting at each line end.

    The frame and its plain text remain unchanged. Shared staff/note cells use
    the winning semantic role; terminals cannot colour dots independently.
    Caller-provided active IDs indicate selection, not an audio transport.
    """
    selected = frozenset(active_ids)
    height = len(frame.text.splitlines())
    return "".join(_colour_row(frame, row, palette, selected) for row in range(height))


def _colour_row(frame: SemanticFrame, row: int, palette: AnsiPalette, selected: frozenset[str]) -> str:
    background = ";".join(map(str, palette.background))
    parts = [f"\x1b[0;48;2;{background}m"]
    previous = None
    column = 0
    for cluster in split_display_clusters(frame.lines[row]):
        role = frame.roles[row][column]
        foreground = palette.foreground(role, active=frame.element_ids[row][column] in selected)
        if foreground != previous:
            parts.append("\x1b[38;2;" + ";".join(map(str, foreground)) + "m")
            previous = foreground
        # Never allow lyric or title control characters to become ANSI commands.
        parts.append("".join(char if char >= " " and not "\x7f" <= char <= "\x9f" else " " for char in cluster.text))
        column += cluster.width
    parts.append("\x1b[0m\n")
    return "".join(parts)
