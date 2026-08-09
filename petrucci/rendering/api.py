from __future__ import annotations

from dataclasses import dataclass

from petrucci.terminal.canvas.framebuffer import draw_frame_rows
from petrucci.core.imported import project_imported_staff
from petrucci.terminal.lyrics import piece_for_lyric_display
from petrucci.core.model import Piece
from petrucci.adapters.piece_view import typeset_piece_score_view
from petrucci.rendering.primitives.helpers import apply_overrides as _apply_overrides_impl
from petrucci.rendering.primitives.helpers import bass_strings_used as _bass_strings_used_impl
from petrucci.rendering.primitives.helpers import clean_text as _clean_text
from petrucci.rendering.primitives.helpers import render_info as _render_info
from petrucci.rendering.primitives.helpers import render_notes as _render_notes
from petrucci.rendering.primitives.helpers import render_plugin as _render_plugin
from petrucci.rendering.primitives.helpers import safe_addstr as _safe_addstr
from petrucci.rendering.bar.legacy import LegacyRenderRequest, render_legacy_piece
from petrucci.rendering.system.status import build_status_lines, status_attr_for_message
from petrucci.terminal.canvas.screen import A_REVERSE, Screen


def _bass_strings_used(piece: Piece, overrides: dict[tuple[int, int, int], str]) -> set[int]:
    return _bass_strings_used_impl(piece, overrides)


def _apply_overrides(
    cells: list[list[str]],
    overrides: dict[tuple[int, int, int], str],
    bar_index: int,
    strings: int,
    bar_width: int,
) -> None:
    _apply_overrides_impl(cells, overrides, bar_index, strings, bar_width)


def _render_ascii_preview(
    stdscr: Screen,
    ascii_lines: list[str],
    status_line: str,
    mode: str,
    status_attr: int,
) -> None:
    height, _width = stdscr.getmaxyx()
    for idx, line in enumerate(ascii_lines[: max(0, height - 1)]):
        _safe_addstr(stdscr, idx, 0, _clean_text(line))
    _safe_addstr(
        stdscr,
        height - 1,
        0,
        _clean_text(f"{status_line}  {mode}  ascii preview"),
        status_attr,
    )


@dataclass(frozen=True)
class _AuxiliaryRequest:
    mode: str
    status_line: str
    status_attr: int
    help_offset: int
    plugin_title: str
    plugin_items: list[str]
    plugin_index: int
    plugin_offset: int
    message: str
    ascii_lines: list[str] | None
    settings: dict[str, str]


@dataclass(frozen=True)
class _CanonicalRequest:
    width: int
    height: int
    mode: str
    bar_offset: int
    cursor_bar: int
    cursor_col: int
    playback_bar: int | None
    playback_col: int | None
    settings: dict[str, str]
    focused_staff: int | None
    cursor_maps: dict[int, list[int]] | None
    status_line: str
    status_attr: int
    cmdline: str
    searchline: str
    message: str


def _render_auxiliary(
    screen: Screen,
    piece: Piece,
    width: int,
    height: int,
    request: _AuxiliaryRequest,
) -> bool:
    if request.mode == "info":
        _render_info(
            screen,
            request.status_line,
            request.status_attr,
            request.help_offset,
            piece,
            {**request.settings, "terminal": f"{width}x{height}"},
        )
    elif request.mode == "notes":
        _render_notes(screen, request.status_line, request.status_attr, request.help_offset, piece)
    elif request.mode == "plugin":
        _render_plugin(
            screen,
            "plugin  j/k move  h back  l/enter open  d download  q close",
            request.status_attr,
            request.plugin_title,
            request.plugin_items,
            request.plugin_index,
            request.plugin_offset,
            request.message,
        )
    elif request.ascii_lines is not None:
        _render_ascii_preview(
            screen,
            request.ascii_lines,
            request.status_line,
            request.mode,
            request.status_attr,
        )
    else:
        return False
    screen.refresh()
    return True


def _render_canonical(
    screen: Screen,
    piece: Piece,
    request: _CanonicalRequest,
) -> bool:
    if request.mode == "help":
        return False
    canonical = typeset_piece_score_view(
        piece,
        width=request.width,
        height=max(1, request.height - 1),
        bar_offset=request.bar_offset,
        cursor=(request.cursor_bar, request.cursor_col),
        playback=(request.playback_bar, request.playback_col)
        if request.playback_bar is not None and request.playback_col is not None
        else None,
        settings=request.settings,
        focused_imported_staff_index=request.focused_staff,
    )
    if canonical is None:
        return False
    draw_frame_rows(screen, canonical.result.frame, set(range(max(0, request.height - 1))))
    if request.cursor_maps is not None:
        request.cursor_maps.clear()
        request.cursor_maps.update(canonical.cursor_display_maps)
    text = build_status_lines(
        mode=request.mode,
        cmdline=request.cmdline,
        searchline=request.searchline,
        message=request.message,
        status_line=request.status_line,
        dur_text=None,
    )
    _safe_addstr(screen, request.height - 1, 0, _clean_text(text), request.status_attr)
    screen.refresh()
    return True


def render_piece(  # noqa: PLR0917 - legacy public facade pending an editor-side request record
    stdscr: Screen,
    piece: Piece,
    bar_offset: int,
    cursor_bar: int,
    cursor_string: int,
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
    mode: str,
    cmdline: str,
    message: str,
    status_line: str,
    searchline: str,
    settings: dict[str, str],
    ascii_lines: list[str] | None,
    stave_breaks: set[int],
    plugin_title: str,
    plugin_items: list[str],
    plugin_index: int,
    plugin_offset: int,
    help_offset: int = 0,
    playback_bar: int | None = None,
    playback_col: int | None = None,
    glisses: list[tuple[int, int, int]] | None = None,
    playback_cache=None,
    playback_markers: list[tuple[int, int]] | None = None,
    cursor_display_maps: dict[int, list[int]] | None = None,
    message_level: str = "info",
    focused_imported_staff_index: int | None = None,
    playback_verse: int | None = None,
) -> None:
    piece = project_imported_staff(piece, focused_imported_staff_index)
    piece = piece_for_lyric_display(piece, settings, active_verse_index=playback_verse)
    stdscr.erase()
    height, width = stdscr.getmaxyx()
    status_attr = status_attr_for_message(message_level) if message else A_REVERSE
    auxiliary = _AuxiliaryRequest(
        mode,
        status_line,
        status_attr,
        help_offset,
        plugin_title,
        plugin_items,
        plugin_index,
        plugin_offset,
        message,
        ascii_lines,
        settings,
    )
    if _render_auxiliary(stdscr, piece, width, height, auxiliary):
        return
    canonical = _CanonicalRequest(
        width,
        height,
        mode,
        bar_offset,
        cursor_bar,
        cursor_col,
        playback_bar,
        playback_col,
        settings,
        focused_imported_staff_index,
        cursor_display_maps,
        status_line,
        status_attr,
        cmdline,
        searchline,
        message,
    )
    if _render_canonical(stdscr, piece, canonical):
        return
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
            mode,
            cmdline,
            message,
            status_line,
            searchline,
            settings,
            stave_breaks,
            help_offset,
            playback_bar,
            playback_col,
            playback_cache,
            playback_markers,
            cursor_display_maps,
            status_attr,
        ),
    )
