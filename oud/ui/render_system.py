from __future__ import annotations

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
    time_cue_reserved_width,
    time_cue_side_pad,
    time_sig_inline_rows,
    visual_row_indices,
)
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
from oud.ui.adapter import A_BOLD, A_REVERSE, Screen
from oud.ui.layout_map import layout_block_rows as _layout_block_rows
from oud.ui.render_bar import build_flag_rows
from oud.ui.render_helpers import apply_overrides, pad_row, safe_addstr


def _merge_mark_rows(base: list[str], user: list[str]) -> list[str]:
    if len(base) != len(user):
        return user
    out = list(base)
    for idx, ch in enumerate(user):
        if ch != " ":
            out[idx] = ch
    return out


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
    if style == "italian":
        return supers.get(ch, ch)
    return subs.get(ch, ch)


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
            right = col + 1
            if right < width and cells[target_row][right] == "-":
                cells[target_row][right] = orn

        # Fingering/annotation marker uses compact unicode and must stay adjacent.
        # If there is no adjacent free slot, drop it instead of drifting.
        if ann != " ":
            mark = _inline_fingering_glyph(ann, style=style)
            right = col + 1
            if right < width and cells[target_row][right] == "-":
                cells[target_row][right] = mark


def _overlay_inline_local_marks_on_display_row(  # noqa: C901
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
) -> None:
    if glisses is None:
        glisses = []
    total_bars = len(piece.bars)
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
                        flag_gap=2 if spacing_fill == "smart" else 1,
                        event_gap=2,
                        cue_pad_total=time_cue_reserved_width(
                            show_time_cue=show_cue,
                            scale_bar=True,
                        ),
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
        )
        for display_idx in range(system_display_strings):
            label = "  "
            if sys_idx == 0:
                actual = system_visual_indices[display_idx]
                label = _string_label(actual, total_strings, tuning_labels, basslabels)
            safe_addstr(stdscr, row_start + (rows["staff"] or 0) + display_idx, 0, label)

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
            sign_cues: list[str] = []
            if bar.fermata:
                sign_cues.append("^")
            if bar.dynamic:
                sign_cues.append(bar.dynamic)
            imported_ann = [" " for _ in range(grid_width)]
            imported_orn = [" " for _ in range(grid_width)]
            imported_ann_targets = [-1 for _ in range(grid_width)]
            imported_orn_targets = [-1 for _ in range(grid_width)]
            show_fingerings = settings.get(
                "showfingerings",
                settings.get("showft3extras", "on"),
            ) == "on"
            show_ornaments = settings.get(
                "showornaments",
                settings.get("showft3extras", "on"),
            ) == "on"
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
            slur_chars = slur_span_chars(settings.get("slurcuestyle", "paren"))
            if slur_chars is None:
                slur_cells = [" " for _ in range(grid_width)]
            else:
                slur_cells = _bar_span_row(slurs, abs_bar, grid_width, *slur_chars)
            tie_chars = tie_span_chars(settings.get("tiecuestyle", "bracket"))
            if tie_chars is None:
                tie_cells = [" " for _ in range(grid_width)]
            else:
                tie_cells = _bar_span_row(ties, abs_bar, grid_width, *tie_chars)
            hold_chars = hold_span_chars(settings.get("holdcuestyle", "angle"))
            if hold_chars is None:
                hold_cells = [" " for _ in range(grid_width)]
            else:
                hold_cells = _bar_span_row(holds, abs_bar, grid_width, *hold_chars)
            gliss_chars = gliss_span_chars(settings.get("glisscuestyle", "hide"))
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
                mode=settings.get("tienoteheads", "show"),
            )
            paren_tie_cols = tie_notehead_parenthesize_cols(
                ties,
                bar_index=abs_bar,
                mode=settings.get("tienoteheads", "show"),
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
                if min_display > display_width and spacing_mode != "auto":
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
            draw_pad = pad + cue_pad_extra
            if rows["meta"] is not None:
                meta_row = row_start + (rows["meta"] or 0)
                safe_addstr(stdscr, meta_row, bar_x - 2, repeat_glyph)
                if abs_bar == 0 and not wrote_time_sig:
                    safe_addstr(stdscr, meta_row, 0, " ")
                meta_x = bar_x
                if number is not None:
                    safe_addstr(stdscr, meta_row, meta_x, number)
                cue_parts: list[str] = []
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
                flagstyle = settings.get("flagstyle", "standard")
                flaglean = settings.get("flaglean", "right")
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
                    unit_anchor_min_gap = max(1, event_min_gap - 1)
                    flag_min_gap = 1 if spacing_fill == "smart" else 0
                    beatsnap_mode = settings.get("beatsnap", "off")
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
                        # Reserve one trailing cell for the right-side dash, but preserve
                        # event spacing while doing so (simple clamping can re-glue notes).
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
                                2,  # unit anchor spacing only; do not reserve flag tails here
                                False,
                            )
                            for (col, denom, dot) in positions
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
                if (
                    playback_bar is not None
                    and playback_col is not None
                    and abs_bar == playback_bar
                    and _playback_in_range(bar, playback_col, bar_width)
                ):
                    content_width = max(1, display_width - pad * 2)
                    pcol = _playback_scaled_col_for_chords(
                        playback_col=playback_col,
                        bar_width=bar_width,
                        grid_width=grid_width,
                        content_width=content_width,
                        positions=positions,
                        src_to_dest=src_to_dest,
                    )
                    safe_addstr(
                        stdscr,
                        row_start + (rows["flag"] or 0),
                        bar_x + draw_pad + pcol,
                        flag_cells[draw_pad + pcol],
                        A_BOLD,
                    )
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
                flagstyle = settings.get("flagstyle", "standard")
                flaglean = settings.get("flaglean", "right")
                flag_cells, stem_cells = build_flag_rows(
                    flag_positions,
                    spacing_mode="auto" if scale_bar else spacing_mode,
                    display_width=display_width,
                    bar_width=bar_width,
                    barpad=pad,
                    flagstyle=flagstyle,
                    flaglean=flaglean,
                )
                safe_addstr(stdscr, row_start + (rows["flag"] or 0), bar_x, "".join(flag_cells))
                if (
                    playback_bar is not None
                    and playback_col is not None
                    and abs_bar == playback_bar
                    and _playback_in_range(bar, playback_col, bar_width)
                ):
                    content_width = max(1, display_width - draw_pad * 2)
                    pcol = _scale_col(playback_col, bar_width, content_width)
                    safe_addstr(
                        stdscr,
                        row_start + (rows["flag"] or 0),
                        bar_x + draw_pad + pcol,
                        flag_cells[draw_pad + pcol],
                        A_BOLD,
                    )
                if rows.get("flag2") is not None:
                    safe_addstr(
                        stdscr,
                        row_start + (rows["flag2"] or 0),
                        bar_x,
                        "".join(stem_cells),
                    )
                if show_dur and rows["dur"] is not None:
                    dur_cells = _bar_durations(
                        durations,
                        abs_bar,
                        total_strings,
                        bar_width,
                        default_duration,
                        hide_redundant=hide_redundant,
                        dotted=dotted,
                    )
                    if scale_bar:
                        content_width = max(1, display_width - draw_pad * 2)
                        dur_cells = _scale_row(dur_cells, content_width, " ")
                    dur_cells = pad_row(dur_cells, display_width, draw_pad)
                    safe_addstr(stdscr, row_start + (rows["dur"] or 0), bar_x, "".join(dur_cells))
            cursor_display_index = cursor_string if cursor_string < system_display_strings else None
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
                        row_cells = _scale_row(row_cells, content_width, fill_char)
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
                        scaled_cursor_col = _scale_col(cursor_col, bar_width, content_width)
                    cell_x = bar_x + draw_pad + scaled_cursor_col
                    safe_addstr(
                        stdscr,
                        y,
                        cell_x,
                        row_text[draw_pad + scaled_cursor_col],
                        A_REVERSE,
                    )
                if (
                    playback_bar is not None
                    and playback_col is not None
                    and abs_bar == playback_bar
                    and _playback_in_range(bar, playback_col, bar_width)
                ):
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
                    play_x = bar_x + draw_pad + scaled_play_col
                    safe_addstr(
                        stdscr,
                        y,
                        play_x,
                        row_text[draw_pad + scaled_play_col],
                        A_BOLD,
                    )
                for col in range(bar_width):
                    if (abs_bar, actual, col) in highlights:
                        content_width = max(1, display_width - pad * 2)
                        if bar.chords:
                            highlight_grid_col = _scale_col(col, bar_width, grid_width)
                            scaled_hl_col = grid_map[highlight_grid_col]
                        else:
                            scaled_hl_col = _scale_col(col, bar_width, content_width)
                        hl_x = bar_x + draw_pad + scaled_hl_col
                        safe_addstr(
                            stdscr,
                            y,
                            hl_x,
                            row_text[draw_pad + scaled_hl_col],
                            A_BOLD,
                        )

            if (
                playback_bar is not None
                and playback_col is not None
                and abs_bar == playback_bar
                and _playback_in_range(bar, playback_col, bar_width)
            ):
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
                marker_y = row_start + (rows["staff"] or 0) + system_display_strings
                marker_x = bar_x + draw_pad + scaled_play_col
                safe_addstr(stdscr, marker_y, marker_x, "^", A_BOLD)

            if spacing_mode == "auto":
                next_gap = gaps_after[local_idx] if local_idx < len(gaps_after) else 0
                bar_x += display_width + next_gap
            else:
                bar_x += display_width + bar_gap
        current_bar_start = bar_end
