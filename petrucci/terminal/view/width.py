"""Width planning and tuning-label projection for legacy tablature views."""

from __future__ import annotations

from fractions import Fraction

from petrucci.core.model import Bar
from petrucci.input.tablature.policy import string_label as tab_string_label
from petrucci.rendering.primitives.utils import (
    _duration_values_by_col,
    chord_positions,
    flag_count,
    flag_positions_from_durations,
    note_type_to_denom,
)


def _source_string_count(
    overrides: dict[tuple[int, int, int], str],
    durations: dict[tuple[int, int, int], int],
    bar_index: int,
) -> int:
    override_max = max((string for bar, string, _col in overrides if bar == bar_index), default=5)
    duration_max = max((string for bar, string, _col in durations if bar == bar_index), default=5)
    return max(override_max, duration_max) + 1


def _bar_flag_positions(
    bar: Bar,
    *,
    bar_index: int,
    strings: int,
    bar_width: int,
    durations: dict[tuple[int, int, int], int],
    default_duration: int,
    dotted: set[tuple[int, int]] | None,
) -> list[tuple[int, int, bool]]:
    if bar.chords:
        return chord_positions(bar, max(bar_width, len(bar.chords)), default_duration)
    return flag_positions_from_durations(
        durations,
        bar_index,
        strings,
        bar_width,
        default_duration,
        dotted=dotted,
    )


def _positions_width(positions: list[tuple[int, int, bool]], *, tail_pad: int = 0) -> int:
    return max(
        (col + 2 + flag_count(denominator) + int(is_dotted) + tail_pad for col, denominator, is_dotted in positions),
        default=0,
    )


def _bar_compact_width(  # noqa: PLR0917 - legacy grid projection pending typed bar inputs
    bar: Bar,
    bar_index: int,
    bar_width: int,
    overrides: dict[tuple[int, int, int], str],
    durations: dict[tuple[int, int, int], int],
    default_duration: int,
    dotted: set[tuple[int, int]] | None = None,
) -> int:
    strings = _source_string_count(overrides, durations, bar_index)
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
    positions = _bar_flag_positions(
        bar,
        bar_index=bar_index,
        strings=strings,
        bar_width=bar_width,
        durations=durations,
        default_duration=default_duration,
        dotted=dotted,
    )
    width_needed = max(min_flag_width, _positions_width(positions, tail_pad=1))
    return max(3, width_needed)


def _time_signature_for_duration(total: Fraction, *, max_denom: int) -> str | None:
    if total <= 0:
        return None
    compound_duration = Fraction(3, 8)
    maximum_compound_denominator = 8
    if total == compound_duration and max_denom <= maximum_compound_denominator:
        return "3/4"
    integer_denominator = 1
    minimum_time_beats = 1
    maximum_time_beats = 12
    for unit in (4, 8, 2, 1):
        beats = total * unit
        if beats.denominator == integer_denominator and minimum_time_beats <= beats.numerator <= maximum_time_beats:
            return f"{beats.numerator}/{unit}"
    return None


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
    return _time_signature_for_duration(total, max_denom=max_denom)


def _parse_pitch_labels(text: str, *, show_octaves: bool, limit: int | None = None) -> list[str]:
    labels: list[str] = []
    index = 0
    while index < len(text):
        note = text[index]
        if not note.isalpha():
            index += 1
            continue
        index += 1
        accidental = ""
        if index < len(text) and text[index] in "+-#b":
            accidental = text[index]
            index += 1
        digits = ""
        while index < len(text) and text[index].isdigit():
            digits += text[index]
            index += 1
        suffix = digits if show_octaves else ""
        labels.append(f"{note}{accidental}{suffix}")
        if limit is not None and len(labels) >= limit:
            break
    return labels


def _bass_tuning_labels(bass: list[str] | None, *, show_octaves: bool) -> list[str]:
    labels: list[str] = []
    for token in bass or []:
        parsed = _parse_pitch_labels(token, show_octaves=show_octaves, limit=1)
        if parsed:
            labels.append(parsed[0])
    return labels


def _pad_tuning_labels(
    labels: list[str],
    strings: int,
    bass: list[str] | None,
    *,
    show_octaves: bool,
) -> list[str]:
    missing = strings - len(labels)
    bass_labels = _bass_tuning_labels(bass, show_octaves=show_octaves)
    if bass_labels:
        labels = bass_labels[:missing] + labels
    if len(labels) < strings:
        labels = [""] * (strings - len(labels)) + labels
    return labels


def _tuning_labels(
    tuning: str,
    strings: int,
    *,
    show_octaves: bool,
    bass: list[str] | None = None,
) -> list[str]:
    if not tuning:
        return [str(strings - idx) for idx in range(strings)]
    labels = _parse_pitch_labels(tuning, show_octaves=show_octaves, limit=strings)
    if len(labels) < strings:
        labels = _pad_tuning_labels(labels, strings, bass, show_octaves=show_octaves)
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


def _nearest_free_column(scaled: list[str], target: int, fill_char: str) -> int | None:
    if scaled[target] == fill_char:
        return target
    for offset in range(1, len(scaled)):
        right = target + offset
        if right < len(scaled) and scaled[right] == fill_char:
            return right
        left = target - offset
        if left >= 0 and scaled[left] == fill_char:
            return left
    return None


def _scaled_row_positions(row: list[str], dest_width: int, fill_char: str) -> list[tuple[int, str]]:
    src_width = len(row)
    return [(_scale_col(src_col, src_width, dest_width), char) for src_col, char in enumerate(row) if char != fill_char]


def _bounded_scaled_target(dest_column: int, last_position: int, dest_width: int) -> int:
    return min(max(dest_column, last_position + 1), dest_width - 1)


def _scale_row(row: list[str], dest_width: int, fill_char: str) -> list[str]:
    if dest_width <= 0:
        return []
    scaled = [fill_char for _ in range(dest_width)]
    src_width = len(row)
    if src_width <= 0:
        return scaled
    positions = _scaled_row_positions(row, dest_width, fill_char)
    if not positions:
        return scaled
    last_pos = -1
    for dest_col, ch in positions:
        target = _bounded_scaled_target(dest_col, last_pos, dest_width)
        free_column = _nearest_free_column(scaled, target, fill_char)
        if free_column is None:
            continue
        scaled[free_column] = ch
        last_pos = free_column
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


def _bar_display_width(  # noqa: PLR0917 - legacy grid projection pending typed bar inputs
    bar: Bar,
    bar_index: int,
    bar_width: int,
    overrides: dict[tuple[int, int, int], str],
    durations: dict[tuple[int, int, int], int],
    default_duration: int,
    dotted: set[tuple[int, int]] | None = None,
) -> int:
    strings = _source_string_count(overrides, durations, bar_index)
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
    positions = _bar_flag_positions(
        bar,
        bar_index=bar_index,
        strings=strings,
        bar_width=bar_width,
        durations=durations,
        default_duration=default_duration,
        dotted=dotted,
    )
    width_needed = max(min_flag_width, _positions_width(positions))
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
