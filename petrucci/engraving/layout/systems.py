from __future__ import annotations

from dataclasses import dataclass

from petrucci.core.model import Piece
from petrucci.engraving.layout.spacing import (
    auto_bar_plan,
    collision_base_bar_widths,
    justified_extra_width,
    short_system_bar_floor,
)
from petrucci.input.tablature.policy import (
    bar_has_multifret_tokens,
    multifret_event_gap,
    show_time_cue_for_bar,
    time_cue_side_pad,
)
from petrucci.rendering.primitives.spacing import required_auto_display_width_for_bar
from petrucci.terminal.view.model import _infer_time_signature, _next_system_start, _parse_time_signature


@dataclass(frozen=True, slots=True)
class SystemPlan:
    bar_start: int
    bar_indices: tuple[int, ...]
    bar_widths: tuple[int, ...]
    gaps_after: tuple[int, ...]

    @property
    def bar_end(self) -> int:
        return self.bar_indices[-1] + 1 if self.bar_indices else self.bar_start


@dataclass(frozen=True, slots=True)
class AutoSystemPlanOptions:
    piece: Piece
    usable_width: int
    bar_width: int
    overrides: dict[tuple[int, int, int], str]
    durations: dict[tuple[int, int, int], int]
    default_duration: int
    dotted: set[tuple[int, int]]
    bar_gap: int
    spacing_fill: str
    stave_breaks: set[int]
    bars_per_line_limit: int
    max_chords: int
    chord_wrap_limit: int
    total_strings: int
    barpad: int
    show_dur: bool
    hide_redundant: bool
    settings: dict[str, str]


def source_breaks_enabled(settings: dict[str, str]) -> bool:
    """Whether the line breaks stored in the score (a TAB file's own lines) end a system."""

    return settings.get("sourcebreaks", "on") == "on"


def plan_fixed_system(
    piece: Piece,
    *,
    bar_start: int,
    bars_per_line_limit: int,
    stave_breaks: set[int],
    honor_bar_breaks: bool = True,
) -> SystemPlan:
    bars_per_line = max(1, bars_per_line_limit)
    bar_end = min(
        len(piece.bars),
        _next_system_start(piece.bars, bar_start, bars_per_line, stave_breaks, honor_bar_breaks=honor_bar_breaks),
    )
    return SystemPlan(bar_start, tuple(range(bar_start, bar_end)), (), ())


def plan_auto_system(options: AutoSystemPlanOptions, *, bar_start: int) -> SystemPlan:
    bar_indices, bar_widths, gaps_after = auto_bar_plan(
        bars=options.piece.bars,
        bar_start=bar_start,
        usable_width=options.usable_width,
        bar_width=options.bar_width,
        overrides=options.overrides,
        durations=options.durations,
        default_duration=options.default_duration,
        dotted=options.dotted,
        bar_gap=options.bar_gap,
        spacing_fill=options.spacing_fill,
        stave_breaks=options.stave_breaks,
        bars_per_line_limit=options.bars_per_line_limit,
        max_chords=options.max_chords,
        chord_wrap_limit=options.chord_wrap_limit,
        honor_bar_breaks=source_breaks_enabled(options.settings),
    )
    justify = sum(bar_widths) + sum(gaps_after) == options.usable_width
    bar_widths = collision_base_bar_widths(
        should_justify=justify,
        planned_widths=bar_widths,
        bars=options.piece.bars,
        bar_indices=bar_indices,
        bar_width=options.bar_width,
        overrides=options.overrides,
        durations=options.durations,
        default_duration=options.default_duration,
        dotted=options.dotted,
    )
    minimums = [_minimum_bar_width(options, bar_index, justify=justify) for bar_index in bar_indices]
    bar_widths = [
        min(max(1, options.usable_width), max(width, minimum))
        for width, minimum in zip(bar_widths, minimums, strict=False)
    ]
    _drop_overflowing_bars(
        bar_indices,
        bar_widths,
        gaps_after,
        usable_width=options.usable_width,
    )
    extra = justified_extra_width(
        should_justify=justify,
        usable_width=options.usable_width,
        widths=bar_widths,
        gaps=gaps_after,
    )
    redistribute_extra_width(bar_widths, gaps_after, spacing_fill=options.spacing_fill, extra=extra)
    return SystemPlan(bar_start, tuple(bar_indices), tuple(bar_widths), tuple(gaps_after))


def _minimum_bar_width(options: AutoSystemPlanOptions, bar_index: int, *, justify: bool) -> int:
    settings = options.settings
    time_value = _resolved_time_value(options, bar_index)
    _beats, _unit, signature = _parse_time_signature(time_value)
    previous = _resolved_time_value(options, bar_index - 1) if bar_index > 0 else None
    show_cue = show_time_cue_for_bar(
        bar_index=bar_index,
        current_time_value=time_value,
        prev_time_value=previous,
        sig_label=signature,
    )
    cue_pad = time_cue_side_pad(show_time_cue=show_cue, scale_bar=True)
    if show_cue and time_value in {"C|", "c|", "2/2", "O", "o", "3/4"}:
        cue_pad = max(cue_pad, 3)
    compact = options.spacing_fill == "compact"
    event_gap = multifret_event_gap(
        style=settings.get("style", "french"),
        policy=settings.get("multifretspacing", "collision-safe"),
        has_multifret=bar_has_multifret_tokens(
            options.piece.bars[bar_index],
            style=settings.get("style", "french"),
            french_c_shape=settings.get("frenchc", "normal"),
            label_mode=settings.get("fretlabelmode", "auto"),
        ),
    )
    if compact:
        event_gap = max(1, event_gap - 1)
    flag_gap = 0 if compact else (2 if options.spacing_fill == "smart" else 1)
    readable_floor = short_system_bar_floor(
        should_justify=justify,
        bar_width=options.bar_width,
        barpad=options.barpad,
        usable_width=options.usable_width,
    )
    required = required_auto_display_width_for_bar(
        options.piece.bars[bar_index],
        total_strings=options.total_strings,
        bar_width=options.bar_width,
        default_duration=options.default_duration,
        style=settings.get("style", "french"),
        french_c=settings.get("frenchc", "normal"),
        fretlabelmode=settings.get("fretlabelmode", "auto"),
        show_dur=options.show_dur,
        hide_redundant=options.hide_redundant,
        barpad=options.barpad,
        flag_gap=flag_gap,
        event_gap=event_gap,
        cue_pad_total=cue_pad * 2,
    )
    return min(max(1, options.usable_width), max(readable_floor, required))


def _resolved_time_value(options: AutoSystemPlanOptions, bar_index: int) -> str:
    value = options.piece.bars[bar_index].time_sig or options.settings.get("time", "C")
    if value in {"auto", "detect"}:
        return _infer_time_signature(options.piece.bars[bar_index], options.default_duration) or "C"
    return value


def _drop_overflowing_bars(
    bar_indices: list[int],
    widths: list[int],
    gaps: list[int],
    *,
    usable_width: int,
) -> None:
    while widths and sum(widths) + sum(gaps) > usable_width:
        widths.pop()
        del bar_indices[len(widths) :]
        del gaps[max(0, len(widths) - 1) :]


def redistribute_extra_width(
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
    if spacing_fill in {"stretch", "smart"}:
        _spread_extra_across_widths(widths, extra, edge_first=spacing_fill == "stretch")
        return
    if spacing_fill == "edge":
        _spread_extra_across_edges(gaps, extra)


def _spread_extra_across_widths(widths: list[int], extra: int, *, edge_first: bool) -> None:
    order = list(range(len(widths)))
    if edge_first:
        order = [item for pair in zip(order, reversed(order), strict=False) for item in pair]
        order = list(dict.fromkeys(order))
    for index in range(extra):
        widths[order[index % len(order)]] += 1


def _spread_extra_across_edges(gaps: list[int], extra: int) -> None:
    if not gaps:
        return
    edge_indices = (0,) if len(gaps) == 1 else (0, len(gaps) - 1)
    for index in range(extra):
        gaps[edge_indices[index % len(edge_indices)]] += 1
