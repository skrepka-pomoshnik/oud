from __future__ import annotations

from petrucci.render_bar import build_flag_rows
from petrucci.render_geometry import (
    _anchor_flag_positions_to_note_cols,
    _event_display_onset_cols,
    _expand_scale_map_from_anchors,
    _grid_display_map,
    _place_duration_cells_aligned,
)
from petrucci.render_helpers import pad_row, safe_addstr
from petrucci.render_marks import (
    _TUPLET_CUE_GLYPHS,
    _merge_nonspace_rows,
    _merge_span_rows_with_cue_priority,
    _overlay_sparse_mark_chars,
)
from petrucci.render_spacing import (
    build_chord_scale_map as _build_chord_scale_map,
)
from petrucci.render_spacing import (
    note_event_columns as _note_event_columns,
)
from petrucci.render_utils import (
    smart_group_map,
    soft_beat_snap_map,
    spread_flag_positions,
    trim_right_slack_for_onsets,
)
from petrucci.screen import A_BOLD, Screen
from petrucci.tab_policy import bar_has_multifret_tokens, multifret_event_gap
from petrucci.view_model import (
    _bar_durations,
    _beamified_chord_flag_positions,
    _filter_redundant_positions,
    _flag_positions_all,
    _scale_col,
    duration_display,
    flag_positions_from_durations,
)


def _render_rhythm_rows(  # noqa: C901, PLR0912
    stdscr: Screen,
    *,
    bar,
    abs_bar: int,
    bar_width: int,
    bar_x: int,
    barpad: int,
    beats: int,
    cells: list[list[str]],
    chord_positions_all: list[tuple[int, int, bool]],
    cursor_bar: int,
    cursor_col: int,
    default_duration: int,
    display_width: int,
    dotted: set[tuple[int, int]],
    draw_pad: int,
    durations: dict[tuple[int, int, int], int],
    french_c: str,
    fretlabelmode: str,
    grid_width: int,
    hide_redundant: bool,
    overrides: dict[tuple[int, int, int], str],
    pad: int,
    row_start: int,
    rows: dict[str, int | None],
    scale_bar: bool,
    settings: dict[str, str],
    show_dur: bool,
    spacing_fill: str,
    spacing_mode: str,
    style: str,
    style_policy,
    total_strings: int,
    ann_cells: list[str],
    slur_cells: list[str],
    tie_cells: list[str],
    hold_cells: list[str],
    gliss_cells: list[str],
    tuplet_cells: list[str],
    scaled_slur_row: list[str] | None,
    scaled_tie_row: list[str] | None,
    scaled_hold_row: list[str] | None,
    scaled_gliss_row: list[str] | None,
    scaled_tuplet_row: list[str] | None,
) -> tuple[list[tuple[int, int, bool]], dict[int, int], list[int], list[int]]:
    positions: list[tuple[int, int, bool]] = []
    text_onset_cols: list[int] = []
    if bar.chords:
        visible_note_cols = set(_note_event_columns(cells, total_strings, grid_width))
        positions = [item for item in chord_positions_all if item[0] in visible_note_cols]
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
                rows["tie"] is not None and rows["tie"] != rows["slur"] and rows["tie"] != rows["hold"]
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
                rows["slur"] is not None and rows["slur"] != rows["tie"] and rows["slur"] != rows["hold"]
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
                rows["hold"] is not None and rows["hold"] != rows["slur"] and rows["hold"] != rows["tie"]
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
            gliss_row_is_distinct = gliss_row is not None and gliss_row not in {
                rows["slur"],
                rows["tie"],
                rows["hold"],
            }
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
            tuplet_row_is_distinct = tuplet_row is not None and tuplet_row not in {
                rows["slur"],
                rows["tie"],
                rows["hold"],
                gliss_row_idx,
            }
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
            row_start + (rows[key] or 0) for key in ("slur", "hold", "gliss", "tie", "tuplet") if rows[key] is not None
        }
        for y in span_y_values:
            row_slur = scaled_slur_row if rows["slur"] is not None and y == row_start + (rows["slur"] or 0) else None
            row_hold = scaled_hold_row if rows["hold"] is not None and y == row_start + (rows["hold"] or 0) else None
            row_tie = scaled_tie_row if rows["tie"] is not None and y == row_start + (rows["tie"] or 0) else None
            row_gliss = (
                scaled_gliss_row if rows.get("gliss") is not None and y == row_start + (rows["gliss"] or 0) else None
            )
            row_tuplet = (
                scaled_tuplet_row if rows.get("tuplet") is not None and y == row_start + (rows["tuplet"] or 0) else None
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
                    if rows.get("gliss") is not None and y == row_start + (rows["gliss"] or 0)
                    else [" " for _ in range(grid_width)]
                ),
                (
                    tie_cells
                    if rows["tie"] is not None and y == row_start + (rows["tie"] or 0)
                    else [" " for _ in range(grid_width)]
                ),
                (
                    tuplet_cells
                    if rows.get("tuplet") is not None and y == row_start + (rows["tuplet"] or 0)
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
            row_start + (rows[key] or 0) for key in ("slur", "hold", "gliss", "tie", "tuplet") if rows[key] is not None
        }
        for y in span_y_values:
            row_slur = scaled_slur_row if rows["slur"] is not None and y == row_start + (rows["slur"] or 0) else None
            row_hold = scaled_hold_row if rows["hold"] is not None and y == row_start + (rows["hold"] or 0) else None
            row_tie = scaled_tie_row if rows["tie"] is not None and y == row_start + (rows["tie"] or 0) else None
            row_gliss = (
                scaled_gliss_row if rows.get("gliss") is not None and y == row_start + (rows["gliss"] or 0) else None
            )
            row_tuplet = (
                scaled_tuplet_row if rows.get("tuplet") is not None and y == row_start + (rows["tuplet"] or 0) else None
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
                b == abs_bar and value not in ("", "-", " ") for (b, _s, _c), value in overrides.items()
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
            dur_source_positions = [(raw_col, raw_col) for (raw_col, _d, _dot) in flag_positions]
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
    return positions, src_to_dest, grid_map, text_onset_cols
