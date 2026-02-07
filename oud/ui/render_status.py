from __future__ import annotations

from oud.core.model import Piece
from oud.core.view_model import chord_positions


def resolve_duration_text(
    *,
    piece: Piece,
    durations: dict[tuple[int, int, int], int],
    dotted: set[tuple[int, int]],
    cursor_bar: int,
    cursor_col: int,
    actual_cursor_string: int,
    bar_width: int,
    default_duration: int = 4,
) -> str | None:
    dur_key = (cursor_bar, actual_cursor_string, cursor_col)
    dur_text: str | int | None = durations.get(dur_key)
    if dur_text is None:
        for s_idx in range(piece.strings):
            alt_key = (cursor_bar, s_idx, cursor_col)
            if alt_key in durations:
                dur_text = durations[alt_key]
                break
    if dur_text is not None and (cursor_bar, cursor_col) in dotted:
        dur_text = f"{dur_text}."
    if dur_text is None and 0 <= cursor_bar < len(piece.bars):
        bar = piece.bars[cursor_bar]
        if bar.chords:
            positions = chord_positions(bar, bar_width, default_duration)
            for col, denom, _dot in positions:
                if col == cursor_col:
                    dur_text = denom
                    break
    return str(dur_text) if dur_text is not None else None


def build_status_lines(
    *,
    mode: str,
    cmdline: str,
    searchline: str,
    message: str,
    status_line: str,
    dur_text: str | None,
) -> tuple[str, str]:
    status = mode
    if mode == "command":
        status = f":{cmdline}"
    if mode == "search":
        status = f"/{searchline}"
    if mode == "help":
        status = "help  j/k scroll  q close"
    if dur_text and mode not in ("command", "search"):
        status = f"{status}  len:{dur_text}"
    if message and mode not in ("command", "search"):
        status = f"{status}  {message}"
    status_line_text = status_line
    if message and mode in ("command", "search"):
        status_line_text = message
    return status, status_line_text
