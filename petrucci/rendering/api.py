"""Paint a Piece score into a terminal screen.

The caller owns every row of the screen it passes in; Petrucci paints score
content only. Status lines, prompts, and pages belong to the application.
"""

from __future__ import annotations

from enum import StrEnum

from petrucci.adapters.piece_view import typeset_piece_score_view
from petrucci.core.imported import project_imported_staff
from petrucci.core.model import Piece
from petrucci.rendering.bar.legacy import LegacyRenderRequest, render_legacy_piece
from petrucci.rendering.staff.playback import PlaybackOverlayCache
from petrucci.terminal.canvas.framebuffer import draw_frame_rows
from petrucci.terminal.canvas.screen import Screen
from petrucci.terminal.text.lyrics import piece_for_lyric_display


class PieceView(StrEnum):
    """Which renderer painted the score."""

    NOTATION = "notation"
    TABLATURE = "tablature"


def _render_notation(
    screen: Screen,
    piece: Piece,
    *,
    bar_offset: int,
    cursor: tuple[int, int],
    playback: tuple[int, int] | None,
    settings: dict[str, str],
    focused_staff: int | None,
    cursor_display_maps: dict[int, list[int]] | None,
) -> bool:
    height, width = screen.getmaxyx()
    content_height = max(1, height)
    canonical = typeset_piece_score_view(
        piece,
        width=width,
        height=content_height,
        bar_offset=bar_offset,
        cursor=cursor,
        playback=playback,
        settings=settings,
        focused_imported_staff_index=focused_staff,
    )
    if canonical is None:
        return False
    draw_frame_rows(screen, canonical.result.frame, set(range(content_height)))
    if cursor_display_maps is not None:
        cursor_display_maps.clear()
        cursor_display_maps.update(canonical.cursor_display_maps)
    return True


def render_piece(
    stdscr: Screen,
    piece: Piece,
    bar_offset: int,
    cursor_bar: int,
    cursor_string: int,
    *,
    cursor_col: int,
    bar_width: int,
    overrides: dict[tuple[int, int, int], str],
    durations: dict[tuple[int, int, int], int],
    ornaments: dict[tuple[int, int], str],
    annotations: dict[tuple[int, int], str],
    highlights: set[tuple[int, int, int]],
    dotted: set[tuple[int, int]],
    slurs: list[tuple[int, int, int]],
    ties: list[tuple[int, int, int]],
    holds: list[tuple[int, int, int]],
    settings: dict[str, str],
    stave_breaks: set[int],
    playback_bar: int | None = None,
    playback_col: int | None = None,
    glisses: list[tuple[int, int, int]] | None = None,
    playback_cache: PlaybackOverlayCache | None = None,
    playback_markers: list[tuple[int, int]] | None = None,
    cursor_display_maps: dict[int, list[int]] | None = None,
    focused_imported_staff_index: int | None = None,
    playback_verse: int | None = None,
    cursor_event: int | None = None,
) -> PieceView:
    """Paint the score into every row of ``stdscr`` and report which view was used.

    ``cursor_event`` places the tablature cursor on that event of the cursor bar
    (``len(bar.chords)`` is the append slot) however densely the bar is drawn;
    without it ``cursor_col`` is scaled from the ``bar_width`` grid.
    """

    piece = project_imported_staff(piece, focused_imported_staff_index)
    piece = piece_for_lyric_display(piece, settings, active_verse_index=playback_verse)
    stdscr.erase()
    playback = (playback_bar, playback_col) if playback_bar is not None and playback_col is not None else None
    if _render_notation(
        stdscr,
        piece,
        bar_offset=bar_offset,
        cursor=(cursor_bar, cursor_col),
        playback=playback,
        settings=settings,
        focused_staff=focused_imported_staff_index,
        cursor_display_maps=cursor_display_maps,
    ):
        stdscr.refresh()
        return PieceView.NOTATION
    height, width = stdscr.getmaxyx()
    render_legacy_piece(
        stdscr,
        LegacyRenderRequest(
            piece,
            width,
            height,
            bar_offset,
            cursor_bar,
            cursor_string,
            cursor_col,
            bar_width,
            overrides,
            durations,
            ornaments,
            annotations,
            highlights,
            dotted,
            slurs,
            ties,
            holds,
            glisses,
            settings,
            stave_breaks,
            playback_bar,
            playback_col,
            playback_cache,
            playback_markers,
            cursor_display_maps,
            cursor_event,
        ),
    )
    stdscr.refresh()
    return PieceView.TABLATURE


__all__ = ["PieceView", "render_piece"]
