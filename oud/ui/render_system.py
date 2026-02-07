from __future__ import annotations

from oud.core.render_utils import spread_flag_positions
from oud.core.view_model import (
    _bar_annotations,
    _bar_compact_width,
    _bar_display_width,
    _bar_durations,
    _bar_number_for_index,
    _bar_ornaments,
    _bar_span_row,
    _bars_fit,
    _filter_redundant_positions,
    _flag_positions_all,
    _infer_time_signature,
    _inline_bass_row,
    _next_system_start,
    _parse_time_signature,
    _scale_col,
    _scale_row,
    _string_label,
    _tactus_row,
    bar_cells,
    bar_cells_from_chords,
    chord_positions,
    duration_display,
    flag_positions_from_durations,
)
from oud.ui.adapter import A_BOLD, A_REVERSE, Screen
from oud.ui.layout_map import layout_block_rows as _layout_block_rows
from oud.ui.render_bar import build_flag_rows
from oud.ui.render_helpers import apply_overrides, pad_row, safe_addstr


def _build_chord_scale_map(
    positions: list[tuple[int, int, bool]],
    bar_width: int,
    content_width: int,
) -> tuple[list[tuple[int, int, bool]], dict[int, int]]:
    scaled_positions = [
        (_scale_col(pos, bar_width, content_width), denom, dot)
        for (pos, denom, dot) in positions
    ]
    spread_positions = spread_flag_positions(scaled_positions, content_width, min_gap=1)
    cols = [col for (col, _denom, _dot) in spread_positions]
    reqs: list[int] = []
    for idx in range(1, len(spread_positions)):
        prev = spread_positions[idx - 1]
        curr = spread_positions[idx]
        same_group = prev[1] == curr[1] and prev[2] == curr[2]
        reqs.append(1 if same_group else 2)
    for idx, req in enumerate(reqs, start=1):
        min_col = cols[idx - 1] + req
        cols[idx] = max(cols[idx], min_col)
    max_col = content_width - 1
    for idx in range(len(cols) - 1, -1, -1):
        cols[idx] = min(cols[idx], max_col)
        if idx > 0:
            req = reqs[idx - 1]
            prev_max = cols[idx] - req
            cols[idx - 1] = min(cols[idx - 1], prev_max)
    for idx, req in enumerate(reqs, start=1):
        min_col = cols[idx - 1] + req
        cols[idx] = max(cols[idx], min_col)
    for idx in range(len(cols)):
        cols[idx] = max(cols[idx], 0)

    spread_positions = [
        (cols[idx], denom, dot)
        for idx, (_col, denom, dot) in enumerate(spread_positions)
    ]
    ordered_raw = sorted(positions, key=lambda item: item[0])
    src_to_dest = {
        raw_col: scaled_col
        for (raw_col, _raw_denom, _raw_dot), (scaled_col, _denom, _dot) in zip(
            ordered_raw, spread_positions, strict=False,
        )
    }
    return spread_positions, src_to_dest


def _scale_chord_row(
    row_cells: list[str],
    *,
    fill_char: str,
    src_to_dest: dict[int, int],
    bar_width: int,
    content_width: int,
) -> list[str]:
    scaled = [fill_char for _ in range(content_width)]
    for src_col, ch in enumerate(row_cells[:bar_width]):
        if ch == fill_char:
            continue
        dest_col = src_to_dest.get(src_col, _scale_col(src_col, bar_width, content_width))
        if 0 <= dest_col < content_width:
            scaled[dest_col] = ch
    return scaled


def render_systems(  # noqa: C901, PLR0912
    stdscr: Screen,
    *,
    piece,
    width: int,
    header_row: int,
    left_margin: int,
    block_h: int,
    systems: int,
    total_strings: int,
    display_indices: list[int],
    display_strings: int,
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
    settings: dict[str, str],
    stave_breaks: set[int],
    playback_bar: int | None,
    playback_col: int | None,
    include_meta: bool,
    show_dur: bool,
    show_extras: bool,
    show_tactus: bool,
    hide_redundant: bool,
    double_stems: bool,
    reverse_strings: bool,
    max_chords: int,
    spacing_mode: str,
    spacing_fill: str,
    bar_gap: int,
    barpad: int,
    usable_width: int,
    bars_per_line_limit: int,
    default_duration: int,
    tuning_labels: list[str],
    basslabels: str,
) -> None:
    total_bars = len(piece.bars)
    current_bar_start = bar_offset
    for sys_idx in range(systems):
        row_start = header_row + 1 + sys_idx * block_h
        rows = _layout_block_rows(
            display_strings,
            include_meta,
            show_dur,
            show_extras,
            show_tactus,
            double_stems,
        )
        # Clear the system block to avoid stale characters after reflow/resizes.
        for clear_row in range(row_start, row_start + block_h):
            safe_addstr(stdscr, clear_row, 0, " " * width)
        bar_start = current_bar_start
        if bar_start >= total_bars:
            break
        if spacing_mode == "auto":
            bars_per_line = _bars_fit(
                piece.bars,
                bar_start,
                bar_gap,
                usable_width,
                bar_width,
                overrides,
                durations,
                default_duration,
                dotted,
                max_chords=max_chords,
                compact=spacing_fill in ("compact", "smart"),
            )
        else:
            bars_per_line = bars_per_line_limit
        if bars_per_line_limit > 0:
            bars_per_line = min(bars_per_line, bars_per_line_limit)
        bars_per_line = max(1, bars_per_line)
        bar_end = _next_system_start(piece.bars, bar_start, bars_per_line, stave_breaks)
        bar_end = min(total_bars, bar_end)
        bar_indices = list(range(bar_start, bar_end))
        bar_widths: list[int] = []
        if spacing_mode == "auto":
            bar_widths.extend(
                _bar_compact_width(
                    piece.bars[abs_bar],
                    abs_bar,
                    bar_width,
                    overrides,
                    durations,
                    default_duration,
                    dotted,
                )
                if spacing_fill in ("compact", "smart")
                else _bar_display_width(
                    piece.bars[abs_bar],
                    abs_bar,
                    bar_width,
                    overrides,
                    durations,
                    default_duration,
                    dotted,
                )
                for abs_bar in bar_indices
            )

            def total_bar_width(widths: list[int]) -> int:
                return sum(widths) + bar_gap * max(0, len(widths) - 1)

            total_width = total_bar_width(bar_widths)
            while bar_widths and total_width > usable_width:
                bar_widths.pop()
                bar_indices = bar_indices[: len(bar_widths)]
                total_width = total_bar_width(bar_widths)
            bar_end = bar_start + len(bar_widths)
            total_width = total_bar_width(bar_widths)
            if bar_widths and spacing_fill == "stretch" and total_width < usable_width:
                extra = usable_width - total_width
                idx = 0
                while extra > 0 and bar_widths:
                    bar_widths[idx] += 1
                    extra -= 1
                    idx = (idx + 1) % len(bar_widths)
        for display_idx in range(display_strings):
            label = "  "
            if sys_idx == 0:
                if reverse_strings:
                    actual = display_indices[display_strings - 1 - display_idx]
                else:
                    actual = display_indices[display_idx]
                label = _string_label(actual, total_strings, tuning_labels, basslabels)
            safe_addstr(stdscr, row_start + (rows["staff"] or 0) + display_idx, 0, label)

        bar_x = left_margin
        gap_sizes: list[int] | None = None
        if spacing_mode == "auto" and bar_widths:
            total_width = sum(bar_widths) + bar_gap * max(0, len(bar_widths) - 1)
            if spacing_fill == "center":
                extra_left = max(0, (usable_width - total_width) // 2)
                bar_x += extra_left
            elif spacing_fill == "smart":
                gaps = max(0, len(bar_widths) - 1)
                gap_sizes = [bar_gap for _ in range(gaps)]
        for local_idx, bar in enumerate(piece.bars[bar_start:bar_end]):
            abs_bar = bar_start + local_idx
            style = settings.get("style", "french")
            french_c = settings.get("frenchc", "normal")
            french_e = settings.get("frenche", "normal")
            cells = (
                bar_cells_from_chords(
                    bar,
                    total_strings,
                    bar_width,
                    default_duration,
                    style,
                    french_c=french_c,
                    french_e=french_e,
                )
                if bar.chords
                else bar_cells(
                    bar,
                    total_strings,
                    bar_width,
                    style,
                    french_c=french_c,
                    french_e=french_e,
                )
            )
            measures = settings.get("measures", "start")
            countdots = settings.get("countdots", "off")
            step_value = 1
            step_text = settings.get("measuresstep", "1")
            if step_text.isdigit():
                step_value = max(1, int(step_text))
            number = _bar_number_for_index(
                piece,
                abs_bar,
                measures,
                countdots,
                step_value,
            )
            time_setting = settings.get("time", "C")
            time_value = bar.time_sig or time_setting
            if time_value in ("auto", "detect"):
                inferred = _infer_time_signature(bar, default_duration)
                time_value = inferred or "C"
            beats, _unit, _sig_label = _parse_time_signature(time_value)
            tactus = _tactus_row(bar_width, beats)
            barline = bar.barline or "|"
            repeat = bar.repeat or ""
            ann_cells = _bar_annotations(annotations, abs_bar, bar_width)
            orn_cells = _bar_ornaments(ornaments, abs_bar, bar_width)
            slur_cells = _bar_span_row(slurs, abs_bar, bar_width, "(", ")", "~")
            tie_cells = _bar_span_row(ties, abs_bar, bar_width, "[", "]", "-")
            hold_cells = _bar_span_row(holds, abs_bar, bar_width, "<", ">", "_")
            apply_overrides(cells, overrides, abs_bar, total_strings, bar_width)
            display_width = bar_width
            if spacing_mode == "auto":
                display_width = bar_widths[local_idx]
            if rows["meta"] is not None:
                meta_row = row_start + (rows["meta"] or 0)
                safe_addstr(stdscr, meta_row, bar_x - 2, repeat)
                if abs_bar == 0:
                    safe_addstr(stdscr, meta_row, 0, " ")
                if number is not None:
                    safe_addstr(stdscr, meta_row, bar_x, number)
            if rows["ann"] is not None:
                ann_row = ann_cells
                if spacing_mode == "auto":
                    content_width = max(1, display_width - barpad * 2)
                    ann_row = _scale_row(ann_cells, content_width, " ")
                    ann_row = pad_row(ann_row, display_width, barpad)
                safe_addstr(stdscr, row_start + (rows["ann"] or 0), bar_x, "".join(ann_row))
            if rows["orn"] is not None:
                orn_row = orn_cells
                if spacing_mode == "auto":
                    content_width = max(1, display_width - barpad * 2)
                    orn_row = _scale_row(orn_cells, content_width, " ")
                    orn_row = pad_row(orn_row, display_width, barpad)
                safe_addstr(stdscr, row_start + (rows["orn"] or 0), bar_x, "".join(orn_row))
            if rows["tactus"] is not None:
                tactus_row = tactus
                if spacing_mode == "auto":
                    content_width = max(1, display_width - barpad * 2)
                    tactus_row = _scale_row(tactus, content_width, " ")
                    tactus_row = pad_row(tactus_row, display_width, barpad)
                safe_addstr(stdscr, row_start + (rows["tactus"] or 0), bar_x, "".join(tactus_row))
            if rows["slur"] is not None:
                slur_row = slur_cells
                if spacing_mode == "auto":
                    content_width = max(1, display_width - barpad * 2)
                    slur_row = _scale_row(slur_cells, content_width, " ")
                    slur_row = pad_row(slur_row, display_width, barpad)
                safe_addstr(stdscr, row_start + (rows["slur"] or 0), bar_x, "".join(slur_row))
            if rows["tie"] is not None:
                tie_row = tie_cells
                if spacing_mode == "auto":
                    content_width = max(1, display_width - barpad * 2)
                    tie_row = _scale_row(tie_cells, content_width, " ")
                    tie_row = pad_row(tie_row, display_width, barpad)
                safe_addstr(stdscr, row_start + (rows["tie"] or 0), bar_x, "".join(tie_row))
            if rows["hold"] is not None:
                hold_row = hold_cells
                if spacing_mode == "auto":
                    content_width = max(1, display_width - barpad * 2)
                    hold_row = _scale_row(hold_cells, content_width, " ")
                    hold_row = pad_row(hold_row, display_width, barpad)
                safe_addstr(stdscr, row_start + (rows["hold"] or 0), bar_x, "".join(hold_row))
            if bar.chords:
                positions = chord_positions(bar, bar_width, default_duration)
                flag_positions = (
                    _filter_redundant_positions(positions) if hide_redundant else positions
                )
                flagstyle = settings.get("flagstyle", "standard")
                if spacing_mode == "auto":
                    content_width = max(1, display_width - barpad * 2)
                    _, src_to_dest = _build_chord_scale_map(
                        positions,
                        bar_width,
                        content_width,
                    )
                    render_positions = [
                        (src_to_dest.get(col, 0), denom, dot)
                        for (col, denom, dot) in flag_positions
                    ]
                    flag_cells, stem_cells = build_flag_rows(
                        render_positions,
                        spacing_mode="fixed",
                        display_width=content_width,
                        bar_width=content_width,
                        barpad=0,
                        flagstyle=flagstyle,
                    )
                    flag_cells = pad_row(flag_cells, display_width, barpad)
                    stem_cells = pad_row(stem_cells, display_width, barpad)
                else:
                    src_to_dest = {}
                    flag_cells, stem_cells = build_flag_rows(
                        flag_positions,
                        spacing_mode=spacing_mode,
                        display_width=display_width,
                        bar_width=bar_width,
                        barpad=barpad,
                        flagstyle=flagstyle,
                    )
                safe_addstr(stdscr, row_start + (rows["flag"] or 0), bar_x, "".join(flag_cells))
                if (
                    playback_bar is not None
                    and playback_col is not None
                    and abs_bar == playback_bar
                    and 0 <= playback_col < bar_width
                ):
                    content_width = max(1, display_width - barpad * 2)
                    pcol = src_to_dest.get(
                        playback_col,
                        _scale_col(playback_col, bar_width, content_width),
                    )
                    safe_addstr(
                        stdscr,
                        row_start + (rows["flag"] or 0),
                        bar_x + barpad + pcol,
                        flag_cells[barpad + pcol],
                        A_BOLD,
                    )
                if rows.get("flag2") is not None:
                    safe_addstr(
                        stdscr,
                        row_start + (rows["flag2"] or 0),
                        bar_x,
                        "".join(stem_cells),
                    )
                if show_dur and rows["dur"] is not None:
                    content_width = max(1, display_width - barpad * 2)
                    if spacing_mode == "auto":
                        dur_cells = [" " for _ in range(content_width)]
                        for col, denom, dot in flag_positions:
                            target_col = src_to_dest.get(
                                col,
                                _scale_col(col, bar_width, content_width),
                            )
                            for idx, ch in enumerate(duration_display(denom, dot)):
                                pos = target_col + idx
                                if 0 <= pos < content_width and dur_cells[pos] == " ":
                                    dur_cells[pos] = ch
                        dur_cells = pad_row(dur_cells, display_width, barpad)
                    else:
                        dur_cells = [" " for _ in range(bar_width)]
                        for col, denom, dot in flag_positions:
                            for idx, ch in enumerate(duration_display(denom, dot)):
                                pos = col + idx
                                if 0 <= pos < bar_width and dur_cells[pos] == " ":
                                    dur_cells[pos] = ch
                    safe_addstr(stdscr, row_start + (rows["dur"] or 0), bar_x, "".join(dur_cells))
                if abs_bar == cursor_bar:
                    for col, _denom, _dot in positions:
                        if col == cursor_col:
                            flag_y = row_start + (rows["flag"] or 0)
                            content_width = max(1, display_width - barpad * 2)
                            scaled_col = src_to_dest.get(
                                col,
                                _scale_col(col, bar_width, content_width),
                            )
                            cursor_x = bar_x + barpad + scaled_col
                            safe_addstr(
                                stdscr,
                                flag_y,
                                cursor_x,
                                flag_cells[barpad + scaled_col],
                                A_BOLD,
                            )
                            if show_dur and rows["dur"] is not None:
                                dur_y = row_start + (rows["dur"] or 0)
                                dur_x = bar_x + barpad + scaled_col
                                safe_addstr(
                                    stdscr,
                                    dur_y,
                                    dur_x,
                                    dur_cells[barpad + scaled_col],
                                    A_BOLD,
                                )
                            break
            else:
                if hide_redundant:
                    flag_positions = flag_positions_from_durations(
                        durations,
                        abs_bar,
                        total_strings,
                        bar_width,
                        default_duration,
                        dotted=dotted,
                    )
                    flag_positions = _filter_redundant_positions(flag_positions)
                else:
                    flag_positions = _flag_positions_all(
                        durations,
                        abs_bar,
                        total_strings,
                        bar_width,
                        default_duration,
                        dotted=dotted,
                    )
                flagstyle = settings.get("flagstyle", "standard")
                flag_cells, stem_cells = build_flag_rows(
                    flag_positions,
                    spacing_mode=spacing_mode,
                    display_width=display_width,
                    bar_width=bar_width,
                    barpad=barpad,
                    flagstyle=flagstyle,
                )
                safe_addstr(stdscr, row_start + (rows["flag"] or 0), bar_x, "".join(flag_cells))
                if (
                    playback_bar is not None
                    and playback_col is not None
                    and abs_bar == playback_bar
                    and 0 <= playback_col < bar_width
                ):
                    content_width = max(1, display_width - barpad * 2)
                    pcol = _scale_col(playback_col, bar_width, content_width)
                    safe_addstr(
                        stdscr,
                        row_start + (rows["flag"] or 0),
                        bar_x + barpad + pcol,
                        flag_cells[barpad + pcol],
                        A_BOLD,
                    )
                if rows.get("flag2") is not None:
                    safe_addstr(
                        stdscr,
                        row_start + (rows["flag2"] or 0),
                        bar_x,
                        "".join(stem_cells),
                    )
                if show_dur and rows["dur"] is not None:
                    dur_cells = _bar_durations(
                        durations,
                        abs_bar,
                        total_strings,
                        bar_width,
                        default_duration,
                        hide_redundant=hide_redundant,
                        dotted=dotted,
                    )
                    if spacing_mode == "auto":
                        content_width = max(1, display_width - barpad * 2)
                        dur_cells = _scale_row(dur_cells, content_width, " ")
                        dur_cells = pad_row(dur_cells, display_width, barpad)
                    safe_addstr(stdscr, row_start + (rows["dur"] or 0), bar_x, "".join(dur_cells))
            cursor_display_index = cursor_string if cursor_string < display_strings else None
            for display_idx in range(display_strings):
                if reverse_strings:
                    actual = display_indices[display_strings - 1 - display_idx]
                else:
                    actual = display_indices[display_idx]
                y = row_start + (rows["staff"] or 0) + display_idx
                row_cells = cells[actual]
                fill_char = "-"
                if actual >= 6:
                    row_cells = _inline_bass_row(row_cells)
                    fill_char = " "
                if spacing_mode == "auto":
                    content_width = max(1, display_width - barpad * 2)
                    if bar.chords:
                        row_cells = _scale_chord_row(
                            row_cells,
                            fill_char=fill_char,
                            src_to_dest=src_to_dest,
                            bar_width=bar_width,
                            content_width=content_width,
                        )
                    else:
                        row_cells = _scale_row(row_cells, content_width, fill_char)
                    row_cells = pad_row(row_cells, display_width, barpad, pad_char=fill_char)
                row_text = "".join(row_cells)
                safe_addstr(stdscr, y, bar_x - 1, "|")
                safe_addstr(stdscr, y, bar_x, row_text)
                safe_addstr(stdscr, y, bar_x + display_width, barline)

                if (
                    abs_bar == cursor_bar
                    and cursor_display_index is not None
                    and display_idx == cursor_display_index
                    and 0 <= cursor_col < bar_width
                ):
                    content_width = max(1, display_width - barpad * 2)
                    cell_x = bar_x + barpad + _scale_col(
                        cursor_col,
                        bar_width,
                        content_width,
                    )
                    safe_addstr(
                        stdscr,
                        y,
                        cell_x,
                        row_text[barpad + _scale_col(cursor_col, bar_width, content_width)],
                        A_REVERSE,
                    )
                if (
                    playback_bar is not None
                    and playback_col is not None
                    and abs_bar == playback_bar
                    and 0 <= playback_col < bar_width
                ):
                    content_width = max(1, display_width - barpad * 2)
                    play_x = bar_x + barpad + _scale_col(
                        playback_col,
                        bar_width,
                        content_width,
                    )
                    safe_addstr(
                        stdscr,
                        y,
                        play_x,
                        row_text[barpad + _scale_col(playback_col, bar_width, content_width)],
                        A_BOLD,
                    )
                for col in range(bar_width):
                    if (abs_bar, actual, col) in highlights:
                        content_width = max(1, display_width - barpad * 2)
                        hl_x = bar_x + barpad + _scale_col(
                            col,
                            bar_width,
                            content_width,
                        )
                        safe_addstr(
                            stdscr,
                            y,
                            hl_x,
                            row_text[barpad + _scale_col(col, bar_width, content_width)],
                            A_BOLD,
                        )

            if spacing_mode == "auto":
                if gap_sizes is not None and local_idx < len(gap_sizes):
                    bar_x += display_width + gap_sizes[local_idx]
                else:
                    bar_x += display_width + bar_gap
            else:
                bar_x += bar_width + bar_gap
        current_bar_start = bar_end
