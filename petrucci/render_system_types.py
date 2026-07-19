from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from petrucci.render_playback import PlaybackOverlayCache
from petrucci.screen import Screen


@dataclass(frozen=True)
class SystemRenderContext:
    stdscr: Screen
    piece: Any
    width: int
    header_row: int
    left_margin: int
    systems: int
    total_strings: int
    display_indices: list[int]
    display_strings: int
    bar_offset: int
    cursor_bar: int
    cursor_string: int
    cursor_col: int
    bar_width: int
    overrides: dict[tuple[int, int, int], str]
    durations: dict[tuple[int, int, int], int]
    ornaments: dict[tuple[int, int], str]
    annotations: dict[tuple[int, int], str]
    highlights: set[tuple[int, int, int]]
    dotted: set[tuple[int, int]]
    slurs: list[tuple[int, int, int]]
    ties: list[tuple[int, int, int]]
    holds: list[tuple[int, int, int]]
    glisses: list[tuple[int, int, int]]
    settings: dict[str, str]
    stave_breaks: set[int]
    effective_playback_markers: list[tuple[int, int]]
    include_meta: bool
    show_dur: bool
    show_extras: bool
    show_tuplets: bool
    show_tactus: bool
    hide_redundant: bool
    double_stems: bool
    reverse_strings: bool
    max_chords: int
    spacing_mode: str
    spacing_fill: str
    bar_gap: int
    barpad: int
    usable_width: int
    bars_per_line_limit: int
    default_duration: int
    tuning_labels: list[str]
    basslabels: str
    chord_wrap_limit: int
    show_melody: bool
    melody_rows_count: int
    show_lyrics: bool
    lyric_rows_count: int
    vocal_pos: str
    playback_cache: PlaybackOverlayCache | None
    cursor_display_maps: dict[int, list[int]] | None
    style_policy: Any
    tuning_pitches: list[int]
    duet_width_lock: bool


@dataclass(frozen=True)
class SystemLayout:
    bar_end: int
    bar_widths: list[int]
    gaps_after: list[int]
    display_strings: int
    visual_indices: list[int]
    rows: dict[str, int | None]
    block_height: int
    lyric_row_offsets: tuple[int, ...]


@dataclass(frozen=True)
class BarBasics:
    style: str
    french_c: str
    fretlabelmode: str
    chord_positions: list[tuple[int, int, bool]]
    grid_width: int
    cells: list[list[str]]


@dataclass(frozen=True)
class BarMetadata:
    number: str | None
    time_setting: str
    time_value: str
    beats: int
    sig_label: str
    barline: str
    repeat_cue: str
    ending_cue: str
    repeat_rows: set[int]
    repeat_left: bool
    repeat_right: bool
    sign_cues: list[str]
    tactus: list[str]


@dataclass(frozen=True)
class BarMarks:
    ann_cells: list[str]
    orn_cells: list[str]
    tuplet_cells: list[str]
    slur_cells: list[str]
    tie_cells: list[str]
    hold_cells: list[str]
    gliss_cells: list[str]
    ann_target_rows: list[int]
    orn_target_rows: list[int]


@dataclass(frozen=True)
class BarLayout:
    display_width: int
    scale_bar: bool
    pad: int
    draw_pad: int
    show_time_signature: bool


@dataclass(frozen=True)
class ScaledCueRows:
    slur: list[str] | None
    tie: list[str] | None
    hold: list[str] | None
    gliss: list[str] | None
    tuplet: list[str] | None
