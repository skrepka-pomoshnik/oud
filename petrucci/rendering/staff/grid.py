from __future__ import annotations

from petrucci.input.tablature.policy import time_sig_inline_rows
from petrucci.rendering.primitives.geometry import _scale_chord_row
from petrucci.rendering.primitives.helpers import pad_row, safe_addstr
from petrucci.rendering.primitives.marks import _overlay_inline_local_marks_on_display_row
from petrucci.terminal.canvas.screen import A_BOLD, A_REVERSE, Screen
from petrucci.terminal.view.model import _inline_bass_row, _scale_col


def record_cursor_display_map(
    cursor_display_maps: dict[int, list[int]] | None,
    *,
    bar,
    abs_bar: int,
    bar_width: int,
    grid_width: int,
    grid_map: list[int],
) -> None:
    if cursor_display_maps is None or not grid_map:
        return
    if bar.chords:
        source_columns = (_scale_col(column, bar_width, grid_width) for column in range(bar_width))
    else:
        source_columns = iter(range(bar_width))
    cursor_display_maps[abs_bar] = [grid_map[min(len(grid_map) - 1, column)] for column in source_columns]


def render_staff_grid(
    stdscr: Screen,
    *,
    bar,
    abs_bar: int,
    ann_cells: list[str],
    ann_target_rows: list[int],
    bar_width: int,
    bar_x: int,
    barline: str,
    barpad: int,
    cells: list[list[str]],
    cursor_bar: int,
    cursor_col: int,
    cursor_string: int,
    display_width: int,
    draw_pad: int,
    grid_map: list[int],
    grid_width: int,
    highlights: set[tuple[int, int, int]],
    orn_cells: list[str],
    orn_target_rows: list[int],
    repeat_left: bool,
    repeat_right: bool,
    repeat_rows: set[int],
    row_start: int,
    rows: dict[str, int | None],
    scale_bar: bool,
    settings: dict[str, str],
    show_time_sig_here: bool,
    sig_label: str,
    src_to_dest: dict[int, int],
    style: str,
    system_display_strings: int,
    system_visual_indices: list[int],
    time_value: str,
    width: int,
) -> list[str]:
    rendered: list[str] = []
    cursor_display_index = cursor_string if cursor_string < system_display_strings else None
    for display_idx, actual in enumerate(system_visual_indices[:system_display_strings]):
        row_cells, fill_char = _staff_row_cells(
            bar=bar,
            actual=actual,
            cells=cells,
            ann_cells=ann_cells,
            ann_target_rows=ann_target_rows,
            orn_cells=orn_cells,
            orn_target_rows=orn_target_rows,
            display_width=display_width,
            draw_pad=draw_pad,
            grid_map=grid_map,
            grid_width=grid_width,
            scale_bar=scale_bar,
            src_to_dest=src_to_dest,
            style=style,
        )
        y = row_start + (rows["staff"] or 0) + display_idx
        row_text = _draw_staff_row(
            stdscr,
            bar=bar,
            bar_x=bar_x,
            barline=barline,
            barpad=barpad,
            display_idx=display_idx,
            display_width=display_width,
            fill_char=fill_char,
            repeat_left=repeat_left,
            repeat_right=repeat_right,
            repeat_rows=repeat_rows,
            row_cells=row_cells,
            settings=settings,
            show_time_sig_here=show_time_sig_here,
            sig_label=sig_label,
            system_display_strings=system_display_strings,
            time_value=time_value,
            width=width,
            y=y,
        )
        rendered.append(row_text)
        _draw_cursor(
            stdscr,
            bar=bar,
            abs_bar=abs_bar,
            bar_width=bar_width,
            bar_x=bar_x,
            cursor_bar=cursor_bar,
            cursor_col=cursor_col,
            cursor_display_index=cursor_display_index,
            display_idx=display_idx,
            draw_pad=draw_pad,
            grid_map=grid_map,
            grid_width=grid_width,
            row_text=row_text,
            y=y,
        )
        _draw_highlights(
            stdscr,
            bar=bar,
            abs_bar=abs_bar,
            actual=actual,
            bar_width=bar_width,
            bar_x=bar_x,
            draw_pad=draw_pad,
            grid_map=grid_map,
            grid_width=grid_width,
            highlights=highlights,
            row_text=row_text,
            y=y,
        )
    return rendered


def _staff_row_cells(
    *,
    bar,
    actual: int,
    cells: list[list[str]],
    ann_cells: list[str],
    ann_target_rows: list[int],
    orn_cells: list[str],
    orn_target_rows: list[int],
    display_width: int,
    draw_pad: int,
    grid_map: list[int],
    grid_width: int,
    scale_bar: bool,
    src_to_dest: dict[int, int],
    style: str,
) -> tuple[list[str], str]:
    source_cells = cells[actual]
    fill_char = "-"
    bass_course_start = 6
    if actual >= bass_course_start:
        source_cells = _inline_bass_row(source_cells)
        fill_char = " "
    row_cells = source_cells
    if scale_bar:
        content_width = max(1, display_width - draw_pad * 2)
        row_cells = _scale_chord_row(
            row_cells,
            fill_char=fill_char,
            src_to_dest=src_to_dest,
            bar_width=grid_width,
            content_width=content_width,
        )
        row_cells = pad_row(row_cells, display_width, draw_pad, pad_char=fill_char)
    elif draw_pad:
        row_cells = pad_row(row_cells, display_width, draw_pad, pad_char=fill_char)
    if bar.chords:
        _overlay_inline_local_marks_on_display_row(
            display_row_cells=row_cells,
            source_row_cells=cells[actual],
            ann_cells=ann_cells,
            orn_cells=orn_cells,
            draw_pad=draw_pad,
            grid_map=src_to_dest if scale_bar else grid_map,
            style=style,
            source_row_index=actual,
            ann_target_rows=ann_target_rows,
            orn_target_rows=orn_target_rows,
        )
    return row_cells, fill_char


def _draw_staff_row(
    stdscr: Screen,
    *,
    bar,
    bar_x: int,
    barline: str,
    barpad: int,
    display_idx: int,
    display_width: int,
    fill_char: str,
    repeat_left: bool,
    repeat_right: bool,
    repeat_rows: set[int],
    row_cells: list[str],
    settings: dict[str, str],
    show_time_sig_here: bool,
    sig_label: str,
    system_display_strings: int,
    time_value: str,
    width: int,
    y: int,
) -> str:
    safe_addstr(stdscr, y, bar_x - 1, ":" if repeat_left and display_idx in repeat_rows else "|")
    row_text = "".join(row_cells)
    safe_addstr(stdscr, y, bar_x, row_text)
    _draw_time_signature(
        stdscr,
        bar_x=bar_x,
        barpad=barpad,
        display_idx=display_idx,
        settings=settings,
        show=show_time_sig_here,
        sig_label=sig_label,
        system_display_strings=system_display_strings,
        time_value=time_value,
        width=width,
        y=y,
    )
    barline_x = min(max(0, width - 2), bar_x + display_width)
    row_text = _ensure_edge_dash(
        stdscr,
        bar=bar,
        bar_x=bar_x,
        barline_x=barline_x,
        fill_char=fill_char,
        row_cells=row_cells,
        row_text=row_text,
        width=width,
        y=y,
    )
    safe_addstr(stdscr, y, barline_x, barline)
    if repeat_right and display_idx in repeat_rows:
        safe_addstr(stdscr, y, barline_x, ":")
    return row_text


def _draw_time_signature(
    stdscr: Screen,
    *,
    bar_x: int,
    barpad: int,
    display_idx: int,
    settings: dict[str, str],
    show: bool,
    sig_label: str,
    system_display_strings: int,
    time_value: str,
    width: int,
    y: int,
) -> None:
    if not show or not sig_label:
        return
    ts_rows = time_sig_inline_rows(time_value, sig_label, style_mode=settings.get("timesigstyle", "symbol"))
    ts_top = max(0, (system_display_strings - len(ts_rows)) // 2) if ts_rows else 0
    if ts_top <= display_idx < ts_top + len(ts_rows):
        safe_addstr(stdscr, y, min(width - 2, bar_x + barpad), ts_rows[display_idx - ts_top])


def _ensure_edge_dash(
    stdscr: Screen,
    *,
    bar,
    bar_x: int,
    barline_x: int,
    fill_char: str,
    row_cells: list[str],
    row_text: str,
    width: int,
    y: int,
) -> str:
    edge_idx = barline_x - 1 - bar_x
    if fill_char != "-" or not row_cells or barline_x != width - 2 or bar.chords:
        return row_text
    if not (0 <= edge_idx < len(row_cells)) or row_cells[edge_idx] in ("-", " "):
        return row_text
    move_to = edge_idx - 1
    while move_to >= 0 and row_cells[move_to] not in ("-", " "):
        move_to -= 1
    if move_to < 0:
        return row_text
    row_cells[move_to] = row_cells[edge_idx]
    row_cells[edge_idx] = "-"
    row_text = "".join(row_cells)
    safe_addstr(stdscr, y, bar_x, row_text)
    return row_text


def _draw_cursor(
    stdscr: Screen,
    *,
    bar,
    abs_bar: int,
    bar_width: int,
    bar_x: int,
    cursor_bar: int,
    cursor_col: int,
    cursor_display_index: int | None,
    display_idx: int,
    draw_pad: int,
    grid_map: list[int],
    grid_width: int,
    row_text: str,
    y: int,
) -> None:
    if abs_bar != cursor_bar or display_idx != cursor_display_index or not (0 <= cursor_col < bar_width):
        return
    source_col = _scale_col(cursor_col, bar_width, grid_width) if bar.chords else cursor_col
    scaled_col = grid_map[source_col]
    cell_idx = draw_pad + scaled_col
    if 0 <= cell_idx < len(row_text):
        safe_addstr(stdscr, y, bar_x + cell_idx, row_text[cell_idx], A_REVERSE)


def _draw_highlights(
    stdscr: Screen,
    *,
    bar,
    abs_bar: int,
    actual: int,
    bar_width: int,
    bar_x: int,
    draw_pad: int,
    grid_map: list[int],
    grid_width: int,
    highlights: set[tuple[int, int, int]],
    row_text: str,
    y: int,
) -> None:
    for column in range(bar_width):
        if (abs_bar, actual, column) not in highlights:
            continue
        source_col = _scale_col(column, bar_width, grid_width) if bar.chords else column
        display_col = draw_pad + grid_map[source_col]
        safe_addstr(stdscr, y, bar_x + display_col, row_text[display_col], A_BOLD)
