"""Width planning and tuning-label projection for legacy tablature views."""

from __future__ import annotations

from fractions import Fraction

from petrucci.model import Bar
from petrucci.render_utils import (
    _duration_values_by_col,
    chord_positions,
    flag_count,
    flag_positions_from_durations,
    note_type_to_denom,
)
from petrucci.tab_policy import string_label as tab_string_label


def _bar_compact_width(  # noqa: C901, PLR0917 - legacy grid projection pending typed bar inputs
    bar: Bar,
    bar_index: int,
    bar_width: int,
    overrides: dict[tuple[int, int, int], str],
    durations: dict[tuple[int, int, int], int],
    default_duration: int,
    dotted: set[tuple[int, int]] | None = None,
) -> int:
    max_string = 5
    for b, s, _c in overrides:
        if b == bar_index:
            max_string = max(max_string, s)
    for b, s, _c in durations:
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


def _infer_time_signature(bar: Bar, default_duration: int = 4) -> str | None:  # noqa: C901
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
    return tab_string_label(
        actual=actual,
        total_strings=total_strings,
        tuning_labels=tuning_labels,
        basslabels=basslabels,
        width=2,
    )


def _inline_bass_row(row: list[str]) -> list[str]:
    inline = [" " for _ in row]
    for idx, ch in enumerate(row):
        if ch in ("-", " "):
            continue
        inline[idx] = ch
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
    for b, _s, col in overrides:
        if b == bar_index:
            cols.add(col)
    for b, _s, col in durations:
        if b == bar_index:
            cols.add(col)
    return cols


def _bar_display_width(  # noqa: C901, PLR0917 - legacy grid projection pending typed bar inputs
    bar: Bar,
    bar_index: int,
    bar_width: int,
    overrides: dict[tuple[int, int, int], str],
    durations: dict[tuple[int, int, int], int],
    default_duration: int,
    dotted: set[tuple[int, int]] | None = None,
) -> int:
    max_string = 5
    for b, s, _c in overrides:
        if b == bar_index:
            max_string = max(max_string, s)
    for b, s, _c in durations:
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


def _bar_flag_span(  # noqa: PLR0917 - legacy grid projection pending typed bar inputs
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
    note_columns = sorted(_bar_note_columns(overrides, durations, bar_index=bar_index))
    duration_by_col = _duration_values_by_col(
        durations,
        bar_index=bar_index,
        strings=strings,
        columns=note_columns,
    )
    for col in note_columns:
        denom = duration_by_col.get(col, default_duration)
        max_slash = max(max_slash, flag_count(denom))
        if dotted is not None and (bar_index, col) in dotted:
            max_dot = 1
    return max_slash, max_dot


def _bar_note_count(  # noqa: PLR0917 - legacy grid projection pending typed bar inputs
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


def _bar_chord_count(  # noqa: PLR0917 - legacy grid projection pending typed bar inputs
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


def _bars_fit(  # noqa: PLR0917 - legacy grid projection pending typed system inputs
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
        if chord_wrap_limit > 0 and count > 0 and (chords_total + chord_count) > chord_wrap_limit:
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
    limit = min(total, start + per_line)
    for idx in range(start, limit):
        next_idx = idx + 1
        if next_idx in breaks or bars[idx].system_break:
            return next_idx
    return limit
