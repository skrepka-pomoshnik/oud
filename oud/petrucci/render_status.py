from __future__ import annotations

from oud.petrucci.model import Piece
from oud.petrucci.render_utils import note_type_to_denom
from oud.petrucci.time_utils import parse_time_signature_value
from oud.petrucci.view_model import chord_positions


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


def _bar_has_manual_entries(
    cursor_bar: int,
    overrides: dict[tuple[int, int, int], str],
    durations: dict[tuple[int, int, int], int],
) -> bool:
    return any(b == cursor_bar for (b, _s, _c) in overrides) or any(
        b == cursor_bar for (b, _s, _c) in durations
    )


def _chord_bar_sum_quarter_beats(
    *,
    piece: Piece,
    bar_index: int,
    bar_width: int,
    default_duration: int,
    dotted: set[tuple[int, int]],
) -> float:
    bar = piece.bars[bar_index]
    positions = chord_positions(bar, bar_width, default_duration)
    total = 0.0
    for idx, chord in enumerate(bar.chords):
        denom = note_type_to_denom(chord.note_type) or default_duration
        is_dotted = chord.dotted
        if idx < len(positions):
            col, _d, _dot = positions[idx]
            if (bar_index, col) in dotted:
                is_dotted = True
        dur = 4.0 / denom
        if is_dotted:
            dur *= 1.5
        total += dur
    return total


def _manual_bar_sum_quarter_beats(
    *,
    piece: Piece,
    bar_index: int,
    bar_width: int,
    durations: dict[tuple[int, int, int], int],
    dotted: set[tuple[int, int]],
) -> float:
    total = 0.0
    last: int | None = None
    last_dot = False
    for col in range(bar_width):
        found = None
        for s_idx in range(piece.strings):
            val = durations.get((bar_index, s_idx, col))
            if val is None:
                continue
            if found is None or val > found:
                found = val
        if found is None:
            continue
        is_dot = (bar_index, col) in dotted
        if found == last and is_dot == last_dot:
            continue
        dur = 4.0 / found
        if is_dot:
            dur *= 1.5
        total += dur
        last = found
        last_dot = is_dot
    return total


def bar_meter_integrity_marker(
    *,
    piece: Piece,
    overrides: dict[tuple[int, int, int], str],
    durations: dict[tuple[int, int, int], int],
    dotted: set[tuple[int, int]],
    cursor_bar: int,
    bar_width: int,
    settings_time: str,
    default_duration: int = 4,
) -> str | None:
    if cursor_bar < 0 or cursor_bar >= len(piece.bars):
        return None
    bar = piece.bars[cursor_bar]
    has_manual = _bar_has_manual_entries(cursor_bar, overrides, durations)
    if not (bar.chords or bar.notes or has_manual):
        return None
    meter = bar.time_sig or settings_time
    parsed = parse_time_signature_value(meter)
    if parsed is None:
        return None
    beats, unit = parsed
    expected = beats * (4.0 / unit)
    if bar.chords:
        total = _chord_bar_sum_quarter_beats(
            piece=piece,
            bar_index=cursor_bar,
            bar_width=bar_width,
            default_duration=default_duration,
            dotted=dotted,
        )
    else:
        total = _manual_bar_sum_quarter_beats(
            piece=piece,
            bar_index=cursor_bar,
            bar_width=bar_width,
            durations=durations,
            dotted=dotted,
        )
    if abs(total - expected) < 0.01:
        return None
    return "M"


def build_status_lines(
    *,
    mode: str,
    cmdline: str,
    searchline: str,
    message: str,
    status_line: str,
    dur_text: str | None,
    integrity_marker: str | None = None,
) -> str:
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
    if mode in ("command", "search"):
        if message and message.startswith(("Matches:", "Options:")):
            return f"{status}  {message}".strip()
        return status
    status_line_text = status_line
    if integrity_marker and status_line_text:
        status_line_text = f"{status_line_text} {integrity_marker}"
    if status_line_text:
        return f"{status_line_text}  {status}".strip()
    return status
