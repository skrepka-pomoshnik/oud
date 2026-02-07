from __future__ import annotations

from oud.core.model import Piece
from oud.core.tuning_utils import parse_bass_strings
from oud.core.view_model import _block_height, _tuning_labels
from oud.ui.adapter import A_REVERSE, Screen
from oud.ui.render_helpers import (
    apply_overrides as _apply_overrides_impl,
)
from oud.ui.render_helpers import (
    bass_strings_used as _bass_strings_used_impl,
)
from oud.ui.render_helpers import (
    clean_text as _clean_text,
)
from oud.ui.render_helpers import (
    render_help as _render_help,
)
from oud.ui.render_helpers import (
    render_info as _render_info,
)
from oud.ui.render_helpers import (
    render_plugin as _render_plugin,
)
from oud.ui.render_helpers import (
    safe_addstr as _safe_addstr,
)
from oud.ui.render_status import build_status_lines, resolve_duration_text
from oud.ui.render_system import render_systems


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
    for idx, line in enumerate(ascii_lines[: max(0, height - 2)]):
        _safe_addstr(stdscr, idx, 0, _clean_text(line))
    _safe_addstr(stdscr, height - 2, 0, _clean_text(status_line), status_attr)
    _safe_addstr(stdscr, height - 1, 0, _clean_text(f"{mode}  ascii preview"), status_attr)


def render_piece(  # noqa: C901, PLR0912
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
) -> None:
    stdscr.erase()
    height, width = stdscr.getmaxyx()
    total_strings = piece.strings

    status_attr = A_REVERSE
    if mode == "info":
        _render_info(stdscr, status_line, status_attr, help_offset, piece, settings)
        stdscr.refresh()
        return
    if mode == "plugin":
        _render_plugin(
            stdscr,
            "plugin  j/k move  h back  l/enter open  d download  q close",
            status_attr,
            plugin_title,
            plugin_items,
            plugin_index,
            plugin_offset,
            message,
        )
        stdscr.refresh()
        return
    if ascii_lines is not None:
        _render_ascii_preview(stdscr, ascii_lines, status_line, mode, status_attr)
        stdscr.refresh()
        return

    header = f"{piece.title or 'Untitled'}  [{len(piece.bars)} bars]"
    tuning_text = piece.tuning or settings.get("tuning", "")
    header_row = 0
    _safe_addstr(stdscr, header_row, 0, _clean_text(header))

    left_margin = 3
    spacing_mode = settings.get("spacingmode", "packed")
    spacing_fill = settings.get("spacingfill", "stretch")
    bargap = settings.get("bargap", "")
    if bargap.isdigit():
        bar_gap = max(0, int(bargap))
    else:
        bar_gap = 1 if spacing_mode in ("packed", "auto") else 3
    barpad = 1
    barpad_text = settings.get("barpad", "1")
    if barpad_text.isdigit():
        barpad = max(0, int(barpad_text))
    max_width = width
    usable_width = max(0, max_width - left_margin)
    linelen = settings.get("linelen", "")
    if linelen.isdigit():
        line_limit = int(linelen)
        if line_limit > 0:
            max_width = min(max_width, line_limit)
            usable_width = max(0, max_width - left_margin)

    default_duration = 4
    include_meta = True
    show_dur = settings.get("showdur", "off") == "on"
    show_extras = settings.get("showextras", "off") == "on"
    show_tactus = settings.get("showtactus", "off") == "on"
    hide_redundant = settings.get("flagredundant", "on") == "on"
    double_stems = settings.get("flagstems", "single") == "double"
    reverse_strings = (
        settings.get("viewinvert", "off") == "on"
        or (
            settings.get("style", "french") == "italian"
            and settings.get("italianorient", "normal") == "reverse"
        )
    )
    show_octaves = settings.get("tuninglabels", "relative") == "absolute"
    used_bass = _bass_strings_used(piece, overrides)
    bass_tokens = parse_bass_strings(settings.get("bassstrings", ""))
    base_strings = min(6, total_strings)
    display_indices = list(range(base_strings))
    display_indices.extend(
        idx for idx in sorted(used_bass) if base_strings <= idx < total_strings
    )
    display_strings = len(display_indices)
    tuning_labels = _tuning_labels(
        tuning_text,
        total_strings,
        show_octaves=show_octaves,
        bass=bass_tokens or None if used_bass else None,
    )
    basslabels = settings.get("basslabels", "tuning")
    block_h = _block_height(
        include_meta,
        display_strings,
        show_dur,
        show_extras,
        show_tactus,
        double_stems,
    )
    available = max(0, height - 2 - 1)
    systems = max(1, available // block_h)
    max_chords = 0
    max_chords_text = settings.get("maxchords", "")
    if max_chords_text.isdigit():
        max_chords = int(max_chords_text)
    if spacing_mode == "auto":
        bars_per_line_limit = 0
    else:
        bars_per_line_limit = max(1, usable_width // (bar_width + bar_gap))
    barsperline = settings.get("barsperline", "")
    if barsperline.isdigit():
        limit = int(barsperline)
        if limit > 0:
            bars_per_line_limit = limit
    maxbars = settings.get("maxbars", "")
    if maxbars.isdigit():
        limit = int(maxbars)
        if limit > 0:
            bars_per_line_limit = (
                limit
                if bars_per_line_limit <= 0
                else min(bars_per_line_limit, limit)
            )

    render_systems(
        stdscr,
        piece=piece,
        width=width,
        header_row=header_row,
        left_margin=left_margin,
        block_h=block_h,
        systems=systems,
        total_strings=total_strings,
        display_indices=display_indices,
        display_strings=display_strings,
        bar_offset=bar_offset,
        cursor_bar=cursor_bar,
        cursor_string=cursor_string,
        cursor_col=cursor_col,
        bar_width=bar_width,
        overrides=overrides,
        durations=durations,
        ornaments=ornaments,
        annotations=annotations,
        highlights=highlights,
        dotted=dotted,
        slurs=slurs,
        ties=ties,
        holds=holds,
        settings=settings,
        stave_breaks=stave_breaks,
        playback_bar=playback_bar,
        playback_col=playback_col,
        include_meta=include_meta,
        show_dur=show_dur,
        show_extras=show_extras,
        show_tactus=show_tactus,
        hide_redundant=hide_redundant,
        double_stems=double_stems,
        reverse_strings=reverse_strings,
        max_chords=max_chords,
        spacing_mode=spacing_mode,
        spacing_fill=spacing_fill,
        bar_gap=bar_gap,
        barpad=barpad,
        usable_width=usable_width,
        bars_per_line_limit=bars_per_line_limit,
        default_duration=default_duration,
        tuning_labels=tuning_labels,
        basslabels=basslabels,
    )

    if display_strings > 0:
        cursor_index = min(cursor_string, display_strings - 1)
        if reverse_strings:
            actual_cursor_string = display_indices[display_strings - 1 - cursor_index]
        else:
            actual_cursor_string = display_indices[cursor_index]
    else:
        actual_cursor_string = cursor_string
    dur_text = resolve_duration_text(
        piece=piece,
        durations=durations,
        dotted=dotted,
        cursor_bar=cursor_bar,
        cursor_col=cursor_col,
        actual_cursor_string=actual_cursor_string,
        bar_width=bar_width,
        default_duration=default_duration,
    )
    status, status_line_text = build_status_lines(
        mode=mode,
        cmdline=cmdline,
        searchline=searchline,
        message=message,
        status_line=status_line,
        dur_text=dur_text,
    )
    _safe_addstr(stdscr, height - 1, 0, _clean_text(status), status_attr)
    _safe_addstr(stdscr, height - 2, 0, _clean_text(status_line_text), status_attr)

    if mode == "help":
        stdscr.erase()
        _render_help(stdscr, status, status_attr, help_offset)

    stdscr.refresh()
