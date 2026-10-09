from __future__ import annotations

from petrucci.rendering.primitives.helpers import pad_row, safe_addstr
from petrucci.rendering.system.types import (
    BarLayout,
    BarMarks,
    BarMetadata,
    ScaledCueRows,
    SystemLayout,
    SystemRenderContext,
)
from petrucci.terminal.view.model import _scale_row


def draw_static_bar_rows(
    context: SystemRenderContext,
    system: SystemLayout,
    metadata: BarMetadata,
    marks: BarMarks,
    layout: BarLayout,
    *,
    abs_bar: int,
    bar_x: int,
    row_start: int,
) -> ScaledCueRows:
    _draw_meta(context, system, metadata, layout, abs_bar=abs_bar, bar_x=bar_x, row_start=row_start)
    _draw_named_row(context, system, "ann", marks.ann_cells, layout, bar_x=bar_x, row_start=row_start)
    _draw_named_row(context, system, "orn", marks.orn_cells, layout, bar_x=bar_x, row_start=row_start)
    _draw_named_row(context, system, "tactus", metadata.tactus, layout, bar_x=bar_x, row_start=row_start)
    return ScaledCueRows(
        slur=_scaled_named_row(system, "slur", marks.slur_cells, layout),
        tie=_scaled_named_row(system, "tie", marks.tie_cells, layout),
        hold=_scaled_named_row(system, "hold", marks.hold_cells, layout),
        gliss=_scaled_named_row(system, "gliss", marks.gliss_cells, layout),
        tuplet=_scaled_named_row(system, "tuplet", marks.tuplet_cells, layout),
    )


def _draw_meta(
    context: SystemRenderContext,
    system: SystemLayout,
    metadata: BarMetadata,
    layout: BarLayout,
    *,
    abs_bar: int,
    bar_x: int,
    row_start: int,
) -> None:
    row = system.rows.get("meta")
    if row is None:
        return
    y = row_start + row
    if abs_bar == 0 and not layout.show_time_signature:
        safe_addstr(context.stdscr, y, 0, " ")
    if metadata.number is not None:
        safe_addstr(context.stdscr, y, bar_x, metadata.number)
    cue_parts = [value for value in (metadata.ending_cue, metadata.repeat_cue) if value]
    cue_parts.extend(metadata.sign_cues)
    if cue_parts:
        cue_x = bar_x + (len(metadata.number) + 1 if metadata.number is not None else 0)
        safe_addstr(context.stdscr, y, cue_x, " ".join(cue_parts))


_MIN_NAME_WIDTH = 2


def draw_chord_names(
    context: SystemRenderContext,
    system: SystemLayout,
    *,
    metadata: BarMetadata,
    layout: BarLayout,
    bar,
    chord_columns: list[tuple[int, int, bool]],
    grid_map: list[int],
    bar_x: int,
    row_start: int,
) -> None:
    """Chord symbols on the bar-number row, each at its chord; never over the bar number, its cues or a neighbour."""

    row = system.rows.get("meta")
    if row is None or not grid_map or not any(chord.name for chord in bar.chords):
        return
    cues = " ".join([value for value in (metadata.ending_cue, metadata.repeat_cue) if value] + metadata.sign_cues)
    reserved = (len(metadata.number) + 1 if metadata.number is not None else 0) + (len(cues) + 1 if cues else 0)
    next_free = bar_x + reserved
    limit = bar_x + layout.display_width
    for chord, (column, _denom, _dot) in zip(bar.chords, chord_columns, strict=False):
        if not chord.name:
            continue
        x = max(next_free, bar_x + layout.draw_pad + grid_map[min(column, len(grid_map) - 1)])
        name = chord.name[: limit - x]  # a symbol that runs past the bar is cut, not left to spill into the next bar
        if len(name) < min(len(chord.name), _MIN_NAME_WIDTH):
            continue
        safe_addstr(context.stdscr, row_start + row, x, name)
        next_free = x + len(name) + 1


def _draw_named_row(
    context: SystemRenderContext,
    system: SystemLayout,
    key: str,
    cells: list[str],
    layout: BarLayout,
    *,
    bar_x: int,
    row_start: int,
) -> None:
    row = system.rows.get(key)
    if row is None:
        return
    scaled = _scale_cells(cells, layout)
    safe_addstr(context.stdscr, row_start + row, bar_x, "".join(scaled))


def _scaled_named_row(
    system: SystemLayout,
    key: str,
    cells: list[str],
    layout: BarLayout,
) -> list[str] | None:
    return None if system.rows.get(key) is None else _scale_cells(cells, layout)


def _scale_cells(cells: list[str], layout: BarLayout) -> list[str]:
    if not layout.scale_bar:
        return cells
    content_width = max(1, layout.display_width - layout.draw_pad * 2)
    return pad_row(_scale_row(cells, content_width, " "), layout.display_width, layout.draw_pad)
