from __future__ import annotations

from petrucci.render_helpers import apply_overrides
from petrucci.render_marks import (
    _imported_ft3_mark_target_rows,
    _merge_mark_rows,
    _place_parenthesize_tie_cues,
    _repeat_dot_display_rows,
    _split_tuplet_cues_from_annotations,
    _target_note_rows_by_col,
)
from petrucci.render_spacing import chord_positions_distinct as _chord_positions_distinct
from petrucci.render_spacing import note_event_columns as _note_event_columns
from petrucci.render_spacing import required_auto_display_width_for_bar as _required_auto_display_width_for_bar
from petrucci.render_spacing import required_duration_content_width as _required_duration_content_width
from petrucci.render_spacing import required_flag_content_width as _required_flag_content_width
from petrucci.render_system_types import BarBasics, BarLayout, BarMarks, BarMetadata, SystemLayout, SystemRenderContext
from petrucci.tab_policy import (
    gliss_span_chars,
    hold_span_chars,
    show_time_cue_for_bar,
    slur_span_chars,
    tie_notehead_hidden_cols,
    tie_notehead_parenthesize_cols,
    tie_span_chars,
    time_cue_side_pad,
)
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
    _tactus_row,
    bar_cells,
    bar_cells_from_chords,
)


def resolved_bar_time_value(piece, bar_index: int, time_setting: str, default_duration: int) -> str:
    value = piece.bars[bar_index].time_sig or time_setting
    if value in ("auto", "detect"):
        value = _infer_time_signature(piece.bars[bar_index], default_duration) or "C"
    return value


def prepare_bar_basics(context: SystemRenderContext, bar) -> BarBasics:
    style = context.settings.get("style", "french")
    french_c = context.settings.get("frenchc", "normal")
    label_mode = context.settings.get("fretlabelmode", "auto")
    positions: list[tuple[int, int, bool]] = []
    grid_width = context.bar_width
    if bar.chords:
        positions, grid_width = _chord_positions_distinct(bar, context.bar_width, context.default_duration)
        cells = bar_cells_from_chords(
            bar,
            context.total_strings,
            grid_width,
            context.default_duration,
            style,
            french_c=french_c,
            label_mode=label_mode,
        )
    else:
        cells = bar_cells(
            bar,
            context.total_strings,
            context.bar_width,
            style,
            french_c=french_c,
            label_mode=label_mode,
        )
    return BarBasics(style, french_c, label_mode, positions, grid_width, cells)


def prepare_bar_metadata(
    context: SystemRenderContext,
    system: SystemLayout,
    bar,
    *,
    abs_bar: int,
    local_index: int,
    grid_width: int,
) -> BarMetadata:
    step_text = context.settings.get("measuresstep", "1")
    step = max(1, int(step_text)) if step_text.isdigit() else 1
    number = _bar_number_for_index(
        context.piece,
        abs_bar,
        context.settings.get("measures", "start"),
        context.settings.get("countdots", "off"),
        step,
        system_start=local_index == 0,
    )
    time_setting = context.settings.get("time", "C")
    time_value = resolved_bar_time_value(context.piece, abs_bar, time_setting, context.default_duration)
    beats, _unit, sig_label = _parse_time_signature(time_value)
    repeat = bar.repeat or ""
    repeat_glyph = repeat if repeat in {".:", ":.", "."} else ""
    endings = tuple(sorted(set(bar.ending_numbers)))
    ending_cue = f"[{','.join(str(value) for value in endings)}.]" if endings else ""
    return BarMetadata(
        number=number,
        time_setting=time_setting,
        time_value=time_value,
        beats=beats,
        sig_label=sig_label,
        barline=bar.barline or "|",
        repeat_cue=repeat if not repeat_glyph else "",
        ending_cue=ending_cue,
        repeat_rows=_repeat_dot_display_rows(system.display_strings),
        repeat_left=repeat in {".:", ":|:", "."},
        repeat_right=repeat in {":.", ":|:", "."},
        sign_cues=_sign_cues(bar),
        tactus=_tactus_row(grid_width, beats),
    )


def _sign_cues(bar) -> list[str]:
    cues = [value for value in (bar.section_title, bar.section_subtitle) if value]
    if bar.fermata:
        cues.append("^")
    if bar.dynamic:
        cues.append(bar.dynamic)
    return cues


def prepare_bar_marks(
    context: SystemRenderContext,
    system: SystemLayout,
    bar,
    basics: BarBasics,
    *,
    abs_bar: int,
) -> BarMarks:
    imported_ann, imported_orn, ann_targets, orn_targets = _imported_marks(context, bar, basics.grid_width)
    ann_cells = _merge_mark_rows(imported_ann, _bar_annotations(context.annotations, abs_bar, basics.grid_width))
    ann_cells, tuplet_cells = _split_tuplet_cues_from_annotations(ann_cells, show_tuplets=context.show_tuplets)
    local_orn = (
        _bar_ornaments(context.ornaments, abs_bar, basics.grid_width)
        if context.style_policy.showornaments
        else [" "] * basics.grid_width
    )
    orn_cells = _merge_mark_rows(imported_orn, local_orn)
    slur_cells = _span_row(
        context.slurs, abs_bar, basics.grid_width, slur_span_chars(context.style_policy.slurcuestyle)
    )
    tie_cells = _span_row(context.ties, abs_bar, basics.grid_width, tie_span_chars(context.style_policy.tiecuestyle))
    hold_cells = _span_row(
        context.holds, abs_bar, basics.grid_width, hold_span_chars(context.style_policy.holdcuestyle)
    )
    gliss_cells = _span_row(
        context.glisses,
        abs_bar,
        basics.grid_width,
        gliss_span_chars(context.style_policy.glisscuestyle),
    )
    apply_overrides(basics.cells, context.overrides, abs_bar, context.total_strings, basics.grid_width)
    target_rows = _target_note_rows_by_col(basics.cells)
    ann_target_rows = _resolved_target_rows(target_rows, ann_targets, imported_ann)
    orn_target_rows = _resolved_target_rows(target_rows, orn_targets, imported_orn)
    _apply_tie_notehead_policy(
        context,
        system,
        basics,
        ann_cells,
        orn_cells,
        tie_cells,
        slur_cells,
        hold_cells,
        gliss_cells,
        abs_bar,
    )
    return BarMarks(
        ann_cells,
        orn_cells,
        tuplet_cells,
        slur_cells,
        tie_cells,
        hold_cells,
        gliss_cells,
        ann_target_rows,
        orn_target_rows,
    )


def _imported_marks(
    context: SystemRenderContext,
    bar,
    grid_width: int,
) -> tuple[list[str], list[str], list[int], list[int]]:
    ann = [" "] * grid_width
    orn = [" "] * grid_width
    ann_targets = [-1] * grid_width
    orn_targets = [-1] * grid_width
    if context.style_policy.showfingerings:
        ann = _bar_imported_ft3_annotations(
            bar,
            bar_width=grid_width,
            default_duration=context.default_duration,
            fingering_mode=context.settings.get("ft3fingering", "both"),
        )
    if context.style_policy.showornaments:
        orn = _bar_imported_ft3_ornaments(
            bar,
            bar_width=grid_width,
            default_duration=context.default_duration,
            ornament_mode=context.settings.get("ft3ornaments", "both"),
        )
    if context.style_policy.showfingerings or context.style_policy.showornaments:
        ann_targets, orn_targets = _imported_ft3_mark_target_rows(
            bar=bar,
            total_strings=context.total_strings,
            grid_width=grid_width,
            default_duration=context.default_duration,
            fingering_mode=context.settings.get("ft3fingering", "both"),
            ornament_mode=context.settings.get("ft3ornaments", "both"),
        )
    return ann, orn, ann_targets, orn_targets


def _span_row(
    spans: list[tuple[int, int, int]],
    abs_bar: int,
    grid_width: int,
    chars: tuple[str, str, str] | None,
) -> list[str]:
    return [" "] * grid_width if chars is None else _bar_span_row(spans, abs_bar, grid_width, *chars)


def _resolved_target_rows(base: list[int], imported: list[int], cells: list[str]) -> list[int]:
    resolved = list(base)
    for column, row_index in enumerate(imported):
        if row_index >= 0 and column < len(resolved) and cells[column] != " ":
            resolved[column] = row_index
    return resolved


def _apply_tie_notehead_policy(
    context: SystemRenderContext,
    system: SystemLayout,
    basics: BarBasics,
    ann_cells: list[str],
    orn_cells: list[str],
    tie_cells: list[str],
    slur_cells: list[str],
    hold_cells: list[str],
    gliss_cells: list[str],
    abs_bar: int,
) -> None:
    hidden = tie_notehead_hidden_cols(context.ties, bar_index=abs_bar, mode=context.style_policy.tienoteheads)
    for column in hidden:
        if 0 <= column < basics.grid_width:
            for row_cells in basics.cells:
                if row_cells[column] != "-":
                    row_cells[column] = "-"
    parenthesized = tie_notehead_parenthesize_cols(
        context.ties,
        bar_index=abs_bar,
        mode=context.style_policy.tienoteheads,
    )
    if parenthesized:
        _place_parenthesize_tie_cues(
            ann_cells=ann_cells,
            orn_cells=orn_cells,
            tie_cells=tie_cells,
            slur_cells=slur_cells,
            hold_cells=hold_cells,
            gliss_cells=gliss_cells,
            paren_tie_cols=parenthesized,
            allow_ann_row=system.rows["ann"] is not None,
        )


def prepare_bar_layout(
    context: SystemRenderContext,
    system: SystemLayout,
    bar,
    basics: BarBasics,
    metadata: BarMetadata,
    *,
    abs_bar: int,
    local_index: int,
) -> BarLayout:
    display_width = system.bar_widths[local_index] if context.spacing_mode == "auto" else context.bar_width
    scale_bar = context.spacing_mode == "auto"
    if bar.chords:
        minimum = _minimum_chord_width(context, system, basics)
        if minimum > display_width and context.spacing_mode != "auto" and not context.duet_width_lock:
            display_width = minimum
            scale_bar = True
    pad = context.barpad if scale_bar else 0
    previous_time = (
        resolved_bar_time_value(context.piece, abs_bar - 1, metadata.time_setting, context.default_duration)
        if abs_bar > 0
        else None
    )
    show_time = show_time_cue_for_bar(
        bar_index=abs_bar,
        current_time_value=metadata.time_value,
        prev_time_value=previous_time,
        sig_label=metadata.sig_label,
    )
    draw_pad = pad + _time_cue_pad(metadata.time_value, show_time=show_time, scale_bar=scale_bar)
    if bar.chords and not scale_bar and not context.duet_width_lock:
        display_width = max(display_width, _fixed_chord_width(context, system, bar, basics, draw_pad))
    return BarLayout(display_width, scale_bar, pad, draw_pad, show_time)


def _minimum_chord_width(context: SystemRenderContext, system: SystemLayout, basics: BarBasics) -> int:
    flags = _filter_redundant_positions(basics.chord_positions) if context.hide_redundant else basics.chord_positions
    gap = 2 if context.spacing_fill == "smart" else 1
    content = max(
        _required_flag_content_width(flags, min_gap=gap),
        len(_note_event_columns(basics.cells, context.total_strings, basics.grid_width)),
    )
    if context.show_dur and system.rows["dur"] is not None:
        content = max(content, _required_duration_content_width(flags, min_gap=gap))
    return content + context.barpad * 2


def _time_cue_pad(time_value: str, *, show_time: bool, scale_bar: bool) -> int:
    cue_pad = time_cue_side_pad(show_time_cue=show_time, scale_bar=scale_bar)
    if show_time and not scale_bar:
        cue_pad = max(cue_pad, time_cue_side_pad(show_time_cue=True, scale_bar=True))
    if show_time and time_value in {"C|", "c|", "2/2", "O", "o", "3/4"}:
        cue_pad = max(cue_pad, 3)
    return cue_pad


def _fixed_chord_width(
    context: SystemRenderContext,
    system: SystemLayout,
    bar,
    basics: BarBasics,
    draw_pad: int,
) -> int:
    compact = context.spacing_fill == "compact"
    return _required_auto_display_width_for_bar(
        bar,
        total_strings=context.total_strings,
        bar_width=context.bar_width,
        default_duration=context.default_duration,
        style=basics.style,
        french_c=basics.french_c,
        fretlabelmode=basics.fretlabelmode,
        show_dur=context.show_dur and system.rows["dur"] is not None,
        hide_redundant=context.hide_redundant,
        barpad=0,
        flag_gap=0 if compact else (2 if context.spacing_fill == "smart" else 1),
        event_gap=1 if compact else 2,
        cue_pad_total=draw_pad * 2,
    )
