from __future__ import annotations

import curses

from core.model import Bar, Piece
from core.render_utils import (
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


def _tuning_labels(tuning: str, strings: int, *, show_octaves: bool) -> list[str]:
    if not tuning:
        return [str(strings - idx) for idx in range(strings)]
    labels: list[str] = []
    idx = 0
    while idx < len(tuning) and len(labels) < strings:
        ch = tuning[idx]
        if ch.isalpha():
            note = ch
            idx += 1
            accidental = ""
            if idx < len(tuning) and tuning[idx] in "+-#b":
                accidental = tuning[idx]
                idx += 1
            digits = ""
            while idx < len(tuning) and tuning[idx].isdigit():
                digits += tuning[idx]
                idx += 1
            label = f"{note}{accidental}"
            if show_octaves and digits:
                label += digits
            label = label.strip()
            labels.append(label if label else note)
        else:
            idx += 1
    if len(labels) < strings:
        labels.extend(str(strings - idx) for idx in range(len(labels), strings))
    labels = labels[:strings]
    labels.reverse()
    return labels


def _scale_col(col: int, src_width: int, dest_width: int) -> int:
    if dest_width <= 1:
        return 0
    if src_width <= 1:
        return 0
    return min(dest_width - 1, (col * (dest_width - 1)) // (src_width - 1))


def _scale_row(row: list[str], dest_width: int, fill_char: str) -> list[str]:
    if dest_width <= 0:
        return []
    scaled = [fill_char for _ in range(dest_width)]
    src_width = len(row)
    if src_width <= 0:
        return scaled
    for src_col, ch in enumerate(row):
        if ch == fill_char:
            continue
        dest_col = _scale_col(src_col, src_width, dest_width)
        scaled[dest_col] = ch
    return scaled


def _bar_note_columns(
    overrides: dict[tuple[int, int, int], str],
    durations: dict[tuple[int, int, int], int],
    bar_index: int,
) -> set[int]:
    cols: set[int] = set()
    for (b, _s, col) in overrides:
        if b == bar_index:
            cols.add(col)
    for (b, _s, col) in durations:
        if b == bar_index:
            cols.add(col)
    return cols


def _bar_display_width(
    bar: Bar,
    bar_index: int,
    bar_width: int,
    overrides: dict[tuple[int, int, int], str],
    durations: dict[tuple[int, int, int], int],
    default_duration: int,
) -> int:
    if bar.chords:
        count = len(chord_positions(bar, bar_width, default_duration))
    else:
        count = len(_bar_note_columns(overrides, durations, bar_index=bar_index))
    count = max(1, count)
    return max(3, (count * 2) + 1)


def _bars_fit(
    bars: list[Bar],
    start: int,
    bar_gap: int,
    usable_width: int,
    bar_width: int,
    overrides: dict[tuple[int, int, int], str],
    durations: dict[tuple[int, int, int], int],
    default_duration: int,
    max_chords: int = 0,
) -> int:
    used = 0
    count = 0
    chord_total = 0
    for idx in range(start, len(bars)):
        bar = bars[idx]
        width = _bar_display_width(
            bar,
            idx,
            bar_width,
            overrides,
            durations,
            default_duration,
        )
        if bar.chords:
            chord_count = len(chord_positions(bar, bar_width, default_duration))
        else:
            chord_count = len(_bar_note_columns(overrides, durations, bar_index=idx))
        needed = width if count == 0 else width + bar_gap
        if max_chords > 0 and chord_total + chord_count > max_chords and count > 0:
            break
        if used + needed > usable_width and count > 0:
            break
        used += needed
        count += 1
        chord_total += chord_count
    return max(1, count)


def _next_system_start(
    bars: list[Bar],
    start: int,
    bars_per_line: int,
    breaks: set[int],
) -> int:
    next_break = min((b for b in breaks if b > start), default=len(bars))
    return min(next_break, start + bars_per_line)

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


def _tactus_row(bar_width: int, beats: int) -> list[str]:
    row = [" " for _ in range(bar_width)]
    if beats <= 0:
        return row
    for i in range(beats):
        pos = int(i * bar_width / beats)
        if 0 <= pos < bar_width:
            row[pos] = "|"
    return row


def _filter_redundant_positions(
    positions: list[tuple[int, int, bool]],
) -> list[tuple[int, int, bool]]:
    filtered: list[tuple[int, int, bool]] = []
    last: tuple[int, bool] | None = None
    for col, denom, dot in positions:
        current = (denom, dot)
        if current != last:
            filtered.append((col, denom, dot))
            last = current
    return filtered

def _bar_number_for_index(
    piece: Piece, bar_index: int, measures: str, countdots: str, step: int
) -> str | None:
    extra = 0
    if countdots == "on":
        for idx in range(bar_index + 1):
            if piece.bars[idx].repeat == ".":
                extra += 1
    number = bar_index + 1 + extra
    if measures == "every":
        return f"[{number}]" if step <= 1 or (number - 1) % step == 0 else None
    if measures == "five":
        return f"[{number}]" if number % 5 == 0 else None
    if measures == "start":
        return f"[{number}]" if bar_index == 0 else None
    return None


def _bar_durations(
    durations: dict[tuple[int, int, int], int],
    bar_index: int,
    strings: int,
    bar_width: int,
    default_duration: int,
    hide_redundant: bool = True,
) -> list[str]:
    row = [" " for _ in range(bar_width)]
    last: int | None = None
    for col in range(bar_width):
        found = None
        explicit = False
        for s_idx in range(strings):
            key = (bar_index, s_idx, col)
            if key in durations:
                explicit = True
                denom = durations[key]
                if found is None or denom > found:
                    found = denom
        if found is None:
            found = default_duration
        if hide_redundant:
            if found != last or explicit:
                row[col] = duration_display(found)
                last = found
        else:
            row[col] = duration_display(found)
    return row


def _flag_positions_all(
    durations: dict[tuple[int, int, int], int],
    bar_index: int,
    strings: int,
    bar_width: int,
    default_duration: int,
    dotted: set[tuple[int, int]] | None = None,
) -> list[tuple[int, int, bool]]:
    positions: list[tuple[int, int, bool]] = []
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
        is_dotted = dotted is not None and (bar_index, col) in dotted
        positions.append((col, found, is_dotted))
    return positions


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
    annotations: dict[tuple[int, int], str],
    bar_index: int,
    bar_width: int,
) -> list[str]:
    row = [" " for _ in range(bar_width)]
    for col in range(bar_width):
        key = (bar_index, col)
        if key in annotations:
            text = annotations[key]
            if text:
                row[col] = text[0]
    return row


def _bar_ornaments(
    ornaments: dict[tuple[int, int], str],
    bar_index: int,
    bar_width: int,
) -> list[str]:
    row = [" " for _ in range(bar_width)]
    for col in range(bar_width):
        key = (bar_index, col)
        if key in ornaments:
            row[col] = ornaments[key]
    return row


def _bar_span_row(
    spans: list[tuple[int, int, int]],
    bar_index: int,
    bar_width: int,
    start_char: str,
    end_char: str,
    fill_char: str,
) -> list[str]:
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
    durations: dict[tuple[int, int, int], int],
    bar_index: int,
    strings: int,
    bar_width: int,
    default_duration: int,
    hide_redundant: bool = True,
) -> list[str]:
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
        if hide_redundant:
            if found != last:
                row[col] = duration_flag(found)
                last = found
        else:
            row[col] = duration_flag(found)
    return row


def build_bar_view(
    bar: Bar,
    overrides: dict[tuple[int, int, int], str],
    durations: dict[tuple[int, int, int], int],
    ornaments: dict[tuple[int, int], str],
    annotations: dict[tuple[int, int], str],
    slurs: list[tuple[int, int, int]],
    ties: list[tuple[int, int, int]],
    holds: list[tuple[int, int, int]],
    bar_index: int,
    strings: int,
    bar_width: int,
    default_duration: int,
    style: str = "french",
    hide_redundant: bool = True,
) -> dict[str, list[str]]:
    cells = bar_cells(bar, strings, bar_width, style)
    for s_idx in range(strings):
        for col in range(bar_width):
            key = (bar_index, s_idx, col)
            if key in overrides:
                cells[s_idx][col] = overrides[key]
    flag_cells = _bar_flags(
        durations,
        bar_index,
        strings,
        bar_width,
        default_duration,
        hide_redundant=hide_redundant,
    )
    dur_cells = _bar_durations(
        durations,
        bar_index,
        strings,
        bar_width,
        default_duration,
        hide_redundant=hide_redundant,
    )
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
    return [
        "HELP",
        "",
        "NAVIGATION                              EDITING",
        "Up   k / ^P / Up                        Insert   i / Enter",
        "Down j / ^N / Down                      Replace  r (one)",
        "Left h / ^B / Left                      Delete   x / [count]x",
        "Right l / ^F / Right                    Clear    Space (insert)",
        "Row  { / } / PgUp / PgDn                Yank     yy  Paste  p",
        "Bar  w / b / , / .                      Delete  dd (bar)",
        "Undo u / Redo ^R                         Bar     o/O  +/-",
        "Top  gg / g                             Help    ? / F1",
        "Flags f (cycle style)                   Letters F (c), E (e)",
        "End  G / $                              Command : / Search /",
        "",
        "INSERT MODE",
        "Frets: french a-p, italian 0-9/x",
        "Durations: 1 2 4 8 6 3 (french) or Ctrl+1..7 (italian), . toggles dot",
        "Barline: | sets thin barline",
        "Esc returns to normal",
        "",
        "COMMANDS",
        ":w [path]        write .tab       :wa [path]        write ascii",
        ":wq/:x           write + quit     :q!               quit without save",
        ":e <path>        open             :source [path]    view file with less",
        ":time <sig>      set time sig     :verify           check measure length",
        ":undo             undo             :redo             redo",
        ":title <text>     set title        :author <text>     set author",
        ":subtitle <text>  set subtitle     :composer <text>   set composer",
        ":footnote <text>  set footnote     :header            insert header template",
        ":midi [path]     export midi      :play [bar] [tempo] play from bar",
        ":lilypond [path] export lilypond  :pdf              compile pdf (P)",
        ":midicmd [path]  show midi command",
        ":bar add|before|after|del         :barline thin|thick|double|hidden|pale",
        ":repeat none|start|end|dots       :orn <char>|clear",
        ":annot <text>|clear               :highlight on/off",
        ":slur start/end/clear             :tie start/end/clear",
        ":hold start/end/clear",
        ":set style=... strings=... tuning=... tuninglabels=... flagstyle=... time=...",
        ":set keys=vim|vim+arrows|casual|casual+arrows",
        (
            ":set spacing=... maxbars=... maxchords=... bargap=... "
            "linelen=... staffthick=... fontstyle=..."
        ),
        ":set flagredundant=on|off",
        ":set spacingmode=packed|spread|auto",
        ":set key=... countdots=on/off grid=on/off",
        ":set measuresstep=... (used with measures=every)",
        ":set italianorient=normal|reverse frenchc=normal|alt frenche=normal|tail",
        ":set midipatch=... midigate=... soundfont=... tempo=...",
        ":set charstyle=... title=... author=... composer=...",
        ":tool reflow|gridflags|comments",
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


def render_piece(  # noqa: PLR0912
    stdscr: curses.window,
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
    spacing_mode = settings.get("spacingmode", "packed")
    bargap = settings.get("bargap", "")
    if bargap.isdigit():
        bar_gap = max(0, int(bargap))
    else:
        bar_gap = 1 if spacing_mode in ("packed", "auto") else 3
    max_width = width
    linelen = settings.get("linelen", "")
    if linelen.isdigit():
        max_width = min(max_width, max(1, int(linelen)))
    usable_width = max(0, max_width - left_margin)

    default_duration = 4
    include_meta = True
    show_dur = settings.get("showdur", "off") == "on"
    show_extras = settings.get("showextras", "off") == "on"
    show_tactus = settings.get("showtactus", "off") == "on"
    hide_redundant = settings.get("flagredundant", "on") == "on"
    reverse_strings = (
        settings.get("style", "french") == "italian"
        and settings.get("italianorient", "normal") == "reverse"
    )
    show_octaves = settings.get("tuninglabels", "relative") == "absolute"
    tuning_labels = _tuning_labels(
        settings.get("tuning", ""),
        strings,
        show_octaves=show_octaves,
    )
    block_h = _block_height(include_meta, strings, show_dur, show_extras, show_tactus)
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
            max_chords=max_chords,
        )
    else:
        bars_per_line = max(1, usable_width // (bar_width + bar_gap))
    maxbars = settings.get("maxbars", "")
    if maxbars.isdigit():
        limit = int(maxbars)
        if limit > 0:
            bars_per_line = min(bars_per_line, limit)
    total_bars = len(piece.bars)

    for sys_idx in range(systems):
        row_start = header_row + 1 + sys_idx * block_h
        rows = _layout_block_rows(strings, include_meta, show_dur, show_extras, show_tactus)
        bar_start = bar_offset
        for _ in range(sys_idx):
            bar_start = _next_system_start(piece.bars, bar_start, bars_per_line, stave_breaks)
        if bar_start >= total_bars:
            break
        bar_end = _next_system_start(piece.bars, bar_start, bars_per_line, stave_breaks)
        bar_end = min(total_bars, bar_end)
        for s_idx in range(strings):
            actual = strings - 1 - s_idx if reverse_strings else s_idx
            if actual < len(tuning_labels):
                label_value = tuning_labels[actual]
            else:
                label_value = str(strings - actual)
            if len(label_value) > 2:
                label_value = label_value[:2]
            label = f"{label_value:>2}"
            _safe_addstr(stdscr, row_start + (rows["staff"] or 0) + s_idx, 0, label)

        bar_x = left_margin
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
            for s_idx in range(strings):
                for col in range(bar_width):
                    key = (abs_bar, s_idx, col)
                    if key in overrides:
                        cells[s_idx][col] = overrides[key]
            display_width = bar_width
            if spacing_mode == "auto":
                display_width = _bar_display_width(
                    bar,
                    abs_bar,
                    bar_width,
                    overrides,
                    durations,
                    default_duration,
                )
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
                    ann_row = _scale_row(ann_cells, display_width, " ")
                _safe_addstr(stdscr, row_start + (rows["ann"] or 0), bar_x, "".join(ann_row))
            if rows["orn"] is not None:
                orn_row = orn_cells
                if spacing_mode == "auto":
                    orn_row = _scale_row(orn_cells, display_width, " ")
                _safe_addstr(stdscr, row_start + (rows["orn"] or 0), bar_x, "".join(orn_row))
            if rows["tactus"] is not None:
                tactus_row = tactus
                if spacing_mode == "auto":
                    tactus_row = _scale_row(tactus, display_width, " ")
                _safe_addstr(
                    stdscr, row_start + (rows["tactus"] or 0), bar_x, "".join(tactus_row)
                )
            if rows["slur"] is not None:
                slur_row = slur_cells
                if spacing_mode == "auto":
                    slur_row = _scale_row(slur_cells, display_width, " ")
                _safe_addstr(stdscr, row_start + (rows["slur"] or 0), bar_x, "".join(slur_row))
            if rows["tie"] is not None:
                tie_row = tie_cells
                if spacing_mode == "auto":
                    tie_row = _scale_row(tie_cells, display_width, " ")
                _safe_addstr(stdscr, row_start + (rows["tie"] or 0), bar_x, "".join(tie_row))
            if rows["hold"] is not None:
                hold_row = hold_cells
                if spacing_mode == "auto":
                    hold_row = _scale_row(hold_cells, display_width, " ")
                _safe_addstr(stdscr, row_start + (rows["hold"] or 0), bar_x, "".join(hold_row))
            if bar.chords:
                positions = chord_positions(bar, bar_width, default_duration)
                flag_positions = (
                    _filter_redundant_positions(positions) if hide_redundant else positions
                )
                if spacing_mode == "auto":
                    scaled_positions = [
                        (_scale_col(pos, bar_width, display_width), denom, dot)
                        for (pos, denom, dot) in flag_positions
                    ]
                    flag_cells = flag_row(scaled_positions, display_width)
                else:
                    flag_cells = flag_row(flag_positions, bar_width)
                _safe_addstr(stdscr, row_start + (rows["flag"] or 0), bar_x, "".join(flag_cells))
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
                        dur_cells = _scale_row(dur_cells, display_width, " ")
                    _safe_addstr(stdscr, row_start + (rows["dur"] or 0), bar_x, "".join(dur_cells))
                if abs_bar == cursor_bar:
                    for col, _denom, _dot in positions:
                        if col == cursor_col:
                            flag_y = row_start + (rows["flag"] or 0)
                            cursor_x = bar_x + _scale_col(col, bar_width, display_width)
                            _safe_addstr(
                                stdscr,
                                flag_y,
                                cursor_x,
                                flag_cells[_scale_col(col, bar_width, display_width)],
                                curses.A_BOLD,
                            )
                            if show_dur and rows["dur"] is not None:
                                dur_y = row_start + (rows["dur"] or 0)
                                dur_x = bar_x + _scale_col(col, bar_width, display_width)
                                _safe_addstr(
                                    stdscr,
                                    dur_y,
                                    dur_x,
                                    dur_cells[_scale_col(col, bar_width, display_width)],
                                    curses.A_BOLD,
                                )
                            break
            else:
                if hide_redundant:
                    flag_positions = flag_positions_from_durations(
                        durations,
                        abs_bar,
                        strings,
                        bar_width,
                        default_duration,
                        dotted=dotted,
                    )
                    flag_positions = _filter_redundant_positions(flag_positions)
                else:
                    flag_positions = _flag_positions_all(
                        durations,
                        abs_bar,
                        strings,
                        bar_width,
                        default_duration,
                        dotted=dotted,
                    )
                if spacing_mode == "auto":
                    scaled_positions = [
                        (_scale_col(col, bar_width, display_width), denom, dot)
                        for (col, denom, dot) in flag_positions
                    ]
                    flag_cells = flag_row(scaled_positions, display_width)
                else:
                    flag_cells = flag_row(flag_positions, bar_width)
                _safe_addstr(stdscr, row_start + (rows["flag"] or 0), bar_x, "".join(flag_cells))
                if show_dur and rows["dur"] is not None:
                    dur_cells = _bar_durations(
                        durations,
                        abs_bar,
                        strings,
                        bar_width,
                        default_duration,
                        hide_redundant=hide_redundant,
                    )
                    if spacing_mode == "auto":
                        dur_cells = _scale_row(dur_cells, display_width, " ")
                    _safe_addstr(stdscr, row_start + (rows["dur"] or 0), bar_x, "".join(dur_cells))
            for s_idx in range(strings):
                actual = strings - 1 - s_idx if reverse_strings else s_idx
                y = row_start + (rows["staff"] or 0) + s_idx
                row_cells = cells[actual]
                if spacing_mode == "auto":
                    row_cells = _scale_row(row_cells, display_width, "-")
                row_text = "".join(row_cells)
                _safe_addstr(stdscr, y, bar_x, row_text)
                _safe_addstr(stdscr, y, bar_x + display_width, barline)

                if (
                    abs_bar == cursor_bar
                    and s_idx == cursor_string
                    and 0 <= cursor_col < bar_width
                ):
                    cell_x = bar_x + _scale_col(cursor_col, bar_width, display_width)
                    _safe_addstr(
                        stdscr,
                        y,
                        cell_x,
                        row_text[_scale_col(cursor_col, bar_width, display_width)],
                        curses.A_REVERSE,
                    )
                for col in range(bar_width):
                    if (abs_bar, actual, col) in highlights:
                        hl_x = bar_x + _scale_col(col, bar_width, display_width)
                        _safe_addstr(
                            stdscr,
                            y,
                            hl_x,
                            row_text[_scale_col(col, bar_width, display_width)],
                            curses.A_BOLD,
                        )

            if spacing_mode == "auto":
                bar_x += display_width + bar_gap
            else:
                bar_x += bar_width + bar_gap

    actual_cursor_string = strings - 1 - cursor_string if reverse_strings else cursor_string
    dur_key = (cursor_bar, actual_cursor_string, cursor_col)
    dur_text = durations.get(dur_key)
    if dur_text is None:
        for s_idx in range(strings):
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
