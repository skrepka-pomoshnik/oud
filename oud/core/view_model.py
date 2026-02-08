from __future__ import annotations

from fractions import Fraction

from oud.core.model import Bar, Piece
from oud.core.render_utils import (
    bar_cells,
    bar_cells_from_chords,
    chord_positions,
    duration_display,
    duration_flag,
    flag_count,
    flag_positions_from_durations,
    flag_row,
    note_type_to_denom,
    place_duration_cells,
)
from oud.ui.layout_map import (
    block_height as _block_height,
)
from oud.ui.layout_map import (
    layout_block_rows as _layout_block_rows,
)
from oud.ui.layout_map import (
    layout_rows as _layout_rows,
)

__all__ = [  # noqa: RUF022
    "_bar_annotations",
    "_bar_compact_width",
    "_bar_display_width",
    "_bar_durations",
    "_bar_flags",
    "_bar_note_columns",
    "_bar_note_count",
    "_bar_number_for_index",
    "_bar_ornaments",
    "_bar_span_row",
    "_bars_fit",
    "_block_height",
    "_filter_redundant_positions",
    "_flag_positions_all",
    "_inline_bass_row",
    "_layout_block_rows",
    "_layout_rows",
    "_next_system_start",
    "_parse_time_signature",
    "_scale_col",
    "_scale_row",
    "_string_label",
    "_tactus_row",
    "_tuning_labels",
    "_infer_time_signature",
    "Bar",
    "Piece",
    "bar_cells",
    "bar_cells_from_chords",
    "build_bar_view",
    "chord_positions",
    "duration_display",
    "duration_flag",
    "flag_count",
    "flag_positions_from_durations",
    "flag_row",
    "note_type_to_denom",
]


def _bar_compact_width(
    bar: Bar,
    bar_index: int,
    bar_width: int,
    overrides: dict[tuple[int, int, int], str],
    durations: dict[tuple[int, int, int], int],
    default_duration: int,
    dotted: set[tuple[int, int]] | None = None,
) -> int:
    max_string = 5
    for (b, s, _c) in overrides:
        if b == bar_index:
            max_string = max(max_string, s)
    for (b, s, _c) in durations:
        if b == bar_index:
            max_string = max(max_string, s)
    strings = max_string + 1
    max_slash, max_dot = _bar_flag_span(
        bar,
        bar_index,
        strings,
        overrides,
        durations,
        default_duration,
        dotted,
    )
    min_flag_width = 2 + max_slash + max_dot
    width_needed = min_flag_width
    tail_pad = 1
    if bar.chords:
        chord_width = max(bar_width, len(bar.chords))
        positions = chord_positions(bar, chord_width, default_duration)
        for col, denom, dot in positions:
            span = 1 + flag_count(denom) + (1 if dot else 0)
            width_needed = max(width_needed, col + span + 1 + tail_pad)
    else:
        positions = flag_positions_from_durations(
            durations,
            bar_index,
            strings,
            bar_width,
            default_duration,
            dotted=dotted,
        )
        for col, denom, dot in positions:
            span = 1 + flag_count(denom) + (1 if dot else 0)
            width_needed = max(width_needed, col + span + 1 + tail_pad)
    return max(3, width_needed)


def _infer_time_signature(bar: Bar, default_duration: int = 4) -> str | None:
    if not bar.chords:
        return None
    total = Fraction(0, 1)
    max_denom = 0
    for chord in bar.chords:
        denom = note_type_to_denom(chord.note_type) or default_duration
        max_denom = max(max_denom, denom)
        dur = Fraction(1, denom)
        if chord.dotted:
            dur = dur * Fraction(3, 2)
        total += dur
    if total <= 0:
        return None
    if total == Fraction(3, 8) and max_denom <= 8:
        return "3/4"
    for unit in (4, 8, 2, 1):
        beats = total * unit
        if beats.denominator == 1:
            beats_int = int(beats.numerator)
            if 1 <= beats_int <= 12:
                return f"{beats_int}/{unit}"
    return None


def _tuning_labels(  # noqa: C901, PLR0912
    tuning: str,
    strings: int,
    *,
    show_octaves: bool,
    bass: list[str] | None = None,
) -> list[str]:
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
        missing = strings - len(labels)
        bass_labels: list[str] = []
        if bass:
            for token in bass:
                note = ""
                accidental = ""
                digits = ""
                for ch in token:
                    if not note and ch.isalpha():
                        note = ch
                    elif note and not accidental and ch in "+-#b":
                        accidental = ch
                    elif note and ch.isdigit():
                        digits += ch
                if not note:
                    continue
                label = f"{note}{accidental}"
                if show_octaves and digits:
                    label += digits
                bass_labels.append(label)
        if bass_labels:
            bass_labels = list(reversed(bass_labels))
            labels = bass_labels[:missing] + labels
            if len(labels) < strings:
                labels = [""] * (strings - len(labels)) + labels
        else:
            labels = [""] * missing + labels
    labels = labels[:strings]
    labels.reverse()
    return labels


def _string_label(
    actual: int,
    total_strings: int,
    tuning_labels: list[str],
    basslabels: str,
) -> str:
    if actual >= 6 and basslabels != "tuning":
        if basslabels == "numeric":
            label_value = str(actual + 1)
        elif basslabels == "slash":
            label_value = "/" * max(1, actual - 5)
        else:
            label_value = str(actual + 1)
    elif actual < len(tuning_labels):
        label_value = tuning_labels[actual]
    else:
        label_value = str(total_strings - actual)
    if len(label_value) > 2:
        label_value = label_value[:2]
    return f"{label_value:>2}"


def _inline_bass_row(row: list[str]) -> list[str]:
    inline = [" " for _ in row]
    for idx, ch in enumerate(row):
        if ch in ("-", " "):
            continue
        inline[idx] = ch
        if idx - 1 >= 0 and inline[idx - 1] == " ":
            inline[idx - 1] = "-"
        if idx + 1 < len(inline) and inline[idx + 1] == " ":
            inline[idx + 1] = "-"
    return inline


def _scale_col(col: int, src_width: int, dest_width: int) -> int:
    if dest_width <= 1:
        return 0
    if src_width <= 1:
        return 0
    return min(dest_width - 1, (col * (dest_width - 1)) // (src_width - 1))


def _scale_row(row: list[str], dest_width: int, fill_char: str) -> list[str]:  # noqa: C901
    if dest_width <= 0:
        return []
    scaled = [fill_char for _ in range(dest_width)]
    src_width = len(row)
    if src_width <= 0:
        return scaled
    positions: list[tuple[int, str]] = []
    for src_col, ch in enumerate(row):
        if ch == fill_char:
            continue
        positions.append((_scale_col(src_col, src_width, dest_width), ch))
    if not positions:
        return scaled
    min_gap = 1
    last_pos = -min_gap
    for dest_col, ch in positions:
        target = max(dest_col, last_pos + min_gap)
        if target >= dest_width:
            target = dest_width - 1
        if scaled[target] != fill_char:
            moved = False
            for offset in range(1, dest_width):
                right = target + offset
                left = target - offset
                if right < dest_width and scaled[right] == fill_char:
                    target = right
                    moved = True
                    break
                if left >= 0 and scaled[left] == fill_char:
                    target = left
                    moved = True
                    break
            if not moved:
                continue
        scaled[target] = ch
        last_pos = target
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
    dotted: set[tuple[int, int]] | None = None,
) -> int:
    max_string = 5
    for (b, s, _c) in overrides:
        if b == bar_index:
            max_string = max(max_string, s)
    for (b, s, _c) in durations:
        if b == bar_index:
            max_string = max(max_string, s)
    strings = max_string + 1
    max_slash, max_dot = _bar_flag_span(
        bar,
        bar_index,
        strings,
        overrides,
        durations,
        default_duration,
        dotted,
    )
    count = _bar_note_count(bar, bar_index, bar_width, overrides, durations, default_duration)
    count = max(1, count)
    min_flag_width = 2 + max_slash + max_dot
    width_needed = min_flag_width
    if bar.chords:
        chord_width = max(bar_width, len(bar.chords))
        positions = chord_positions(bar, chord_width, default_duration)
        for col, denom, dot in positions:
            span = 1 + flag_count(denom) + (1 if dot else 0)
            width_needed = max(width_needed, col + span + 1)
    else:
        positions = flag_positions_from_durations(
            durations,
            bar_index,
            strings,
            bar_width,
            default_duration,
            dotted=dotted,
        )
        for col, denom, dot in positions:
            span = 1 + flag_count(denom) + (1 if dot else 0)
            width_needed = max(width_needed, col + span + 1)
    min_unit = max(2, 2 + max_slash + max_dot)
    return max(3, width_needed, (count * min_unit) + 1)


def _bar_flag_span(
    bar: Bar,
    bar_index: int,
    strings: int,
    overrides: dict[tuple[int, int, int], str],
    durations: dict[tuple[int, int, int], int],
    default_duration: int,
    dotted: set[tuple[int, int]] | None = None,
) -> tuple[int, int]:
    max_slash = 0
    max_dot = 0
    if bar.chords:
        for chord in bar.chords:
            denom = note_type_to_denom(chord.note_type) or default_duration
            max_slash = max(max_slash, flag_count(denom))
            max_dot = max(max_dot, 1 if chord.dotted else 0)
        return max_slash, max_dot
    for col in _bar_note_columns(overrides, durations, bar_index=bar_index):
        found = None
        for s_idx in range(strings):
            key = (bar_index, s_idx, col)
            if key in durations:
                denom = durations[key]
                if found is None or denom > found:
                    found = denom
        denom = found or default_duration
        max_slash = max(max_slash, flag_count(denom))
        if dotted is not None and (bar_index, col) in dotted:
            max_dot = 1
    return max_slash, max_dot


def _bar_note_count(
    bar: Bar,
    bar_index: int,
    bar_width: int,
    overrides: dict[tuple[int, int, int], str],
    durations: dict[tuple[int, int, int], int],
    default_duration: int,
) -> int:
    _ = bar_width, default_duration
    if bar.chords:
        return len(bar.chords)
    return len(_bar_note_columns(overrides, durations, bar_index=bar_index))


def _bar_chord_count(
    bar: Bar,
    bar_index: int,
    bar_width: int,
    overrides: dict[tuple[int, int, int], str],
    durations: dict[tuple[int, int, int], int],
    default_duration: int,
) -> int:
    if bar.chords:
        return len(bar.chords)
    count = _bar_note_count(
        bar,
        bar_index,
        bar_width,
        overrides,
        durations,
        default_duration,
    )
    if count > 0:
        return count
    if bar.notes:
        return len(bar.notes)
    return 0


def _bars_fit(
    bars: list[Bar],
    bar_offset: int,
    bar_gap: int,
    usable_width: int,
    bar_width: int,
    overrides: dict[tuple[int, int, int], str],
    durations: dict[tuple[int, int, int], int],
    default_duration: int,
    dotted: set[tuple[int, int]] | None,
    *,
    max_chords: int = 0,
    compact: bool = False,
    chord_wrap_limit: int = 0,
) -> int:
    if usable_width <= 0:
        return 1
    count = 0
    total = 0
    chords_total = 0
    for idx in range(bar_offset, len(bars)):
        chord_count = _bar_chord_count(
            bars[idx],
            idx,
            bar_width,
            overrides,
            durations,
            default_duration,
        )
        if (
            chord_wrap_limit > 0
            and count > 0
            and (chords_total + chord_count) > chord_wrap_limit
        ):
            break
        if compact:
            display = _bar_compact_width(
                bars[idx],
                idx,
                bar_width,
                overrides,
                durations,
                default_duration,
                dotted,
            )
        else:
            display = _bar_display_width(
                bars[idx],
                idx,
                bar_width,
                overrides,
                durations,
                default_duration,
                dotted,
            )
        if max_chords > 0:
            display = max(display, (max_chords * 2) + 1)
        needed = display if count == 0 else display + bar_gap
        if total + needed > usable_width:
            break
        total += needed
        chords_total += chord_count
        count += 1
    return max(1, count)


def _next_system_start(
    bars: list[Bar],
    start: int,
    per_line: int,
    breaks: set[int],
) -> int:
    total = len(bars)
    if not breaks:
        return min(total, start + per_line)
    for offset in range(1, per_line + 1):
        idx = start + offset
        if idx in breaks:
            return idx
    return min(total, start + per_line)


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
    default_duration: int = 4,
) -> list[tuple[int, int, bool]]:
    if not positions:
        return []
    filtered: list[tuple[int, int, bool]] = []
    prev_denom = default_duration
    prev_dot = False
    for idx, (col, denom, dot) in enumerate(positions):
        if idx == 0:
            filtered.append((col, denom, dot))
            prev_denom = denom
            prev_dot = dot
            continue
        if denom != prev_denom or dot != prev_dot:
            filtered.append((col, denom, dot))
            prev_denom = denom
            prev_dot = dot
    return filtered


def _bar_number_for_index(
    piece: Piece,
    bar_index: int,
    measures: str,
    countdots: str,
    step: int,
) -> str | None:
    extra = 0
    if countdots == "on":
        for idx in range(bar_index + 1):
            if piece.bars[idx].repeat == ".":
                extra += 1
    number = bar_index + 1 + extra
    if measures == "every":
        if step <= 0:
            step = 1
        if bar_index > 0 and number % step == 0:
            return f"[{number}]"
        return None
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
    *,
    hide_redundant: bool = True,
    dotted: set[tuple[int, int]] | None = None,
) -> list[str]:
    row = [" " for _ in range(bar_width)]
    last: int | None = None
    last_dot = False
    for col in range(bar_width):
        found = None
        for s_idx in range(strings):
            key = (bar_index, s_idx, col)
            if key in durations:
                denom = durations[key]
                if found is None or denom > found:
                    found = denom
        denom = found if found is not None else default_duration
        if hide_redundant:
            if found is None:
                continue
            is_dotted = dotted is not None and (bar_index, col) in dotted
            if denom != last or is_dotted != last_dot:
                place_duration_cells(row, col, denom, is_dotted)
                last = denom
                last_dot = is_dotted
        else:
            is_dotted = dotted is not None and (bar_index, col) in dotted
            place_duration_cells(row, col, denom, is_dotted)
    return row


def _flag_positions_all(
    durations: dict[tuple[int, int, int], int],
    bar_index: int,
    strings: int,
    bar_width: int,
    default_duration: int,
    dotted: set[tuple[int, int]] | None = None,
) -> list[tuple[int, int, bool]]:
    has_duration = any(b == bar_index for (b, _s, _c) in durations)
    if not has_duration:
        return [(col, default_duration, False) for col in range(bar_width)]
    return flag_positions_from_durations(
        durations,
        bar_index=bar_index,
        strings=strings,
        bar_width=bar_width,
        default_duration=default_duration,
        dotted=dotted,
    )


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
        start_pos = max(0, min(bar_width - 1, start))
        end_pos = max(0, min(bar_width - 1, end))
        if start_pos == end_pos:
            row[start_pos] = start_char
            continue
        if start_pos > end_pos:
            start_pos, end_pos = end_pos, start_pos
        row[start_pos] = start_char
        for col in range(start_pos + 1, end_pos):
            row[col] = fill_char
        row[end_pos] = end_char
    return row


def _bar_flags(
    durations: dict[tuple[int, int, int], int],
    bar_index: int,
    strings: int,
    bar_width: int,
    default_duration: int,
    *,
    hide_redundant: bool = True,
) -> list[str]:
    row = [" " for _ in range(bar_width)]
    for col in range(bar_width):
        found = None
        for s_idx in range(strings):
            key = (bar_index, s_idx, col)
            if key in durations:
                denom = durations[key]
                if found is None or denom > found:
                    found = denom
        denom = found if found is not None else default_duration
        if hide_redundant:
            if found is None:
                continue
            row[col] = duration_flag(denom)
        else:
            row[col] = duration_flag(denom)
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
    style: str,
    *,
    french_c: str = "normal",
) -> dict[str, list[str]]:
    bar_cells_data = (
        bar_cells_from_chords(
            bar,
            strings,
            bar_width,
            default_duration,
            style,
            french_c=french_c,
        )
        if bar.chords
        else bar_cells(
            bar,
            strings,
            bar_width,
            style,
            french_c=french_c,
        )
    )
    for (b, s, col), ch in overrides.items():
        if b != bar_index:
            continue
        if s >= strings or col >= bar_width:
            continue
        bar_cells_data[s][col] = ch
    flag_cells = _bar_flags(
        durations,
        bar_index,
        strings,
        bar_width,
        default_duration,
    )
    dur_cells = _bar_durations(
        durations,
        bar_index,
        strings,
        bar_width,
        default_duration,
    )
    if not any(b == bar_index for (b, _s, _c) in durations):
        override_cols = {
            col for (b, _s, col) in overrides if b == bar_index and col < bar_width
        }
        for col in override_cols:
            dur_cells[col] = duration_display(default_duration)
    ann_cells = _bar_annotations(annotations, bar_index, bar_width)
    orn_cells = _bar_ornaments(ornaments, bar_index, bar_width)
    slur_cells = _bar_span_row(slurs, bar_index, bar_width, "(", ")", "~")
    tie_cells = _bar_span_row(ties, bar_index, bar_width, "[", "]", "-")
    hold_cells = _bar_span_row(holds, bar_index, bar_width, "<", ">", "_")
    rows = ["".join(bar_cells_data[s_idx]) for s_idx in range(strings)]
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
