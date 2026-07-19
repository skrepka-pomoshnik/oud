from __future__ import annotations

from petrucci.render_geometry import _scale_chord_row
from petrucci.render_helpers import pad_row, safe_addstr
from petrucci.render_marks import _overlay_inline_local_marks_on_display_row
from petrucci.render_playback import PlaybackOverlayCache, _playback_overlay_ops_for_bar
from petrucci.render_text_lanes import (
    draw_melody_key_signature,
    draw_melody_time_signature,
    melody_key_signature_width,
)
from petrucci.render_vocal import (
    lyric_rows_for_bar,
    melody_rows_for_bar,
    vocal_onset_cols_for_bar,
)
from petrucci.screen import A_BOLD, A_REVERSE, Screen
from petrucci.tab_policy import time_sig_inline_rows
from petrucci.view_model import _inline_bass_row, _scale_col


def _render_staff_and_playback(  # noqa: C901, PLR0912
    stdscr: Screen,
    *,
    piece,
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
    cursor_display_maps: dict[int, list[int]] | None,
    cursor_string: int,
    display_width: int,
    draw_pad: int,
    effective_playback_markers: list[tuple[int, int]],
    grid_map: list[int],
    grid_width: int,
    highlights: set[tuple[int, int, int]],
    lyric_row_offsets: tuple[int, ...],
    melody_rows_count: int,
    orn_cells: list[str],
    orn_target_rows: list[int],
    pad: int,
    playback_cache: PlaybackOverlayCache | None,
    positions: list[tuple[int, int, bool]],
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
    text_onset_cols: list[int],
    time_value: str,
    tuning_pitches: list[int],
    width: int,
) -> None:
    if cursor_display_maps is not None and grid_map:
        if bar.chords:
            cursor_display_maps[abs_bar] = [
                grid_map[min(len(grid_map) - 1, _scale_col(col, bar_width, grid_width))] for col in range(bar_width)
            ]
        else:
            cursor_display_maps[abs_bar] = [grid_map[min(len(grid_map) - 1, col)] for col in range(bar_width)]
    cursor_display_index = cursor_string if cursor_string < system_display_strings else None
    rendered_staff_rows: list[str] = []
    for display_idx in range(system_display_strings):
        actual = system_visual_indices[display_idx]
        y = row_start + (rows["staff"] or 0) + display_idx
        row_cells = cells[actual]
        fill_char = "-"
        if actual >= 6:
            row_cells = _inline_bass_row(row_cells)
            fill_char = " "
        if scale_bar:
            content_width = max(1, display_width - draw_pad * 2)
            if bar.chords:
                row_cells = _scale_chord_row(
                    row_cells,
                    fill_char=fill_char,
                    src_to_dest=src_to_dest,
                    bar_width=grid_width,
                    content_width=content_width,
                )
            else:
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
        row_text = "".join(row_cells)
        safe_addstr(stdscr, y, bar_x - 1, "|")
        if repeat_left and display_idx in repeat_rows:
            safe_addstr(stdscr, y, bar_x - 1, ":")
        safe_addstr(stdscr, y, bar_x, row_text)
        if show_time_sig_here and sig_label:
            ts_rows = time_sig_inline_rows(
                time_value,
                sig_label,
                style_mode=settings.get("timesigstyle", "symbol"),
            )
            ts_top = 0
            if ts_rows:
                ts_top = max(0, (system_display_strings - len(ts_rows)) // 2)
            if ts_top <= display_idx < (ts_top + len(ts_rows)):
                # Draw inside the first bar (auftact area), not over left labels.
                ts_text = ts_rows[display_idx - ts_top]
                # Anchor the cue at the beginning of the reserved auftact pad.
                # This leaves whitespace after the cue before the first note.
                ts_x = min(width - 2, bar_x + barpad)
                safe_addstr(stdscr, y, ts_x, ts_text)
        barline_x = min(max(0, width - 2), bar_x + display_width)
        if fill_char == "-" and row_cells and barline_x == (width - 2) and not bar.chords:
            # Guarantee one visible dash before the actually drawn right barline.
            edge_idx = barline_x - 1 - bar_x
            if 0 <= edge_idx < len(row_cells) and row_cells[edge_idx] not in ("-", " "):
                move_to = edge_idx - 1
                while move_to >= 0 and row_cells[move_to] not in ("-", " "):
                    move_to -= 1
                if move_to >= 0:
                    row_cells[move_to] = row_cells[edge_idx]
                    row_cells[edge_idx] = "-"
                    row_text = "".join(row_cells)
                    safe_addstr(stdscr, y, bar_x, row_text)
        safe_addstr(stdscr, y, barline_x, barline)
        if repeat_right and display_idx in repeat_rows:
            safe_addstr(stdscr, y, barline_x, ":")
        rendered_staff_rows.append(row_text)

        if (
            abs_bar == cursor_bar
            and cursor_display_index is not None
            and display_idx == cursor_display_index
            and 0 <= cursor_col < bar_width
        ):
            content_width = max(1, display_width - draw_pad * 2)
            if bar.chords:
                cursor_grid_col = _scale_col(cursor_col, bar_width, grid_width)
                scaled_cursor_col = grid_map[cursor_grid_col]
            else:
                scaled_cursor_col = grid_map[cursor_col]
            cell_x = bar_x + draw_pad + scaled_cursor_col
            cell_idx = draw_pad + scaled_cursor_col
            if not (0 <= cell_idx < len(row_text)):
                continue
            safe_addstr(
                stdscr,
                y,
                cell_x,
                row_text[cell_idx],
                A_REVERSE,
            )
        for col in range(bar_width):
            if (abs_bar, actual, col) in highlights:
                content_width = max(1, display_width - pad * 2)
                if bar.chords:
                    highlight_grid_col = _scale_col(col, bar_width, grid_width)
                    scaled_hl_col = grid_map[highlight_grid_col]
                else:
                    scaled_hl_col = grid_map[col]
                hl_x = bar_x + draw_pad + scaled_hl_col
                safe_addstr(
                    stdscr,
                    y,
                    hl_x,
                    row_text[draw_pad + scaled_hl_col],
                    A_BOLD,
                )

        playback_vocal_onset_cols: list[int] = []
        melody_row_base: int | None = None
        rendered_melody_rows: list[str] | None = None
        vocal_left_pad = draw_pad
        melody_key_pad = 0
        if abs_bar == 0 and (bar.time_sig or settings.get("time", "")):
            vocal_left_pad += 2
        if abs_bar == 0:
            melody_key_pad = melody_key_signature_width(piece.key)
            vocal_left_pad += melody_key_pad
        if rows.get("melody") is not None:
            melody_row_base = row_start + (rows["melody"] or 0)
            playback_vocal_onset_cols = vocal_onset_cols_for_bar(
                bar,
                onset_cols=text_onset_cols,
                width=display_width,
                left_pad=vocal_left_pad,
            )
            melody_rows = melody_rows_for_bar(
                bar,
                onset_cols=playback_vocal_onset_cols,
                width=display_width,
                left_pad=vocal_left_pad,
                tuning_pitches=tuning_pitches,
            )
            if abs_bar == 0 and melody_rows:
                draw_melody_time_signature(
                    melody_rows,
                    time_sig=bar.time_sig or settings.get("time", ""),
                    left_pad=max(0, vocal_left_pad - melody_key_pad),
                )
                draw_melody_key_signature(
                    melody_rows,
                    key=piece.key,
                    left_pad=max(0, vocal_left_pad - melody_key_pad + 2),
                )
            rendered_melody_rows = ["".join(row) for row in melody_rows]
            for melody_row_idx, melody_cells in enumerate(melody_rows[:melody_rows_count]):
                y = melody_row_base + melody_row_idx
                row_text = "".join(melody_cells)
                if row_text.strip():
                    safe_addstr(stdscr, y, bar_x - 1, "|")
                safe_addstr(stdscr, y, bar_x, "".join(melody_cells))
                if row_text.strip():
                    safe_addstr(
                        stdscr,
                        y,
                        min(max(0, width - 2), bar_x + display_width),
                        barline,
                    )
    if lyric_row_offsets:
        vocal_onset_cols = vocal_onset_cols_for_bar(
            bar,
            onset_cols=text_onset_cols,
            width=display_width,
            left_pad=vocal_left_pad,
        )
        lyric_rows = lyric_rows_for_bar(
            bar,
            onset_cols=vocal_onset_cols,
            width=display_width,
            left_pad=vocal_left_pad,
            lyric_rows_count=len(lyric_row_offsets),
        )
        for lyric_idx, lyric_row in enumerate(lyric_row_offsets):
            lyric_cells = lyric_rows[lyric_idx] if lyric_idx < len(lyric_rows) else [" "] * display_width
            safe_addstr(stdscr, row_start + lyric_row, bar_x - 1, "|")
            safe_addstr(stdscr, row_start + lyric_row, bar_x, "".join(lyric_cells))
            safe_addstr(
                stdscr,
                row_start + lyric_row,
                min(max(0, width - 2), bar_x + display_width),
                barline,
            )

    if playback_cache is not None:
        playback_limit = len(bar.chords) if bar.chords else bar_width
        for overlay_col in range(max(0, playback_limit)):
            playback_cache[(abs_bar, overlay_col)] = _playback_overlay_ops_for_bar(
                bar=bar,
                playback_col=overlay_col,
                bar_width=bar_width,
                grid_width=grid_width,
                positions=positions,
                src_to_dest=src_to_dest,
                draw_pad=draw_pad,
                display_width=display_width,
                row_start=row_start,
                rows=rows,
                system_display_strings=system_display_strings,
                system_visual_indices=system_visual_indices,
                rendered_staff_rows=rendered_staff_rows,
                bar_x=bar_x,
                tuning_pitches=tuning_pitches,
                melody_row_base=melody_row_base,
                vocal_onset_cols=playback_vocal_onset_cols,
                rendered_melody_rows=rendered_melody_rows,
            )
    playback_cols = [marker_col for marker_bar, marker_col in effective_playback_markers if marker_bar == abs_bar]
    for marker_col in playback_cols:
        playback_ops = _playback_overlay_ops_for_bar(
            bar=bar,
            playback_col=marker_col,
            bar_width=bar_width,
            grid_width=grid_width,
            positions=positions,
            src_to_dest=src_to_dest,
            draw_pad=draw_pad,
            display_width=display_width,
            row_start=row_start,
            rows=rows,
            system_display_strings=system_display_strings,
            system_visual_indices=system_visual_indices,
            rendered_staff_rows=rendered_staff_rows,
            bar_x=bar_x,
            tuning_pitches=tuning_pitches,
            melody_row_base=melody_row_base,
            vocal_onset_cols=playback_vocal_onset_cols,
            rendered_melody_rows=rendered_melody_rows,
        )
        for y, x, text, attr in playback_ops:
            safe_addstr(stdscr, y, x, text, attr)
