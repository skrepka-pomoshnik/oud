from __future__ import annotations

from dataclasses import dataclass

from petrucci.render_helpers import safe_addstr
from petrucci.render_text_lanes import (
    draw_melody_key_signature,
    draw_melody_time_signature,
    melody_key_signature_width,
)
from petrucci.render_vocal import lyric_rows_for_bar, melody_rows_for_bar, vocal_onset_cols_for_bar
from petrucci.screen import Screen


@dataclass(frozen=True)
class RenderedVocalRows:
    melody_row_base: int | None
    onset_cols: list[int]
    melody_rows: list[str] | None


def render_vocal_rows(
    stdscr: Screen,
    *,
    piece,
    bar,
    abs_bar: int,
    bar_x: int,
    barline: str,
    display_width: int,
    draw_pad: int,
    lyric_row_offsets: tuple[int, ...],
    melody_rows_count: int,
    row_start: int,
    rows: dict[str, int | None],
    settings: dict[str, str],
    text_onset_cols: list[int],
    tuning_pitches: list[int],
    width: int,
) -> RenderedVocalRows:
    key_pad = melody_key_signature_width(piece.key) if abs_bar == 0 else 0
    left_pad = draw_pad + key_pad
    if abs_bar == 0 and (bar.time_sig or settings.get("time", "")):
        left_pad += 2
    onset_cols = vocal_onset_cols_for_bar(
        bar,
        onset_cols=text_onset_cols,
        width=display_width,
        left_pad=left_pad,
    )
    melody_base, rendered_melody = _render_melody(
        stdscr,
        piece=piece,
        bar=bar,
        abs_bar=abs_bar,
        bar_x=bar_x,
        barline=barline,
        display_width=display_width,
        key_pad=key_pad,
        left_pad=left_pad,
        melody_rows_count=melody_rows_count,
        onset_cols=onset_cols,
        row_start=row_start,
        rows=rows,
        settings=settings,
        tuning_pitches=tuning_pitches,
        width=width,
    )
    _render_lyrics(
        stdscr,
        bar=bar,
        bar_x=bar_x,
        barline=barline,
        display_width=display_width,
        left_pad=left_pad,
        lyric_row_offsets=lyric_row_offsets,
        onset_cols=onset_cols,
        row_start=row_start,
        width=width,
    )
    return RenderedVocalRows(melody_base, onset_cols, rendered_melody)


def _render_melody(
    stdscr: Screen,
    *,
    piece,
    bar,
    abs_bar: int,
    bar_x: int,
    barline: str,
    display_width: int,
    key_pad: int,
    left_pad: int,
    melody_rows_count: int,
    onset_cols: list[int],
    row_start: int,
    rows: dict[str, int | None],
    settings: dict[str, str],
    tuning_pitches: list[int],
    width: int,
) -> tuple[int | None, list[str] | None]:
    if rows.get("melody") is None:
        return None, None
    row_base = row_start + (rows["melody"] or 0)
    melody_rows = melody_rows_for_bar(
        bar,
        onset_cols=onset_cols,
        width=display_width,
        left_pad=left_pad,
        tuning_pitches=tuning_pitches,
    )
    if abs_bar == 0 and melody_rows:
        draw_melody_time_signature(
            melody_rows,
            time_sig=bar.time_sig or settings.get("time", ""),
            left_pad=max(0, left_pad - key_pad),
        )
        draw_melody_key_signature(
            melody_rows,
            key=piece.key,
            left_pad=max(0, left_pad - key_pad + 2),
        )
    rendered = ["".join(row) for row in melody_rows]
    for row_index, row_text in enumerate(rendered[:melody_rows_count]):
        y = row_base + row_index
        if row_text.strip():
            safe_addstr(stdscr, y, bar_x - 1, "|")
        safe_addstr(stdscr, y, bar_x, row_text)
        if row_text.strip():
            safe_addstr(stdscr, y, min(max(0, width - 2), bar_x + display_width), barline)
    return row_base, rendered


def _render_lyrics(
    stdscr: Screen,
    *,
    bar,
    bar_x: int,
    barline: str,
    display_width: int,
    left_pad: int,
    lyric_row_offsets: tuple[int, ...],
    onset_cols: list[int],
    row_start: int,
    width: int,
) -> None:
    if not lyric_row_offsets:
        return
    lyric_rows = lyric_rows_for_bar(
        bar,
        onset_cols=onset_cols,
        width=display_width,
        left_pad=left_pad,
        lyric_rows_count=len(lyric_row_offsets),
    )
    for lyric_index, lyric_row in enumerate(lyric_row_offsets):
        lyric_cells = lyric_rows[lyric_index] if lyric_index < len(lyric_rows) else [" "] * display_width
        y = row_start + lyric_row
        safe_addstr(stdscr, y, bar_x - 1, "|")
        safe_addstr(stdscr, y, bar_x, "".join(lyric_cells))
        safe_addstr(stdscr, y, min(max(0, width - 2), bar_x + display_width), barline)
