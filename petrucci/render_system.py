from __future__ import annotations

from petrucci.layout_map import block_height as _block_height
from petrucci.layout_map import layout_block_rows as _layout_block_rows
from petrucci.render_helpers import apply_overrides, pad_row, safe_addstr
from petrucci.render_marks import (
    _imported_ft3_mark_target_rows,
    _merge_mark_rows,
    _place_parenthesize_tie_cues,
    _repeat_dot_display_rows,
    _split_tuplet_cues_from_annotations,
    _target_note_rows_by_col,
)
from petrucci.render_playback import PlaybackOverlayCache
from petrucci.render_rhythm_rows import _render_rhythm_rows
from petrucci.render_spacing import (
    chord_positions_distinct as _chord_positions_distinct,
)
from petrucci.render_spacing import (
    note_event_columns as _note_event_columns,
)
from petrucci.render_spacing import (
    required_auto_display_width_for_bar as _required_auto_display_width_for_bar,
)
from petrucci.render_spacing import (
    required_duration_content_width as _required_duration_content_width,
)
from petrucci.render_spacing import (
    required_flag_content_width as _required_flag_content_width,
)
from petrucci.render_staff_rows import _render_staff_and_playback
from petrucci.screen import Screen
from petrucci.system_plan import AutoSystemPlanOptions, plan_auto_system, plan_fixed_system
from petrucci.tab_policy import (
    gliss_span_chars,
    hold_span_chars,
    show_time_cue_for_bar,
    slur_span_chars,
    system_display_indices_for_bars,
    tie_notehead_hidden_cols,
    tie_notehead_parenthesize_cols,
    tie_span_chars,
    time_cue_side_pad,
    visual_row_indices,
)
from petrucci.tab_style import resolve_tab_style_policy
from petrucci.tuning_utils import parse_tuning_pitches
from petrucci.view_model import (
    _bar_annotations,
    _bar_imported_ft3_annotations,
    _bar_imported_ft3_ornaments,
    _bar_number_for_index,
    _bar_ornaments,
    _bar_span_row,
    _filter_redundant_positions,
    _infer_time_signature,
    _parse_time_signature,
    _scale_row,
    _string_label,
    _tactus_row,
    bar_cells,
    bar_cells_from_chords,
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
    systems: int,
    total_strings: int,
    display_indices: list[int],  # noqa: ARG001
    display_strings: int,  # noqa: ARG001 - retained by the public rendering call contract
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
    if not effective_playback_markers and playback_bar is not None and playback_col is not None:
        effective_playback_markers = [(playback_bar, playback_col)]
    style_policy = resolve_tab_style_policy(settings)
    total_bars = len(piece.bars)
    melody_rows_count = max(1, melody_rows_count) if show_melody else 0
    tuning_pitches = parse_tuning_pitches(settings.get("tuning", ""))
    duet_width_lock = settings.get("duetwidthlock", "off") == "on"
    current_bar_start = bar_offset
    row_start = header_row + 1
    for sys_idx in range(systems):
        bar_start = current_bar_start
        if bar_start >= total_bars:
            break
        if spacing_mode == "auto":
            plan = plan_auto_system(
                AutoSystemPlanOptions(
                    piece=piece,
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
                    total_strings=total_strings,
                    barpad=barpad,
                    show_dur=show_dur,
                    hide_redundant=hide_redundant,
                    settings=settings,
                ),
                bar_start=bar_start,
            )
        else:
            plan = plan_fixed_system(
                piece,
                bar_start=bar_start,
                bars_per_line_limit=bars_per_line_limit,
                stave_breaks=stave_breaks,
            )
        bar_widths = list(plan.bar_widths)
        gaps_after = list(plan.gaps_after)
        bar_end = plan.bar_end
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
        system_block_h = _block_height(
            include_meta,
            system_display_strings,
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
        # Clear only the rows this system owns. Bass courses that appear later
        # must not create blank spacer rows in otherwise six-course systems.
        for clear_row in range(row_start, row_start + system_block_h):
            safe_addstr(stdscr, clear_row, 0, " " * width)
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
                system_start=local_idx == 0,
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
            if bar.section_title:
                sign_cues.append(bar.section_title)
            if bar.section_subtitle:
                sign_cues.append(bar.section_subtitle)
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
                _bar_ornaments(ornaments, abs_bar, grid_width) if show_ornaments else [" " for _ in range(grid_width)]
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
                    _filter_redundant_positions(chord_positions_all) if hide_redundant else chord_positions_all
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
                _resolved_bar_time_value(piece, abs_bar - 1, time_setting, default_duration) if abs_bar > 0 else None
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
            positions, src_to_dest, grid_map, text_onset_cols = _render_rhythm_rows(
                stdscr,
                bar=bar,
                abs_bar=abs_bar,
                bar_width=bar_width,
                bar_x=bar_x,
                barpad=barpad,
                beats=beats,
                cells=cells,
                chord_positions_all=chord_positions_all,
                cursor_bar=cursor_bar,
                cursor_col=cursor_col,
                default_duration=default_duration,
                display_width=display_width,
                dotted=dotted,
                draw_pad=draw_pad,
                durations=durations,
                french_c=french_c,
                fretlabelmode=fretlabelmode,
                grid_width=grid_width,
                hide_redundant=hide_redundant,
                overrides=overrides,
                pad=pad,
                row_start=row_start,
                rows=rows,
                scale_bar=scale_bar,
                settings=settings,
                show_dur=show_dur,
                spacing_fill=spacing_fill,
                spacing_mode=spacing_mode,
                style=style,
                style_policy=style_policy,
                total_strings=total_strings,
                ann_cells=ann_cells,
                slur_cells=slur_cells,
                tie_cells=tie_cells,
                hold_cells=hold_cells,
                gliss_cells=gliss_cells,
                tuplet_cells=tuplet_cells,
                scaled_slur_row=scaled_slur_row,
                scaled_tie_row=scaled_tie_row,
                scaled_hold_row=scaled_hold_row,
                scaled_gliss_row=scaled_gliss_row,
                scaled_tuplet_row=scaled_tuplet_row,
            )
            _render_staff_and_playback(
                stdscr,
                piece=piece,
                bar=bar,
                abs_bar=abs_bar,
                ann_cells=ann_cells,
                ann_target_rows=ann_target_rows,
                bar_width=bar_width,
                bar_x=bar_x,
                barline=barline,
                barpad=barpad,
                cells=cells,
                cursor_bar=cursor_bar,
                cursor_col=cursor_col,
                cursor_display_maps=cursor_display_maps,
                cursor_string=cursor_string,
                display_width=display_width,
                draw_pad=draw_pad,
                effective_playback_markers=effective_playback_markers,
                grid_map=grid_map,
                grid_width=grid_width,
                highlights=highlights,
                lyric_row_offsets=lyric_row_offsets,
                melody_rows_count=melody_rows_count,
                orn_cells=orn_cells,
                orn_target_rows=orn_target_rows,
                pad=pad,
                playback_cache=playback_cache,
                positions=positions,
                repeat_left=repeat_left,
                repeat_right=repeat_right,
                repeat_rows=repeat_rows,
                row_start=row_start,
                rows=rows,
                scale_bar=scale_bar,
                settings=settings,
                show_time_sig_here=show_time_sig_here,
                sig_label=_sig_label,
                src_to_dest=src_to_dest,
                style=style,
                system_display_strings=system_display_strings,
                system_visual_indices=system_visual_indices,
                text_onset_cols=text_onset_cols,
                time_value=time_value,
                tuning_pitches=tuning_pitches,
                width=width,
            )
            if spacing_mode == "auto":
                next_gap = gaps_after[local_idx] if local_idx < len(gaps_after) else 0
                bar_x += display_width + next_gap
            else:
                bar_x += display_width + bar_gap
        current_bar_start = bar_end
        row_start += system_block_h
