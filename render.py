from __future__ import annotations

import curses
from typing import Dict, List, Tuple

from model import Bar, Piece
from render_utils import (
    bar_cells,
    bar_cells_from_chords,
    chord_positions,
    duration_display,
    duration_flag,
    flag_positions_from_durations,
    flag_row,
)


def _safe_addstr(stdscr: curses.window, y: int, x: int, text: str, attr: int = 0) -> None:
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
    except curses.error:
        return
    except ValueError:
        return


def _clean_text(text: str) -> str:
    return "".join(ch if 32 <= ord(ch) <= 126 else " " for ch in text)

def _parse_time_signature(value: str) -> tuple[int, int, str]:
    text = value.strip()
    if text in ("C", "c", "4/4"):
        return 4, 4, "C"
    if text in ("O", "o", "3/4"):
        return 3, 4, "O"
    if "/" in text:
        parts = text.split("/", 1)
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            beats = int(parts[0])
            unit = int(parts[1])
            return max(1, beats), max(1, unit), f"{beats}/{unit}"
    return 0, 0, ""


def _tactus_row(bar_width: int, beats: int) -> List[str]:
    row = [" " for _ in range(bar_width)]
    if beats <= 0:
        return row
    for i in range(beats):
        pos = int(i * bar_width / beats)
        if 0 <= pos < bar_width:
            row[pos] = "|"
    return row

def _bar_number_for_index(
    piece: Piece, bar_index: int, measures: str, countdots: str
) -> str | None:
    extra = 0
    if countdots == "on":
        for idx in range(bar_index + 1):
            if piece.bars[idx].repeat == ".":
                extra += 1
    if measures == "every":
        return str(bar_index + 1 + extra)
    if measures == "five":
        number = bar_index + 1 + extra
        return str(number) if number % 5 == 0 else None
    if measures == "start":
        return str(bar_index + 1 + extra) if bar_index == 0 else None
    return None


def _bar_durations(
    durations: Dict[Tuple[int, int, int], int],
    bar_index: int,
    strings: int,
    bar_width: int,
    default_duration: int,
) -> List[str]:
    row = [" " for _ in range(bar_width)]
    last: int | None = None
    for col in range(bar_width):
        found = None
        for s_idx in range(strings):
            key = (bar_index, s_idx, col)
            if key in durations:
                denom = durations[key]
                if found is None or denom > found:
                    found = denom
        if found is None:
            found = default_duration
        if found != last:
            row[col] = duration_display(found)
            last = found
    return row


def _layout_rows(height: int, strings: int) -> dict[str, int | None]:
    available = height - 2
    if available <= 0:
        return {"header": None, "meta": None, "staff": None}
    if available <= strings:
        return {"header": None, "meta": None, "staff": 0}
    header_row = 0
    remaining = available - 1
    meta_row = None
    if remaining - 1 >= strings:
        meta_row = header_row + 1
        remaining -= 1
    optional = ["dur", "flag", "tactus", "slur", "tie", "hold", "orn", "ann"]
    rows: dict[str, int | None] = {
        "header": header_row,
        "meta": meta_row,
        "staff": None,
        "dur": None,
        "flag": None,
        "tactus": None,
        "slur": None,
        "tie": None,
        "hold": None,
        "orn": None,
        "ann": None,
    }
    current = header_row + 1
    if meta_row is not None:
        current += 1
    for name in optional:
        if remaining - 1 >= strings:
            rows[name] = current
            current += 1
            remaining -= 1
    rows["staff"] = current
    return rows


def _layout_block_rows(
    strings: int,
    include_meta: bool,
    show_dur: bool,
    show_extras: bool,
    show_tactus: bool,
) -> dict[str, int | None]:
    rows: dict[str, int | None] = {
        "meta": None,
        "ann": None,
        "orn": None,
        "tactus": None,
        "slur": None,
        "tie": None,
        "hold": None,
        "flag": None,
        "dur": None,
        "staff": None,
    }
    current = 0
    if include_meta:
        rows["meta"] = current
        current += 1
        if show_extras:
            rows["ann"] = current
            current += 1
            rows["orn"] = current
            current += 1
    if show_tactus:
        rows["tactus"] = current
        current += 1
    if show_extras:
        rows["slur"] = current
        current += 1
        rows["tie"] = current
        current += 1
        rows["hold"] = current
        current += 1
    rows["flag"] = current
    current += 1
    if show_dur:
        rows["dur"] = current
        current += 1
    rows["staff"] = current
    return rows


def _block_height(
    include_meta: bool,
    strings: int,
    show_dur: bool,
    show_extras: bool,
    show_tactus: bool,
) -> int:
    base = 0
    if include_meta:
        base += 1
        if show_extras:
            base += 2
    if show_tactus:
        base += 1
    if show_extras:
        base += 3
    base += 1
    if show_dur:
        base += 1
    return base + strings
def _bar_annotations(
    annotations: Dict[Tuple[int, int], str],
    bar_index: int,
    bar_width: int,
) -> List[str]:
    row = [" " for _ in range(bar_width)]
    for col in range(bar_width):
        key = (bar_index, col)
        if key in annotations:
            text = annotations[key]
            if text:
                row[col] = text[0]
    return row


def _bar_ornaments(
    ornaments: Dict[Tuple[int, int], str],
    bar_index: int,
    bar_width: int,
) -> List[str]:
    row = [" " for _ in range(bar_width)]
    for col in range(bar_width):
        key = (bar_index, col)
        if key in ornaments:
            row[col] = ornaments[key]
    return row


def _bar_span_row(
    spans: List[Tuple[int, int, int]],
    bar_index: int,
    bar_width: int,
    start_char: str,
    end_char: str,
    fill_char: str,
) -> List[str]:
    row = [" " for _ in range(bar_width)]
    for b, start, end in spans:
        if b != bar_index:
            continue
        if 0 <= start < bar_width:
            row[start] = start_char
        if 0 <= end < bar_width:
            row[end] = end_char
        for col in range(start + 1, min(end, bar_width - 1)):
            row[col] = fill_char
    return row


def _bar_flags(
    durations: Dict[Tuple[int, int, int], int],
    bar_index: int,
    strings: int,
    bar_width: int,
    default_duration: int,
) -> List[str]:
    row = [" " for _ in range(bar_width)]
    last: int | None = None
    for col in range(bar_width):
        found = None
        for s_idx in range(strings):
            key = (bar_index, s_idx, col)
            if key in durations:
                denom = durations[key]
                if found is None or denom > found:
                    found = denom
        if found is None:
            found = default_duration
        if found != last:
            row[col] = duration_flag(found)
            last = found
    return row


def build_bar_view(
    bar: Bar,
    overrides: Dict[Tuple[int, int, int], str],
    durations: Dict[Tuple[int, int, int], int],
    ornaments: Dict[Tuple[int, int], str],
    annotations: Dict[Tuple[int, int], str],
    slurs: List[Tuple[int, int, int]],
    ties: List[Tuple[int, int, int]],
    holds: List[Tuple[int, int, int]],
    bar_index: int,
    strings: int,
    bar_width: int,
    default_duration: int,
    style: str = "french",
) -> dict[str, List[str]]:
    cells = bar_cells(bar, strings, bar_width, style)
    for s_idx in range(strings):
        for col in range(bar_width):
            key = (bar_index, s_idx, col)
            if key in overrides:
                cells[s_idx][col] = overrides[key]
    flag_cells = _bar_flags(durations, bar_index, strings, bar_width, default_duration)
    dur_cells = _bar_durations(durations, bar_index, strings, bar_width, default_duration)
    ann_cells = _bar_annotations(annotations, bar_index, bar_width)
    orn_cells = _bar_ornaments(ornaments, bar_index, bar_width)
    slur_cells = _bar_span_row(slurs, bar_index, bar_width, "(", ")", "~")
    tie_cells = _bar_span_row(ties, bar_index, bar_width, "[", "]", "-")
    hold_cells = _bar_span_row(holds, bar_index, bar_width, "<", ">", "_")
    rows = ["".join(cells[s_idx]) for s_idx in range(strings)]
    return {
        "ann": ["".join(ann_cells)],
        "orn": ["".join(orn_cells)],
        "slur": ["".join(slur_cells)],
        "tie": ["".join(tie_cells)],
        "hold": ["".join(hold_cells)],
        "flag": ["".join(flag_cells)],
        "dur": ["".join(dur_cells)],
        "rows": rows,
    }


def _render_ascii_preview(
    stdscr: curses.window,
    ascii_lines: List[str],
    status_line: str,
    mode: str,
    status_attr: int,
) -> None:
    height, _width = stdscr.getmaxyx()
    for idx, line in enumerate(ascii_lines[: max(0, height - 2)]):
        _safe_addstr(stdscr, idx, 0, _clean_text(line))
    _safe_addstr(stdscr, height - 2, 0, _clean_text(status_line), status_attr)
    _safe_addstr(stdscr, height - 1, 0, _clean_text(f"{mode}  ascii preview"), status_attr)


def _help_lines() -> List[str]:
    return [
        "Help",
        "",
        "Hotkeys",
        "h/j/k/l or arrows  move",
        "w/b               next/prev bar, e end bar",
        "{/}               prev/next row",
        "i or Enter        insert",
        "r                 replace one",
        "/                 search bar",
        ":                 command",
        "?                 help",
        "q                 quit",
        "j/k               scroll help",
        "p                 print pdf (lilypond)",
        "m                 export+play midi",
        "",
        "Insert mode",
        "french frets a-p; italian frets 0-9/x",
        "durations: 1-7 (french) or w/h/q/e/s/t (italian)",
        "esc               normal",
        "",
        "Commands",
        ":w [path]         write .tab",
        ":wa [path]        write ascii",
        ":e <path>         open",
        ":set style=... strings=... measures=... tuning=... flagstyle=... time=...",
        ":set key=... countdots=on/off",
        ":set keys=vim|vim+arrows spacing=... linelen=... staffthick=... fontstyle=...",
        ":set charstyle=...",
        ":set italianorient=normal|reverse frenchc=normal|alt frenche=normal|tail",
        ":set midipatch=... tempo=... grid=on/off",
        ":convert french|italian",
        ":barline thin|thick|double|hidden|pale",
        ":repeat none|start|end|dots",
        ":orn <char>|clear   :annot <text>|clear   :highlight on/off",
        ":slur start/end/clear  :tie start/end/clear  :hold start/end/clear",
        "Tab               complete command/path",
        ":ascii on/off  :midi [path]  :play [bar]  :lilypond [path]",
    ]


def _render_help(
    stdscr: curses.window,
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


def render_piece(
    stdscr: curses.window,
    piece: Piece,
    bar_offset: int,
    cursor_bar: int,
    cursor_string: int,
    cursor_col: int,
    bar_width: int,
    overrides: Dict[Tuple[int, int, int], str],
    durations: Dict[Tuple[int, int, int], int],
    ornaments: Dict[Tuple[int, int], str],
    annotations: Dict[Tuple[int, int], str],
    highlights: set[Tuple[int, int, int]],
    slurs: List[Tuple[int, int, int]],
    ties: List[Tuple[int, int, int]],
    holds: List[Tuple[int, int, int]],
    mode: str,
    cmdline: str,
    message: str,
    status_line: str,
    searchline: str,
    settings: Dict[str, str],
    ascii_lines: List[str] | None,
    help_offset: int = 0,
) -> None:
    stdscr.erase()
    height, width = stdscr.getmaxyx()
    strings = piece.strings

    status_attr = curses.A_REVERSE

    if ascii_lines is not None:
        _render_ascii_preview(stdscr, ascii_lines, status_line, mode, status_attr)
        stdscr.refresh()
        return

    header = f"{piece.title or 'Untitled'}  [{len(piece.bars)} bars]"
    header_row = 0
    _safe_addstr(stdscr, header_row, 0, _clean_text(header))

    left_margin = 3
    bar_gap = 2
    usable_width = max(0, width - left_margin)
    bars_per_screen = max(1, usable_width // (bar_width + bar_gap))

    include_meta = True
    show_dur = settings.get("showdur", "off") == "on"
    show_extras = settings.get("showextras", "off") == "on"
    show_tactus = settings.get("showtactus", "off") == "on"
    reverse_strings = (
        settings.get("style", "french") == "italian"
        and settings.get("italianorient", "normal") == "reverse"
    )
    block_h = _block_height(include_meta, strings, show_dur, show_extras, show_tactus)
    available = max(0, height - 2 - 1)
    systems = max(1, available // block_h)
    bars_per_line = max(1, usable_width // (bar_width + bar_gap))
    total_bars = len(piece.bars)
    default_duration = 4

    for sys_idx in range(systems):
        row_start = header_row + 1 + sys_idx * block_h
        rows = _layout_block_rows(strings, include_meta, show_dur, show_extras, show_tactus)
        bar_start = bar_offset + sys_idx * bars_per_line
        if bar_start >= total_bars:
            break
        bar_end = min(total_bars, bar_start + bars_per_line)
        for s_idx in range(strings):
            actual = strings - 1 - s_idx if reverse_strings else s_idx
            label_value = strings - actual
            label = f"{label_value:>2}"
            _safe_addstr(stdscr, row_start + (rows["staff"] or 0) + s_idx, 0, label)

        for local_idx, bar in enumerate(piece.bars[bar_start:bar_end]):
            abs_bar = bar_start + local_idx
            style = settings.get("style", "french")
            french_c = settings.get("frenchc", "normal")
            french_e = settings.get("frenche", "normal")
            cells = (
                bar_cells_from_chords(
                    bar,
                    strings,
                    bar_width,
                    default_duration,
                    style,
                    french_c=french_c,
                    french_e=french_e,
                )
                if bar.chords
                else bar_cells(
                    bar,
                    strings,
                    bar_width,
                    style,
                    french_c=french_c,
                    french_e=french_e,
                )
            )
            measures = settings.get("measures", "start")
            countdots = settings.get("countdots", "off")
            number = _bar_number_for_index(piece, abs_bar, measures, countdots)
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
            for s_idx in range(strings):
                for col in range(bar_width):
                    key = (abs_bar, s_idx, col)
                    if key in overrides:
                        cells[s_idx][col] = overrides[key]
            bar_x = left_margin + local_idx * (bar_width + bar_gap)
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
                _safe_addstr(stdscr, row_start + (rows["ann"] or 0), bar_x, "".join(ann_cells))
            if rows["orn"] is not None:
                _safe_addstr(stdscr, row_start + (rows["orn"] or 0), bar_x, "".join(orn_cells))
            if rows["tactus"] is not None:
                _safe_addstr(stdscr, row_start + (rows["tactus"] or 0), bar_x, "".join(tactus))
            if rows["slur"] is not None:
                _safe_addstr(stdscr, row_start + (rows["slur"] or 0), bar_x, "".join(slur_cells))
            if rows["tie"] is not None:
                _safe_addstr(stdscr, row_start + (rows["tie"] or 0), bar_x, "".join(tie_cells))
            if rows["hold"] is not None:
                _safe_addstr(stdscr, row_start + (rows["hold"] or 0), bar_x, "".join(hold_cells))
            if bar.chords:
                positions = chord_positions(bar, bar_width, default_duration)
                flag_cells = flag_row(positions, bar_width)
                _safe_addstr(stdscr, row_start + (rows["flag"] or 0), bar_x, "".join(flag_cells))
                if show_dur and rows["dur"] is not None:
                    dur_cells = [" " for _ in range(bar_width)]
                    last: int | None = None
                    for col, denom, _dot in positions:
                        if denom != last:
                            dur_cells[col] = duration_display(denom)
                            last = denom
                    _safe_addstr(stdscr, row_start + (rows["dur"] or 0), bar_x, "".join(dur_cells))
                if abs_bar == cursor_bar:
                    for col, _denom, _dot in positions:
                        if col == cursor_col:
                            flag_y = row_start + (rows["flag"] or 0)
                            _safe_addstr(
                                stdscr,
                                flag_y,
                                bar_x + col,
                                flag_cells[col],
                                curses.A_BOLD,
                            )
                            if show_dur and rows["dur"] is not None:
                                dur_y = row_start + (rows["dur"] or 0)
                                _safe_addstr(
                                    stdscr,
                                    dur_y,
                                    bar_x + col,
                                    dur_cells[col],
                                    curses.A_BOLD,
                                )
                            break
            else:
                flag_positions = flag_positions_from_durations(
                    durations,
                    abs_bar,
                    strings,
                    bar_width,
                    default_duration,
                )
                flag_cells = flag_row(flag_positions, bar_width)
                _safe_addstr(stdscr, row_start + (rows["flag"] or 0), bar_x, "".join(flag_cells))
                if show_dur and rows["dur"] is not None:
                    dur_cells = _bar_durations(
                        durations,
                        abs_bar,
                        strings,
                        bar_width,
                        default_duration,
                    )
                    _safe_addstr(stdscr, row_start + (rows["dur"] or 0), bar_x, "".join(dur_cells))
            for s_idx in range(strings):
                actual = strings - 1 - s_idx if reverse_strings else s_idx
                y = row_start + (rows["staff"] or 0) + s_idx
                row_text = "".join(cells[actual])
                _safe_addstr(stdscr, y, bar_x, row_text)
                _safe_addstr(stdscr, y, bar_x + bar_width, barline)

                if (
                    abs_bar == cursor_bar
                    and s_idx == cursor_string
                    and 0 <= cursor_col < bar_width
                ):
                    cell_x = bar_x + cursor_col
                    _safe_addstr(
                        stdscr,
                        y,
                        cell_x,
                        row_text[cursor_col],
                        curses.A_REVERSE,
                    )
                for col in range(bar_width):
                    if (abs_bar, actual, col) in highlights:
                        _safe_addstr(stdscr, y, bar_x + col, row_text[col], curses.A_BOLD)

            if (
                abs_bar == cursor_bar
                and s_idx == cursor_string
                and 0 <= cursor_col < bar_width
            ):
                cell_x = bar_x + cursor_col
                _safe_addstr(
                    stdscr,
                    y,
                    cell_x,
                    row_text[cursor_col],
                    curses.A_REVERSE,
                )
            for col in range(bar_width):
                if (abs_bar, actual, col) in highlights:
                    _safe_addstr(stdscr, y, bar_x + col, row_text[col], curses.A_BOLD)

    actual_cursor_string = strings - 1 - cursor_string if reverse_strings else cursor_string
    dur_key = (cursor_bar, actual_cursor_string, cursor_col)
    dur_text = durations.get(dur_key)
    if dur_text is None:
        for s_idx in range(strings):
            alt_key = (cursor_bar, s_idx, cursor_col)
            if alt_key in durations:
                dur_text = durations[alt_key]
                break
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
    _safe_addstr(stdscr, height - 1, 0, _clean_text(status), status_attr)
    _safe_addstr(stdscr, height - 2, 0, _clean_text(status_line), status_attr)

    if mode == "help":
        stdscr.erase()
        _render_help(stdscr, status, status_attr, help_offset)

    stdscr.refresh()
