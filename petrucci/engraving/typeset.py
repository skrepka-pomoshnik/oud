from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from petrucci.adapters.piece_view import typeset_piece_score_view
from petrucci.core.model import Piece
from petrucci.rendering.api import render_piece
from petrucci.terminal.canvas.framebuffer import Frame, FrameBuffer

DEFAULT_TYPESET_SETTINGS: dict[str, str] = {
    "style": "french",
    "tuning": "",
    "layout": "auto",
    "justify": "smart",
    "measures": "system",
    "bargap": "1",
    "barpad": "1",
    "showdur": "off",
    "showspans": "on",
    "showtuplets": "on",
    "showtactus": "off",
    "showmelody": "on",
    "showlyrics": "on",
    "showfingerings": "on",
    "showornaments": "on",
    "flagredundant": "on",
    "tuninglabels": "relative",
    "basslabels": "tuning",
    "frenchc": "normal",
}


@dataclass(frozen=True)
class TypesetOptions:
    width: int = 100
    height: int = 30
    bar_width: int = 12
    bar_offset: int = 0
    cursor: tuple[int, int, int] = (0, 0, 0)
    include_status: bool = False
    settings: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class TypesetResult:
    frame: Frame
    cursor_display_maps: dict[int, list[int]]

    @property
    def lines(self) -> tuple[str, ...]:
        return tuple(self.frame.lines)

    @property
    def text(self) -> str:
        lines = [line.rstrip() for line in self.frame.lines]
        while lines and not lines[-1]:
            lines.pop()
        return "\n".join(lines) + ("\n" if lines else "")


def typeset_piece(
    piece: Piece,
    *,
    options: TypesetOptions | None = None,
    overrides: Mapping[tuple[int, int, int], str] | None = None,
    durations: Mapping[tuple[int, int, int], int] | None = None,
    ornaments: Mapping[tuple[int, int], str] | None = None,
    annotations: Mapping[tuple[int, int], str] | None = None,
    highlights: set[tuple[int, int, int]] | None = None,
    dotted: set[tuple[int, int]] | None = None,
    slurs: list[tuple[int, int, int]] | None = None,
    ties: list[tuple[int, int, int]] | None = None,
    holds: list[tuple[int, int, int]] | None = None,
    glisses: list[tuple[int, int, int]] | None = None,
    stave_breaks: set[int] | None = None,
    playback: tuple[int, int] | None = None,
) -> TypesetResult:
    """Typeset a score into a reusable character-cell frame and plain text."""
    opts = options or TypesetOptions()
    settings = dict(DEFAULT_TYPESET_SETTINGS)
    if piece.style:
        settings["style"] = piece.style
    if piece.tuning:
        settings["tuning"] = piece.tuning
    settings.update(opts.settings)

    width = max(1, opts.width)
    content_height = max(1, opts.height)
    cursor_bar, cursor_string, cursor_col = opts.cursor
    canonical = typeset_piece_score_view(
        piece,
        width=width,
        height=content_height,
        bar_offset=opts.bar_offset,
        cursor=(cursor_bar, cursor_col),
        playback=playback,
        settings=settings,
    )
    if canonical is not None and not opts.include_status:
        return TypesetResult(
            frame=canonical.result.frame,
            cursor_display_maps=canonical.cursor_display_maps,
        )
    render_height = content_height if opts.include_status else content_height + 1
    screen = FrameBuffer(render_height, width)
    cursor_display_maps: dict[int, list[int]] = {}
    playback_bar = playback[0] if playback is not None else None
    playback_col = playback[1] if playback is not None else None
    render_piece(
        screen,
        piece,
        bar_offset=opts.bar_offset,
        cursor_bar=cursor_bar,
        cursor_string=cursor_string,
        cursor_col=cursor_col,
        bar_width=max(1, opts.bar_width),
        overrides=dict(overrides or {}),
        durations=dict(durations or {}),
        ornaments=dict(ornaments or {}),
        annotations=dict(annotations or {}),
        highlights=set(highlights or set()),
        dotted=set(dotted or set()),
        slurs=list(slurs or []),
        ties=list(ties or []),
        holds=list(holds or []),
        mode="normal",
        cmdline="",
        message="",
        status_line="",
        searchline="",
        settings=settings,
        ascii_lines=None,
        stave_breaks=set(stave_breaks or set()),
        plugin_title="",
        plugin_items=[],
        plugin_index=0,
        plugin_offset=0,
        playback_bar=playback_bar,
        playback_col=playback_col,
        glisses=list(glisses or []),
        cursor_display_maps=cursor_display_maps,
    )
    frame = screen.snapshot()
    if not opts.include_status:
        frame = Frame(lines=frame.lines[:-1], attrs=frame.attrs[:-1])
    return TypesetResult(frame=frame, cursor_display_maps=cursor_display_maps)


def typeset_text(piece: Piece, **kwargs) -> str:
    """Convenience wrapper returning only clean, right-trimmed ASCII text."""
    return typeset_piece(piece, **kwargs).text
