from __future__ import annotations

from petrucci.terminal.view.model import _scale_col


def _event_display_onset_cols(
    *,
    positions: list[tuple[int, int, bool]] | None,
    grid_map: list[int] | None,
    draw_pad: int,
) -> list[int]:
    if not positions or not grid_map:
        return []
    cols: list[int] = []
    seen: set[int] = set()
    for raw_col, _denom, _dot in positions:
        if not (0 <= raw_col < len(grid_map)):
            continue
        disp_col = draw_pad + grid_map[raw_col]
        if disp_col in seen:
            continue
        seen.add(disp_col)
        cols.append(disp_col)
    return cols


def _anchor_flag_positions_to_note_cols(
    positions: list[tuple[int, int, bool]],
    note_cols: list[int],
) -> list[tuple[int, int, bool]]:
    if not positions or not note_cols:
        return []
    ordered_note_cols = sorted(note_cols)
    anchored: list[tuple[int, int, bool]] = []
    note_idx = 0
    last_col = -1
    for raw_col, denom, dot in sorted(positions, key=lambda item: item[0]):
        while note_idx < len(ordered_note_cols) and ordered_note_cols[note_idx] <= last_col:
            note_idx += 1
        scan_idx = note_idx
        while scan_idx < len(ordered_note_cols) and ordered_note_cols[scan_idx] < raw_col:
            scan_idx += 1
        if scan_idx >= len(ordered_note_cols):
            scan_idx = note_idx
        if scan_idx >= len(ordered_note_cols):
            break
        col = ordered_note_cols[scan_idx]
        anchored.append((col, denom, dot))
        last_col = col
        note_idx = scan_idx + 1
    return anchored


def _interpolated_anchor_destination(
    raw_col: int,
    left: int,
    right: int,
    anchor_map: dict[int, int],
) -> int:
    left_dest = anchor_map[left]
    right_dest = anchor_map[right]
    span_dest = right_dest - left_dest
    if span_dest <= 1:
        return right_dest
    destination = left_dest + round(((raw_col - left) * span_dest) / (right - left))
    return max(left_dest + 1, min(right_dest - 1, destination))


def _anchor_destination(
    raw_col: int,
    anchors: list[int],
    anchor_map: dict[int, int],
    *,
    width_hint: int,
    content_width: int,
) -> int:
    if raw_col in anchor_map:
        return anchor_map[raw_col]
    left = max((column for column in anchors if column < raw_col), default=None)
    right = min((column for column in anchors if column > raw_col), default=None)
    if left is not None and right is not None and right > left:
        return _interpolated_anchor_destination(raw_col, left, right, anchor_map)
    if left is not None:
        return anchor_map[left] + (raw_col - left)
    if right is not None:
        return anchor_map[right] - (right - raw_col)
    return _scale_col(raw_col, width_hint, content_width)


def _expand_scale_map_from_anchors(
    all_positions: list[tuple[int, int, bool]],
    anchor_map: dict[int, int],
    *,
    content_width: int,
) -> dict[int, int]:
    if not all_positions:
        return {}
    raw_cols = sorted({col for col, _denom, _dot in all_positions})
    if not anchor_map:
        return {col: _scale_col(col, max(1, raw_cols[-1] + 1), content_width) for col in raw_cols}
    anchors = sorted(anchor_map)
    out: dict[int, int] = {}
    prev_dest = -1
    width_hint = max(1, raw_cols[-1] + 1)
    for raw_col in raw_cols:
        dest = _anchor_destination(
            raw_col,
            anchors,
            anchor_map,
            width_hint=width_hint,
            content_width=content_width,
        )
        dest = max(0, min(content_width - 1, dest))
        dest = max(dest, prev_dest)
        out[raw_col] = dest
        prev_dest = dest
    return out


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
    # The cell after the last event is the bar's append slot; it keeps a cell of its own.
    append_col = max(src_to_dest, default=-1) + 1
    for grid_col in range(width):
        is_event_col = grid_col in src_to_dest
        dest = src_to_dest.get(grid_col, _scale_col(grid_col, width, content))
        dest = max(0, min(content - 1, dest))
        if grid_col > 0 and dest < prev:
            dest = prev
        if (not is_event_col) and grid_col > 0 and dest > prev + 1:
            dest = prev + 1
        if grid_col == append_col and grid_col > 0 and dest == prev and prev + 1 < content:
            dest = prev + 1
        mapping.append(dest)
        prev = dest
    return mapping
