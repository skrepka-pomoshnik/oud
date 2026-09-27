from __future__ import annotations

from petrucci.core.model import Bar, Note
from petrucci.input.tablature.policy import fret_label


def format_fret(
    style: str,
    fret: int,
    french_c_shape: str = "normal",
    label_mode: str = "auto",
    **legacy: str,
) -> str:
    legacy_c = legacy.get("french_c") or legacy.get("frenchc")
    if legacy_c and french_c_shape == "normal":
        french_c_shape = legacy_c
    return fret_label(
        style,
        fret,
        french_c_shape=french_c_shape,
        label_mode=label_mode,
    )


def _place_legacy_note(
    cells: list[list[str]],
    next_col: list[int],
    note: Note,
    *,
    strings: int,
    bar_width: int,
    style: str,
    french_c_shape: str,
    label_mode: str,
) -> None:
    string_index = note.string - 1
    if not (0 <= string_index < strings):
        return
    col = next_col[string_index]
    if col >= bar_width:
        return
    text = format_fret(style, note.fret, french_c_shape=french_c_shape, label_mode=label_mode)[-2:]
    for offset, char in enumerate(text[: bar_width - col]):
        cells[string_index][col + offset] = char
    next_col[string_index] = min(bar_width, col + max(1, len(text)) + 1)


def bar_cells(
    bar: Bar,
    strings: int,
    bar_width: int,
    style: str,
    *,
    french_c_shape: str = "normal",
    label_mode: str = "auto",
    **legacy: str,
) -> list[list[str]]:
    legacy_c = legacy.get("french_c") or legacy.get("frenchc")
    if legacy_c and french_c_shape == "normal":
        french_c_shape = legacy_c
    cells = [["-" for _ in range(bar_width)] for _ in range(strings)]
    next_col = [0 for _ in range(strings)]

    for note in bar.notes:
        _place_legacy_note(
            cells,
            next_col,
            note,
            strings=strings,
            bar_width=bar_width,
            style=style,
            french_c_shape=french_c_shape,
            label_mode=label_mode,
        )

    return cells


def note_type_to_denom(note_type: int) -> int | None:
    mapping = {
        2: 1,
        3: 2,
        4: 4,
        5: 8,
        6: 16,
        7: 32,
        8: 64,
        9: 128,
        10: 256,
    }
    return mapping.get(note_type)


def chord_positions(
    bar: Bar,
    bar_width: int,
    default_duration: int,
) -> list[tuple[int, int, bool]]:
    chords = list(bar.chords or [])
    denoms: list[int] = []
    dotted: list[bool] = []
    for chord in chords:
        denom = note_type_to_denom(chord.note_type) or default_duration
        denoms.append(denom)
        dotted.append(bool(chord.dotted))
    if not denoms:
        return []
    max_denom = max(denoms)
    base = max_denom * 2
    units: list[int] = []
    for denom, dot in zip(denoms, dotted, strict=False):
        u = max(1, base // denom)
        if dot:
            u = max(1, (u * 3) // 2)
        units.append(u)
    total = sum(units)
    if total <= 0:
        return []
    positions: list[tuple[int, int, bool]] = []
    cum = 0
    prev_pos = -1
    for denom, dot, u in zip(denoms, dotted, units, strict=False):
        raw_pos = min(bar_width - 1, (cum * (bar_width - 1)) // total)
        pos = min(bar_width - 1, max(raw_pos, prev_pos + 1))
        positions.append((pos, denom, dot))
        prev_pos = pos
        cum += u
    return positions


def chord_slot_positions(
    bar: Bar,
    bar_width: int,
    default_duration: int,
    *,
    min_gap: int = 1,
) -> list[tuple[int, int, bool]]:
    _ = min_gap
    return chord_positions(bar, bar_width, default_duration)


def bar_cells_from_chords(
    bar: Bar,
    strings: int,
    bar_width: int,
    default_duration: int,
    style: str,
    *,
    french_c_shape: str = "normal",
    label_mode: str = "auto",
    **legacy: str,
) -> list[list[str]]:
    legacy_c = legacy.get("french_c") or legacy.get("frenchc")
    if legacy_c and french_c_shape == "normal":
        french_c_shape = legacy_c
    cells = [["-" for _ in range(bar_width)] for _ in range(strings)]
    positions = chord_positions(bar, bar_width, default_duration)
    if not positions:
        return cells
    chords = list(bar.chords or [])
    for chord, (col, _denom, _dot) in zip(chords, positions, strict=False):
        for note in chord.notes:
            s_idx = note.string - 1
            if 0 <= s_idx < strings and 0 <= col < bar_width:
                cells[s_idx][col] = format_fret(
                    style,
                    note.fret,
                    french_c_shape=french_c_shape,
                    label_mode=label_mode,
                )
    return cells


def duration_display(duration: int, dotted: bool = False) -> str:
    text = str(duration)
    return f"{text}." if dotted else text


def place_duration_cells(
    row: list[str],
    col: int,
    duration: int,
    dotted: bool = False,
) -> None:
    text = duration_display(duration, dotted)
    width = len(row)
    if col < 0 or col >= width:
        return
    for idx, ch in enumerate(text):
        pos = col + idx
        if 0 <= pos < width and row[pos] == " ":
            row[pos] = ch


def duration_flag(duration: int) -> str:
    mapping = {
        1: "W",
        2: "w",
        4: "0",
        8: "1",
        16: "2",
        32: "3",
        64: "4",
        128: "5",
    }
    return mapping.get(duration, "?")


def flag_count(denom: int) -> int:
    # Historical tablature rhythm cue style:
    # minim (2) = plain stem, crotchet (4) = 1 flag, quaver (8) = 2 flags, ...
    plain_stem_denominator = 2
    if denom <= plain_stem_denominator:
        return 0
    count = 0
    value = max(1, denom)
    while value > plain_stem_denominator:
        count += 1
        value //= 2
    return count


def _place_flag_stem(row: list[str], column: int, stem: str, stem_width: int) -> None:
    row[column] = stem
    for extra in range(1, max(1, stem_width)):
        position = column + extra
        if position < len(row) and row[position] == " ":
            row[position] = stem


def _flag_start(
    column: int,
    stem_width: int,
    *,
    dotted: bool,
    dotplacement: str,
    dot_positions: list[int],
) -> int:
    start = column + max(1, stem_width)
    if dotted and dotplacement == "afterstem":
        dot_positions.append(start)
        return start + 1
    return start


def _place_flags(row: list[str], start: int, count: int, flag: str) -> None:
    for offset in range(count):
        position = start + offset
        if position < len(row):
            row[position] = flag


def _queue_trailing_dot(
    dot_positions: list[int],
    *,
    start: int,
    flag_total: int,
    dotted: bool,
    dotplacement: str,
    bar_width: int,
) -> None:
    position = start + flag_total
    if dotted and dotplacement != "afterstem" and position < bar_width:
        dot_positions.append(position)


def _place_pending_dot(row: list[str], position: int, dot: str) -> None:
    while position < len(row) and row[position] != " ":
        position += 1
    if position < len(row):
        row[position] = dot


def flag_row_style(
    positions: list[tuple[int, int, bool]],
    bar_width: int,
    *,
    stem: str,
    flag: str,
    dot: str = ".",
    stem_width: int = 1,
    dotplacement: str = "afterflag",
) -> list[str]:
    row = [" " for _ in range(bar_width)]
    dot_positions: list[int] = []
    for col, denom, dotted in positions:
        _place_flag_stem(row, col, stem, stem_width)
        slash_count = flag_count(denom)
        flag_start = _flag_start(
            col,
            stem_width,
            dotted=dotted,
            dotplacement=dotplacement,
            dot_positions=dot_positions,
        )
        _place_flags(row, flag_start, slash_count, flag)
        _queue_trailing_dot(
            dot_positions,
            start=flag_start,
            flag_total=slash_count,
            dotted=dotted,
            dotplacement=dotplacement,
            bar_width=bar_width,
        )
    for position in dot_positions:
        _place_pending_dot(row, position, dot)
    return row


def flag_row(positions: list[tuple[int, int, bool]], bar_width: int) -> list[str]:
    return flag_row_style(positions, bar_width, stem="|", flag="\\")


def spread_flag_positions(
    positions: list[tuple[int, int, bool]],
    bar_width: int,
    *,
    min_gap: int = 0,
) -> list[tuple[int, int, bool]]:
    if not positions or bar_width <= 0:
        return []
    ordered = sorted(positions, key=lambda item: item[0])
    if len(ordered) == 1:
        col, denom, dot = ordered[0]
        return [(max(0, min(bar_width - 1, col)), denom, dot)]

    spans = [1 + flag_count(denom) + (1 if dot else 0) for (_c, denom, dot) in ordered]

    gap = max(0, min_gap)
    while gap >= 0:
        solved = _solve_spread_cols(ordered, spans, bar_width, gap)
        if solved is not None:
            return [(solved[idx], denom, dot) for idx, (_c, denom, dot) in enumerate(ordered)]
        gap -= 1

    cols = _fallback_spread_cols(len(ordered), spans, bar_width)
    return [(cols[idx], denom, dot) for idx, (_c, denom, dot) in enumerate(ordered)]


def _solve_spread_cols(
    ordered: list[tuple[int, int, bool]],
    spans: list[int],
    bar_width: int,
    gap: int,
) -> list[int] | None:
    starts_max = [max(0, bar_width - span) for span in spans]
    lower: list[int] = [0] * len(ordered)
    upper: list[int] = [0] * len(ordered)

    lower[0] = max(0, min(starts_max[0], ordered[0][0]))
    for idx in range(1, len(ordered)):
        required = lower[idx - 1] + spans[idx - 1] + gap
        lower[idx] = max(required, ordered[idx][0])
        lower[idx] = min(lower[idx], starts_max[idx])

    upper[-1] = starts_max[-1]
    for idx in range(len(ordered) - 2, -1, -1):
        upper[idx] = min(starts_max[idx], upper[idx + 1] - (spans[idx] + gap))

    for idx in range(len(ordered)):
        if lower[idx] > upper[idx]:
            return None

    cols = [0] * len(ordered)
    cols[0] = max(lower[0], min(ordered[0][0], upper[0]))
    for idx in range(1, len(ordered)):
        min_required = cols[idx - 1] + spans[idx - 1] + gap
        cols[idx] = max(min_required, min(ordered[idx][0], upper[idx]))
        cols[idx] = max(cols[idx], lower[idx])
        if cols[idx] > upper[idx]:
            return None
    return cols


def _fallback_spread_cols(count: int, spans: list[int], bar_width: int) -> list[int]:
    step = max(1, (bar_width - 1) // max(1, count - 1))
    return [min(max(0, bar_width - spans[idx]), idx * step) for idx in range(count)]


def stem_row_style(
    positions: list[tuple[int, int, bool]],
    bar_width: int,
    *,
    stem: str,
    stem_width: int = 1,
) -> list[str]:
    row = [" " for _ in range(bar_width)]
    for col, _denom, _dotted in positions:
        row[col] = stem
        for extra in range(1, max(1, stem_width)):
            pos = col + extra
            if pos < bar_width and row[pos] == " ":
                row[pos] = stem
    return row


def flag_positions_from_durations(
    durations: dict[tuple[int, int, int], int],
    bar_index: int,
    strings: int,
    bar_width: int,
    default_duration: int,
    *,
    dotted: set[tuple[int, int]] | None = None,
) -> list[tuple[int, int, bool]]:
    if bar_width <= 0:
        return []
    explicit_by_col = _duration_values_by_col(
        durations,
        bar_index=bar_index,
        strings=strings,
        columns=range(bar_width),
    )

    positions: list[tuple[int, int, bool]] = []
    last_col = -1
    last_duration = default_duration
    for col, denominator in sorted(explicit_by_col.items()):
        reset_col = last_col + 1
        if last_col >= 0 and reset_col < col and last_duration != default_duration:
            positions.append((reset_col, default_duration, dotted is not None and (bar_index, reset_col) in dotted))
        elif last_col < 0 and col > 0:
            positions.append((0, default_duration, dotted is not None and (bar_index, 0) in dotted))
        positions.append((col, denominator, dotted is not None and (bar_index, col) in dotted))
        last_col = col
        last_duration = denominator
    if not positions:
        return [(0, default_duration, dotted is not None and (bar_index, 0) in dotted)]
    reset_col = last_col + 1
    if reset_col < bar_width and last_duration != default_duration:
        positions.append((reset_col, default_duration, dotted is not None and (bar_index, reset_col) in dotted))
    return positions


def _dense_duration_values(
    durations: dict[tuple[int, int, int], int],
    *,
    bar_index: int,
    strings: int,
    columns: range | list[int],
) -> dict[int, int]:
    values: dict[int, int] = {}
    for col in columns:
        denominators = (
            durations[(bar_index, string_index, col)]
            for string_index in range(strings)
            if (bar_index, string_index, col) in durations
        )
        denominator = max(denominators, default=None)
        if denominator is not None:
            values[col] = denominator
    return values


def _sparse_duration_values(
    durations: dict[tuple[int, int, int], int],
    *,
    bar_index: int,
    strings: int,
    columns: range | list[int],
) -> dict[int, int]:
    values: dict[int, int] = {}
    for (duration_bar, string_index, col), denominator in durations.items():
        if duration_bar != bar_index or not (0 <= string_index < strings) or col not in columns:
            continue
        values[col] = max(values.get(col, denominator), denominator)
    return values


def _duration_values_by_col(
    durations: dict[tuple[int, int, int], int],
    *,
    bar_index: int,
    strings: int,
    columns: range | list[int],
) -> dict[int, int]:
    if strings <= 0 or not columns:
        return {}
    if len(columns) * strings <= len(durations):
        return _dense_duration_values(durations, bar_index=bar_index, strings=strings, columns=columns)
    return _sparse_duration_values(durations, bar_index=bar_index, strings=strings, columns=columns)


def _distributed_group_gaps(targets: list[int], extra: int, *, start: int = 0) -> dict[int, int]:
    gaps: dict[int, int] = {}
    for index in range(extra):
        target = targets[(index + start) % len(targets)]
        gaps[target] = gaps.get(target, 0) + 1
    return gaps


def smart_group_map(
    all_positions: list[tuple[int, int, bool]],
    group_positions: list[tuple[int, int, bool]],
    content_width: int,
    *,
    min_gap: int = 1,
) -> dict[int, int]:
    if content_width <= 0 or not all_positions:
        return {}
    raw_cols = sorted({col for col, _denom, _dot in all_positions})
    if not raw_cols:
        return {}
    if len(raw_cols) == 1:
        return {raw_cols[0]: 0}

    groups = sorted({col for col, _denom, _dot in group_positions})
    boundaries = [col for col in groups if col in set(raw_cols[1:])]

    gap = max(1, min_gap)
    base_span = (len(raw_cols) - 1) * gap
    extra = max(0, content_width - (base_span + 1))
    targets = boundaries or raw_cols
    start = 0 if boundaries else 1
    gap_before = _distributed_group_gaps(targets, extra, start=start) if extra > 0 else {}

    mapping: dict[int, int] = {}
    cursor = 0
    mapping[raw_cols[0]] = 0
    for raw in raw_cols[1:]:
        cursor += gap + gap_before.get(raw, 0)
        cursor = min(cursor, content_width - 1)
        mapping[raw] = cursor
    return mapping


def soft_beat_snap_map(
    positions: list[tuple[int, int, bool]],
    *,
    grid_width: int,
    content_width: int,
    beats: int,
    min_gap: int = 1,
) -> dict[int, int]:
    if content_width <= 0 or beats <= 1 or not positions:
        return {}
    ordered = sorted(positions, key=lambda item: item[0])
    if len(ordered) == 1:
        raw = ordered[0][0]
        return {raw: max(0, min(content_width - 1, content_width // 2))}

    width = max(1, grid_width)
    bucket_count = max(1, beats)
    raw_buckets = [min(bucket_count - 1, (raw_col * bucket_count) // width) for (raw_col, _denom, _dot) in ordered]
    min_bucket = min(raw_buckets)
    max_bucket = max(raw_buckets)
    active_bucket_count = max(1, (max_bucket - min_bucket) + 1)
    seeded: list[tuple[int, int, bool]] = []
    raw_cols: list[int] = []
    for (raw_col, denom, dot), bucket in zip(ordered, raw_buckets, strict=False):
        active_bucket = bucket - min_bucket
        dst_start = (active_bucket * content_width) // active_bucket_count
        dst_end = ((active_bucket + 1) * content_width) // active_bucket_count - 1
        dst_end = max(dst_end, dst_start)
        raw_start = (bucket * width) // bucket_count
        raw_end = ((bucket + 1) * width) // bucket_count - 1
        raw_end = max(raw_end, raw_start)
        if raw_end == raw_start:
            target = dst_start
        else:
            target = dst_start + ((raw_col - raw_start) * max(0, dst_end - dst_start)) // (raw_end - raw_start)
        seeded.append((max(0, min(content_width - 1, target)), denom, dot))
        raw_cols.append(raw_col)

    # Soft beat snap arranges note onsets; visible flag tails are placed later.
    # Using full flag spans here (especially with hidden redundant flags) over-reserves
    # width and leaves misleading trailing dash space.
    # Use a stem-only placeholder (minim-like) so this pass spaces note anchors only,
    # not visible flag tails.
    unit_seeded = [(col, 2, False) for (col, _denom, _dot) in seeded]
    spread = spread_flag_positions(unit_seeded, content_width, min_gap=max(0, min_gap))
    return {raw: col for raw, (col, _denom, _dot) in zip(raw_cols, spread, strict=False)}


def _scaled_onset_map(
    source: dict[int, int],
    raws: list[int],
    *,
    first_col: int,
    current_last: int,
    target_last: int,
    content_width: int,
    min_gap: int,
) -> dict[int, int]:
    current_span = max(1, current_last - first_col)
    target_span = max(1, target_last - first_col)
    seeded = [
        (
            max(
                0,
                min(
                    content_width - 1,
                    first_col + ((source[raw] - first_col) * target_span) // current_span,
                ),
            ),
            4,
            False,
        )
        for raw in raws
    ]
    spread = spread_flag_positions(seeded, content_width, min_gap=max(0, min_gap))
    trimmed = dict(source)
    for raw, (col, _denom, _dot) in zip(raws, spread, strict=False):
        trimmed[raw] = col
    return trimmed


def trim_right_slack_for_onsets(
    src_to_dest: dict[int, int],
    *,
    all_positions: list[tuple[int, int, bool]],
    visible_positions: list[tuple[int, int, bool]] | None,
    content_width: int,
    min_gap: int = 1,
) -> dict[int, int]:
    if content_width <= 0 or not src_to_dest or not all_positions:
        return src_to_dest
    last_raw = max(col for (col, _denom, _dot) in all_positions)
    if last_raw not in src_to_dest:
        return src_to_dest
    visible_map = {col: (denom, dot) for (col, denom, dot) in (visible_positions or all_positions)}
    required_slack = 1
    if last_raw in visible_map:
        denom, dot = visible_map[last_raw]
        required_slack = max(1, 1 + flag_count(denom) + (1 if dot else 0))
    ordered_raws = sorted(raw for (raw, _denom, _dot) in all_positions if raw in src_to_dest)
    if not ordered_raws:
        return src_to_dest
    first_raw = ordered_raws[0]
    first_col = src_to_dest[first_raw]
    current_last = src_to_dest[last_raw]
    current_slack = (content_width - 1) - current_last
    shift = current_slack - required_slack
    if shift <= 0:
        return src_to_dest
    target_last = max(first_col, (content_width - 1) - required_slack)
    if first_col <= 1 and current_last > first_col and target_last > current_last:
        return _scaled_onset_map(
            src_to_dest,
            ordered_raws,
            first_col=first_col,
            current_last=current_last,
            target_last=target_last,
            content_width=content_width,
            min_gap=min_gap,
        )
    return {raw: min(content_width - 1, col + shift) for raw, col in src_to_dest.items()}
