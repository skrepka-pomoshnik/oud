from __future__ import annotations

from oud.editor.core.state import EditorState
from petrucci.spacing import (
    auto_bar_plan,
    collision_base_bar_widths,
    justified_extra_width,
    short_system_bar_floor,
)
from petrucci.view_model import _next_system_start

_SYSTEM_LAYOUT_SETTING_KEYS = (
    "layout",
    "justify",
    "linelen",
    "bargap",
    "barpad",
    "barsperline",
    "maxbars",
    "maxchords",
    "chordwrap",
    "showdur",
    "flagredundant",
    "style",
    "frenchc",
    "fretlabelmode",
    "multifretspacing",
    "time",
)


def _system_layout_cache_key(state: EditorState, width: int) -> tuple[object, ...] | None:
    if state.modified:
        return None
    bar_shapes = tuple(
        (
            id(bar),
            id(bar.chords),
            len(bar.chords),
            id(bar.notes),
            len(bar.notes),
            bar.system_break,
            bar.time_sig,
        )
        for bar in state.piece.bars
    )
    return (
        id(state.piece),
        id(state.piece.bars),
        len(state.piece.bars),
        state.piece.strings,
        width,
        state.bar_width,
        len(state.undo_stack),
        state.clean_undo_depth,
        tuple((key, state.settings.get(key, "")) for key in _SYSTEM_LAYOUT_SETTING_KEYS),
        tuple(sorted(state.stave_breaks)),
        tuple(sorted(state.overrides.items())),
        tuple(sorted(state.durations.items())),
        tuple(sorted(state.dotted)),
        bar_shapes,
    )


def bar_gap(state: EditorState) -> int:
    gap = state.settings.get("bargap", "")
    if gap.isdigit():
        return max(0, int(gap))
    mode = state.settings.get("layout", "packed")
    return 1 if mode in ("packed", "auto") else 3


def bars_per_line(state: EditorState, width: int) -> int:
    fixed = state.settings.get("barsperline", "")
    if fixed.isdigit():
        fixed_value = int(fixed)
        if fixed_value > 0:
            return fixed_value
    left_margin = 3
    max_width = width
    linelen = state.settings.get("linelen", "")
    if linelen.isdigit():
        line_limit = int(linelen)
        if line_limit > 0:
            max_width = min(max_width, line_limit)
    right_padding = 1
    usable_width = max(0, max_width - left_margin - right_padding)
    per_line = max(1, usable_width // (state.bar_width + bar_gap(state)))
    maxbars = state.settings.get("maxbars", "")
    if maxbars.isdigit():
        limit = int(maxbars)
        if limit > 0:
            per_line = min(per_line, limit)
    return per_line


def _sorted_breaks(state: EditorState, bars: int) -> list[int]:
    breaks = [idx for idx in state.stave_breaks if 0 < idx < bars]
    return sorted(set(breaks))


def system_start_indices(state: EditorState, bars: int, per_line: int) -> list[int]:
    starts = [0]
    breaks = _sorted_breaks(state, bars)
    idx = 0
    while idx < bars:
        next_break = next((b for b in breaks if b > idx), bars)
        limit = min(next_break, idx + per_line)
        if limit >= bars:
            break
        starts.append(limit)
        idx = limit
    return starts


def system_index(state: EditorState, bar_index: int, per_line: int) -> int:
    starts = system_start_indices(state, len(state.piece.bars), per_line)
    for idx, _start in enumerate(starts):
        if idx + 1 < len(starts) and bar_index >= starts[idx + 1]:
            continue
        return idx
    return max(0, len(starts) - 1)


def system_start_index(state: EditorState, system_idx: int, per_line: int) -> int:
    starts = system_start_indices(state, len(state.piece.bars), per_line)
    if system_idx < 0:
        return 0
    if system_idx >= len(starts):
        return starts[-1]
    return starts[system_idx]


def system_range(state: EditorState, bar_index: int, per_line: int) -> tuple[int, int]:
    starts = system_start_indices(state, len(state.piece.bars), per_line)
    for idx, start in enumerate(starts):
        end = starts[idx + 1] if idx + 1 < len(starts) else len(state.piece.bars)
        if start <= bar_index < end:
            return start, end
    return 0, len(state.piece.bars)


def jump_system_row(state: EditorState, bar_index: int, delta: int, per_line: int) -> int:
    starts = system_start_indices(state, len(state.piece.bars), per_line)
    if not starts:
        return 0
    current_idx = 0
    for idx, start in enumerate(starts):
        end = starts[idx + 1] if idx + 1 < len(starts) else len(state.piece.bars)
        if start <= bar_index < end:
            current_idx = idx
            break
    current_start = starts[current_idx]
    offset = max(0, bar_index - current_start)
    target_idx = min(len(starts) - 1, max(0, current_idx + delta))
    target_start = starts[target_idx]
    target_end = starts[target_idx + 1] if target_idx + 1 < len(starts) else len(state.piece.bars)
    return min(target_end - 1, target_start + offset)


def dynamic_system_starts(state: EditorState, width: int) -> list[int]:  # noqa: C901, PLR0912
    cache_key = _system_layout_cache_key(state, width)
    if cache_key is not None and state.system_layout_cache_key == cache_key:
        return list(state.system_layout_cache_starts)
    bars = state.piece.bars
    total = len(bars)
    if total <= 0:
        return [0]
    left_margin = 3
    max_width = width
    linelen = state.settings.get("linelen", "")
    if linelen.isdigit():
        line_limit = int(linelen)
        if line_limit > 0:
            max_width = min(max_width, line_limit)
    right_padding = 1
    usable_width = max(1, max_width - left_margin - right_padding)
    spacing_mode = state.settings.get("layout", "packed")
    bargap = state.settings.get("bargap", "")
    bar_gap = max(0, int(bargap)) if bargap.isdigit() else 1 if spacing_mode in ("packed", "auto") else 3
    barsperline = state.settings.get("barsperline", "")
    bars_per_line_limit = 0
    if spacing_mode != "auto":
        bars_per_line_limit = max(1, usable_width // (state.bar_width + bar_gap))
    if barsperline.isdigit():
        limit = int(barsperline)
        if limit > 0:
            bars_per_line_limit = limit
    maxbars = state.settings.get("maxbars", "")
    if maxbars.isdigit():
        limit = int(maxbars)
        if limit > 0:
            bars_per_line_limit = limit if bars_per_line_limit <= 0 else min(bars_per_line_limit, limit)
    starts = [0]
    current = 0
    while current < total:
        if spacing_mode == "auto":
            bar_indices, _widths, _gaps = auto_system_bar_plan_with_gaps(state, current, width)
            if bars_per_line_limit > 0 and bar_indices:
                capped = bar_indices[:bars_per_line_limit]
                bar_indices = capped
            next_start = (bar_indices[-1] + 1) if bar_indices else (current + 1)
            if state.stave_breaks:
                # Respect manual breaks by truncating at the first break within the planned system.
                next_start = _next_system_start(
                    bars,
                    current,
                    max(1, next_start - current),
                    state.stave_breaks,
                )
        else:
            bars_per_line = bars_per_line_limit
            if bars_per_line_limit > 0:
                bars_per_line = min(bars_per_line, bars_per_line_limit)
            bars_per_line = max(1, bars_per_line)
            next_start = _next_system_start(bars, current, bars_per_line, state.stave_breaks)
        if next_start <= current:
            break
        if next_start < total:
            starts.append(next_start)
        current = next_start
    if cache_key is not None:
        state.system_layout_cache_key = cache_key
        state.system_layout_cache_starts = tuple(starts)
    return starts


def auto_system_bar_plan(
    state: EditorState,
    start_bar: int,
    width: int,
) -> tuple[list[int], list[int]]:
    bar_indices, bar_widths, _gaps = auto_system_bar_plan_with_gaps(state, start_bar, width)
    return bar_indices, bar_widths


def auto_system_bar_plan_with_gaps(  # noqa: C901
    state: EditorState,
    start_bar: int,
    width: int,
) -> tuple[list[int], list[int], list[int]]:
    bars = state.piece.bars
    total = len(bars)
    if start_bar < 0 or start_bar >= total:
        return [], [], []
    left_margin = 3
    max_width = width
    linelen = state.settings.get("linelen", "")
    if linelen.isdigit():
        line_limit = int(linelen)
        if line_limit > 0:
            max_width = min(max_width, line_limit)
    right_padding = 1
    usable_width = max(1, max_width - left_margin - right_padding)
    spacing_fill = state.settings.get("justify", "stretch")
    bargap = state.settings.get("bargap", "")
    bar_gap = max(0, int(bargap)) if bargap.isdigit() else 1
    bars_per_line_limit = 0
    barsperline = state.settings.get("barsperline", "")
    if barsperline.isdigit():
        value = int(barsperline)
        if value > 0:
            bars_per_line_limit = value
    maxbars = state.settings.get("maxbars", "")
    if maxbars.isdigit():
        value = int(maxbars)
        if value > 0:
            bars_per_line_limit = value if bars_per_line_limit <= 0 else min(bars_per_line_limit, value)
    max_chords_text = state.settings.get("maxchords", "0")
    max_chords = int(max_chords_text) if max_chords_text.isdigit() else 0
    chord_wrap_text = state.settings.get("chordwrap", "0")
    chord_wrap_limit = int(chord_wrap_text) if chord_wrap_text.isdigit() else 0
    bar_indices, bar_widths, gaps = auto_bar_plan(
        bars=bars,
        bar_start=start_bar,
        usable_width=usable_width,
        bar_width=state.bar_width,
        overrides=state.overrides,
        durations=state.durations,
        default_duration=4,
        dotted=state.dotted,
        bar_gap=bar_gap,
        spacing_fill=spacing_fill,
        stave_breaks=state.stave_breaks,
        bars_per_line_limit=bars_per_line_limit,
        max_chords=max_chords,
        chord_wrap_limit=chord_wrap_limit,
    )
    if state.settings.get("layout", "packed") == "auto" and bar_indices:
        justify_system = sum(bar_widths) + sum(gaps) == usable_width
        bar_widths = collision_base_bar_widths(
            should_justify=justify_system,
            planned_widths=bar_widths,
            bars=bars,
            bar_indices=bar_indices,
            bar_width=state.bar_width,
            overrides=state.overrides,
            durations=state.durations,
            default_duration=4,
            dotted=state.dotted,
        )
        # Match renderer's final width normalization so navigation and viewport
        # operate on the same system breaks the user actually sees.
        from petrucci.system_plan import redistribute_extra_width  # noqa: PLC0415

        min_widths = _renderer_min_bar_widths(state, bar_indices)
        readable_floor = short_system_bar_floor(
            should_justify=justify_system,
            bar_width=state.bar_width,
            barpad=int(state.settings.get("barpad", "1")) if state.settings.get("barpad", "1").isdigit() else 1,
            usable_width=usable_width,
        )
        min_widths = [max(width, readable_floor) for width in min_widths]
        bar_widths = [
            min(max(1, usable_width), max(width, min_width))
            for width, min_width in zip(bar_widths, min_widths, strict=False)
        ]
        while bar_widths and (sum(bar_widths) + sum(gaps)) > usable_width:
            bar_widths.pop()
            bar_indices = bar_indices[: len(bar_widths)]
            gaps = gaps[: max(0, len(bar_widths) - 1)]
        extra = justified_extra_width(
            should_justify=justify_system,
            usable_width=usable_width,
            widths=bar_widths,
            gaps=gaps,
        )
        redistribute_extra_width(
            bar_widths,
            gaps,
            spacing_fill=spacing_fill,
            extra=extra,
        )
    return bar_indices, bar_widths, gaps


def _renderer_min_bar_widths(state: EditorState, bar_indices: list[int]) -> list[int]:
    """Per-bar minimum display widths, mirroring render_systems' computation."""
    from petrucci.render_bar_state import resolved_bar_time_value  # noqa: PLC0415
    from petrucci.render_spacing import required_auto_display_width_for_bar  # noqa: PLC0415
    from petrucci.tab_policy import (  # noqa: PLC0415
        bar_has_multifret_tokens,
        multifret_event_gap,
        show_time_cue_for_bar,
        time_cue_side_pad,
    )
    from petrucci.view_model import _parse_time_signature  # noqa: PLC0415

    bars = state.piece.bars
    barpad_text = state.settings.get("barpad", "1")
    barpad = int(barpad_text) if barpad_text.isdigit() else 1
    show_dur = state.settings.get("showdur", "off") == "on"
    hide_redundant = state.settings.get("flagredundant", "on") == "on"
    style = state.settings.get("style", "french")
    french_c = state.settings.get("frenchc", "normal")
    fretlabelmode = state.settings.get("fretlabelmode", "auto")
    spacing_fill = state.settings.get("justify", "stretch")
    time_setting = state.settings.get("time", "C")
    compact_fill = spacing_fill == "compact"
    auto_flag_gap = 0 if compact_fill else (2 if spacing_fill == "smart" else 1)
    min_widths: list[int] = []
    for abs_bar in bar_indices:
        auto_event_gap = multifret_event_gap(
            style=style,
            policy=state.settings.get("multifretspacing", "collision-safe"),
            has_multifret=bar_has_multifret_tokens(
                bars[abs_bar],
                style=style,
                french_c_shape=french_c,
                label_mode=fretlabelmode,
            ),
        )
        if compact_fill:
            auto_event_gap = max(1, auto_event_gap - 1)
        current_time = resolved_bar_time_value(state.piece, abs_bar, time_setting, 4)
        _beats, _unit, sig_label = _parse_time_signature(current_time)
        prev_time = resolved_bar_time_value(state.piece, abs_bar - 1, time_setting, 4) if abs_bar > 0 else None
        show_cue = show_time_cue_for_bar(
            bar_index=abs_bar,
            current_time_value=current_time,
            prev_time_value=prev_time,
            sig_label=sig_label,
        )
        cue_pad_extra = time_cue_side_pad(show_time_cue=show_cue, scale_bar=True)
        if show_cue and current_time in {"C|", "c|", "2/2", "O", "o", "3/4"}:
            cue_pad_extra = max(cue_pad_extra, 3)
        min_widths.append(
            required_auto_display_width_for_bar(
                bars[abs_bar],
                total_strings=state.piece.strings,
                bar_width=state.bar_width,
                default_duration=4,
                style=style,
                french_c=french_c,
                fretlabelmode=fretlabelmode,
                show_dur=show_dur,
                hide_redundant=hide_redundant,
                barpad=barpad,
                flag_gap=auto_flag_gap,
                event_gap=auto_event_gap,
                cue_pad_total=cue_pad_extra * 2,
            ),
        )
    return min_widths


def jump_system_row_dynamic(  # noqa: C901
    state: EditorState,
    bar_index: int,
    delta: int,
    width: int,
) -> int:
    starts = dynamic_system_starts(state, width)
    if not starts:
        return 0
    current_idx = 0
    for idx, start in enumerate(starts):
        end = starts[idx + 1] if idx + 1 < len(starts) else len(state.piece.bars)
        if start <= bar_index < end:
            current_idx = idx
            break
    target_idx = min(len(starts) - 1, max(0, current_idx + delta))
    if target_idx == current_idx:
        return bar_index
    current_start = starts[current_idx]
    target_start = starts[target_idx]
    current_indices, current_widths, current_gaps = auto_system_bar_plan_with_gaps(
        state,
        current_start,
        width,
    )
    target_indices, target_widths, target_gaps = auto_system_bar_plan_with_gaps(
        state,
        target_start,
        width,
    )
    if not target_indices or not target_widths:
        return bar_index

    def _spans(
        indices: list[int],
        widths: list[int],
        gaps: list[int],
    ) -> list[tuple[int, int, int]]:
        x = 0
        spans: list[tuple[int, int, int]] = []
        for idx, abs_bar in enumerate(indices):
            w = max(1, widths[idx])
            spans.append((abs_bar, x, x + w))
            if idx < len(gaps):
                x += w + max(0, gaps[idx])
            else:
                x += w
        return spans

    current_spans = _spans(current_indices, current_widths, current_gaps)
    target_spans = _spans(target_indices, target_widths, target_gaps)
    current_span = next((span for span in current_spans if span[0] == bar_index), None)
    if current_span is None:
        return target_indices[0]
    _bar, x0, x1 = current_span
    anchor_x = x0 + max(0, (x1 - x0 - 1) // 2)

    for abs_bar, t0, t1 in target_spans:
        if t0 <= anchor_x < t1:
            return abs_bar
    return min(target_spans, key=lambda span: abs((span[1] + span[2]) // 2 - anchor_x))[0]
