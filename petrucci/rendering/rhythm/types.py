from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from petrucci.terminal.canvas.screen import Screen


@dataclass(frozen=True)
class RhythmRenderContext:
    stdscr: Screen
    bar: Any
    abs_bar: int
    bar_width: int
    bar_x: int
    barpad: int
    beats: int
    cells: list[list[str]]
    chord_positions_all: list[tuple[int, int, bool]]
    cursor_bar: int
    cursor_col: int
    default_duration: int
    display_width: int
    dotted: set[tuple[int, int]]
    draw_pad: int
    durations: dict[tuple[int, int, int], int]
    french_c: str
    fretlabelmode: str
    grid_width: int
    hide_redundant: bool
    overrides: dict[tuple[int, int, int], str]
    pad: int
    row_start: int
    rows: dict[str, int | None]
    scale_bar: bool
    settings: dict[str, str]
    show_dur: bool
    spacing_fill: str
    spacing_mode: str
    style: str
    style_policy: Any
    total_strings: int
    ann_cells: list[str]
    slur_cells: list[str]
    tie_cells: list[str]
    hold_cells: list[str]
    gliss_cells: list[str]
    tuplet_cells: list[str]
    scaled_slur_row: list[str] | None
    scaled_tie_row: list[str] | None
    scaled_hold_row: list[str] | None
    scaled_gliss_row: list[str] | None
    scaled_tuplet_row: list[str] | None


@dataclass(frozen=True)
class RhythmRenderResult:
    positions: list[tuple[int, int, bool]]
    src_to_dest: dict[int, int]
    grid_map: list[int]
    text_onset_cols: list[int]


@dataclass(frozen=True)
class FlagRowPlan:
    flag_cells: list[str]
    stem_cells: list[str]
    src_to_dest: dict[int, int]
    duration_positions: list[tuple[int, int]]
