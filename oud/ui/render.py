from __future__ import annotations

from oud.core.help_text import help_lines
from oud.core.render_utils import flag_row_style, stem_row_style
from oud.core.tuning_utils import parse_bass_strings
from oud.core.view_model import (
    Piece,
    _bar_annotations,
    _bar_display_width,
    _bar_durations,
    _bar_number_for_index,
    _bar_ornaments,
    _bar_span_row,
    _bars_fit,
    _filter_redundant_positions,
    _flag_positions_all,
    _inline_bass_row,
    _next_system_start,
    _parse_time_signature,
    _scale_col,
    _scale_row,
    _string_label,
    _tactus_row,
    _tuning_labels,
    bar_cells,
    bar_cells_from_chords,
    chord_positions,
    duration_display,
    flag_positions_from_durations,
)
from oud.ui.adapter import A_BOLD, A_REVERSE, CursesError, Screen
from oud.ui.layout_map import block_height as _block_height
from oud.ui.layout_map import layout_block_rows as _layout_block_rows


def _safe_addstr(stdscr: Screen, y: int, x: int, text: str, attr: int = 0) -> None:
    height, width = stdscr.getmaxyx()
    if height <= 0 or width <= 0:
        return
    if y < 0 or y >= height or x >= width:
        return
    if x < 0:
        text = text[-x:]
        x = 0
    if x >= width:
        return
    try:
        stdscr.addstr(y, x, text[: max(0, width - x)], attr)
    except CursesError:
        return
    except ValueError:
        return


def _bass_strings_used(piece: Piece, overrides: dict[tuple[int, int, int], str]) -> set[int]:
    used: set[int] = set()
    for (_bar, string, _col) in overrides:
        if string >= 6:
            used.add(string)
    for bar in piece.bars:
        for note in bar.notes:
            if note.string >= 6:
                used.add(note.string)
        for chord in bar.chords:
            for note in chord.notes:
                idx = note.string - 1
                if idx >= 6:
                    used.add(idx)
    return used


def _apply_overrides(
    cells: list[list[str]],
    overrides: dict[tuple[int, int, int], str],
    bar_index: int,
    strings: int,
    bar_width: int,
) -> None:
    for s_idx in range(strings):
        for col in range(bar_width):
            key = (bar_index, s_idx, col)
            if key not in overrides:
                continue
            value = overrides[key]
            if value == "r":
                cells[s_idx][col] = "_"
                next_col = col + 1
                if (
                    next_col < bar_width
                    and cells[s_idx][next_col] in ("-", " ")
                    and (bar_index, s_idx, next_col) not in overrides
                ):
                    cells[s_idx][next_col] = "."
            else:
                cells[s_idx][col] = value


def _clean_text(text: str) -> str:
    return "".join(ch if 32 <= ord(ch) <= 126 else " " for ch in text)


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


def _help_lines() -> list[str]:
    return help_lines()


def _render_help(
    stdscr: Screen,
    status: str,
    status_attr: int,
    help_offset: int,
) -> None:
    height, _width = stdscr.getmaxyx()
    lines = _help_lines()
    max_lines = max(0, height - 1)
    max_offset = max(0, len(lines) - max_lines)
    offset = min(max(0, help_offset), max_offset)
    for idx, line in enumerate(lines[offset : offset + max_lines]):
        _safe_addstr(stdscr, idx, 0, _clean_text(line))
    _safe_addstr(stdscr, height - 1, 0, _clean_text(status), status_attr)


def _render_plugin(
    stdscr: Screen,
    status: str,
    status_attr: int,
    title: str,
    items: list[str],
    index: int,
    offset: int,
    message: str,
) -> None:
    height, width = stdscr.getmaxyx()
    _safe_addstr(stdscr, 0, 0, _clean_text(title))
    max_lines = max(0, height - 2)
    visible = items[offset : offset + max_lines]
    for row, label in enumerate(visible, start=1):
        absolute = offset + row - 1
        prefix = ">" if absolute == index else " "
        text = _clean_text(f"{prefix} {label}")
        attr = status_attr if absolute == index else 0
        _safe_addstr(stdscr, row, 0, text[: max(0, width - 1)], attr)
    status_text = status
    if message:
        status_text = f"{status}  {message}"
    _safe_addstr(stdscr, height - 1, 0, _clean_text(status_text), status_attr)


def _pad_row(row: list[str], width: int, pad: int, *, pad_char: str = " ") -> list[str]:
    if width <= 0:
        return []
    pad = max(0, min(pad, max(0, (width - 1) // 2)))
    if pad == 0:
        if len(row) < width:
            return row + [" "] * (width - len(row))
        return row[:width]
    content_width = max(1, width - pad * 2)
    if len(row) < content_width:
        row = row + [" "] * (content_width - len(row))
    row = row[:content_width]
    return ([pad_char] * pad) + row + ([pad_char] * pad)


def _info_lines(piece: Piece, settings: dict[str, str]) -> list[str]:
    def line(label: str, value: str | None) -> str:
        return f"{label:<14}{value or ''}"

    fields = [
        line("Title:", piece.title),
        line("Subtitle:", piece.subtitle),
        line("Author:", piece.author),
        line("Composer:", piece.composer),
        line("Footnote:", piece.footnote),
        line("Bars:", str(len(piece.bars))),
        line("Strings:", str(piece.strings)),
        line("Style:", settings.get("style")),
        line("Tuning:", settings.get("tuning")),
        line("Time:", settings.get("time")),
        line("Key:", settings.get("key")),
        line("Spacing:", settings.get("spacingmode")),
        line("Flagstyle:", settings.get("flagstyle")),
        line("Grid:", settings.get("grid")),
        line("ShowDur:", settings.get("showdur")),
        line("ShowExtras:", settings.get("showextras")),
        line("ShowTactus:", settings.get("showtactus")),
        line("Measures:", settings.get("measures")),
        line("MeasuresStep:", settings.get("measuresstep")),
        line("MidiPatch:", settings.get("midipatch")),
        line("MidiGate:", settings.get("midigate")),
        line("Tempo:", settings.get("tempo")),
        line("Soundfont:", settings.get("soundfont")),
        line("TuneLabels:", settings.get("tuninglabels")),
        line("ItalianOrient:", settings.get("italianorient")),
        line("French c:", settings.get("frenchc")),
        line("French e:", settings.get("frenche")),
        line("FlagRedundant:", settings.get("flagredundant")),
    ]
    return ["INFO", "", *fields, "", "q/esc to close"]


def _render_info(
    stdscr: Screen,
    status: str,
    status_attr: int,
    info_offset: int,
    piece: Piece,
    settings: dict[str, str],
) -> None:
    height, _width = stdscr.getmaxyx()
    lines = _info_lines(piece, settings)
    max_lines = max(0, height - 1)
    max_offset = max(0, len(lines) - max_lines)
    offset = min(max(0, info_offset), max_offset)
    for idx, line in enumerate(lines[offset : offset + max_lines]):
        _safe_addstr(stdscr, idx, 0, _clean_text(line))
    _safe_addstr(stdscr, height - 1, 0, _clean_text(status), status_attr)


def render_piece(  # noqa: PLR0912, C901
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
    if settings.get("showtuning", "on") == "on" and tuning_text:
        header = f"{header}  {tuning_text}"
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
    if spacing_mode == "auto":
        max_chords = 0
        max_chords_text = settings.get("maxchords", "")
        if max_chords_text.isdigit():
            max_chords = int(max_chords_text)
        bars_per_line = _bars_fit(
            piece.bars,
            bar_offset,
            bar_gap,
            usable_width,
            bar_width,
            overrides,
            durations,
            default_duration,
            dotted,
            max_chords=max_chords,
        )
    else:
        bars_per_line = max(1, usable_width // (bar_width + bar_gap))
    barsperline = settings.get("barsperline", "")
    if barsperline.isdigit():
        limit = int(barsperline)
        if limit > 0:
            bars_per_line = limit
    maxbars = settings.get("maxbars", "")
    if maxbars.isdigit():
        limit = int(maxbars)
        if limit > 0:
            bars_per_line = min(bars_per_line, limit)
    max_fit = max(1, usable_width // max(1, bar_width + bar_gap))
    bars_per_line = min(bars_per_line, max_fit)
    total_bars = len(piece.bars)

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
            _safe_addstr(stdscr, clear_row, 0, " " * width)
        bar_start = bar_offset
        for _ in range(sys_idx):
            bar_start = _next_system_start(piece.bars, bar_start, bars_per_line, stave_breaks)
        if bar_start >= total_bars:
            break
        bar_end = _next_system_start(piece.bars, bar_start, bars_per_line, stave_breaks)
        bar_end = min(total_bars, bar_end)
        bar_indices = list(range(bar_start, bar_end))
        bar_widths: list[int] = []
        if spacing_mode == "auto":
            bar_widths.extend(
                _bar_display_width(
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
            if bar_widths and total_width > usable_width:
                overflow = total_width - usable_width
                idx = len(bar_widths) - 1
                while overflow > 0 and any(width > 3 for width in bar_widths):
                    if bar_widths[idx] > 3:
                        bar_widths[idx] -= 1
                        overflow -= 1
                    idx -= 1
                    if idx < 0:
                        idx = len(bar_widths) - 1
            total_width = total_bar_width(bar_widths)
            if bar_widths and spacing_fill == "stretch" and total_width < usable_width:
                extra = usable_width - total_width
                idx = 0
                while extra > 0 and bar_widths:
                    bar_widths[idx] += 1
                    extra -= 1
                    idx = (idx + 1) % len(bar_widths)
        for display_idx in range(display_strings):
            if reverse_strings:
                actual = display_indices[display_strings - 1 - display_idx]
            else:
                actual = display_indices[display_idx]
            label = _string_label(actual, total_strings, tuning_labels, basslabels)
            _safe_addstr(stdscr, row_start + (rows["staff"] or 0) + display_idx, 0, label)

        bar_x = left_margin
        if spacing_mode == "auto" and bar_widths and spacing_fill == "center":
            total_width = sum(bar_widths) + bar_gap * max(0, len(bar_widths) - 1)
            extra_left = max(0, (usable_width - total_width) // 2)
            bar_x += extra_left
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
            key_label = settings.get("key", "")
            beats, _unit, sig_label = _parse_time_signature(settings.get("time", "C"))
            tactus = _tactus_row(bar_width, beats)
            barline = bar.barline or "|"
            repeat = bar.repeat or ""
            ann_cells = _bar_annotations(annotations, abs_bar, bar_width)
            orn_cells = _bar_ornaments(ornaments, abs_bar, bar_width)
            slur_cells = _bar_span_row(slurs, abs_bar, bar_width, "(", ")", "~")
            tie_cells = _bar_span_row(ties, abs_bar, bar_width, "[", "]", "-")
            hold_cells = _bar_span_row(holds, abs_bar, bar_width, "<", ">", "_")
            _apply_overrides(cells, overrides, abs_bar, total_strings, bar_width)
            display_width = bar_width
            if spacing_mode == "auto":
                display_width = bar_widths[local_idx]
            if rows["meta"] is not None:
                meta_row = row_start + (rows["meta"] or 0)
                _safe_addstr(stdscr, meta_row, bar_x - 2, repeat)
                if sig_label and abs_bar == 0:
                    _safe_addstr(stdscr, meta_row, 0, sig_label)
                if key_label and abs_bar == 0:
                    _safe_addstr(stdscr, meta_row, 4, f"key:{key_label}")
                if number is not None:
                    _safe_addstr(stdscr, meta_row, bar_x, number)
            if rows["ann"] is not None:
                ann_row = ann_cells
                if spacing_mode == "auto":
                    content_width = max(1, display_width - barpad * 2)
                    ann_row = _scale_row(ann_cells, content_width, " ")
                    ann_row = _pad_row(ann_row, display_width, barpad)
                _safe_addstr(stdscr, row_start + (rows["ann"] or 0), bar_x, "".join(ann_row))
            if rows["orn"] is not None:
                orn_row = orn_cells
                if spacing_mode == "auto":
                    content_width = max(1, display_width - barpad * 2)
                    orn_row = _scale_row(orn_cells, content_width, " ")
                    orn_row = _pad_row(orn_row, display_width, barpad)
                _safe_addstr(stdscr, row_start + (rows["orn"] or 0), bar_x, "".join(orn_row))
            if rows["tactus"] is not None:
                tactus_row = tactus
                if spacing_mode == "auto":
                    content_width = max(1, display_width - barpad * 2)
                    tactus_row = _scale_row(tactus, content_width, " ")
                    tactus_row = _pad_row(tactus_row, display_width, barpad)
                _safe_addstr(
                    stdscr, row_start + (rows["tactus"] or 0), bar_x, "".join(tactus_row),
                )
            if rows["slur"] is not None:
                slur_row = slur_cells
                if spacing_mode == "auto":
                    content_width = max(1, display_width - barpad * 2)
                    slur_row = _scale_row(slur_cells, content_width, " ")
                    slur_row = _pad_row(slur_row, display_width, barpad)
                _safe_addstr(stdscr, row_start + (rows["slur"] or 0), bar_x, "".join(slur_row))
            if rows["tie"] is not None:
                tie_row = tie_cells
                if spacing_mode == "auto":
                    content_width = max(1, display_width - barpad * 2)
                    tie_row = _scale_row(tie_cells, content_width, " ")
                    tie_row = _pad_row(tie_row, display_width, barpad)
                _safe_addstr(stdscr, row_start + (rows["tie"] or 0), bar_x, "".join(tie_row))
            if rows["hold"] is not None:
                hold_row = hold_cells
                if spacing_mode == "auto":
                    content_width = max(1, display_width - barpad * 2)
                    hold_row = _scale_row(hold_cells, content_width, " ")
                    hold_row = _pad_row(hold_row, display_width, barpad)
                _safe_addstr(stdscr, row_start + (rows["hold"] or 0), bar_x, "".join(hold_row))
            if bar.chords:
                positions = chord_positions(bar, bar_width, default_duration)
                flag_positions = (
                    _filter_redundant_positions(positions) if hide_redundant else positions
                )
                flagstyle = settings.get("flagstyle", "standard")
                stem = "I"
                flag = "\\"
                if flagstyle == "italian":
                    stem = "I"
                    flag = "/"
                elif flagstyle == "thin":
                    stem = "|"
                    flag = "/"
                elif flagstyle == "board":
                    stem = "|"
                    flag = "="
                elif flagstyle == "englishgrid":
                    stem = "|"
                    flag = "-"
                elif flagstyle == "continental":
                    stem = "Γ"
                    flag = "F"
                elif flagstyle == "capirola":
                    stem = "I"
                    flag = "-"
                if spacing_mode == "auto":
                    content_width = max(1, display_width - barpad * 2)
                    scaled_positions = [
                        (_scale_col(pos, bar_width, content_width), denom, dot)
                        for (pos, denom, dot) in flag_positions
                    ]
                    flag_cells = flag_row_style(
                        scaled_positions,
                        content_width,
                        stem=stem,
                        flag=flag,
                    )
                    flag_cells = _pad_row(flag_cells, display_width, barpad)
                    stem_cells = stem_row_style(
                        scaled_positions,
                        content_width,
                        stem=stem,
                    )
                    stem_cells = _pad_row(stem_cells, display_width, barpad)
                else:
                    flag_cells = flag_row_style(
                        flag_positions,
                        bar_width,
                        stem=stem,
                        flag=flag,
                    )
                    stem_cells = stem_row_style(flag_positions, bar_width, stem=stem)
                _safe_addstr(stdscr, row_start + (rows["flag"] or 0), bar_x, "".join(flag_cells))
                if rows.get("flag2") is not None:
                    _safe_addstr(
                        stdscr,
                        row_start + (rows["flag2"] or 0),
                        bar_x,
                        "".join(stem_cells),
                    )
                if show_dur and rows["dur"] is not None:
                    dur_cells = [" " for _ in range(bar_width)]
                    last: int | None = None
                    for col, denom, _dot in positions:
                        if hide_redundant:
                            if denom != last:
                                dur_cells[col] = duration_display(denom)
                                last = denom
                        else:
                            dur_cells[col] = duration_display(denom)
                    if spacing_mode == "auto":
                        content_width = max(1, display_width - barpad * 2)
                        dur_cells = _scale_row(dur_cells, content_width, " ")
                        dur_cells = _pad_row(dur_cells, display_width, barpad)
                    _safe_addstr(stdscr, row_start + (rows["dur"] or 0), bar_x, "".join(dur_cells))
                if abs_bar == cursor_bar:
                    for col, _denom, _dot in positions:
                        if col == cursor_col:
                            flag_y = row_start + (rows["flag"] or 0)
                            content_width = max(1, display_width - barpad * 2)
                            cursor_x = bar_x + barpad + _scale_col(
                                col,
                                bar_width,
                                content_width,
                            )
                            _safe_addstr(
                                stdscr,
                                flag_y,
                                cursor_x,
                                flag_cells[barpad + _scale_col(col, bar_width, content_width)],
                                A_BOLD,
                            )
                            if show_dur and rows["dur"] is not None:
                                dur_y = row_start + (rows["dur"] or 0)
                                dur_x = bar_x + barpad + _scale_col(
                                    col,
                                    bar_width,
                                    content_width,
                                )
                                _safe_addstr(
                                    stdscr,
                                    dur_y,
                                    dur_x,
                                    dur_cells[barpad + _scale_col(col, bar_width, content_width)],
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
                stem = "I"
                flag = "\\"
                if flagstyle == "italian":
                    stem = "I"
                    flag = "/"
                elif flagstyle == "thin":
                    stem = "|"
                    flag = "/"
                elif flagstyle == "board":
                    stem = "|"
                    flag = "="
                elif flagstyle == "englishgrid":
                    stem = "|"
                    flag = "-"
                elif flagstyle == "continental":
                    stem = "Γ"
                    flag = "F"
                elif flagstyle == "capirola":
                    stem = "I"
                    flag = "-"
                if spacing_mode == "auto":
                    content_width = max(1, display_width - barpad * 2)
                    scaled_positions = [
                        (_scale_col(col, bar_width, content_width), denom, dot)
                        for (col, denom, dot) in flag_positions
                    ]
                    flag_cells = flag_row_style(
                        scaled_positions,
                        content_width,
                        stem=stem,
                        flag=flag,
                    )
                    flag_cells = _pad_row(flag_cells, display_width, barpad)
                    stem_cells = stem_row_style(
                        scaled_positions,
                        content_width,
                        stem=stem,
                    )
                    stem_cells = _pad_row(stem_cells, display_width, barpad)
                else:
                    flag_cells = flag_row_style(
                        flag_positions,
                        bar_width,
                        stem=stem,
                        flag=flag,
                    )
                    stem_cells = stem_row_style(flag_positions, bar_width, stem=stem)
                _safe_addstr(stdscr, row_start + (rows["flag"] or 0), bar_x, "".join(flag_cells))
                if rows.get("flag2") is not None:
                    _safe_addstr(
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
                        dur_cells = _pad_row(dur_cells, display_width, barpad)
                    _safe_addstr(stdscr, row_start + (rows["dur"] or 0), bar_x, "".join(dur_cells))
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
                    row_cells = _scale_row(row_cells, content_width, fill_char)
                    row_cells = _pad_row(row_cells, display_width, barpad, pad_char=fill_char)
                row_text = "".join(row_cells)
                _safe_addstr(stdscr, y, bar_x, row_text)
                _safe_addstr(stdscr, y, bar_x + display_width, barline)

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
                    _safe_addstr(
                        stdscr,
                        y,
                        cell_x,
                        row_text[barpad + _scale_col(cursor_col, bar_width, content_width)],
                        A_REVERSE,
                    )
                for col in range(bar_width):
                    if (abs_bar, actual, col) in highlights:
                        content_width = max(1, display_width - barpad * 2)
                        hl_x = bar_x + barpad + _scale_col(
                            col,
                            bar_width,
                            content_width,
                        )
                        _safe_addstr(
                            stdscr,
                            y,
                            hl_x,
                            row_text[barpad + _scale_col(col, bar_width, content_width)],
                            A_BOLD,
                        )

            if spacing_mode == "auto":
                bar_x += display_width + bar_gap
            else:
                bar_x += bar_width + bar_gap

    if display_strings > 0:
        cursor_index = min(cursor_string, display_strings - 1)
        if reverse_strings:
            actual_cursor_string = display_indices[display_strings - 1 - cursor_index]
        else:
            actual_cursor_string = display_indices[cursor_index]
    else:
        actual_cursor_string = cursor_string
    dur_key = (cursor_bar, actual_cursor_string, cursor_col)
    dur_text = durations.get(dur_key)
    if dur_text is None:
        for s_idx in range(total_strings):
            alt_key = (cursor_bar, s_idx, cursor_col)
            if alt_key in durations:
                dur_text = durations[alt_key]
                break
    if dur_text is not None and (cursor_bar, cursor_col) in dotted:
        dur_text = f"{dur_text}."
    if dur_text is None and 0 <= cursor_bar < len(piece.bars):
        bar = piece.bars[cursor_bar]
        if bar.chords:
            positions = chord_positions(bar, bar_width, default_duration)
            for col, denom, _dot in positions:
                if col == cursor_col:
                    dur_text = denom
                    break
    status = f"{mode}"
    if mode == "command":
        status = f":{cmdline}"
    if mode == "search":
        status = f"/{searchline}"
    if mode == "help":
        status = "help  j/k scroll  q close"
    if dur_text and mode not in ("command", "search"):
        status = f"{status}  len:{dur_text}"
    if message and mode not in ("command", "search"):
        status = f"{status}  {message}"
    status_line_text = status_line
    if message and mode in ("command", "search"):
        status_line_text = message
    _safe_addstr(stdscr, height - 1, 0, _clean_text(status), status_attr)
    _safe_addstr(stdscr, height - 2, 0, _clean_text(status_line_text), status_attr)

    if mode == "help":
        stdscr.erase()
        _render_help(stdscr, status, status_attr, help_offset)

    stdscr.refresh()
