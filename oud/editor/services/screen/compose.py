"""Compose the editor screen: Petrucci paints the score, the editor paints its chrome."""

from __future__ import annotations

from dataclasses import dataclass

from oud.editor.core.coordinates import cursor_event
from oud.editor.core.input.help import help_lines
from oud.editor.core.input.modes import Mode
from oud.editor.core.state import EditorState
from oud.editor.navigation.view.focus import current_view_staff
from oud.editor.services.screen.pages import (
    PLUGIN_HINT,
    info_lines,
    notes_lines,
    paint_ascii_preview,
    paint_page,
    paint_plugin_browser,
)
from oud.editor.services.screen.rhythm import bar_meter_marker, cursor_duration_text
from oud.editor.services.screen.status import (
    StatusModel,
    render_status,
    status_model,
    status_row_attr,
    status_row_text,
    status_row_visible,
)
from oud.exports.export_tab import export_ascii
from petrucci.adapters.duet import is_duet_score_piece
from petrucci.rendering.api import PieceView, render_piece
from petrucci.rendering.primitives.helpers import clean_text, safe_addstr
from petrucci.rendering.staff.playback import PlaybackOverlayCache
from petrucci.terminal.canvas.framebuffer import Frame, FrameBuffer, draw_frame_rows


@dataclass(frozen=True)
class EditorFrame:
    """One full editor screen and the playback overlay cache built while painting it."""

    frame: Frame
    playback_cache: PlaybackOverlayCache | None


def _paint_page_mode(screen: FrameBuffer, state: EditorState, *, height: int, width: int) -> bool:
    attr = status_row_attr(state)
    status = status_row_text(state, width=width)
    if state.mode == Mode.HELP:
        paint_page(screen, help_lines(state), offset=state.help_offset, status=status, status_attr=attr)
    elif state.mode == Mode.INFO:
        lines = info_lines(state.piece, {**state.settings, "terminal": f"{width}x{height}"})
        paint_page(screen, lines, offset=state.info_offset, status=status, status_attr=attr)
    elif state.mode == Mode.NOTES:
        paint_page(screen, notes_lines(state.piece), offset=state.notes_offset, status=status, status_attr=attr)
    elif state.mode == Mode.PLUGIN:
        plugin_status = StatusModel(message=state.visible_message, level=state.visible_message_level, mode=PLUGIN_HINT)
        paint_plugin_browser(
            screen,
            title=state.plugin_title,
            items=[f"{item.title}{'/' if item.is_dir else ''}" for item in state.plugin_items],
            index=state.plugin_index,
            offset=state.plugin_offset,
            status=render_status(plugin_status, width),
            status_attr=attr,
        )
    else:
        return False
    return True


def _ascii_preview_lines(state: EditorState) -> list[str]:
    return export_ascii(
        state.piece,
        state.overrides,
        state.durations,
        state.bar_width,
        settings=state.settings,
        ornaments=state.ornaments,
        annotations=state.annotations,
        slurs=state.slurs,
        ties=state.ties,
        holds=state.holds,
    ).splitlines()


def _new_playback_cache(state: EditorState) -> PlaybackOverlayCache | None:
    # Tablature playback is painted as an overlay; imported and duet scores repaint the marker.
    if is_duet_score_piece(state.piece) or state.piece.imported_score is not None:
        return None
    return {}


def _paint_score(
    screen: FrameBuffer,
    state: EditorState,
    *,
    show_status: bool,
    playback_cache: PlaybackOverlayCache | None,
) -> None:
    height, width = screen.getmaxyx()
    content_height = max(1, height - int(show_status))
    score = FrameBuffer(content_height, width)
    focused_staff = current_view_staff(state)
    view = render_piece(
        score,
        state.piece,
        state.bar_offset,
        state.cursor_bar,
        state.cursor_string,
        cursor_col=state.cursor_col,
        bar_width=state.bar_width,
        overrides=state.overrides,
        durations=state.durations,
        ornaments=state.ornaments,
        annotations=state.annotations,
        highlights=state.highlights,
        dotted=state.dotted,
        slurs=state.slurs,
        ties=state.ties,
        holds=state.holds,
        settings=state.settings,
        stave_breaks=state.stave_breaks,
        playback_bar=None if playback_cache is not None else state.playback_bar,
        playback_col=None if playback_cache is not None else state.playback_col,
        playback_markers=None if playback_cache is not None else state.playback.markers,
        playback_cache=playback_cache,
        cursor_display_maps=state.display_cursor_maps,
        focused_imported_staff_index=(
            focused_staff.source_index if not focused_staff.key.startswith("duet-") else None
        ),
        playback_verse=state.playback.verse,
        cursor_event=cursor_event(state),
    )
    draw_frame_rows(screen, score.snapshot(), set(range(content_height)))
    if show_status:
        tablature = view is PieceView.TABLATURE
        status = status_row_text(
            state,
            duration=cursor_duration_text(state) if tablature else None,
            meter=bar_meter_marker(state) if tablature else None,
            width=width,
        )
        safe_addstr(screen, height - 1, 0, clean_text(status), status_row_attr(state))


def compose_editor_frame(state: EditorState, *, height: int, width: int) -> EditorFrame:
    """Paint the full editor screen for the current mode."""

    screen = FrameBuffer(height, width)
    show_status = status_row_visible(state)
    playback_cache = _new_playback_cache(state)
    state.display_cursor_maps.clear()
    if _paint_page_mode(screen, state, height=height, width=width):
        return EditorFrame(screen.snapshot(), playback_cache)
    if state.ascii_preview:
        preview = status_model(state, mode=f"{state.mode}  ascii preview")
        status = render_status(preview, width) if show_status else None
        paint_ascii_preview(screen, _ascii_preview_lines(state), status=status, status_attr=status_row_attr(state))
        return EditorFrame(screen.snapshot(), playback_cache)
    _paint_score(screen, state, show_status=show_status, playback_cache=playback_cache)
    return EditorFrame(screen.snapshot(), playback_cache)
