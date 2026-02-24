from __future__ import annotations

from oud.core.render_utils import (
    smart_group_map,
    soft_beat_snap_map,
    spread_flag_positions,
    trim_right_slack_for_onsets,
)
from oud.core.spacing import auto_bar_plan
from oud.core.tab_policy import (
    hold_span_chars,
    show_time_cue_for_bar,
    slur_span_chars,
    system_display_indices_for_bars,
    tie_notehead_hidden_cols,
    tie_notehead_parenthesize_cols,
    tie_span_chars,
    time_cue_reserved_width,
    time_cue_side_pad,
    time_sig_inline_rows,
    visual_row_indices,
)
from oud.core.view_model import (
    _bar_annotations,
    _bar_durations,
    _bar_number_for_index,
    _bar_ornaments,
    _bar_span_row,
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
    flag_count,
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
    *,
    min_gap: int = 2,
) -> tuple[list[tuple[int, int, bool]], dict[int, int]]:
    scaled_positions = [
        (_scale_col(pos, bar_width, content_width), denom, dot)
        for (pos, denom, dot) in positions
    ]
    spread_positions = spread_flag_positions(
        scaled_positions,
        content_width,
        min_gap=max(0, min_gap),
    )
    ordered_raw = sorted(positions, key=lambda item: item[0])
    src_to_dest = {
        raw_col: scaled_col
        for (raw_col, _raw_denom, _raw_dot), (scaled_col, _denom, _dot) in zip(
            ordered_raw, spread_positions, strict=False,
        )
    }
    return spread_positions, src_to_dest


def _note_event_columns(cells: list[list[str]], total_strings: int, grid_width: int) -> list[int]:
    cols: list[int] = []
    for col in range(grid_width):
        for actual in range(total_strings):
            if cells[actual][col] != "-":
                cols.append(col)
                break
    return cols


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
        target = max(0, min(content_width - 1, dest_col))
        # Keep noteheads anchored to their mapped event columns.
        # Drifting to nearest free slot causes visual rhythm slippage.
        # Inline bass connector dashes are secondary glyphs and must not erase notes
        # when compression maps them onto the same target cell.
        if ch == "-" and scaled[target] != fill_char:
            continue
        scaled[target] = ch
    return scaled


def _place_duration_cells_aligned(row: list[str], col: int, text: str) -> None:
    width = len(row)
    if col < 0 or col >= width or not text:
        return
    for idx, ch in enumerate(text):
        target = col + idx
        if target >= width:
            break
        row[target] = ch


def _required_flag_content_width(
    positions: list[tuple[int, int, bool]],
    *,
    min_gap: int = 1,
) -> int:
    if not positions:
        return 1
    spans = [1 + flag_count(denom) + (1 if dot else 0) for (_c, denom, dot) in positions]
    return max(1, sum(spans) + max(0, len(spans) - 1) * max(0, min_gap))


def _required_duration_content_width(
    positions: list[tuple[int, int, bool]],
    *,
    min_gap: int = 1,
) -> int:
    if not positions:
        return 1
    spans = [max(1, len(duration_display(denom, dot))) for (_c, denom, dot) in positions]
    return max(1, sum(spans) + max(0, len(spans) - 1) * max(0, min_gap))


def _required_auto_display_width_for_bar(
    bar,
    *,
    total_strings: int,
    bar_width: int,
    default_duration: int,
    style: str,
    french_c: str,
    show_dur: bool,
    hide_redundant: bool,
    barpad: int,
    flag_gap: int = 1,
    event_gap: int = 2,
    cue_pad_total: int = 0,
) -> int:
    if not bar.chords:
        return 1
    positions, grid_width = _chord_positions_distinct(bar, bar_width, default_duration)
    flag_positions = _filter_redundant_positions(positions) if hide_redundant else positions
    ordered_flags = sorted(flag_positions, key=lambda item: item[0])
    cells = bar_cells_from_chords(
        bar,
        total_strings,
        grid_width,
        default_duration,
        style,
        french_c=french_c,
    )
    min_content = _required_flag_content_width(ordered_flags, min_gap=flag_gap)
    note_cols = _note_event_columns(cells, total_strings, grid_width)
    # Keep at least one visible dash between noteheads and also before the right barline.
    # Required note span plus one trailing dash before the closing barline.
    if note_cols:
        min_note_content = 2 + (max(0, len(note_cols) - 1) * max(1, event_gap))
        min_content = max(min_content, min_note_content)
    if show_dur:
        min_content = max(
            min_content,
            _required_duration_content_width(ordered_flags, min_gap=flag_gap),
        )
    return max(1, min_content + (barpad * 2) + max(0, cue_pad_total))


def _redistribute_extra_width(  # noqa: C901, PLR0912
    widths: list[int],
    gaps: list[int],
    *,
    spacing_fill: str,
    extra: int,
) -> None:
    if not widths or extra <= 0:
        return
    if len(widths) == 1:
        widths[0] += extra
        return
    if spacing_fill == "stretch":
        left = 0
        right = len(widths) - 1
        while extra > 0 and left <= right:
            widths[left] += 1
            extra -= 1
            if extra <= 0:
                break
            if right != left:
                widths[right] += 1
                extra -= 1
            left += 1
            right -= 1
            if left > right:
                left = 0
                right = len(widths) - 1
        return
    if spacing_fill == "smart":
        idx = 0
        while extra > 0:
            widths[idx] += 1
            extra -= 1
            idx = (idx + 1) % len(widths)
        return
    if spacing_fill == "edge":
        if len(gaps) == 1:
            gaps[0] += extra
            return
        while extra > 0 and gaps:
            gaps[0] += 1
            extra -= 1
            if extra <= 0:
                break
            gaps[-1] += 1
            extra -= 1


def _grid_display_map(
    *,
    grid_width: int,
    content_width: int,
    src_to_dest: dict[int, int],
) -> list[int]:
    width = max(1, grid_width)
    content = max(1, content_width)
    mapping: list[int] = []
    prev = 0
    for grid_col in range(width):
        dest = src_to_dest.get(grid_col, _scale_col(grid_col, width, content))
        dest = max(0, min(content - 1, dest))
        if grid_col > 0 and dest < prev:
            dest = prev
        if grid_col > 0 and dest > prev + 1:
            dest = prev + 1
        mapping.append(dest)
        prev = dest
    return mapping


def _chord_positions_distinct(
    bar,
    bar_width: int,
    default_duration: int,
) -> tuple[list[tuple[int, int, bool]], int]:
    if not bar.chords:
        return chord_positions(bar, bar_width, default_duration), bar_width
    width = max(1, bar_width, len(bar.chords))
    max_width = max(width, len(bar.chords) * 2 + 2)
    while width <= max_width:
        positions = chord_positions(bar, width, default_duration)
        cols = [col for col, _denom, _dot in positions]
        if len(cols) == len(set(cols)):
            return positions, width
        width += 1
    return chord_positions(bar, max_width, default_duration), max_width


def _playback_scaled_col_for_chords(
    *,
    playback_col: int,
    bar_width: int,
    grid_width: int,
    content_width: int,
    positions: list[tuple[int, int, bool]],
    src_to_dest: dict[int, int],
) -> int:
    if not positions:
        return 0
    if 0 <= playback_col < len(positions):
        raw_col = positions[playback_col][0]
    else:
        raw_col = _scale_col(playback_col, bar_width, grid_width)
    col = src_to_dest.get(raw_col, _scale_col(raw_col, grid_width, content_width))
    return max(0, min(content_width - 1, col))


def _playback_in_range(bar, playback_col: int, bar_width: int) -> bool:
    if playback_col < 0:
        return False
    if bar.chords:
        return playback_col < len(bar.chords)
    return playback_col < bar_width


def _resolved_bar_time_value(
    piece,
    bar_index: int,
    time_setting: str,
    default_duration: int,
) -> str:
    value = piece.bars[bar_index].time_sig or time_setting
    if value in ("auto", "detect"):
        inferred = _infer_time_signature(piece.bars[bar_index], default_duration)
        value = inferred or "C"
    return value


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
    display_indices: list[int],  # noqa: ARG001
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
    chord_wrap_limit: int,
) -> None:
    total_bars = len(piece.bars)
    current_bar_start = bar_offset
    for sys_idx in range(systems):
        row_start = header_row + 1 + sys_idx * block_h
        rows_proto = _layout_block_rows(
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
        gaps_after: list[int] = []
        bar_widths: list[int] = []
        if spacing_mode == "auto":
            bar_indices, bar_widths, gaps_after = auto_bar_plan(
                bars=piece.bars,
                bar_start=bar_start,
                usable_width=usable_width,
                bar_width=bar_width,
                overrides=overrides,
                durations=durations,
                default_duration=default_duration,
                dotted=dotted,
                bar_gap=bar_gap,
                spacing_fill=spacing_fill,
                stave_breaks=stave_breaks,
                bars_per_line_limit=bars_per_line_limit,
                max_chords=max_chords,
                chord_wrap_limit=chord_wrap_limit,
            )
            # Enforce per-bar minimums up-front so later rendering never expands
            # bars after fit (which can visually split bars in stretch modes).
            time_setting = settings.get("time", "C")
            min_widths: list[int] = []
            for abs_bar in bar_indices:
                current_time = _resolved_bar_time_value(
                    piece, abs_bar, time_setting, default_duration,
                )
                _beats, _unit, sig_label = _parse_time_signature(current_time)
                prev_time = (
                    _resolved_bar_time_value(piece, abs_bar - 1, time_setting, default_duration)
                    if abs_bar > 0
                    else None
                )
                show_cue = show_time_cue_for_bar(
                    bar_index=abs_bar,
                    current_time_value=current_time,
                    prev_time_value=prev_time,
                    sig_label=sig_label,
                )
                min_widths.append(
                    _required_auto_display_width_for_bar(
                        piece.bars[abs_bar],
                        total_strings=total_strings,
                        bar_width=bar_width,
                        default_duration=default_duration,
                        style=settings.get("style", "french"),
                        french_c=settings.get("frenchc", "normal"),
                        show_dur=show_dur and rows_proto["dur"] is not None,
                        hide_redundant=hide_redundant,
                        barpad=barpad,
                        flag_gap=2 if spacing_fill == "smart" else 1,
                        event_gap=2,
                        cue_pad_total=time_cue_reserved_width(
                            show_time_cue=show_cue,
                            scale_bar=True,
                        ),
                    ),
                )
            bar_widths = [
                max(width, min_width)
                for width, min_width in zip(bar_widths, min_widths, strict=False)
            ]
            while bar_widths and (sum(bar_widths) + sum(gaps_after)) > usable_width:
                bar_widths.pop()
                bar_indices = bar_indices[: len(bar_widths)]
                gaps_after = gaps_after[: max(0, len(bar_widths) - 1)]
            extra = max(0, usable_width - (sum(bar_widths) + sum(gaps_after)))
            _redistribute_extra_width(
                bar_widths,
                gaps_after,
                spacing_fill=spacing_fill,
                extra=extra,
            )
            bar_end = bar_indices[-1] + 1 if bar_indices else bar_start
        else:
            bars_per_line = bars_per_line_limit
            bars_per_line = max(1, bars_per_line)
            bar_end = _next_system_start(piece.bars, bar_start, bars_per_line, stave_breaks)
            bar_end = min(total_bars, bar_end)
            bar_indices = list(range(bar_start, bar_end))
        # Show extra bass rows only when they are used in this rendered system.
        system_display_indices = system_display_indices_for_bars(
            piece.bars[bar_start:bar_end],
            total_strings=total_strings,
        )
        system_display_strings = len(system_display_indices)
        system_visual_indices = visual_row_indices(
            system_display_indices,
            reverse=reverse_strings,
        )
        rows = _layout_block_rows(
            system_display_strings,
            include_meta,
            show_dur,
            show_extras,
            show_tactus,
            double_stems,
        )
        for display_idx in range(system_display_strings):
            label = "  "
            if sys_idx == 0:
                actual = system_visual_indices[display_idx]
                label = _string_label(actual, total_strings, tuning_labels, basslabels)
            safe_addstr(stdscr, row_start + (rows["staff"] or 0) + display_idx, 0, label)

        bar_x = left_margin
        if spacing_mode == "auto" and bar_widths:
            total_width = sum(bar_widths) + bar_gap * max(0, len(bar_widths) - 1)
            if spacing_fill == "center":
                extra_left = max(0, (usable_width - total_width) // 2)
                bar_x += extra_left
        for local_idx, bar in enumerate(piece.bars[bar_start:bar_end]):
            abs_bar = bar_start + local_idx
            style = settings.get("style", "french")
            french_c = settings.get("frenchc", "normal")
            chord_positions_all: list[tuple[int, int, bool]] = []
            grid_width = bar_width
            if bar.chords:
                chord_positions_all, grid_width = _chord_positions_distinct(
                    bar,
                    bar_width,
                    default_duration,
                )
                cells = bar_cells_from_chords(
                    bar,
                    total_strings,
                    grid_width,
                    default_duration,
                    style,
                    french_c=french_c,
                )
            else:
                cells = bar_cells(
                    bar,
                    total_strings,
                    bar_width,
                    style,
                    french_c=french_c,
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
            time_value = _resolved_bar_time_value(piece, abs_bar, time_setting, default_duration)
            beats, _unit, _sig_label = _parse_time_signature(time_value)
            tactus = _tactus_row(grid_width, beats)
            barline = bar.barline or "|"
            repeat = bar.repeat or ""
            repeat_glyph = repeat if repeat in {".:", ":.", "."} else ""
            repeat_cue = repeat if not repeat_glyph else ""
            ann_cells = _bar_annotations(annotations, abs_bar, grid_width)
            orn_cells = _bar_ornaments(ornaments, abs_bar, grid_width)
            slur_chars = slur_span_chars(settings.get("slurcuestyle", "paren"))
            if slur_chars is None:
                slur_cells = [" " for _ in range(grid_width)]
            else:
                slur_cells = _bar_span_row(slurs, abs_bar, grid_width, *slur_chars)
            tie_chars = tie_span_chars(settings.get("tiecuestyle", "bracket"))
            if tie_chars is None:
                tie_cells = [" " for _ in range(grid_width)]
            else:
                tie_cells = _bar_span_row(ties, abs_bar, grid_width, *tie_chars)
            hold_chars = hold_span_chars(settings.get("holdcuestyle", "angle"))
            if hold_chars is None:
                hold_cells = [" " for _ in range(grid_width)]
            else:
                hold_cells = _bar_span_row(holds, abs_bar, grid_width, *hold_chars)
            apply_overrides(cells, overrides, abs_bar, total_strings, grid_width)
            hidden_tie_cols = tie_notehead_hidden_cols(
                ties,
                bar_index=abs_bar,
                mode=settings.get("tienoteheads", "show"),
            )
            paren_tie_cols = tie_notehead_parenthesize_cols(
                ties,
                bar_index=abs_bar,
                mode=settings.get("tienoteheads", "show"),
            )
            if hidden_tie_cols:
                for hide_col in hidden_tie_cols:
                    if not (0 <= hide_col < grid_width):
                        continue
                    for row_cells in cells:
                        if row_cells[hide_col] != "-":
                            row_cells[hide_col] = "-"
            if paren_tie_cols:
                for end_col in paren_tie_cols:
                    if not (0 <= end_col < grid_width):
                        continue
                    if tie_cells[end_col] == " ":
                        tie_cells[end_col] = ")"
                    left = end_col - 1
                    if left >= 0 and tie_cells[left] == " ":
                        tie_cells[left] = "("
            display_width = bar_width
            if spacing_mode == "auto":
                display_width = bar_widths[local_idx]
            scale_bar = spacing_mode == "auto"
            if bar.chords:
                preview_flags = (
                    _filter_redundant_positions(chord_positions_all)
                    if hide_redundant
                    else chord_positions_all
                )
                smart_gap = 2 if spacing_fill == "smart" else 1
                min_content = _required_flag_content_width(preview_flags, min_gap=smart_gap)
                note_cols = _note_event_columns(cells, total_strings, grid_width)
                min_content = max(min_content, len(note_cols))
                if show_dur and rows["dur"] is not None:
                    min_content = max(
                        min_content,
                        _required_duration_content_width(preview_flags, min_gap=smart_gap),
                    )
                min_display = min_content + barpad * 2
                if min_display > display_width and spacing_mode != "auto":
                    display_width = min_display
                    scale_bar = True
            pad = barpad if scale_bar else 0
            prev_time = (
                _resolved_bar_time_value(piece, abs_bar - 1, time_setting, default_duration)
                if abs_bar > 0
                else None
            )
            show_time_sig_here = show_time_cue_for_bar(
                bar_index=abs_bar,
                current_time_value=time_value,
                prev_time_value=prev_time,
                sig_label=_sig_label,
            )
            wrote_time_sig = show_time_sig_here
            cue_pad_extra = time_cue_side_pad(show_time_cue=show_time_sig_here, scale_bar=scale_bar)
            draw_pad = pad + cue_pad_extra
            if rows["meta"] is not None:
                meta_row = row_start + (rows["meta"] or 0)
                safe_addstr(stdscr, meta_row, bar_x - 2, repeat_glyph)
                if abs_bar == 0 and not wrote_time_sig:
                    safe_addstr(stdscr, meta_row, 0, " ")
                meta_x = bar_x
                if number is not None:
                    safe_addstr(stdscr, meta_row, meta_x, number)
                if repeat_cue:
                    cue_x = meta_x + (len(number) + 1 if number is not None else 0)
                    safe_addstr(stdscr, meta_row, cue_x, repeat_cue)
            if rows["ann"] is not None:
                ann_row = ann_cells
                if scale_bar:
                    content_width = max(1, display_width - draw_pad * 2)
                    ann_row = _scale_row(ann_cells, content_width, " ")
                    ann_row = pad_row(ann_row, display_width, draw_pad)
                safe_addstr(stdscr, row_start + (rows["ann"] or 0), bar_x, "".join(ann_row))
            if rows["orn"] is not None:
                orn_row = orn_cells
                if scale_bar:
                    content_width = max(1, display_width - draw_pad * 2)
                    orn_row = _scale_row(orn_cells, content_width, " ")
                    orn_row = pad_row(orn_row, display_width, draw_pad)
                safe_addstr(stdscr, row_start + (rows["orn"] or 0), bar_x, "".join(orn_row))
            if rows["tactus"] is not None:
                tactus_row = tactus
                if scale_bar:
                    content_width = max(1, display_width - draw_pad * 2)
                    tactus_row = _scale_row(tactus, content_width, " ")
                    tactus_row = pad_row(tactus_row, display_width, draw_pad)
                safe_addstr(stdscr, row_start + (rows["tactus"] or 0), bar_x, "".join(tactus_row))
            if rows["slur"] is not None:
                slur_row = slur_cells
                if scale_bar:
                    content_width = max(1, display_width - draw_pad * 2)
                    slur_row = _scale_row(slur_cells, content_width, " ")
                    slur_row = pad_row(slur_row, display_width, draw_pad)
                safe_addstr(stdscr, row_start + (rows["slur"] or 0), bar_x, "".join(slur_row))
            if rows["tie"] is not None:
                tie_row = tie_cells
                if scale_bar:
                    content_width = max(1, display_width - draw_pad * 2)
                    tie_row = _scale_row(tie_cells, content_width, " ")
                    tie_row = pad_row(tie_row, display_width, draw_pad)
                safe_addstr(stdscr, row_start + (rows["tie"] or 0), bar_x, "".join(tie_row))
            if rows["hold"] is not None:
                hold_row = hold_cells
                if scale_bar:
                    content_width = max(1, display_width - draw_pad * 2)
                    hold_row = _scale_row(hold_cells, content_width, " ")
                    hold_row = pad_row(hold_row, display_width, draw_pad)
                safe_addstr(stdscr, row_start + (rows["hold"] or 0), bar_x, "".join(hold_row))
            if bar.chords:
                visible_note_cols = set(_note_event_columns(cells, total_strings, grid_width))
                positions = [
                    item for item in chord_positions_all if item[0] in visible_note_cols
                ]
                flag_positions = (
                    _filter_redundant_positions(positions) if hide_redundant else positions
                )
                ordered_flags = sorted(flag_positions, key=lambda item: item[0])
                flagstyle = settings.get("flagstyle", "standard")
                dur_source_positions: list[tuple[int, int]] = []
                if scale_bar:
                    content_width = max(1, display_width - draw_pad * 2)
                    event_min_gap = 2
                    unit_anchor_min_gap = 1
                    flag_min_gap = 1 if spacing_fill == "smart" else 0
                    beatsnap_mode = settings.get("beatsnap", "off")
                    if beatsnap_mode == "soft" and beats > 1:
                        src_to_dest = soft_beat_snap_map(
                            positions,
                            grid_width=grid_width,
                            content_width=content_width,
                            beats=beats,
                            min_gap=unit_anchor_min_gap,
                        )
                        src_to_dest = trim_right_slack_for_onsets(
                            src_to_dest,
                            all_positions=positions,
                            visible_positions=ordered_flags,
                            content_width=content_width,
                            min_gap=unit_anchor_min_gap,
                        )
                    elif spacing_fill == "smart":
                        src_to_dest = smart_group_map(
                            positions,
                            ordered_flags,
                            content_width,
                            min_gap=event_min_gap,
                        )
                    else:
                        _, src_to_dest = _build_chord_scale_map(
                            positions,
                            grid_width,
                            content_width,
                            min_gap=event_min_gap,
                        )
                    if content_width > 1 and src_to_dest:
                        # Reserve one trailing cell for the right-side dash, but preserve
                        # event spacing while doing so (simple clamping can re-glue notes).
                        anchor_width = max(1, content_width - 1)
                        seeded_event_positions = [
                            (
                                _scale_col(
                                    src_to_dest.get(
                                        col,
                                        _scale_col(col, grid_width, content_width),
                                    ),
                                    content_width,
                                    anchor_width,
                                ),
                                2,  # unit anchor spacing only; do not reserve flag tails here
                                False,
                            )
                            for (col, denom, dot) in positions
                        ]
                        spread_event_positions = spread_flag_positions(
                            seeded_event_positions,
                            anchor_width,
                            min_gap=unit_anchor_min_gap,
                        )
                        src_to_dest = {
                            raw_col: scaled_col
                            for (raw_col, _d1, _dot1), (scaled_col, _d2, _dot2) in zip(
                                positions,
                                spread_event_positions,
                                strict=False,
                            )
                        }
                    final_flag_positions = [
                        (
                            src_to_dest.get(col, _scale_col(col, grid_width, content_width)),
                            denom,
                            dot,
                        )
                        for (col, denom, dot) in ordered_flags
                    ]
                    dur_source_positions = [
                        (
                            raw_col,
                            src_to_dest.get(
                                raw_col,
                                _scale_col(raw_col, grid_width, content_width),
                            ),
                        )
                        for (raw_col, _denom, _dot) in ordered_flags
                    ]
                    flag_cells, stem_cells = build_flag_rows(
                        final_flag_positions,
                        spacing_mode="fixed",
                        display_width=content_width,
                        bar_width=content_width,
                        barpad=0,
                        flagstyle=flagstyle,
                        min_gap=flag_min_gap,
                    )
                    flag_cells = pad_row(flag_cells, display_width, draw_pad)
                    stem_cells = pad_row(stem_cells, display_width, draw_pad)
                else:
                    src_to_dest = {}
                    final_flag_positions = spread_flag_positions(
                        ordered_flags,
                        bar_width,
                        min_gap=1,
                    )
                    dur_source_positions = [
                        (raw_col, col)
                        for (raw_col, _denom, _dot), (col, _d2, _dot2) in zip(
                            ordered_flags,
                            final_flag_positions,
                            strict=False,
                        )
                    ]
                    flag_cells, stem_cells = build_flag_rows(
                        flag_positions,
                        spacing_mode=spacing_mode,
                        display_width=display_width,
                        bar_width=bar_width,
                        barpad=barpad,
                        flagstyle=flagstyle,
                    )
                content_width = max(1, display_width - draw_pad * 2)
                grid_map = _grid_display_map(
                    grid_width=grid_width,
                    content_width=content_width,
                    src_to_dest=src_to_dest,
                )
                safe_addstr(stdscr, row_start + (rows["flag"] or 0), bar_x, "".join(flag_cells))
                if (
                    playback_bar is not None
                    and playback_col is not None
                    and abs_bar == playback_bar
                    and _playback_in_range(bar, playback_col, bar_width)
                ):
                    content_width = max(1, display_width - pad * 2)
                    pcol = _playback_scaled_col_for_chords(
                        playback_col=playback_col,
                        bar_width=bar_width,
                        grid_width=grid_width,
                        content_width=content_width,
                        positions=positions,
                        src_to_dest=src_to_dest,
                    )
                    safe_addstr(
                        stdscr,
                        row_start + (rows["flag"] or 0),
                        bar_x + draw_pad + pcol,
                        flag_cells[draw_pad + pcol],
                        A_BOLD,
                    )
                if rows.get("flag2") is not None:
                    safe_addstr(
                        stdscr,
                        row_start + (rows["flag2"] or 0),
                        bar_x,
                        "".join(stem_cells),
                    )
                dur_col_map: dict[int, int] = {}
                dur_padded = False
                if show_dur and rows["dur"] is not None:
                    if scale_bar or spacing_mode == "auto":
                        content_width = max(1, display_width - draw_pad * 2)
                        dur_cells = [" " for _ in range(content_width)]
                        for (raw_col, denom, dot), (_raw_key, target_col) in zip(
                            ordered_flags,
                            dur_source_positions,
                            strict=False,
                        ):
                            dur_col_map[raw_col] = target_col
                            _place_duration_cells_aligned(
                                dur_cells,
                                target_col,
                                duration_display(denom, dot),
                            )
                        dur_cells = pad_row(dur_cells, display_width, draw_pad)
                        dur_padded = True
                    else:
                        dur_cells = [" " for _ in range(bar_width)]
                        for (raw_col, denom, dot), (_raw_key, target_col) in zip(
                            ordered_flags,
                            dur_source_positions,
                            strict=False,
                        ):
                            dur_col_map[raw_col] = target_col
                            _place_duration_cells_aligned(
                                dur_cells,
                                target_col,
                                duration_display(denom, dot),
                            )
                    safe_addstr(stdscr, row_start + (rows["dur"] or 0), bar_x, "".join(dur_cells))
                if abs_bar == cursor_bar:
                    for col, _denom, _dot in positions:
                        cursor_grid_col = _scale_col(cursor_col, bar_width, grid_width)
                        if col == cursor_grid_col:
                            flag_y = row_start + (rows["flag"] or 0)
                            scaled_col = grid_map[col]
                            cursor_x = bar_x + draw_pad + scaled_col
                            safe_addstr(
                                stdscr,
                                flag_y,
                                cursor_x,
                                flag_cells[draw_pad + scaled_col],
                                A_BOLD,
                            )
                            if show_dur and rows["dur"] is not None:
                                dur_y = row_start + (rows["dur"] or 0)
                                dur_col = dur_col_map.get(col, scaled_col)
                                if dur_padded:
                                    dur_idx = draw_pad + dur_col
                                    dur_x = bar_x + dur_idx
                                else:
                                    dur_idx = dur_col
                                    dur_x = bar_x + dur_idx
                                if 0 <= dur_idx < len(dur_cells):
                                    safe_addstr(
                                        stdscr,
                                        dur_y,
                                        dur_x,
                                        dur_cells[dur_idx],
                                        A_BOLD,
                                    )
                            break
            else:
                has_explicit_content = bool(bar.notes)
                if not has_explicit_content:
                    has_explicit_content = any(
                        b == abs_bar and value not in ("", "-", " ")
                        for (b, _s, _c), value in overrides.items()
                    ) or any(b == abs_bar for (b, _s, _c) in durations)
                if hide_redundant:
                    if has_explicit_content:
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
                        flag_positions = []
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
                    spacing_mode="auto" if scale_bar else spacing_mode,
                    display_width=display_width,
                    bar_width=bar_width,
                    barpad=pad,
                    flagstyle=flagstyle,
                )
                safe_addstr(stdscr, row_start + (rows["flag"] or 0), bar_x, "".join(flag_cells))
                if (
                    playback_bar is not None
                    and playback_col is not None
                    and abs_bar == playback_bar
                    and _playback_in_range(bar, playback_col, bar_width)
                ):
                    content_width = max(1, display_width - draw_pad * 2)
                    pcol = _scale_col(playback_col, bar_width, content_width)
                    safe_addstr(
                        stdscr,
                        row_start + (rows["flag"] or 0),
                        bar_x + draw_pad + pcol,
                        flag_cells[draw_pad + pcol],
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
                    if scale_bar:
                        content_width = max(1, display_width - draw_pad * 2)
                        dur_cells = _scale_row(dur_cells, content_width, " ")
                    dur_cells = pad_row(dur_cells, display_width, draw_pad)
                    safe_addstr(stdscr, row_start + (rows["dur"] or 0), bar_x, "".join(dur_cells))
            cursor_display_index = cursor_string if cursor_string < system_display_strings else None
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
                        row_cells = _scale_row(row_cells, content_width, fill_char)
                    row_cells = pad_row(row_cells, display_width, draw_pad, pad_char=fill_char)
                row_text = "".join(row_cells)
                safe_addstr(stdscr, y, bar_x - 1, "|")
                safe_addstr(stdscr, y, bar_x, row_text)
                if show_time_sig_here and _sig_label:
                    ts_rows = time_sig_inline_rows(
                        time_value,
                        _sig_label,
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
                        scaled_cursor_col = _scale_col(cursor_col, bar_width, content_width)
                    cell_x = bar_x + draw_pad + scaled_cursor_col
                    safe_addstr(
                        stdscr,
                        y,
                        cell_x,
                        row_text[draw_pad + scaled_cursor_col],
                        A_REVERSE,
                    )
                if (
                    playback_bar is not None
                    and playback_col is not None
                    and abs_bar == playback_bar
                    and _playback_in_range(bar, playback_col, bar_width)
                ):
                    content_width = max(1, display_width - draw_pad * 2)
                    if bar.chords:
                        scaled_play_col = _playback_scaled_col_for_chords(
                            playback_col=playback_col,
                            bar_width=bar_width,
                            grid_width=grid_width,
                            content_width=content_width,
                            positions=positions,
                            src_to_dest=src_to_dest,
                        )
                    else:
                        scaled_play_col = _scale_col(playback_col, bar_width, content_width)
                    play_x = bar_x + draw_pad + scaled_play_col
                    safe_addstr(
                        stdscr,
                        y,
                        play_x,
                        row_text[draw_pad + scaled_play_col],
                        A_BOLD,
                    )
                for col in range(bar_width):
                    if (abs_bar, actual, col) in highlights:
                        content_width = max(1, display_width - pad * 2)
                        if bar.chords:
                            highlight_grid_col = _scale_col(col, bar_width, grid_width)
                            scaled_hl_col = grid_map[highlight_grid_col]
                        else:
                            scaled_hl_col = _scale_col(col, bar_width, content_width)
                        hl_x = bar_x + draw_pad + scaled_hl_col
                        safe_addstr(
                            stdscr,
                            y,
                            hl_x,
                            row_text[draw_pad + scaled_hl_col],
                            A_BOLD,
                        )

            if (
                playback_bar is not None
                and playback_col is not None
                and abs_bar == playback_bar
                and _playback_in_range(bar, playback_col, bar_width)
            ):
                content_width = max(1, display_width - draw_pad * 2)
                if bar.chords:
                    scaled_play_col = _playback_scaled_col_for_chords(
                        playback_col=playback_col,
                        bar_width=bar_width,
                        grid_width=grid_width,
                        content_width=content_width,
                        positions=positions,
                        src_to_dest=src_to_dest,
                    )
                else:
                    scaled_play_col = _scale_col(playback_col, bar_width, content_width)
                marker_y = row_start + (rows["staff"] or 0) + system_display_strings
                marker_x = bar_x + draw_pad + scaled_play_col
                safe_addstr(stdscr, marker_y, marker_x, "^", A_BOLD)

            if spacing_mode == "auto":
                next_gap = gaps_after[local_idx] if local_idx < len(gaps_after) else 0
                bar_x += display_width + next_gap
            else:
                bar_x += display_width + bar_gap
        current_bar_start = bar_end
