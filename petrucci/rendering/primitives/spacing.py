from __future__ import annotations

from petrucci.core.model import Bar
from petrucci.rendering.primitives.utils import spread_flag_positions
from petrucci.terminal.view.model import (
    _filter_redundant_positions,
    _scale_col,
    bar_cells_from_chords,
    chord_positions,
    duration_display,
    flag_count,
)


def build_chord_scale_map(
    positions: list[tuple[int, int, bool]],
    bar_width: int,
    content_width: int,
    *,
    min_gap: int = 2,
) -> tuple[list[tuple[int, int, bool]], dict[int, int]]:
    scaled_positions = [(_scale_col(pos, bar_width, content_width), denom, dot) for (pos, denom, dot) in positions]
    spread_positions = spread_flag_positions(scaled_positions, content_width, min_gap=max(0, min_gap))
    ordered_raw = sorted(positions, key=lambda item: item[0])
    mapping = {
        raw_col: scaled_col
        for (raw_col, _raw_denom, _raw_dot), (scaled_col, _denom, _dot) in zip(
            ordered_raw,
            spread_positions,
            strict=False,
        )
    }
    return spread_positions, mapping


def note_event_columns(cells: list[list[str]], total_strings: int, grid_width: int) -> list[int]:
    return [column for column in range(grid_width) if any(cells[row][column] != "-" for row in range(total_strings))]


def required_flag_content_width(positions: list[tuple[int, int, bool]], *, min_gap: int = 1) -> int:
    if not positions:
        return 1
    spans = [1 + flag_count(denom) + int(dot) for _column, denom, dot in positions]
    return max(1, sum(spans) + max(0, len(spans) - 1) * max(0, min_gap))


def required_duration_content_width(positions: list[tuple[int, int, bool]], *, min_gap: int = 1) -> int:
    if not positions:
        return 1
    spans = [max(1, len(duration_display(denom, dot))) for _column, denom, dot in positions]
    return max(1, sum(spans) + max(0, len(spans) - 1) * max(0, min_gap))


def required_auto_display_width_for_bar(
    bar: Bar,
    *,
    total_strings: int,
    bar_width: int,
    default_duration: int,
    style: str,
    french_c: str,
    fretlabelmode: str,
    show_dur: bool,
    hide_redundant: bool,
    barpad: int,
    flag_gap: int = 1,
    event_gap: int = 2,
    cue_pad_total: int = 0,
) -> int:
    if not bar.chords:
        return 1
    positions, grid_width = chord_positions_distinct(bar, bar_width, default_duration)
    flag_positions = _filter_redundant_positions(positions) if hide_redundant else positions
    ordered_flags = sorted(flag_positions, key=lambda item: item[0])
    cells = bar_cells_from_chords(
        bar,
        total_strings,
        grid_width,
        default_duration,
        style,
        french_c=french_c,
        label_mode=fretlabelmode,
    )
    minimum = required_flag_content_width(ordered_flags, min_gap=flag_gap)
    note_columns = note_event_columns(cells, total_strings, grid_width)
    if note_columns:
        minimum = max(minimum, 2 + max(0, len(note_columns) - 1) * max(1, event_gap))
    if show_dur:
        minimum = max(minimum, required_duration_content_width(ordered_flags, min_gap=flag_gap))
    minimum = max(minimum, _lyric_content_width(bar), _melody_content_width(bar))
    return max(1, minimum + barpad * 2 + max(0, cue_pad_total))


def _lyric_content_width(bar: Bar) -> int:
    if bar.lyric_event_rows:
        return max(
            (
                sum(len(event.text.strip()) for event in row if event.text.strip())
                + max(0, sum(1 for event in row if event.text.strip()) - 1)
                for row in bar.lyric_event_rows
            ),
            default=0,
        )
    if bar.lyrics:
        return len(" ".join(part for part in bar.lyrics if part.strip()).strip())
    return 0


def _melody_content_width(bar: Bar) -> int:
    if not bar.melody_events:
        return 0
    return sum(max(1, len(event.text.strip())) for event in bar.melody_events) + max(0, len(bar.melody_events) - 1)


def chord_positions_distinct(
    bar: Bar,
    bar_width: int,
    default_duration: int,
) -> tuple[list[tuple[int, int, bool]], int]:
    if not bar.chords:
        return chord_positions(bar, bar_width, default_duration), bar_width
    width = max(1, bar_width, len(bar.chords))
    maximum = max(width, len(bar.chords) * 2 + 2)
    while width <= maximum:
        positions = chord_positions(bar, width, default_duration)
        columns = [column for column, _denom, _dot in positions]
        if len(columns) == len(set(columns)):
            return positions, width
        width += 1
    return chord_positions(bar, maximum, default_duration), maximum
