from __future__ import annotations

from petrucci.core.model import Piece
from petrucci.core.music.time import parse_time_signature_value
from petrucci.rendering.primitives.utils import note_type_to_denom
from petrucci.terminal.canvas.screen import A_BOLD, A_DIM, A_REVERSE, A_UNDERLINE
from petrucci.terminal.view.model import chord_positions


def _manual_duration_at(
    durations: dict[tuple[int, int, int], int],
    *,
    bar: int,
    col: int,
    preferred_string: int,
    strings: int,
) -> int | None:
    preferred = durations.get((bar, preferred_string, col))
    if preferred is not None:
        return preferred
    return next((durations[(bar, string, col)] for string in range(strings) if (bar, string, col) in durations), None)


def _chord_duration_at(piece: Piece, *, bar: int, col: int, width: int, default_duration: int) -> int | None:
    if not 0 <= bar < len(piece.bars) or not piece.bars[bar].chords:
        return None
    return next(
        (
            denominator
            for position, denominator, _dot in chord_positions(piece.bars[bar], width, default_duration)
            if position == col
        ),
        None,
    )


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
    dur_text: str | int | None = _manual_duration_at(
        durations,
        bar=cursor_bar,
        col=cursor_col,
        preferred_string=actual_cursor_string,
        strings=piece.strings,
    )
    if dur_text is not None and (cursor_bar, cursor_col) in dotted:
        dur_text = f"{dur_text}."
    if dur_text is None:
        dur_text = _chord_duration_at(
            piece,
            bar=cursor_bar,
            col=cursor_col,
            width=bar_width,
            default_duration=default_duration,
        )
    return str(dur_text) if dur_text is not None else None


def _bar_has_manual_entries(
    cursor_bar: int,
    overrides: dict[tuple[int, int, int], str],
    durations: dict[tuple[int, int, int], int],
) -> bool:
    return any(b == cursor_bar for (b, _s, _c) in overrides) or any(b == cursor_bar for (b, _s, _c) in durations)


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


def _manual_duration_at_column(
    durations: dict[tuple[int, int, int], int],
    *,
    bar_index: int,
    strings: int,
    col: int,
) -> int | None:
    values = (
        durations[(bar_index, string_index, col)]
        for string_index in range(strings)
        if (bar_index, string_index, col) in durations
    )
    return max(values, default=None)


def _quarter_beats(denominator: int, *, dotted: bool) -> float:
    beats = 4.0 / denominator
    return beats * 1.5 if dotted else beats


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
        found = _manual_duration_at_column(
            durations,
            bar_index=bar_index,
            strings=piece.strings,
            col=col,
        )
        if found is None:
            continue
        is_dot = (bar_index, col) in dotted
        if found == last and is_dot == last_dot:
            continue
        total += _quarter_beats(found, dotted=is_dot)
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
    duration_tolerance = 0.01
    if abs(total - expected) < duration_tolerance:
        return None
    return "M"


def _mode_status(mode: str, cmdline: str, searchline: str) -> str:
    if mode == "command":
        return f":{cmdline}"
    if mode == "search":
        return f"/{searchline}"
    if mode == "help":
        return "help  j/k scroll  q close"
    return mode


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
    status = _mode_status(mode, cmdline, searchline)
    if dur_text and not message and mode not in ("command", "search"):
        status = f"{status}  len:{dur_text}"
    if message and mode not in ("command", "search"):
        status = f"{status}  {message}"
    if mode in ("command", "search"):
        suffix = f"  {message}" if message else ""
        return f"{status}{suffix}"
    status_line_text = status_line
    if integrity_marker and status_line_text:
        status_line_text = f"{status_line_text} {integrity_marker}"
    if status_line_text:
        return f"{status_line_text}  {status}".strip()
    return status


def status_attr_for_message(level: str) -> int:
    return {
        "success": A_REVERSE | A_BOLD,
        "warning": A_REVERSE | A_UNDERLINE,
        "error": A_REVERSE | A_BOLD | A_UNDERLINE,
        "confirm": A_REVERSE | A_DIM,
    }.get(level, A_REVERSE)
