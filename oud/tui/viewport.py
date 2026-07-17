from __future__ import annotations

from oud.editor.controller_utils import string_index
from oud.editor.layout import bars_per_line, dynamic_system_starts, system_index, system_start_index
from oud.editor.state import EditorState
from oud.editor.visual_cursor_map import (
    system_display_indices_for_bar as _system_display_indices_for_bar,
)
from oud.petrucci.duet_score import (
    duet_bar_mapping,
    duet_logical_bar_count,
    duet_raw_bar_index,
    is_duet_score_piece,
)
from oud.petrucci.layout_map import block_height as _block_height
from oud.petrucci.render import (
    _piece_has_lyrics,
    _piece_has_melody_grid,
    _piece_lyric_row_count,
)
from oud.petrucci.render_vocal import melody_row_count


def rows_per_screen(state: EditorState, height: int) -> int:
    # Mirror render_piece's block-height inputs exactly; any drift makes the
    # viewport disagree with the renderer about how many systems fit.
    include_meta = True
    show_dur = state.settings.get("showdur", "off") == "on"
    show_extras = state.settings.get("showspans", "off") == "on"
    show_tactus = state.settings.get("showtactus", "off") == "on"
    show_tuplets = state.settings.get("showtuplets", "off") == "on"
    # Render always reserves the second tablature stem row.
    double_stems = True
    show_melody = state.settings.get("showmelody", "on") == "on" and _piece_has_melody_grid(
        state.piece,
    )
    melody_rows_count = melody_row_count() if show_melody else 0
    show_lyrics = state.settings.get("showlyrics", "on") == "on" and _piece_has_lyrics(
        state.piece,
    )
    lyric_rows_count = _piece_lyric_row_count(state.piece, max_rows=99) if show_lyrics else 0
    total_strings = state.piece.strings
    base_strings = min(6, total_strings)
    display_strings = base_strings
    block_h = _block_height(
        include_meta,
        display_strings,
        show_dur,
        show_extras,
        show_tuplets,
        show_tactus,
        double_stems,
        show_melody=show_melody,
        melody_rows_count=melody_rows_count,
        show_lyrics=show_lyrics,
        lyric_rows_count=lyric_rows_count,
        vocal_pos=state.settings.get("vocalpos", "bottom"),
    )
    available = max(0, height - 2 - 1)
    return max(1, available // block_h)


def _duet_viewport_row_mapping(state: EditorState, width: int, height: int):
    per_line = bars_per_line(state, width)
    rows = rows_per_screen(state, height)
    logical_bars = duet_logical_bar_count(state.piece)
    logical_breaks = sorted(
        {
            logical
            for raw in state.stave_breaks
            if raw > 0
            for _staff, logical in [duet_bar_mapping(raw, piece=state.piece)]
        },
    )
    starts = [0]
    idx = 0
    while idx < logical_bars:
        next_break = next((b for b in logical_breaks if b > idx), logical_bars)
        limit = min(next_break, idx + per_line)
        if limit >= logical_bars:
            break
        starts.append(limit)
        idx = limit

    def row_for_bar(bar_index: int) -> int:
        _staff, logical = duet_bar_mapping(max(0, bar_index), piece=state.piece)
        for idx, _start in enumerate(starts):
            if idx + 1 < len(starts) and logical >= starts[idx + 1]:
                continue
            return idx
        return max(0, len(starts) - 1)

    def start_for_row(row_index: int) -> int:
        logical_start = 0
        if row_index <= 0:
            logical_start = starts[0] if starts else 0
        elif row_index >= len(starts):
            logical_start = starts[-1] if starts else 0
        else:
            logical_start = starts[row_index]
        return duet_raw_bar_index(0, logical_start, piece=state.piece)

    return rows, row_for_bar, start_for_row


def _viewport_row_mapping(state: EditorState, width: int, height: int):
    if is_duet_score_piece(state.piece):
        return _duet_viewport_row_mapping(state, width, height)

    per_line = bars_per_line(state, width)
    rows = rows_per_screen(state, height)
    if state.settings.get("layout", "packed") == "auto":
        starts = dynamic_system_starts(state, width)

        def row_for_bar(bar_index: int) -> int:
            row = 0
            for idx, start in enumerate(starts):
                next_start = starts[idx + 1] if idx + 1 < len(starts) else len(state.piece.bars)
                if start <= bar_index < next_start:
                    row = idx
                    break
            return row

        def start_for_row(row_index: int) -> int:
            if row_index <= 0:
                return starts[0] if starts else 0
            if row_index >= len(starts):
                return starts[-1] if starts else 0
            return starts[row_index]
    else:
        row_for_bar = lambda bar_index: system_index(state, bar_index, per_line)  # noqa: E731
        start_for_row = lambda row_index: system_start_index(state, row_index, per_line)  # noqa: E731
    return rows, row_for_bar, start_for_row


def _playback_target_bar(state: EditorState) -> int | None:
    if state.settings.get("playbackscroll", "on") != "on":
        return None
    if state.playback_bar is None:
        return None
    if state.playback.markers:
        if is_duet_score_piece(state.piece):
            logical = min(
                duet_bar_mapping(marker_bar, piece=state.piece)[1] for marker_bar, _marker_col in state.playback.markers
            )
            return duet_raw_bar_index(0, logical, piece=state.piece)
        return min(marker_bar for marker_bar, _marker_col in state.playback.markers)
    return max(0, state.playback_bar)


def _playback_is_between_events(state: EditorState) -> bool:
    return bool(
        state.settings.get("playbackscroll", "on") == "on"
        and state.midi_proc is not None
        and state.playback.started_at is not None
        and state.playback.timeline
        and state.playback_bar is None
    )


def _viewport_target_bar(state: EditorState) -> int | None:
    playback_target = _playback_target_bar(state)
    if playback_target is not None:
        return playback_target
    if _playback_is_between_events(state):
        return None
    return state.cursor_bar


def scroll_viewport_page(state: EditorState, width: int, height: int, delta_pages: int) -> None:
    rows, row_for_bar, start_for_row = _viewport_row_mapping(state, width, height)
    current_row = row_for_bar(state.bar_offset)
    target_row = max(0, current_row + delta_pages * max(1, rows))
    state.bar_offset = start_for_row(target_row)
    state.viewport_scroll_hold_ticks = 1


def ensure_cursor_visible(state: EditorState, width: int, height: int) -> None:
    hold = int(getattr(state, "viewport_scroll_hold_ticks", 0))
    if hold > 0:
        state.viewport_scroll_hold_ticks = hold - 1
        return
    rows, _row_for_bar, _start_for_row = _viewport_row_mapping(state, width, height)
    target_bar = _viewport_target_bar(state)
    if target_bar is None:
        # Keep the current score position through rests between playback events.
        return
    if is_duet_score_piece(state.piece):
        _staff, logical = duet_bar_mapping(target_bar, piece=state.piece)
        target_bar = duet_raw_bar_index(0, logical, piece=state.piece)
    cursor_row = _row_for_bar(target_bar)
    first_row = _row_for_bar(state.bar_offset)
    scroll_mode = state.settings.get("scrollmode", "smooth")

    def _page_start_row(row: int) -> int:
        if rows <= 1:
            return row
        return max(0, (row // rows) * rows)

    if cursor_row < first_row:
        target_row = cursor_row if scroll_mode != "page" else _page_start_row(cursor_row)
        state.bar_offset = _start_for_row(target_row)
    if cursor_row >= first_row + rows:
        target_row = _page_start_row(cursor_row) if scroll_mode == "page" else cursor_row - rows + 1
        state.bar_offset = _start_for_row(target_row)

    # Clamp cursor to rows that are actually visible in the current rendered system.
    # Auto layout hides unused bass rows per system, so a globally valid cursor_string
    # can become invisible after J/K jumps.
    reverse_strings = state.settings.get("viewinvert", "off") == "on" or (
        state.settings.get("style") == "italian" and state.settings.get("italianorient", "normal") == "reverse"
    )
    display_indices = _system_display_indices_for_bar(state, state.cursor_bar)
    if not display_indices:
        return
    actual = string_index(state, state.cursor_string)
    visual_rows = list(reversed(display_indices)) if reverse_strings else display_indices
    if actual in visual_rows:
        state.cursor_string = visual_rows.index(actual)
    else:
        state.cursor_string = max(0, min(state.cursor_string, len(visual_rows) - 1))
