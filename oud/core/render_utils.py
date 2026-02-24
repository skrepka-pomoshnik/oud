from __future__ import annotations

from oud.core.model import Bar
from oud.core.tab_policy import fret_label


def format_fret(
    style: str,
    fret: int,
    french_c_shape: str = "normal",
    **legacy: str,
) -> str:
    legacy_c = legacy.get("french_c") or legacy.get("frenchc")
    if legacy_c and french_c_shape == "normal":
        french_c_shape = legacy_c
    return fret_label(style, fret, french_c_shape=french_c_shape)


def bar_cells(
    bar: Bar,
    strings: int,
    bar_width: int,
    style: str,
    french_c_shape: str = "normal",
    **legacy: str,
) -> list[list[str]]:
    legacy_c = legacy.get("french_c") or legacy.get("frenchc")
    if legacy_c and french_c_shape == "normal":
        french_c_shape = legacy_c
    cells = [["-" for _ in range(bar_width)] for _ in range(strings)]
    next_col = [0 for _ in range(strings)]

    for note in bar.notes:
        s_idx = note.string - 1
        if s_idx < 0 or s_idx >= strings:
            continue
        col = next_col[s_idx]
        if col >= bar_width:
            continue
        text = format_fret(style, note.fret, french_c_shape=french_c_shape)
        if len(text) > 2:
            text = text[-2:]
        for offset, ch in enumerate(text):
            if col + offset >= bar_width:
                break
            cells[s_idx][col + offset] = ch
        next_col[s_idx] = min(bar_width, col + max(1, len(text)) + 1)

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
    bar: Bar, bar_width: int, default_duration: int,
) -> list[tuple[int, int, bool]]:
    chords = [chord for chord in (bar.chords or []) if chord.notes]
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


def bar_cells_from_chords(
    bar: Bar,
    strings: int,
    bar_width: int,
    default_duration: int,
    style: str,
    french_c_shape: str = "normal",
    **legacy: str,
) -> list[list[str]]:
    legacy_c = legacy.get("french_c") or legacy.get("frenchc")
    if legacy_c and french_c_shape == "normal":
        french_c_shape = legacy_c
    cells = [["-" for _ in range(bar_width)] for _ in range(strings)]
    positions = chord_positions(bar, bar_width, default_duration)
    if not positions:
        return cells
    chords = [chord for chord in (bar.chords or []) if chord.notes]
    for chord, (col, _denom, _dot) in zip(chords, positions, strict=False):
        for note in chord.notes:
            s_idx = note.string - 1
            if 0 <= s_idx < strings and 0 <= col < bar_width:
                cells[s_idx][col] = format_fret(
                    style,
                    note.fret,
                    french_c_shape=french_c_shape,
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
    if denom <= 2:
        return 0
    count = 0
    value = max(1, denom)
    while value > 2:
        count += 1
        value //= 2
    return count


def flag_row_style(  # noqa: C901
    positions: list[tuple[int, int, bool]],
    bar_width: int,
    *,
    stem: str,
    flag: str,
    dot: str = ".",
    stem_width: int = 1,
) -> list[str]:
    row = [" " for _ in range(bar_width)]
    dot_positions: list[int] = []
    for col, denom, dotted in positions:
        row[col] = stem
        for extra in range(1, max(1, stem_width)):
            pos = col + extra
            if pos < bar_width and row[pos] == " ":
                row[pos] = stem
        slash_count = flag_count(denom)
        for i in range(slash_count):
            pos = col + max(1, stem_width) + i
            if pos < bar_width:
                row[pos] = flag
        if dotted:
            pos = col + max(1, stem_width) + slash_count
            if pos < bar_width:
                dot_positions.append(pos)
    for pos in dot_positions:
        idx = pos
        while idx < bar_width and row[idx] != " ":
            idx += 1
        if idx < bar_width:
            row[idx] = dot
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
            return [
                (solved[idx], denom, dot) for idx, (_c, denom, dot) in enumerate(ordered)
            ]
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
    dotted: set[tuple[int, int]] | None = None,
) -> list[tuple[int, int, bool]]:
    positions: list[tuple[int, int, bool]] = []
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
        if found != last or explicit:
            is_dotted = dotted is not None and (bar_index, col) in dotted
            positions.append((col, found, is_dotted))
            last = found
    return positions


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
    gap_before: dict[int, int] = {}

    if boundaries and extra > 0:
        idx = 0
        while extra > 0:
            key = boundaries[idx % len(boundaries)]
            gap_before[key] = gap_before.get(key, 0) + 1
            extra -= 1
            idx += 1
    elif extra > 0:
        idx = 1
        while extra > 0:
            key = raw_cols[idx % len(raw_cols)]
            gap_before[key] = gap_before.get(key, 0) + 1
            extra -= 1
            idx += 1

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
    raw_buckets = [
        min(bucket_count - 1, (raw_col * bucket_count) // width)
        for (raw_col, _denom, _dot) in ordered
    ]
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
            target = dst_start + ((raw_col - raw_start) * max(0, dst_end - dst_start)) // (
                raw_end - raw_start
            )
        seeded.append((max(0, min(content_width - 1, target)), denom, dot))
        raw_cols.append(raw_col)

    # Soft beat snap arranges note onsets; visible flag tails are placed later.
    # Using full flag spans here (especially with hidden redundant flags) over-reserves
    # width and leaves misleading trailing dash space.
    # Use a stem-only placeholder (minim-like) so this pass spaces note anchors only,
    # not visible flag tails.
    unit_seeded = [(col, 2, False) for (col, _denom, _dot) in seeded]
    spread = spread_flag_positions(unit_seeded, content_width, min_gap=max(0, min_gap))
    return {
        raw: col
        for raw, (col, _denom, _dot) in zip(raw_cols, spread, strict=False)
    }


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
    visible_map = {
        col: (denom, dot) for (col, denom, dot) in (visible_positions or all_positions)
    }
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
        curr_span = max(1, current_last - first_col)
        target_span = max(1, target_last - first_col)
        seeded = []
        for raw in ordered_raws:
            col = src_to_dest[raw]
            scaled = first_col + ((col - first_col) * target_span) // curr_span
            seeded.append((max(0, min(content_width - 1, scaled)), 4, False))
        spread = spread_flag_positions(seeded, content_width, min_gap=max(0, min_gap))
        trimmed = dict(src_to_dest)
        for raw, (col, _denom, _dot) in zip(ordered_raws, spread, strict=False):
            trimmed[raw] = col
        return trimmed
    return {raw: min(content_width - 1, col + shift) for raw, col in src_to_dest.items()}
