from __future__ import annotations

import unicodedata

from oud.core.render_utils import (
    smart_group_map,
    soft_beat_snap_map,
    spread_flag_positions,
    trim_right_slack_for_onsets,
)
from oud.core.spacing import auto_bar_plan
from oud.core.tab_policy import (
    bar_has_multifret_tokens,
    gliss_span_chars,
    hold_span_chars,
    multifret_event_gap,
    show_time_cue_for_bar,
    slur_span_chars,
    system_display_indices_for_bars,
    tie_notehead_hidden_cols,
    tie_notehead_parenthesize_cols,
    tie_span_chars,
    time_cue_side_pad,
    time_sig_inline_rows,
    visual_row_indices,
)
from oud.core.tab_style import resolve_tab_style_policy
from oud.core.tuning_utils import parse_tuning_pitches
from oud.core.view_model import (
    _bar_annotations,
    _bar_durations,
    _bar_imported_ft3_annotations,
    _bar_imported_ft3_ornaments,
    _bar_number_for_index,
    _bar_ornaments,
    _bar_span_row,
    _beamified_chord_flag_positions,
    _filter_redundant_positions,
    _flag_positions_all,
    _ft3_display_fingering_for_note,
    _ft3_ornament_glyph,
    _infer_time_signature,
    _inline_bass_row,
    _next_system_start,
    _parse_time_signature,
    _scale_col,
    _scale_row,
    _string_label,
    _tactus_row,
    bar_cells,
    bar_cells_from_chords,
    chord_positions,
    duration_display,
    flag_count,
    flag_positions_from_durations,
)
from oud.core.vocal_line import infer_vocal_events
from oud.ui.adapter import A_BOLD, A_REVERSE, Screen
from oud.ui.framebuffer import _split_display_clusters
from oud.ui.layout_map import layout_block_rows as _layout_block_rows
from oud.ui.render_bar import build_flag_rows
from oud.ui.render_helpers import apply_overrides, pad_row, safe_addstr
from oud.ui.render_text_lanes import (
    draw_melody_key_signature,
    draw_melody_time_signature,
    melody_key_signature_width,
)
from oud.ui.render_vocal import lyric_rows_for_bar, melody_rows_for_bar, vocal_onset_cols_for_bar

PlaybackOverlayCache = dict[tuple[int, int], list[tuple[int, int, str, int]]]


def _merge_mark_rows(base: list[str], user: list[str]) -> list[str]:
    if len(base) != len(user):
        return user
    out = list(base)
    for idx, ch in enumerate(user):
        if ch != " ":
            out[idx] = ch
    return out


def _repeat_dot_display_rows(display_strings: int) -> set[int]:
    if display_strings <= 0:
        return set()
    if display_strings == 1:
        return {0}
    hi = min(display_strings - 1, display_strings // 2)
    lo = max(0, hi - 1)
    return {lo, hi}


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


def _overlay_sparse_mark_chars(
    stdscr: Screen,
    *,
    y: int,
    bar_x: int,
    draw_pad: int,
    grid_map: list[int],
    row_cells: list[str],
    keep: set[str],
) -> None:
    if not row_cells or not grid_map:
        return
    for src_col, ch in enumerate(row_cells):
        if ch not in keep:
            continue
        if not (0 <= src_col < len(grid_map)):
            continue
        dst_col = grid_map[src_col]
        safe_addstr(stdscr, y, bar_x + draw_pad + dst_col, ch)


def _place_parenthesize_tie_cues(  # noqa: C901
    *,
    ann_cells: list[str],
    orn_cells: list[str],
    tie_cells: list[str],
    slur_cells: list[str] | None,
    hold_cells: list[str] | None,
    gliss_cells: list[str] | None,
    paren_tie_cols: set[int],
    allow_ann_row: bool = True,
) -> None:
    def _place_open(end_col: int) -> None:
        if allow_ann_row and 0 <= end_col < len(ann_cells) and ann_cells[end_col] == " ":
            ann_cells[end_col] = "("
            return
        for row in (tie_cells, slur_cells or [], hold_cells or [], gliss_cells or []):
            left = end_col - 1
            while 0 <= left < len(row):
                if row[left] == " ":
                    row[left] = "("
                    return
                left -= 1

    def _place_close(end_col: int) -> None:
        for row in (tie_cells, orn_cells, slur_cells or [], hold_cells or [], gliss_cells or []):
            if 0 <= end_col < len(row) and row[end_col] == " ":
                row[end_col] = ")"
                return

    for end_col in paren_tie_cols:
        if not (0 <= end_col < len(tie_cells)):
            continue
        _place_open(end_col)
        _place_close(end_col)


def _merge_nonspace_rows(*rows: list[str]) -> list[str]:
    if not rows:
        return []
    width = len(rows[0])
    out = [" " for _ in range(width)]
    for row in rows:
        if len(row) != width:
            continue
        for idx, ch in enumerate(row):
            if ch != " ":
                out[idx] = ch
    return out


def _nearest_note_cell_idx(row_text: str, target_idx: int) -> int | None:
    clusters = _split_display_clusters(row_text)
    if not clusters:
        return None
    max_idx = len(clusters) - 1
    target_idx = max(0, min(max_idx, target_idx))
    for distance in range(5):
        right = target_idx + distance
        if 0 <= right <= max_idx and clusters[right] not in {" ", "-", "|"}:
            return right
        if distance == 0:
            continue
        left = target_idx - distance
        if 0 <= left <= max_idx and clusters[left] not in {" ", "-", "|"}:
            return left
    return None


def _playback_note_strings(bar, playback_col: int) -> set[int]:
    if not bar.chords or not (0 <= playback_col < len(bar.chords)):
        return set()
    chord = bar.chords[playback_col]
    return {note.string - 1 for note in chord.notes}


def _inline_fingering_glyph(ch: str, *, style: str = "french") -> str:
    supers = {
        "0": "⁰",
        "1": "¹",
        "2": "²",
        "3": "³",
        "4": "⁴",
        "5": "⁵",
        "6": "⁶",
        "7": "⁷",
        "8": "⁸",
        "9": "⁹",
        "t": "ᵗ",
        "T": "ᵀ",
    }
    subs = {
        "0": "₀",
        "1": "₁",
        "2": "₂",
        "3": "₃",
        "4": "₄",
        "5": "₅",
        "6": "₆",
        "7": "₇",
        "8": "₈",
        "9": "₉",
        "t": "ₜ",
        "T": "ₜ",
    }
    out: list[str] = []
    for part in ch:
        if unicodedata.combining(part):
            out.append(part)
            continue
        if style == "italian":
            out.append(supers.get(part, part))
        else:
            out.append(subs.get(part, part))
    return "".join(out)


def _combining_only_mark(text: str) -> bool:
    return bool(text) and all(unicodedata.combining(ch) for ch in text)


def _overlay_inline_local_marks(
    *,
    cells: list[list[str]],
    ann_cells: list[str],
    orn_cells: list[str],
    style: str = "french",
) -> None:
    if not cells:
        return
    strings = len(cells)
    width = len(cells[0])
    for col in range(min(width, len(ann_cells), len(orn_cells))):
        note_rows = [row for row in range(strings) if cells[row][col] != "-"]
        if not note_rows:
            continue
        target_row = note_rows[0]
        ann = ann_cells[col]
        orn = orn_cells[col]

        # Ornament/grace marker sits immediately to the right of the note (a#).
        if orn != " ":
            if _combining_only_mark(orn):
                cells[target_row][col] = cells[target_row][col] + orn
            else:
                right = col + 1
                if right < width and cells[target_row][right] == "-":
                    cells[target_row][right] = orn

        # Fingering/annotation marker uses compact unicode and must stay adjacent.
        # If there is no adjacent free slot, drop it instead of drifting.
        if ann != " ":
            mark = _inline_fingering_glyph(ann, style=style)
            if _combining_only_mark(mark):
                cells[target_row][col] = cells[target_row][col] + mark
            else:
                right = col + 1
                if right < width and cells[target_row][right] == "-":
                    cells[target_row][right] = mark


def _overlay_inline_local_marks_on_display_row(  # noqa: C901, PLR0912
    *,
    display_row_cells: list[str],
    source_row_cells: list[str],
    ann_cells: list[str],
    orn_cells: list[str],
    draw_pad: int,
    grid_map: dict[int, int] | list[int],
    style: str = "french",
    source_row_index: int | None = None,
    ann_target_rows: list[int] | None = None,
    orn_target_rows: list[int] | None = None,
) -> None:
    width = len(source_row_cells)
    for col in range(min(width, len(ann_cells), len(orn_cells))):
        if source_row_cells[col] == "-":
            continue
        if isinstance(grid_map, dict):
            mapped = grid_map.get(col, col)
        else:
            mapped = grid_map[col] if 0 <= col < len(grid_map) else col
        disp_col = draw_pad + mapped
        if not (0 <= disp_col < len(display_row_cells)):
            continue
        orn = orn_cells[col]
        if (
            orn != " "
            and orn_target_rows is not None
            and source_row_index is not None
            and (col >= len(orn_target_rows) or orn_target_rows[col] != source_row_index)
        ):
            orn = " "
        if orn != " ":
            if _combining_only_mark(orn):
                display_row_cells[disp_col] = display_row_cells[disp_col] + orn
            else:
                right = disp_col + 1
                if right < len(display_row_cells) and display_row_cells[right] in ("-", " "):
                    display_row_cells[right] = orn
        ann = ann_cells[col]
        if (
            ann != " "
            and ann_target_rows is not None
            and source_row_index is not None
            and (col >= len(ann_target_rows) or ann_target_rows[col] != source_row_index)
        ):
            ann = " "
        if ann != " ":
            mark = _inline_fingering_glyph(ann, style=style)
            if _combining_only_mark(mark):
                display_row_cells[disp_col] = display_row_cells[disp_col] + mark
            else:
                right = disp_col + 1
                if right < len(display_row_cells) and display_row_cells[right] in ("-", " "):
                    display_row_cells[right] = mark


def _merge_span_rows_with_cue_priority(  # noqa: C901
    *,
    slur_row: list[str] | None,
    hold_row: list[str] | None,
    gliss_row: list[str] | None,
    tie_row: list[str] | None,
    tuplet_row: list[str] | None = None,
) -> list[str]:
    source_rows = (slur_row, hold_row, gliss_row, tie_row, tuplet_row)
    base_rows = [row for row in source_rows if row is not None]
    if not base_rows:
        return []
    width = len(base_rows[0])
    out = [" " for _ in range(width)]
    for idx in range(width):
        chars = [
            row[idx]
            for row in (slur_row, hold_row, tie_row, tuplet_row)
            if row is not None and idx < len(row) and row[idx] != " "
        ]
        if not chars:
            continue
        if ")" in chars:
            out[idx] = ")"
            continue
        if "(" in chars:
            out[idx] = "("
            continue
        if (
            tuplet_row is not None
            and idx < len(tuplet_row)
            and tuplet_row[idx] != " "
        ):
            out[idx] = tuplet_row[idx]
            continue
        if tie_row is not None and idx < len(tie_row) and tie_row[idx] != " ":
            out[idx] = tie_row[idx]
            continue
        if gliss_row is not None and idx < len(gliss_row) and gliss_row[idx] != " ":
            out[idx] = gliss_row[idx]
            continue
        if hold_row is not None and idx < len(hold_row) and hold_row[idx] != " ":
            out[idx] = hold_row[idx]
            continue
        if slur_row is not None and idx < len(slur_row) and slur_row[idx] != " ":
            out[idx] = slur_row[idx]
    return out


_TUPLET_CUE_GLYPHS = {"²", "³", "⁴", "⁵", "⁶", "⁷", "⁸", "⁹"}


def _split_tuplet_cues_from_annotations(
    ann_cells: list[str],
    *,
    show_tuplets: bool,
) -> tuple[list[str], list[str]]:
    inline = list(ann_cells)
    tuplet = [" " for _ in ann_cells]
    for idx, ch in enumerate(ann_cells):
        if ch not in _TUPLET_CUE_GLYPHS:
            continue
        inline[idx] = " "
        if show_tuplets:
            tuplet[idx] = ch
    return inline, tuplet


def _build_chord_scale_map(
    positions: list[tuple[int, int, bool]],
    bar_width: int,
    content_width: int,
    *,
    min_gap: int = 2,
) -> tuple[list[tuple[int, int, bool]], dict[int, int]]:
    scaled_positions = [
        (_scale_col(pos, bar_width, content_width), denom, dot)
        for (pos, denom, dot) in positions
    ]
    spread_positions = spread_flag_positions(
        scaled_positions,
        content_width,
        min_gap=max(0, min_gap),
    )
    ordered_raw = sorted(positions, key=lambda item: item[0])
    src_to_dest = {
        raw_col: scaled_col
        for (raw_col, _raw_denom, _raw_dot), (scaled_col, _denom, _dot) in zip(
            ordered_raw, spread_positions, strict=False,
        )
    }
    return spread_positions, src_to_dest


def _target_note_rows_by_col(cells: list[list[str]]) -> list[int]:
    if not cells:
        return []
    width = len(cells[0])
    targets = [-1 for _ in range(width)]
    for col in range(width):
        for row_idx, row in enumerate(cells):
            if col < len(row) and row[col] != "-":
                targets[col] = row_idx
                break
    return targets


def _imported_ft3_mark_target_rows(  # noqa: C901, PLR0912
    *,
    bar,
    total_strings: int,
    grid_width: int,
    default_duration: int,
    fingering_mode: str,
    ornament_mode: str,
) -> tuple[list[int], list[int]]:
    ann_targets = [-1 for _ in range(grid_width)]
    orn_targets = [-1 for _ in range(grid_width)]
    if not getattr(bar, "chords", None):
        return ann_targets, orn_targets
    positions = chord_positions(bar, grid_width, default_duration)
    for idx, chord in enumerate(bar.chords):
        if idx >= len(positions):
            break
        col = positions[idx][0]
        if not (0 <= col < grid_width):
            continue
        if ann_targets[col] < 0:
            for note in chord.notes:
                if not (1 <= note.string <= total_strings):
                    continue
                if _ft3_display_fingering_for_note(note, fingering_mode=fingering_mode):
                    ann_targets[col] = note.string - 1
                    break
        if orn_targets[col] < 0:
            for note in chord.notes:
                if not (1 <= note.string <= total_strings):
                    continue
                left = note.left_ornament
                right = note.right_ornament
                if ornament_mode == "left":
                    picked = left
                elif ornament_mode == "right":
                    picked = right
                elif ornament_mode == "both":
                    picked = left or right
                else:
                    picked = None
                if _ft3_ornament_glyph(picked):
                    orn_targets[col] = note.string - 1
                    break
    return ann_targets, orn_targets


def _note_event_columns(cells: list[list[str]], total_strings: int, grid_width: int) -> list[int]:
    cols: list[int] = []
    for col in range(grid_width):
        for actual in range(total_strings):
            if cells[actual][col] != "-":
                cols.append(col)
                break
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
        if raw_col in anchor_map:
            dest = anchor_map[raw_col]
        else:
            left = max((col for col in anchors if col < raw_col), default=None)
            right = min((col for col in anchors if col > raw_col), default=None)
            if left is not None and right is not None and right > left:
                left_dest = anchor_map[left]
                right_dest = anchor_map[right]
                span_raw = right - left
                span_dest = right_dest - left_dest
                if span_dest > 1:
                    dest = left_dest + round(((raw_col - left) * span_dest) / span_raw)
                    dest = max(left_dest + 1, min(right_dest - 1, dest))
                else:
                    dest = right_dest
            elif left is not None:
                dest = anchor_map[left] + (raw_col - left)
            elif right is not None:
                dest = anchor_map[right] - (right - raw_col)
            else:
                dest = _scale_col(raw_col, width_hint, content_width)
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


def _required_flag_content_width(
    positions: list[tuple[int, int, bool]],
    *,
    min_gap: int = 1,
) -> int:
    if not positions:
        return 1
    spans = [1 + flag_count(denom) + (1 if dot else 0) for (_c, denom, dot) in positions]
    return max(1, sum(spans) + max(0, len(spans) - 1) * max(0, min_gap))


def _required_duration_content_width(
    positions: list[tuple[int, int, bool]],
    *,
    min_gap: int = 1,
) -> int:
    if not positions:
        return 1
    spans = [max(1, len(duration_display(denom, dot))) for (_c, denom, dot) in positions]
    return max(1, sum(spans) + max(0, len(spans) - 1) * max(0, min_gap))


def _required_auto_display_width_for_bar(
    bar,
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
    positions, grid_width = _chord_positions_distinct(bar, bar_width, default_duration)
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
    min_content = _required_flag_content_width(ordered_flags, min_gap=flag_gap)
    note_cols = _note_event_columns(cells, total_strings, grid_width)
    # Keep at least one visible dash between noteheads and also before the right barline.
    # Required note span plus one trailing dash before the closing barline.
    if note_cols:
        min_note_content = 2 + (max(0, len(note_cols) - 1) * max(1, event_gap))
        min_content = max(min_content, min_note_content)
    if show_dur:
        min_content = max(
            min_content,
            _required_duration_content_width(ordered_flags, min_gap=flag_gap),
        )
    lyric_rows = getattr(bar, "lyric_event_rows", None) or []
    if lyric_rows:
        lyric_content = max(
            (
                sum(len((ev.text or "").strip()) for ev in row if (ev.text or "").strip())
                + max(0, sum(1 for ev in row if (ev.text or "").strip()) - 1)
                for row in lyric_rows
            ),
            default=0,
        )
        min_content = max(min_content, lyric_content)
    elif getattr(bar, "lyrics", None):
        lyric_content = max(
            (len(" ".join(part for part in bar.lyrics if part.strip()).strip()),),
            default=0,
        )
        min_content = max(min_content, lyric_content)
    melody_events = getattr(bar, "melody_events", None) or []
    if melody_events:
        melody_content = sum(max(1, len((ev.text or "").strip())) for ev in melody_events)
        melody_content += max(0, len(melody_events) - 1)
        min_content = max(min_content, melody_content)
    return max(1, min_content + (barpad * 2) + max(0, cue_pad_total))


def _redistribute_extra_width(  # noqa: C901, PLR0912
    widths: list[int],
    gaps: list[int],
    *,
    spacing_fill: str,
    extra: int,
) -> None:
    if not widths or extra <= 0:
        return
    if len(widths) == 1:
        widths[0] += extra
        return
    if spacing_fill == "stretch":
        left = 0
        right = len(widths) - 1
        while extra > 0 and left <= right:
            widths[left] += 1
            extra -= 1
            if extra <= 0:
                break
            if right != left:
                widths[right] += 1
                extra -= 1
            left += 1
            right -= 1
            if left > right:
                left = 0
                right = len(widths) - 1
        return
    if spacing_fill == "smart":
        idx = 0
        while extra > 0:
            widths[idx] += 1
            extra -= 1
            idx = (idx + 1) % len(widths)
        return
    if spacing_fill == "edge":
        if len(gaps) == 1:
            gaps[0] += extra
            return
        while extra > 0 and gaps:
            gaps[0] += 1
            extra -= 1
            if extra <= 0:
                break
            gaps[-1] += 1
            extra -= 1


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
    for grid_col in range(width):
        is_event_col = grid_col in src_to_dest
        dest = src_to_dest.get(grid_col, _scale_col(grid_col, width, content))
        dest = max(0, min(content - 1, dest))
        if grid_col > 0 and dest < prev:
            dest = prev
        if (not is_event_col) and grid_col > 0 and dest > prev + 1:
            dest = prev + 1
        mapping.append(dest)
        prev = dest
    return mapping


def _chord_positions_distinct(
    bar,
    bar_width: int,
    default_duration: int,
) -> tuple[list[tuple[int, int, bool]], int]:
    if not bar.chords:
        return chord_positions(bar, bar_width, default_duration), bar_width
    width = max(1, bar_width, len(bar.chords))
    max_width = max(width, len(bar.chords) * 2 + 2)
    while width <= max_width:
        positions = chord_positions(bar, width, default_duration)
        cols = [col for col, _denom, _dot in positions]
        if len(cols) == len(set(cols)):
            return positions, width
        width += 1
    return chord_positions(bar, max_width, default_duration), max_width


def _playback_scaled_col_for_chords(
    *,
    playback_col: int,
    bar_width: int,
    grid_width: int,
    content_width: int,
    positions: list[tuple[int, int, bool]],
    src_to_dest: dict[int, int],
) -> int:
    if not positions:
        return 0
    if 0 <= playback_col < len(positions):
        raw_col = positions[playback_col][0]
    else:
        raw_col = _scale_col(playback_col, bar_width, grid_width)
    col = src_to_dest.get(raw_col, _scale_col(raw_col, grid_width, content_width))
    return max(0, min(content_width - 1, col))


def _playback_in_range(bar, playback_col: int, bar_width: int) -> bool:
    if playback_col < 0:
        return False
    if bar.chords:
        return playback_col < len(bar.chords)
    return playback_col < bar_width


def _melody_playback_col(
    *,
    bar,
    playback_col: int,
    onset_cols: list[int],
    tuning_pitches: list[int],
) -> int | None:
    if playback_col < 0 or not onset_cols:
        return None
    vocal_events = infer_vocal_events(bar, tuning_pitches=tuning_pitches)
    for event in vocal_events:
        if event.chord_index != playback_col:
            continue
        if 0 <= event.onset_index < len(onset_cols):
            return onset_cols[event.onset_index]
    chord_count = len(bar.chords)
    if chord_count > 1 and len(onset_cols) > 1:
        mapped = round(playback_col * (len(onset_cols) - 1) / (chord_count - 1))
        mapped = max(0, min(len(onset_cols) - 1, mapped))
        return onset_cols[mapped]
    if 0 <= playback_col < len(onset_cols):
        return onset_cols[playback_col]
    return onset_cols[-1]


def _tab_playback_highlight_ops(
    *,
    bar,
    playback_col: int,
    bar_width: int,
    grid_width: int,
    positions: list[tuple[int, int, bool]],
    src_to_dest: dict[int, int],
    draw_pad: int,
    display_width: int,
    row_start: int,
    rows: dict[str, int | None],
    system_display_strings: int,
    system_visual_indices: list[int],
    rendered_staff_rows: list[str],
    bar_x: int,
) -> tuple[list[tuple[int, int, str, int]], int]:
    content_width = max(1, display_width - draw_pad * 2)
    if bar.chords:
        scaled_play_col = _playback_scaled_col_for_chords(
            playback_col=playback_col,
            bar_width=bar_width,
            grid_width=grid_width,
            content_width=content_width,
            positions=positions,
            src_to_dest=src_to_dest,
        )
    else:
        scaled_play_col = _scale_col(playback_col, bar_width, content_width)
    note_strings = _playback_note_strings(bar, playback_col)
    playback_cell_idx = draw_pad + scaled_play_col
    ops: list[tuple[int, int, str, int]] = []

    for display_idx in range(system_display_strings):
        actual = system_visual_indices[display_idx]
        y = row_start + (rows["staff"] or 0) + display_idx
        row_text = (
            rendered_staff_rows[display_idx]
            if display_idx < len(rendered_staff_rows)
            else ""
        )
        row_clusters = _split_display_clusters(row_text)
        if not (0 <= playback_cell_idx < len(row_clusters)):
            continue
        target_idx = playback_cell_idx
        if bar.chords:
            if actual not in note_strings:
                continue
            nearest = _nearest_note_cell_idx(row_text, playback_cell_idx)
            if nearest is None:
                continue
            target_idx = nearest
        ch = row_clusters[target_idx]
        if ch in {" ", "-", "|"}:
            continue
        ops.append((y, bar_x + target_idx, ch, A_REVERSE))
    return ops, scaled_play_col


def _playback_marker_ops(
    *,
    bar,
    playback_col: int,
    scaled_play_col: int,
    row_start: int,
    rows: dict[str, int | None],
    system_display_strings: int,
    draw_pad: int,
    bar_x: int,
    display_width: int,
    tuning_pitches: list[int],
    melody_row_base: int | None,
    vocal_onset_cols: list[int],
    rendered_melody_rows: list[str] | None,
) -> list[tuple[int, int, str, int]]:
    marker_y = row_start + (rows["staff"] or 0) + system_display_strings
    marker_x = bar_x + draw_pad + scaled_play_col
    if melody_row_base is not None and marker_y >= melody_row_base:
        marker_y = melody_row_base
        marker_x = max(0, bar_x - 2)
    ops: list[tuple[int, int, str, int]] = [(marker_y, marker_x, "^", A_BOLD)]
    if melody_row_base is None:
        return ops
    melody_col = _melody_playback_col(
        bar=bar,
        playback_col=playback_col,
        onset_cols=vocal_onset_cols,
        tuning_pitches=tuning_pitches,
    )
    if melody_col is None:
        return ops
    melody_x = bar_x + max(0, min(display_width - 1, melody_col))
    if rendered_melody_rows:
        for rel_y, melody_row in enumerate(rendered_melody_rows):
            if 0 <= melody_col < len(melody_row) and melody_row[melody_col] == " ":
                ops.append((melody_row_base + rel_y, melody_x, "v", A_BOLD))
                return ops
    ops.append(
        (
            melody_row_base,
            max(0, bar_x - 2),
            "v",
            A_BOLD,
        ),
    )
    return ops


def _playback_overlay_ops_for_bar(
    *,
    bar,
    playback_col: int,
    bar_width: int,
    grid_width: int,
    positions: list[tuple[int, int, bool]],
    src_to_dest: dict[int, int],
    draw_pad: int,
    display_width: int,
    row_start: int,
    rows: dict[str, int | None],
    system_display_strings: int,
    system_visual_indices: list[int],
    rendered_staff_rows: list[str],
    bar_x: int,
    tuning_pitches: list[int],
    melody_row_base: int | None,
    vocal_onset_cols: list[int],
    rendered_melody_rows: list[str] | None,
) -> list[tuple[int, int, str, int]]:
    if not _playback_in_range(bar, playback_col, bar_width):
        return []
    note_ops, scaled_play_col = _tab_playback_highlight_ops(
        bar=bar,
        playback_col=playback_col,
        bar_width=bar_width,
        grid_width=grid_width,
        positions=positions,
        src_to_dest=src_to_dest,
        draw_pad=draw_pad,
        display_width=display_width,
        row_start=row_start,
        rows=rows,
        system_display_strings=system_display_strings,
        system_visual_indices=system_visual_indices,
        rendered_staff_rows=rendered_staff_rows,
        bar_x=bar_x,
    )
    return note_ops + _playback_marker_ops(
        bar=bar,
        playback_col=playback_col,
        scaled_play_col=scaled_play_col,
        row_start=row_start,
        rows=rows,
        system_display_strings=system_display_strings,
        draw_pad=draw_pad,
        bar_x=bar_x,
        display_width=display_width,
        tuning_pitches=tuning_pitches,
        melody_row_base=melody_row_base,
        vocal_onset_cols=vocal_onset_cols,
        rendered_melody_rows=rendered_melody_rows,
    )


def _resolved_bar_time_value(
    piece,
    bar_index: int,
    time_setting: str,
    default_duration: int,
) -> str:
    value = piece.bars[bar_index].time_sig or time_setting
    if value in ("auto", "detect"):
        inferred = _infer_time_signature(piece.bars[bar_index], default_duration)
        value = inferred or "C"
    return value


def render_systems(  # noqa: C901, PLR0912
    stdscr: Screen,
    *,
    piece,
    width: int,
    header_row: int,
    left_margin: int,
    block_h: int,
    systems: int,
    total_strings: int,
    display_indices: list[int],  # noqa: ARG001
    display_strings: int,
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
    glisses: list[tuple[int, int, int]] | None,
    settings: dict[str, str],
    stave_breaks: set[int],
    playback_bar: int | None,
    playback_col: int | None,
    playback_markers: list[tuple[int, int]] | None,
    include_meta: bool,
    show_dur: bool,
    show_extras: bool,
    show_tuplets: bool,
    show_tactus: bool,
    hide_redundant: bool,
    double_stems: bool,
    reverse_strings: bool,
    max_chords: int,
    spacing_mode: str,
    spacing_fill: str,
    bar_gap: int,
    barpad: int,
    usable_width: int,
    bars_per_line_limit: int,
    default_duration: int,
    tuning_labels: list[str],
    basslabels: str,
    chord_wrap_limit: int,
    show_melody: bool = False,
    melody_rows_count: int = 1,
    show_lyrics: bool = False,
    lyric_rows_count: int = 0,
    vocal_pos: str = "bottom",
    playback_cache: PlaybackOverlayCache | None = None,
    cursor_display_maps: dict[int, list[int]] | None = None,
) -> None:
    if glisses is None:
        glisses = []
    effective_playback_markers = list(playback_markers or [])
    if (
        not effective_playback_markers
        and playback_bar is not None
        and playback_col is not None
    ):
        effective_playback_markers = [(playback_bar, playback_col)]
    style_policy = resolve_tab_style_policy(settings)
    total_bars = len(piece.bars)
    melody_rows_count = max(1, melody_rows_count) if show_melody else 0
    tuning_pitches = parse_tuning_pitches(settings.get("tuning", ""))
    duet_width_lock = settings.get("duetwidthlock", "off") == "on"
    current_bar_start = bar_offset
    for sys_idx in range(systems):
        row_start = header_row + 1 + sys_idx * block_h
        rows_proto = _layout_block_rows(
            display_strings,
            include_meta,
            show_dur,
            show_extras,
            show_tuplets,
            show_tactus,
            double_stems,
            show_melody=show_melody,
            melody_rows_count=melody_rows_count,
            show_lyrics=show_lyrics,
            lyric_rows_count=lyric_rows_count,
            vocal_pos=vocal_pos,
        )
        # Clear the system block to avoid stale characters after reflow/resizes.
        for clear_row in range(row_start, row_start + block_h):
            safe_addstr(stdscr, clear_row, 0, " " * width)
        bar_start = current_bar_start
        if bar_start >= total_bars:
            break
        gaps_after: list[int] = []
        bar_widths: list[int] = []
        if spacing_mode == "auto":
            bar_indices, bar_widths, gaps_after = auto_bar_plan(
                bars=piece.bars,
                bar_start=bar_start,
                usable_width=usable_width,
                bar_width=bar_width,
                overrides=overrides,
                durations=durations,
                default_duration=default_duration,
                dotted=dotted,
                bar_gap=bar_gap,
                spacing_fill=spacing_fill,
                stave_breaks=stave_breaks,
                bars_per_line_limit=bars_per_line_limit,
                max_chords=max_chords,
                chord_wrap_limit=chord_wrap_limit,
            )
            # Enforce per-bar minimums up-front so later rendering never expands
            # bars after fit (which can visually split bars in stretch modes).
            time_setting = settings.get("time", "C")
            min_widths: list[int] = []
            for abs_bar in bar_indices:
                current_time = _resolved_bar_time_value(
                    piece, abs_bar, time_setting, default_duration,
                )
                _beats, _unit, sig_label = _parse_time_signature(current_time)
                prev_time = (
                    _resolved_bar_time_value(piece, abs_bar - 1, time_setting, default_duration)
                    if abs_bar > 0
                    else None
                )
                show_cue = show_time_cue_for_bar(
                    bar_index=abs_bar,
                    current_time_value=current_time,
                    prev_time_value=prev_time,
                    sig_label=sig_label,
                )
                cue_pad_extra = time_cue_side_pad(show_time_cue=show_cue, scale_bar=True)
                if show_cue and current_time in {"C|", "c|", "2/2"}:
                    cue_pad_extra = max(cue_pad_extra, 3)
                if show_cue and current_time in {"O", "o", "3/4"}:
                    cue_pad_extra = max(cue_pad_extra, 3)
                compact_fill = spacing_fill == "compact"
                auto_event_gap = 1 if compact_fill else 2
                auto_flag_gap = 0 if compact_fill else (2 if spacing_fill == "smart" else 1)
                min_widths.append(
                    _required_auto_display_width_for_bar(
                        piece.bars[abs_bar],
                        total_strings=total_strings,
                        bar_width=bar_width,
                        default_duration=default_duration,
                        style=settings.get("style", "french"),
                        french_c=settings.get("frenchc", "normal"),
                        fretlabelmode=settings.get("fretlabelmode", "auto"),
                        show_dur=show_dur and rows_proto["dur"] is not None,
                        hide_redundant=hide_redundant,
                        barpad=barpad,
                        flag_gap=auto_flag_gap,
                        event_gap=auto_event_gap,
                        cue_pad_total=cue_pad_extra * 2,
                    ),
                )
            bar_widths = [
                max(width, min_width)
                for width, min_width in zip(bar_widths, min_widths, strict=False)
            ]
            while bar_widths and (sum(bar_widths) + sum(gaps_after)) > usable_width:
                bar_widths.pop()
                bar_indices = bar_indices[: len(bar_widths)]
                gaps_after = gaps_after[: max(0, len(bar_widths) - 1)]
            extra = max(0, usable_width - (sum(bar_widths) + sum(gaps_after)))
            _redistribute_extra_width(
                bar_widths,
                gaps_after,
                spacing_fill=spacing_fill,
                extra=extra,
            )
            bar_end = bar_indices[-1] + 1 if bar_indices else bar_start
        else:
            bars_per_line = bars_per_line_limit
            bars_per_line = max(1, bars_per_line)
            bar_end = _next_system_start(piece.bars, bar_start, bars_per_line, stave_breaks)
            bar_end = min(total_bars, bar_end)
            bar_indices = list(range(bar_start, bar_end))
        # Show extra bass rows only when they are used in this rendered system.
        system_display_indices = system_display_indices_for_bars(
            piece.bars[bar_start:bar_end],
            total_strings=total_strings,
        )
        system_display_strings = len(system_display_indices)
        system_visual_indices = visual_row_indices(
            system_display_indices,
            reverse=reverse_strings,
        )
        rows = _layout_block_rows(
            system_display_strings,
            include_meta,
            show_dur,
            show_extras,
            show_tuplets,
            show_tactus,
            double_stems,
            show_melody=show_melody,
            melody_rows_count=melody_rows_count,
            show_lyrics=show_lyrics,
            lyric_rows_count=lyric_rows_count,
            vocal_pos=vocal_pos,
        )
        for display_idx in range(system_display_strings):
            label = "  "
            if sys_idx == 0:
                actual = system_visual_indices[display_idx]
                label = _string_label(actual, total_strings, tuning_labels, basslabels)
            safe_addstr(stdscr, row_start + (rows["staff"] or 0) + display_idx, 0, label)
        if rows.get("melody") is not None:
            for melody_row_idx in range(melody_rows_count):
                safe_addstr(
                    stdscr,
                    row_start + (rows["melody"] or 0) + melody_row_idx,
                    0,
                    "  ",
                )
        lyric_base = rows.get("lyric")
        lyric_row_offsets = (
            tuple((lyric_base or 0) + idx for idx in range(max(0, lyric_rows_count)))
            if lyric_base is not None and lyric_rows_count > 0
            else ()
        )
        for lyric_row in lyric_row_offsets:
            safe_addstr(stdscr, row_start + lyric_row, 0, "  ")

        bar_x = left_margin
        if spacing_mode == "auto" and bar_widths:
            total_width = sum(bar_widths) + bar_gap * max(0, len(bar_widths) - 1)
            if spacing_fill == "center":
                extra_left = max(0, (usable_width - total_width) // 2)
                bar_x += extra_left
        for local_idx, bar in enumerate(piece.bars[bar_start:bar_end]):
            abs_bar = bar_start + local_idx
            style = settings.get("style", "french")
            french_c = settings.get("frenchc", "normal")
            fretlabelmode = settings.get("fretlabelmode", "auto")
            chord_positions_all: list[tuple[int, int, bool]] = []
            positions: list[tuple[int, int, bool]] = []
            src_to_dest: dict[int, int] = {}
            grid_width = bar_width
            if bar.chords:
                chord_positions_all, grid_width = _chord_positions_distinct(
                    bar,
                    bar_width,
                    default_duration,
                )
                cells = bar_cells_from_chords(
                    bar,
                    total_strings,
                    grid_width,
                    default_duration,
                    style,
                    french_c=french_c,
                    label_mode=fretlabelmode,
                )
            else:
                cells = bar_cells(
                    bar,
                    total_strings,
                    bar_width,
                    style,
                    french_c=french_c,
                    label_mode=fretlabelmode,
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
            time_setting = settings.get("time", "C")
            time_value = _resolved_bar_time_value(piece, abs_bar, time_setting, default_duration)
            beats, _unit, _sig_label = _parse_time_signature(time_value)
            tactus = _tactus_row(grid_width, beats)
            barline = bar.barline or "|"
            repeat = bar.repeat or ""
            repeat_glyph = repeat if repeat in {".:", ":.", "."} else ""
            repeat_cue = repeat if not repeat_glyph else ""
            ending_numbers = tuple(sorted(set(bar.ending_numbers)))
            ending_cue = ""
            if ending_numbers:
                joined = ",".join(str(num) for num in ending_numbers)
                ending_cue = f"[{joined}.]"
            repeat_rows = _repeat_dot_display_rows(system_display_strings)
            repeat_left = repeat in {".:", ":|:", "."}
            repeat_right = repeat in {":.", ":|:", "."}
            sign_cues: list[str] = []
            if bar.fermata:
                sign_cues.append("^")
            if bar.dynamic:
                sign_cues.append(bar.dynamic)
            imported_ann = [" " for _ in range(grid_width)]
            imported_orn = [" " for _ in range(grid_width)]
            imported_ann_targets = [-1 for _ in range(grid_width)]
            imported_orn_targets = [-1 for _ in range(grid_width)]
            show_fingerings = style_policy.showfingerings
            show_ornaments = style_policy.showornaments
            if show_fingerings:
                imported_ann = _bar_imported_ft3_annotations(
                    bar,
                    bar_width=grid_width,
                    default_duration=default_duration,
                    fingering_mode=settings.get("ft3fingering", "both"),
                )
            if show_ornaments:
                imported_orn = _bar_imported_ft3_ornaments(
                    bar,
                    bar_width=grid_width,
                    default_duration=default_duration,
                    ornament_mode=settings.get("ft3ornaments", "both"),
                )
            if show_fingerings or show_ornaments:
                imported_ann_targets, imported_orn_targets = _imported_ft3_mark_target_rows(
                    bar=bar,
                    total_strings=total_strings,
                    grid_width=grid_width,
                    default_duration=default_duration,
                    fingering_mode=settings.get("ft3fingering", "both"),
                    ornament_mode=settings.get("ft3ornaments", "both"),
                )
            ann_cells = _merge_mark_rows(
                imported_ann,
                _bar_annotations(annotations, abs_bar, grid_width),
            )
            ann_cells, tuplet_cells = _split_tuplet_cues_from_annotations(
                ann_cells,
                show_tuplets=show_tuplets,
            )
            local_orn = (
                _bar_ornaments(ornaments, abs_bar, grid_width)
                if show_ornaments
                else [" " for _ in range(grid_width)]
            )
            orn_cells = _merge_mark_rows(
                imported_orn,
                local_orn,
            )
            slur_chars = slur_span_chars(style_policy.slurcuestyle)
            if slur_chars is None:
                slur_cells = [" " for _ in range(grid_width)]
            else:
                slur_cells = _bar_span_row(slurs, abs_bar, grid_width, *slur_chars)
            tie_chars = tie_span_chars(style_policy.tiecuestyle)
            if tie_chars is None:
                tie_cells = [" " for _ in range(grid_width)]
            else:
                tie_cells = _bar_span_row(ties, abs_bar, grid_width, *tie_chars)
            hold_chars = hold_span_chars(style_policy.holdcuestyle)
            if hold_chars is None:
                hold_cells = [" " for _ in range(grid_width)]
            else:
                hold_cells = _bar_span_row(holds, abs_bar, grid_width, *hold_chars)
            gliss_chars = gliss_span_chars(style_policy.glisscuestyle)
            if gliss_chars is None:
                gliss_cells = [" " for _ in range(grid_width)]
            else:
                gliss_cells = _bar_span_row(glisses, abs_bar, grid_width, *gliss_chars)
            apply_overrides(cells, overrides, abs_bar, total_strings, grid_width)
            top_note_targets = _target_note_rows_by_col(cells)
            ann_target_rows = list(top_note_targets)
            orn_target_rows = list(top_note_targets)
            for col, row_idx in enumerate(imported_ann_targets):
                if row_idx >= 0 and col < len(ann_target_rows) and imported_ann[col] != " ":
                    ann_target_rows[col] = row_idx
            for col, row_idx in enumerate(imported_orn_targets):
                if row_idx >= 0 and col < len(orn_target_rows) and imported_orn[col] != " ":
                    orn_target_rows[col] = row_idx
            hidden_tie_cols = tie_notehead_hidden_cols(
                ties,
                bar_index=abs_bar,
                mode=style_policy.tienoteheads,
            )
            paren_tie_cols = tie_notehead_parenthesize_cols(
                ties,
                bar_index=abs_bar,
                mode=style_policy.tienoteheads,
            )
            if hidden_tie_cols:
                for hide_col in hidden_tie_cols:
                    if not (0 <= hide_col < grid_width):
                        continue
                    for row_cells in cells:
                        if row_cells[hide_col] != "-":
                            row_cells[hide_col] = "-"
            if paren_tie_cols:
                _place_parenthesize_tie_cues(
                    ann_cells=ann_cells,
                    orn_cells=orn_cells,
                    tie_cells=tie_cells,
                    slur_cells=slur_cells,
                    hold_cells=hold_cells,
                    gliss_cells=gliss_cells,
                    paren_tie_cols=paren_tie_cols,
                    allow_ann_row=rows["ann"] is not None,
                )
            display_width = bar_width
            if spacing_mode == "auto":
                display_width = bar_widths[local_idx]
            scale_bar = spacing_mode == "auto"
            if bar.chords:
                preview_flags = (
                    _filter_redundant_positions(chord_positions_all)
                    if hide_redundant
                    else chord_positions_all
                )
                smart_gap = 2 if spacing_fill == "smart" else 1
                min_content = _required_flag_content_width(preview_flags, min_gap=smart_gap)
                note_cols = _note_event_columns(cells, total_strings, grid_width)
                min_content = max(min_content, len(note_cols))
                if show_dur and rows["dur"] is not None:
                    min_content = max(
                        min_content,
                        _required_duration_content_width(preview_flags, min_gap=smart_gap),
                    )
                min_display = min_content + barpad * 2
                if min_display > display_width and spacing_mode != "auto" and not duet_width_lock:
                    display_width = min_display
                    scale_bar = True
            pad = barpad if scale_bar else 0
            prev_time = (
                _resolved_bar_time_value(piece, abs_bar - 1, time_setting, default_duration)
                if abs_bar > 0
                else None
            )
            show_time_sig_here = show_time_cue_for_bar(
                bar_index=abs_bar,
                current_time_value=time_value,
                prev_time_value=prev_time,
                sig_label=_sig_label,
            )
            wrote_time_sig = show_time_sig_here
            cue_pad_extra = time_cue_side_pad(show_time_cue=show_time_sig_here, scale_bar=scale_bar)
            if show_time_sig_here and not scale_bar:
                # Packed/fixed layout also needs an auftact lane; otherwise the first
                # rhythm flag starts directly above the in-staff time cue.
                cue_pad_extra = max(
                    cue_pad_extra,
                    time_cue_side_pad(show_time_cue=True, scale_bar=True),
                )
            if show_time_sig_here and time_value in {"C|", "c|", "2/2"}:
                cue_pad_extra = max(cue_pad_extra, 3)
            if show_time_sig_here and time_value in {"O", "o", "3/4"}:
                cue_pad_extra = max(cue_pad_extra, 3)
            draw_pad = pad + cue_pad_extra
            if bar.chords and not scale_bar and not duet_width_lock:
                compact_fill = spacing_fill == "compact"
                fixed_event_gap = 1 if compact_fill else 2
                fixed_flag_gap = 0 if compact_fill else (2 if spacing_fill == "smart" else 1)
                display_width = max(
                    display_width,
                    _required_auto_display_width_for_bar(
                        bar,
                        total_strings=total_strings,
                        bar_width=bar_width,
                        default_duration=default_duration,
                        style=style,
                        french_c=french_c,
                        fretlabelmode=fretlabelmode,
                        show_dur=show_dur and rows["dur"] is not None,
                        hide_redundant=hide_redundant,
                        barpad=0,
                        flag_gap=fixed_flag_gap,
                        event_gap=fixed_event_gap,
                        cue_pad_total=draw_pad * 2,
                    ),
                )
            text_onset_cols: list[int] = []
            if rows["meta"] is not None:
                meta_row = row_start + (rows["meta"] or 0)
                if abs_bar == 0 and not wrote_time_sig:
                    safe_addstr(stdscr, meta_row, 0, " ")
                meta_x = bar_x
                if number is not None:
                    safe_addstr(stdscr, meta_row, meta_x, number)
                cue_parts: list[str] = []
                if ending_cue:
                    cue_parts.append(ending_cue)
                if repeat_cue:
                    cue_parts.append(repeat_cue)
                cue_parts.extend(sign_cues)
                if cue_parts:
                    cue_text = " ".join(cue_parts)
                    cue_x = meta_x + (len(number) + 1 if number is not None else 0)
                    safe_addstr(stdscr, meta_row, cue_x, cue_text)
            if rows["ann"] is not None:
                ann_row = ann_cells
                if scale_bar:
                    content_width = max(1, display_width - draw_pad * 2)
                    ann_row = _scale_row(ann_cells, content_width, " ")
                    ann_row = pad_row(ann_row, display_width, draw_pad)
                safe_addstr(stdscr, row_start + (rows["ann"] or 0), bar_x, "".join(ann_row))
            if rows["orn"] is not None:
                orn_row = orn_cells
                if scale_bar:
                    content_width = max(1, display_width - draw_pad * 2)
                    orn_row = _scale_row(orn_cells, content_width, " ")
                    orn_row = pad_row(orn_row, display_width, draw_pad)
                safe_addstr(stdscr, row_start + (rows["orn"] or 0), bar_x, "".join(orn_row))
            if rows["tactus"] is not None:
                tactus_row = tactus
                if scale_bar:
                    content_width = max(1, display_width - draw_pad * 2)
                    tactus_row = _scale_row(tactus, content_width, " ")
                    tactus_row = pad_row(tactus_row, display_width, draw_pad)
                safe_addstr(stdscr, row_start + (rows["tactus"] or 0), bar_x, "".join(tactus_row))
            scaled_tuplet_row: list[str] | None = None
            if rows.get("tuplet") is not None:
                scaled_tuplet_row = tuplet_cells
                if scale_bar:
                    content_width = max(1, display_width - draw_pad * 2)
                    scaled_tuplet_row = _scale_row(tuplet_cells, content_width, " ")
                    scaled_tuplet_row = pad_row(scaled_tuplet_row, display_width, draw_pad)
            scaled_slur_row: list[str] | None = None
            scaled_tie_row: list[str] | None = None
            scaled_hold_row: list[str] | None = None
            scaled_gliss_row: list[str] | None = None
            if rows["slur"] is not None:
                scaled_slur_row = slur_cells
                if scale_bar:
                    content_width = max(1, display_width - draw_pad * 2)
                    scaled_slur_row = _scale_row(slur_cells, content_width, " ")
                    scaled_slur_row = pad_row(scaled_slur_row, display_width, draw_pad)
            if rows["tie"] is not None:
                scaled_tie_row = tie_cells
                if scale_bar:
                    content_width = max(1, display_width - draw_pad * 2)
                    scaled_tie_row = _scale_row(tie_cells, content_width, " ")
                    scaled_tie_row = pad_row(scaled_tie_row, display_width, draw_pad)
            if rows["hold"] is not None:
                scaled_hold_row = hold_cells
                if scale_bar:
                    content_width = max(1, display_width - draw_pad * 2)
                    scaled_hold_row = _scale_row(hold_cells, content_width, " ")
                    scaled_hold_row = pad_row(scaled_hold_row, display_width, draw_pad)
            if rows.get("gliss") is not None:
                scaled_gliss_row = gliss_cells
                if scale_bar:
                    content_width = max(1, display_width - draw_pad * 2)
                    scaled_gliss_row = _scale_row(gliss_cells, content_width, " ")
                    scaled_gliss_row = pad_row(scaled_gliss_row, display_width, draw_pad)
            if bar.chords:
                visible_note_cols = set(_note_event_columns(cells, total_strings, grid_width))
                positions = [
                    item for item in chord_positions_all if item[0] in visible_note_cols
                ]
                flag_positions = _beamified_chord_flag_positions(
                    bar,
                    positions,
                    hide_redundant=hide_redundant,
                    default_duration=default_duration,
                )
                ordered_flags = sorted(flag_positions, key=lambda item: item[0])
                flagstyle = style_policy.flagstyle
                flaglean = style_policy.flaglean
                dur_source_positions: list[tuple[int, int]] = []
                if scale_bar:
                    content_width = max(1, display_width - draw_pad * 2)
                    event_min_gap = multifret_event_gap(
                        style=style,
                        policy=settings.get("multifretspacing", "collision-safe"),
                            has_multifret=bar_has_multifret_tokens(
                                bar,
                                style=style,
                                french_c_shape=french_c,
                                label_mode=fretlabelmode,
                            ),
                        )
                    if spacing_fill == "compact":
                        event_min_gap = max(1, event_min_gap - 1)
                    unit_anchor_min_gap = max(1, event_min_gap - 1)
                    if spacing_fill == "smart":
                        flag_min_gap = 1
                    elif spacing_fill == "compact":
                        flag_min_gap = 0
                    else:
                        flag_min_gap = 0
                    beatsnap_mode = settings.get("beatsnap", "off")
                    has_grid_groups = any(chord.grid for chord in bar.chords)
                    if has_grid_groups:
                        if beatsnap_mode == "soft" and beats > 1:
                            anchor_src_to_dest = soft_beat_snap_map(
                                ordered_flags,
                                grid_width=grid_width,
                                content_width=content_width,
                                beats=beats,
                                min_gap=max(1, flag_min_gap),
                            )
                            anchor_src_to_dest = trim_right_slack_for_onsets(
                                anchor_src_to_dest,
                                all_positions=ordered_flags,
                                visible_positions=ordered_flags,
                                content_width=content_width,
                                min_gap=max(1, flag_min_gap),
                            )
                        elif spacing_fill == "smart":
                            anchor_src_to_dest = smart_group_map(
                                ordered_flags,
                                ordered_flags,
                                content_width,
                                min_gap=max(1, flag_min_gap),
                            )
                        else:
                            _, anchor_src_to_dest = _build_chord_scale_map(
                                ordered_flags,
                                grid_width,
                                content_width,
                                min_gap=max(1, flag_min_gap),
                            )
                        if content_width > 1 and anchor_src_to_dest:
                            anchor_width = max(1, content_width - 1)
                            seeded_flag_positions = [
                                (
                                    _scale_col(
                                        anchor_src_to_dest.get(
                                            col,
                                            _scale_col(col, grid_width, content_width),
                                        ),
                                        content_width,
                                        anchor_width,
                                    ),
                                    denom,
                                    dot,
                                )
                                for (col, denom, dot) in ordered_flags
                            ]
                            spread_flag_positions_scaled = spread_flag_positions(
                                seeded_flag_positions,
                                anchor_width,
                                min_gap=max(1, flag_min_gap),
                            )
                            anchor_src_to_dest = {
                                raw_col: scaled_col
                                for (raw_col, _d1, _dot1), (scaled_col, _d2, _dot2) in zip(
                                    ordered_flags,
                                    spread_flag_positions_scaled,
                                    strict=False,
                                )
                            }
                        if len({col for col, _denom, _dot in ordered_flags}) < len(
                            {col for col, _denom, _dot in positions},
                        ):
                            # Redundant flag hiding may collapse several note onsets to a single
                            # visible flag anchor. Keep flag placement reduced, but map note columns
                            # from the full onset set so equally spaced attacks remain distinct.
                            if beatsnap_mode == "soft" and beats > 1:
                                src_to_dest = soft_beat_snap_map(
                                    positions,
                                    grid_width=grid_width,
                                    content_width=content_width,
                                    beats=beats,
                                    min_gap=unit_anchor_min_gap,
                                )
                                src_to_dest = trim_right_slack_for_onsets(
                                    src_to_dest,
                                    all_positions=positions,
                                    visible_positions=ordered_flags,
                                    content_width=content_width,
                                    min_gap=unit_anchor_min_gap,
                                )
                            elif spacing_fill == "smart":
                                src_to_dest = smart_group_map(
                                    positions,
                                    ordered_flags,
                                    content_width,
                                    min_gap=event_min_gap,
                                )
                            else:
                                _, src_to_dest = _build_chord_scale_map(
                                    positions,
                                    grid_width,
                                    content_width,
                                    min_gap=event_min_gap,
                                )
                            if content_width > 1 and src_to_dest:
                                anchor_width = max(1, content_width - 1)
                                seeded_event_positions = [
                                    (
                                        _scale_col(
                                            src_to_dest.get(
                                                col,
                                                _scale_col(col, grid_width, content_width),
                                            ),
                                            content_width,
                                            anchor_width,
                                        ),
                                        2,
                                        False,
                                    )
                                    for (col, _denom, _dot) in positions
                                ]
                                spread_event_positions = spread_flag_positions(
                                    seeded_event_positions,
                                    anchor_width,
                                    min_gap=unit_anchor_min_gap,
                                )
                                src_to_dest = {
                                    raw_col: scaled_col
                                    for (raw_col, _d1, _dot1), (scaled_col, _d2, _dot2) in zip(
                                        positions,
                                        spread_event_positions,
                                        strict=False,
                                    )
                                }
                        else:
                            src_to_dest = _expand_scale_map_from_anchors(
                                positions,
                                anchor_src_to_dest,
                                content_width=content_width,
                            )
                        final_flag_positions = [
                            (
                                anchor_src_to_dest.get(
                                    col,
                                    _scale_col(col, grid_width, content_width),
                                ),
                                denom,
                                dot,
                            )
                            for (col, denom, dot) in ordered_flags
                        ]
                    else:
                        if beatsnap_mode == "soft" and beats > 1:
                            src_to_dest = soft_beat_snap_map(
                                positions,
                                grid_width=grid_width,
                                content_width=content_width,
                                beats=beats,
                                min_gap=unit_anchor_min_gap,
                            )
                            src_to_dest = trim_right_slack_for_onsets(
                                src_to_dest,
                                all_positions=positions,
                                visible_positions=ordered_flags,
                                content_width=content_width,
                                min_gap=unit_anchor_min_gap,
                            )
                        elif spacing_fill == "smart":
                            src_to_dest = smart_group_map(
                                positions,
                                ordered_flags,
                                content_width,
                                min_gap=event_min_gap,
                            )
                        else:
                            _, src_to_dest = _build_chord_scale_map(
                                positions,
                                grid_width,
                                content_width,
                                min_gap=event_min_gap,
                            )
                        if content_width > 1 and src_to_dest:
                            anchor_width = max(1, content_width - 1)
                            seeded_event_positions = [
                                (
                                    _scale_col(
                                        src_to_dest.get(
                                            col,
                                            _scale_col(col, grid_width, content_width),
                                        ),
                                        content_width,
                                        anchor_width,
                                    ),
                                    2,
                                    False,
                                )
                                for (col, _denom, _dot) in positions
                            ]
                            spread_event_positions = spread_flag_positions(
                                seeded_event_positions,
                                anchor_width,
                                min_gap=unit_anchor_min_gap,
                            )
                            src_to_dest = {
                                raw_col: scaled_col
                                for (raw_col, _d1, _dot1), (scaled_col, _d2, _dot2) in zip(
                                    positions,
                                    spread_event_positions,
                                    strict=False,
                                )
                            }
                        final_flag_positions = [
                            (
                                src_to_dest.get(col, _scale_col(col, grid_width, content_width)),
                                denom,
                                dot,
                            )
                            for (col, denom, dot) in ordered_flags
                        ]
                    dur_source_positions = [
                        (
                            raw_col,
                            src_to_dest.get(
                                raw_col,
                                _scale_col(raw_col, grid_width, content_width),
                            ),
                        )
                        for (raw_col, _denom, _dot) in ordered_flags
                    ]
                    flag_cells, stem_cells = build_flag_rows(
                        final_flag_positions,
                        spacing_mode="fixed",
                        display_width=content_width,
                        bar_width=content_width,
                        barpad=0,
                        flagstyle=flagstyle,
                        flaglean=flaglean,
                        stem_width=style_policy.stem_width,
                        dotplacement=style_policy.dotplacement,
                        min_gap=flag_min_gap,
                    )
                    flag_cells = pad_row(flag_cells, display_width, draw_pad)
                    stem_cells = pad_row(stem_cells, display_width, draw_pad)
                else:
                    src_to_dest = {}
                    final_flag_positions = spread_flag_positions(
                        ordered_flags,
                        bar_width,
                        min_gap=1,
                    )
                    dur_source_positions = [
                        (raw_col, col)
                        for (raw_col, _denom, _dot), (col, _d2, _dot2) in zip(
                            ordered_flags,
                            final_flag_positions,
                            strict=False,
                        )
                    ]
                    flag_cells, stem_cells = build_flag_rows(
                        flag_positions,
                        spacing_mode=spacing_mode,
                        display_width=display_width,
                        bar_width=bar_width,
                        barpad=barpad,
                        flagstyle=flagstyle,
                        flaglean=flaglean,
                    )
                    if draw_pad:
                        flag_cells = pad_row(flag_cells, display_width, draw_pad)
                        stem_cells = pad_row(stem_cells, display_width, draw_pad)
                content_width = max(1, display_width - draw_pad * 2)
                grid_map = _grid_display_map(
                    grid_width=grid_width,
                    content_width=content_width,
                    src_to_dest=src_to_dest,
                )
                text_onset_cols = _event_display_onset_cols(
                    positions=positions,
                    grid_map=grid_map,
                    draw_pad=draw_pad,
                )
                # Generic row scaling can drop sparse cue endpoints. Re-overlay them using
                # the same chord/display map so parenthesize/tie/slur cue punctuation survives.
                if scale_bar:
                    sparse_cues = {"(", ")", "[", "]", "<", ">", "/", "\\"} | _TUPLET_CUE_GLYPHS
                    if rows["ann"] is not None:
                        _overlay_sparse_mark_chars(
                            stdscr,
                            y=row_start + (rows["ann"] or 0),
                            bar_x=bar_x,
                            draw_pad=draw_pad,
                            grid_map=grid_map,
                            row_cells=ann_cells,
                            keep=sparse_cues,
                        )
                    tie_row_is_distinct = (
                        rows["tie"] is not None
                        and rows["tie"] != rows["slur"]
                        and rows["tie"] != rows["hold"]
                    )
                    if tie_row_is_distinct:
                        _overlay_sparse_mark_chars(
                            stdscr,
                            y=row_start + (rows["tie"] or 0),
                            bar_x=bar_x,
                            draw_pad=draw_pad,
                            grid_map=grid_map,
                            row_cells=tie_cells,
                            keep=sparse_cues,
                        )
                    slur_row_is_distinct = (
                        rows["slur"] is not None
                        and rows["slur"] != rows["tie"]
                        and rows["slur"] != rows["hold"]
                    )
                    if slur_row_is_distinct:
                        _overlay_sparse_mark_chars(
                            stdscr,
                            y=row_start + (rows["slur"] or 0),
                            bar_x=bar_x,
                            draw_pad=draw_pad,
                            grid_map=grid_map,
                            row_cells=slur_cells,
                            keep=sparse_cues,
                        )
                    hold_row_is_distinct = (
                        rows["hold"] is not None
                        and rows["hold"] != rows["slur"]
                        and rows["hold"] != rows["tie"]
                    )
                    if hold_row_is_distinct:
                        _overlay_sparse_mark_chars(
                            stdscr,
                            y=row_start + (rows["hold"] or 0),
                            bar_x=bar_x,
                            draw_pad=draw_pad,
                            grid_map=grid_map,
                            row_cells=hold_cells,
                            keep=sparse_cues,
                        )
                    gliss_row = rows.get("gliss")
                    gliss_row_is_distinct = (
                        gliss_row is not None
                        and gliss_row not in {rows["slur"], rows["tie"], rows["hold"]}
                    )
                    if gliss_row_is_distinct:
                        _overlay_sparse_mark_chars(
                            stdscr,
                            y=row_start + (gliss_row or 0),
                            bar_x=bar_x,
                            draw_pad=draw_pad,
                            grid_map=grid_map,
                            row_cells=gliss_cells,
                            keep=sparse_cues,
                        )
                    tuplet_row = rows.get("tuplet")
                    gliss_row_idx = rows.get("gliss")
                    tuplet_row_is_distinct = (
                        tuplet_row is not None
                        and tuplet_row not in {
                            rows["slur"],
                            rows["tie"],
                            rows["hold"],
                            gliss_row_idx,
                        }
                    )
                    if tuplet_row_is_distinct:
                        _overlay_sparse_mark_chars(
                            stdscr,
                            y=row_start + (tuplet_row or 0),
                            bar_x=bar_x,
                            draw_pad=draw_pad,
                            grid_map=grid_map,
                            row_cells=tuplet_cells,
                            keep=sparse_cues,
                        )
                span_rows_to_draw: dict[int, list[str]] = {}
                span_y_values = {
                    row_start + (rows[key] or 0)
                    for key in ("slur", "hold", "gliss", "tie", "tuplet")
                    if rows[key] is not None
                }
                for y in span_y_values:
                    row_slur = (
                        scaled_slur_row
                        if rows["slur"] is not None and y == row_start + (rows["slur"] or 0)
                        else None
                    )
                    row_hold = (
                        scaled_hold_row
                        if rows["hold"] is not None and y == row_start + (rows["hold"] or 0)
                        else None
                    )
                    row_tie = (
                        scaled_tie_row
                        if rows["tie"] is not None and y == row_start + (rows["tie"] or 0)
                        else None
                    )
                    row_gliss = (
                        scaled_gliss_row
                        if rows.get("gliss") is not None and y == row_start + (rows["gliss"] or 0)
                        else None
                    )
                    row_tuplet = (
                        scaled_tuplet_row
                        if rows.get("tuplet") is not None and y == row_start + (rows["tuplet"] or 0)
                        else None
                    )
                    span_rows_to_draw[y] = _merge_span_rows_with_cue_priority(
                        slur_row=row_slur,
                        hold_row=row_hold,
                        gliss_row=row_gliss,
                        tie_row=row_tie,
                        tuplet_row=row_tuplet,
                    )
                for y, merged_row in span_rows_to_draw.items():
                    safe_addstr(stdscr, y, bar_x, "".join(merged_row))
                    span_overlay_rows = _merge_nonspace_rows(
                        (
                            ann_cells
                            if rows["ann"] is not None and y == row_start + (rows["ann"] or 0)
                            else [" " for _ in range(grid_width)]
                        ),
                        (
                            slur_cells
                            if rows["slur"] is not None and y == row_start + (rows["slur"] or 0)
                            else [" " for _ in range(grid_width)]
                        ),
                        (
                            hold_cells
                            if rows["hold"] is not None and y == row_start + (rows["hold"] or 0)
                            else [" " for _ in range(grid_width)]
                        ),
                        (
                            gliss_cells
                            if rows.get("gliss") is not None
                            and y == row_start + (rows["gliss"] or 0)
                            else [" " for _ in range(grid_width)]
                        ),
                        (
                            tie_cells
                            if rows["tie"] is not None and y == row_start + (rows["tie"] or 0)
                            else [" " for _ in range(grid_width)]
                        ),
                        (
                            tuplet_cells
                            if rows.get("tuplet") is not None
                            and y == row_start + (rows["tuplet"] or 0)
                            else [" " for _ in range(grid_width)]
                        ),
                    )
                    _overlay_sparse_mark_chars(
                        stdscr,
                        y=y,
                        bar_x=bar_x,
                        draw_pad=draw_pad,
                        grid_map=grid_map,
                        row_cells=span_overlay_rows,
                        keep=sparse_cues,
                    )
                safe_addstr(stdscr, row_start + (rows["flag"] or 0), bar_x, "".join(flag_cells))
                if rows.get("flag2") is not None:
                    safe_addstr(
                        stdscr,
                        row_start + (rows["flag2"] or 0),
                        bar_x,
                        "".join(stem_cells),
                    )
                dur_col_map: dict[int, int] = {}
                dur_padded = False
                if show_dur and rows["dur"] is not None:
                    if scale_bar or spacing_mode == "auto":
                        content_width = max(1, display_width - draw_pad * 2)
                        dur_cells = [" " for _ in range(content_width)]
                        for (raw_col, denom, dot), (_raw_key, target_col) in zip(
                            ordered_flags,
                            dur_source_positions,
                            strict=False,
                        ):
                            dur_col_map[raw_col] = target_col
                            _place_duration_cells_aligned(
                                dur_cells,
                                target_col,
                                duration_display(denom, dot),
                            )
                        dur_cells = pad_row(dur_cells, display_width, draw_pad)
                        dur_padded = True
                    else:
                        dur_cells = [" " for _ in range(bar_width)]
                        for (raw_col, denom, dot), (_raw_key, target_col) in zip(
                            ordered_flags,
                            dur_source_positions,
                            strict=False,
                        ):
                            dur_col_map[raw_col] = target_col
                            _place_duration_cells_aligned(
                                dur_cells,
                                target_col,
                                duration_display(denom, dot),
                            )
                        if draw_pad:
                            dur_cells = pad_row(dur_cells, display_width, draw_pad)
                            dur_padded = True
                    safe_addstr(stdscr, row_start + (rows["dur"] or 0), bar_x, "".join(dur_cells))
                if abs_bar == cursor_bar:
                    for col, _denom, _dot in positions:
                        cursor_grid_col = _scale_col(cursor_col, bar_width, grid_width)
                        if col == cursor_grid_col:
                            flag_y = row_start + (rows["flag"] or 0)
                            scaled_col = grid_map[col]
                            cursor_x = bar_x + draw_pad + scaled_col
                            safe_addstr(
                                stdscr,
                                flag_y,
                                cursor_x,
                                flag_cells[draw_pad + scaled_col],
                                A_BOLD,
                            )
                            if show_dur and rows["dur"] is not None:
                                dur_y = row_start + (rows["dur"] or 0)
                                dur_col = dur_col_map.get(col, scaled_col)
                                if dur_padded:
                                    dur_idx = draw_pad + dur_col
                                    dur_x = bar_x + dur_idx
                                else:
                                    dur_idx = dur_col
                                    dur_x = bar_x + dur_idx
                                if 0 <= dur_idx < len(dur_cells):
                                    safe_addstr(
                                        stdscr,
                                        dur_y,
                                        dur_x,
                                        dur_cells[dur_idx],
                                        A_BOLD,
                                    )
                            break
            else:
                src_to_dest: dict[int, int] = {}
                grid_map: list[int] = list(range(max(1, grid_width)))
                dur_source_positions: list[tuple[int, int]] = []
                span_rows_to_draw: dict[int, list[str]] = {}
                span_y_values = {
                    row_start + (rows[key] or 0)
                    for key in ("slur", "hold", "gliss", "tie", "tuplet")
                    if rows[key] is not None
                }
                for y in span_y_values:
                    row_slur = (
                        scaled_slur_row
                        if rows["slur"] is not None and y == row_start + (rows["slur"] or 0)
                        else None
                    )
                    row_hold = (
                        scaled_hold_row
                        if rows["hold"] is not None and y == row_start + (rows["hold"] or 0)
                        else None
                    )
                    row_tie = (
                        scaled_tie_row
                        if rows["tie"] is not None and y == row_start + (rows["tie"] or 0)
                        else None
                    )
                    row_gliss = (
                        scaled_gliss_row
                        if rows.get("gliss") is not None and y == row_start + (rows["gliss"] or 0)
                        else None
                    )
                    row_tuplet = (
                        scaled_tuplet_row
                        if rows.get("tuplet") is not None and y == row_start + (rows["tuplet"] or 0)
                        else None
                    )
                    span_rows_to_draw[y] = _merge_span_rows_with_cue_priority(
                        slur_row=row_slur,
                        hold_row=row_hold,
                        gliss_row=row_gliss,
                        tie_row=row_tie,
                        tuplet_row=row_tuplet,
                    )
                for y, merged_row in span_rows_to_draw.items():
                    safe_addstr(stdscr, y, bar_x, "".join(merged_row))
                has_explicit_content = bool(bar.notes)
                if not has_explicit_content:
                    has_explicit_content = any(
                        b == abs_bar and value not in ("", "-", " ")
                        for (b, _s, _c), value in overrides.items()
                    ) or any(b == abs_bar for (b, _s, _c) in durations)
                visible_note_cols = _note_event_columns(cells, total_strings, grid_width)
                if hide_redundant:
                    if has_explicit_content:
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
                        flag_positions = []
                else:
                    flag_positions = _flag_positions_all(
                        durations,
                        abs_bar,
                        total_strings,
                        bar_width,
                        default_duration,
                        dotted=dotted,
                    )
                flag_positions = _anchor_flag_positions_to_note_cols(
                    flag_positions,
                    visible_note_cols,
                )
                flagstyle = style_policy.flagstyle
                flaglean = style_policy.flaglean
                if scale_bar:
                    content_width = max(1, display_width - draw_pad * 2)
                    event_positions = [(col, 2, False) for col in visible_note_cols]
                    event_min_gap = 1 if spacing_fill == "compact" else 2
                    if event_positions:
                        _, src_to_dest = _build_chord_scale_map(
                            event_positions,
                            grid_width,
                            content_width,
                            min_gap=event_min_gap,
                        )
                        if content_width > 1 and src_to_dest:
                            anchor_width = max(1, content_width - 1)
                            seeded_event_positions = [
                                (
                                    _scale_col(
                                        src_to_dest.get(
                                            col,
                                            _scale_col(col, grid_width, content_width),
                                        ),
                                        content_width,
                                        anchor_width,
                                    ),
                                    2,
                                    False,
                                )
                                for col in visible_note_cols
                            ]
                            spread_event_positions = spread_flag_positions(
                                seeded_event_positions,
                                anchor_width,
                                min_gap=event_min_gap,
                            )
                            src_to_dest = {
                                raw_col: scaled_col
                                for (raw_col, _d1, _dot1), (scaled_col, _d2, _dot2) in zip(
                                    event_positions,
                                    spread_event_positions,
                                    strict=False,
                                )
                            }
                    final_flag_positions = [
                        (
                            src_to_dest.get(col, _scale_col(col, grid_width, content_width)),
                            denom,
                            dot,
                        )
                        for (col, denom, dot) in flag_positions
                    ]
                    dur_source_positions = [
                        (
                            raw_col,
                            src_to_dest.get(
                                raw_col,
                                _scale_col(raw_col, grid_width, content_width),
                            ),
                        )
                        for (raw_col, _denom, _dot) in flag_positions
                    ]
                    flag_cells, stem_cells = build_flag_rows(
                        final_flag_positions,
                        spacing_mode="fixed",
                        display_width=content_width,
                        bar_width=content_width,
                        barpad=0,
                        flagstyle=flagstyle,
                        flaglean=flaglean,
                        stem_width=style_policy.stem_width,
                        dotplacement=style_policy.dotplacement,
                    )
                    flag_cells = pad_row(flag_cells, display_width, draw_pad)
                    stem_cells = pad_row(stem_cells, display_width, draw_pad)
                    grid_map = _grid_display_map(
                        grid_width=grid_width,
                        content_width=content_width,
                        src_to_dest=src_to_dest,
                    )
                else:
                    flag_cells, stem_cells = build_flag_rows(
                        flag_positions,
                        spacing_mode=spacing_mode,
                        display_width=display_width,
                        bar_width=bar_width,
                        barpad=pad,
                        flagstyle=flagstyle,
                        flaglean=flaglean,
                        stem_width=style_policy.stem_width,
                        dotplacement=style_policy.dotplacement,
                    )
                    if draw_pad:
                        flag_cells = pad_row(flag_cells, display_width, draw_pad)
                        stem_cells = pad_row(stem_cells, display_width, draw_pad)
                    dur_source_positions = [
                        (raw_col, raw_col) for (raw_col, _d, _dot) in flag_positions
                    ]
                safe_addstr(stdscr, row_start + (rows["flag"] or 0), bar_x, "".join(flag_cells))
                if rows.get("flag2") is not None:
                    safe_addstr(
                        stdscr,
                        row_start + (rows["flag2"] or 0),
                        bar_x,
                        "".join(stem_cells),
                    )
                if show_dur and rows["dur"] is not None:
                    if scale_bar:
                        content_width = max(1, display_width - draw_pad * 2)
                        dur_cells = [" " for _ in range(content_width)]
                        for (_raw_col, denom, dot), (_raw_key, target_col) in zip(
                            flag_positions,
                            dur_source_positions,
                            strict=False,
                        ):
                            _place_duration_cells_aligned(
                                dur_cells,
                                target_col,
                                duration_display(denom, dot),
                            )
                        dur_cells = pad_row(dur_cells, display_width, draw_pad)
                    else:
                        dur_cells = _bar_durations(
                            durations,
                            abs_bar,
                            total_strings,
                            bar_width,
                            default_duration,
                            hide_redundant=hide_redundant,
                            dotted=dotted,
                        )
                        dur_cells = pad_row(dur_cells, display_width, draw_pad)
                    safe_addstr(stdscr, row_start + (rows["dur"] or 0), bar_x, "".join(dur_cells))
            if cursor_display_maps is not None and grid_map:
                if bar.chords:
                    cursor_display_maps[abs_bar] = [
                        grid_map[
                            min(len(grid_map) - 1, _scale_col(col, bar_width, grid_width))
                        ]
                        for col in range(bar_width)
                    ]
                else:
                    cursor_display_maps[abs_bar] = [
                        grid_map[min(len(grid_map) - 1, col)] for col in range(bar_width)
                    ]
            cursor_display_index = cursor_string if cursor_string < system_display_strings else None
            rendered_staff_rows: list[str] = []
            for display_idx in range(system_display_strings):
                actual = system_visual_indices[display_idx]
                y = row_start + (rows["staff"] or 0) + display_idx
                row_cells = cells[actual]
                fill_char = "-"
                if actual >= 6:
                    row_cells = _inline_bass_row(row_cells)
                    fill_char = " "
                if scale_bar:
                    content_width = max(1, display_width - draw_pad * 2)
                    if bar.chords:
                        row_cells = _scale_chord_row(
                            row_cells,
                            fill_char=fill_char,
                            src_to_dest=src_to_dest,
                            bar_width=grid_width,
                            content_width=content_width,
                        )
                    else:
                        row_cells = _scale_chord_row(
                            row_cells,
                            fill_char=fill_char,
                            src_to_dest=src_to_dest,
                            bar_width=grid_width,
                            content_width=content_width,
                        )
                    row_cells = pad_row(row_cells, display_width, draw_pad, pad_char=fill_char)
                elif draw_pad:
                    row_cells = pad_row(row_cells, display_width, draw_pad, pad_char=fill_char)
                if bar.chords:
                    _overlay_inline_local_marks_on_display_row(
                        display_row_cells=row_cells,
                        source_row_cells=cells[actual],
                        ann_cells=ann_cells,
                        orn_cells=orn_cells,
                        draw_pad=draw_pad,
                        grid_map=grid_map,
                        style=style,
                        source_row_index=actual,
                        ann_target_rows=ann_target_rows,
                        orn_target_rows=orn_target_rows,
                    )
                row_text = "".join(row_cells)
                safe_addstr(stdscr, y, bar_x - 1, "|")
                if repeat_left and display_idx in repeat_rows:
                    safe_addstr(stdscr, y, bar_x - 1, ":")
                safe_addstr(stdscr, y, bar_x, row_text)
                if show_time_sig_here and _sig_label:
                    ts_rows = time_sig_inline_rows(
                        time_value,
                        _sig_label,
                        style_mode=settings.get("timesigstyle", "symbol"),
                    )
                    ts_top = 0
                    if ts_rows:
                        ts_top = max(0, (system_display_strings - len(ts_rows)) // 2)
                    if ts_top <= display_idx < (ts_top + len(ts_rows)):
                        # Draw inside the first bar (auftact area), not over left labels.
                        ts_text = ts_rows[display_idx - ts_top]
                        # Anchor the cue at the beginning of the reserved auftact pad.
                        # This leaves whitespace after the cue before the first note.
                        ts_x = min(width - 2, bar_x + barpad)
                        safe_addstr(stdscr, y, ts_x, ts_text)
                barline_x = min(max(0, width - 2), bar_x + display_width)
                if fill_char == "-" and row_cells and barline_x == (width - 2) and not bar.chords:
                    # Guarantee one visible dash before the actually drawn right barline.
                    edge_idx = barline_x - 1 - bar_x
                    if 0 <= edge_idx < len(row_cells) and row_cells[edge_idx] not in ("-", " "):
                        move_to = edge_idx - 1
                        while move_to >= 0 and row_cells[move_to] not in ("-", " "):
                            move_to -= 1
                        if move_to >= 0:
                            row_cells[move_to] = row_cells[edge_idx]
                            row_cells[edge_idx] = "-"
                            row_text = "".join(row_cells)
                            safe_addstr(stdscr, y, bar_x, row_text)
                safe_addstr(stdscr, y, barline_x, barline)
                if repeat_right and display_idx in repeat_rows:
                    safe_addstr(stdscr, y, barline_x, ":")
                rendered_staff_rows.append(row_text)

                if (
                    abs_bar == cursor_bar
                    and cursor_display_index is not None
                    and display_idx == cursor_display_index
                    and 0 <= cursor_col < bar_width
                ):
                    content_width = max(1, display_width - draw_pad * 2)
                    if bar.chords:
                        cursor_grid_col = _scale_col(cursor_col, bar_width, grid_width)
                        scaled_cursor_col = grid_map[cursor_grid_col]
                    else:
                        scaled_cursor_col = grid_map[cursor_col]
                    cell_x = bar_x + draw_pad + scaled_cursor_col
                    cell_idx = draw_pad + scaled_cursor_col
                    if not (0 <= cell_idx < len(row_text)):
                        continue
                    safe_addstr(
                        stdscr,
                        y,
                        cell_x,
                        row_text[cell_idx],
                        A_REVERSE,
                    )
                for col in range(bar_width):
                    if (abs_bar, actual, col) in highlights:
                        content_width = max(1, display_width - pad * 2)
                        if bar.chords:
                            highlight_grid_col = _scale_col(col, bar_width, grid_width)
                            scaled_hl_col = grid_map[highlight_grid_col]
                        else:
                            scaled_hl_col = grid_map[col]
                        hl_x = bar_x + draw_pad + scaled_hl_col
                        safe_addstr(
                            stdscr,
                            y,
                            hl_x,
                            row_text[draw_pad + scaled_hl_col],
                            A_BOLD,
                        )

                playback_vocal_onset_cols: list[int] = []
                melody_row_base: int | None = None
                rendered_melody_rows: list[str] | None = None
                vocal_left_pad = draw_pad
                melody_key_pad = 0
                if abs_bar == 0 and (bar.time_sig or settings.get("time", "")):
                    vocal_left_pad += 2
                if abs_bar == 0:
                    melody_key_pad = melody_key_signature_width(piece.key)
                    vocal_left_pad += melody_key_pad
                if rows.get("melody") is not None:
                    melody_row_base = row_start + (rows["melody"] or 0)
                    playback_vocal_onset_cols = vocal_onset_cols_for_bar(
                        bar,
                        onset_cols=text_onset_cols,
                        width=display_width,
                        left_pad=vocal_left_pad,
                    )
                    melody_rows = melody_rows_for_bar(
                        bar,
                        onset_cols=playback_vocal_onset_cols,
                        width=display_width,
                        left_pad=vocal_left_pad,
                        tuning_pitches=tuning_pitches,
                    )
                    if abs_bar == 0 and melody_rows:
                        draw_melody_time_signature(
                            melody_rows,
                            time_sig=bar.time_sig or settings.get("time", ""),
                            left_pad=max(0, vocal_left_pad - melody_key_pad),
                        )
                        draw_melody_key_signature(
                            melody_rows,
                            key=piece.key,
                            left_pad=max(0, vocal_left_pad - melody_key_pad + 2),
                        )
                    rendered_melody_rows = ["".join(row) for row in melody_rows]
                    for melody_row_idx, melody_cells in enumerate(melody_rows[:melody_rows_count]):
                        y = melody_row_base + melody_row_idx
                        row_text = "".join(melody_cells)
                        if row_text.strip():
                            safe_addstr(stdscr, y, bar_x - 1, "|")
                        safe_addstr(stdscr, y, bar_x, "".join(melody_cells))
                        if row_text.strip():
                            safe_addstr(
                                stdscr,
                                y,
                                min(max(0, width - 2), bar_x + display_width),
                                barline,
                            )
            if lyric_row_offsets:
                vocal_onset_cols = vocal_onset_cols_for_bar(
                    bar,
                    onset_cols=text_onset_cols,
                    width=display_width,
                    left_pad=vocal_left_pad,
                )
                lyric_rows = lyric_rows_for_bar(
                    bar,
                    onset_cols=vocal_onset_cols,
                    width=display_width,
                    left_pad=vocal_left_pad,
                    lyric_rows_count=len(lyric_row_offsets),
                )
                for lyric_idx, lyric_row in enumerate(lyric_row_offsets):
                    lyric_cells = (
                        lyric_rows[lyric_idx]
                        if lyric_idx < len(lyric_rows)
                        else [" "] * display_width
                    )
                    safe_addstr(stdscr, row_start + lyric_row, bar_x - 1, "|")
                    safe_addstr(stdscr, row_start + lyric_row, bar_x, "".join(lyric_cells))
                    safe_addstr(
                        stdscr,
                        row_start + lyric_row,
                        min(max(0, width - 2), bar_x + display_width),
                        barline,
                    )

            if playback_cache is not None:
                playback_limit = len(bar.chords) if bar.chords else bar_width
                for overlay_col in range(max(0, playback_limit)):
                    playback_cache[(abs_bar, overlay_col)] = _playback_overlay_ops_for_bar(
                        bar=bar,
                        playback_col=overlay_col,
                        bar_width=bar_width,
                        grid_width=grid_width,
                        positions=positions,
                        src_to_dest=src_to_dest,
                        draw_pad=draw_pad,
                        display_width=display_width,
                        row_start=row_start,
                        rows=rows,
                        system_display_strings=system_display_strings,
                        system_visual_indices=system_visual_indices,
                        rendered_staff_rows=rendered_staff_rows,
                        bar_x=bar_x,
                        tuning_pitches=tuning_pitches,
                        melody_row_base=melody_row_base,
                        vocal_onset_cols=playback_vocal_onset_cols,
                        rendered_melody_rows=rendered_melody_rows,
                    )
            playback_cols = [
                marker_col
                for marker_bar, marker_col in effective_playback_markers
                if marker_bar == abs_bar
            ]
            for marker_col in playback_cols:
                playback_ops = _playback_overlay_ops_for_bar(
                    bar=bar,
                    playback_col=marker_col,
                    bar_width=bar_width,
                    grid_width=grid_width,
                    positions=positions,
                    src_to_dest=src_to_dest,
                    draw_pad=draw_pad,
                    display_width=display_width,
                    row_start=row_start,
                    rows=rows,
                    system_display_strings=system_display_strings,
                    system_visual_indices=system_visual_indices,
                    rendered_staff_rows=rendered_staff_rows,
                    bar_x=bar_x,
                    tuning_pitches=tuning_pitches,
                    melody_row_base=melody_row_base,
                    vocal_onset_cols=playback_vocal_onset_cols,
                    rendered_melody_rows=rendered_melody_rows,
                )
                for y, x, text, attr in playback_ops:
                    safe_addstr(stdscr, y, x, text, attr)

            if spacing_mode == "auto":
                next_gap = gaps_after[local_idx] if local_idx < len(gaps_after) else 0
                bar_x += display_width + next_gap
            else:
                bar_x += display_width + bar_gap
        current_bar_start = bar_end
