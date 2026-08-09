from __future__ import annotations

from petrucci.framebuffer import _split_display_clusters
from petrucci.screen import A_BOLD, A_REVERSE
from petrucci.view_model import _scale_col
from petrucci.vocal_line import infer_vocal_events

PlaybackOverlayCache = dict[tuple[int, int], list[tuple[int, int, str, int]]]


def _nearest_note_cell_idx(row_text: str, target_idx: int) -> int | None:
    clusters = _split_display_clusters(row_text)
    if not clusters:
        return None
    max_idx = len(clusters) - 1
    target_idx = max(0, min(max_idx, target_idx))
    for distance in range(5):
        right = target_idx + distance
        if 0 <= right <= max_idx and clusters[right] not in {" ", "-", "|"}:
            return right
        if distance == 0:
            continue
        left = target_idx - distance
        if 0 <= left <= max_idx and clusters[left] not in {" ", "-", "|"}:
            return left
    return None


def _playback_note_strings(bar, playback_col: int) -> set[int]:
    if not bar.chords or not (0 <= playback_col < len(bar.chords)):
        return set()
    chord = bar.chords[playback_col]
    return {note.string - 1 for note in chord.notes}


def _playback_scaled_col_for_chords(
    *,
    playback_col: int,
    bar_width: int,
    grid_width: int,
    content_width: int,
    positions: list[tuple[int, int, bool]],
    src_to_dest: dict[int, int],
) -> int:
    if not positions:
        return 0
    if 0 <= playback_col < len(positions):
        raw_col = positions[playback_col][0]
    else:
        raw_col = _scale_col(playback_col, bar_width, grid_width)
    col = src_to_dest.get(raw_col, _scale_col(raw_col, grid_width, content_width))
    return max(0, min(content_width - 1, col))


def _playback_in_range(bar, playback_col: int, bar_width: int) -> bool:
    if playback_col < 0:
        return False
    if bar.chords:
        return playback_col < len(bar.chords)
    return playback_col < bar_width


def _melody_playback_col(
    *,
    bar,
    playback_col: int,
    onset_cols: list[int],
    tuning_pitches: list[int],
) -> int | None:
    if playback_col < 0 or not onset_cols:
        return None
    vocal_events = infer_vocal_events(bar, tuning_pitches=tuning_pitches)
    for event in vocal_events:
        if event.chord_index != playback_col:
            continue
        if 0 <= event.onset_index < len(onset_cols):
            return onset_cols[event.onset_index]
    chord_count = len(bar.chords)
    if chord_count > 1 and len(onset_cols) > 1:
        mapped = round(playback_col * (len(onset_cols) - 1) / (chord_count - 1))
        mapped = max(0, min(len(onset_cols) - 1, mapped))
        return onset_cols[mapped]
    if 0 <= playback_col < len(onset_cols):
        return onset_cols[playback_col]
    return onset_cols[-1]


def _tab_playback_highlight_ops(  # noqa: C901
    *,
    bar,
    playback_col: int,
    bar_width: int,
    grid_width: int,
    positions: list[tuple[int, int, bool]],
    src_to_dest: dict[int, int],
    draw_pad: int,
    display_width: int,
    row_start: int,
    rows: dict[str, int | None],
    system_display_strings: int,
    system_visual_indices: list[int],
    rendered_staff_rows: list[str],
    bar_x: int,
) -> tuple[list[tuple[int, int, str, int]], int]:
    content_width = max(1, display_width - draw_pad * 2)
    if bar.chords:
        scaled_play_col = _playback_scaled_col_for_chords(
            playback_col=playback_col,
            bar_width=bar_width,
            grid_width=grid_width,
            content_width=content_width,
            positions=positions,
            src_to_dest=src_to_dest,
        )
    else:
        scaled_play_col = _scale_col(playback_col, bar_width, content_width)
    note_strings = _playback_note_strings(bar, playback_col)
    playback_cell_idx = draw_pad + scaled_play_col
    ops: list[tuple[int, int, str, int]] = []

    for display_idx in range(system_display_strings):
        actual = system_visual_indices[display_idx]
        y = row_start + (rows["staff"] or 0) + display_idx
        row_text = rendered_staff_rows[display_idx] if display_idx < len(rendered_staff_rows) else ""
        row_clusters = _split_display_clusters(row_text)
        if not (0 <= playback_cell_idx < len(row_clusters)):
            continue
        target_idx = playback_cell_idx
        if bar.chords:
            if actual not in note_strings:
                continue
            nearest = _nearest_note_cell_idx(row_text, playback_cell_idx)
            if nearest is None:
                continue
            target_idx = nearest
        ch = row_clusters[target_idx]
        if ch in {" ", "-", "|"}:
            continue
        ops.append((y, bar_x + target_idx, ch, A_REVERSE))
    return ops, scaled_play_col


def _playback_marker_position(
    *,
    rows: dict[str, int | None],
    row_start: int,
    bar_x: int,
    draw_pad: int,
    scaled_play_col: int,
    melody_row_base: int | None,
) -> tuple[int, int]:
    marker_row = rows.get("meta")
    if marker_row is None:
        marker_row = rows.get("flag") or 0
    marker_y = row_start + marker_row
    marker_x = bar_x + draw_pad + scaled_play_col
    if melody_row_base is not None and marker_y >= melody_row_base:
        return melody_row_base, max(0, bar_x - 2)
    return marker_y, marker_x


def _melody_marker_op(
    *,
    melody_col: int,
    melody_row_base: int,
    melody_x: int,
    rendered_melody_rows: list[str] | None,
    fallback: tuple[int, int],
    tab_marker: tuple[int, int],
) -> tuple[int, int, str, int] | None:
    for relative_y, melody_row in enumerate(rendered_melody_rows or []):
        if 0 <= melody_col < len(melody_row) and melody_row[melody_col] == " ":
            return melody_row_base + relative_y, melody_x, "v", A_BOLD
    if fallback != tab_marker:
        return *fallback, "v", A_BOLD
    return None


def _playback_marker_ops(
    *,
    bar,
    playback_col: int,
    scaled_play_col: int,
    row_start: int,
    rows: dict[str, int | None],
    draw_pad: int,
    bar_x: int,
    display_width: int,
    tuning_pitches: list[int],
    melody_row_base: int | None,
    vocal_onset_cols: list[int],
    rendered_melody_rows: list[str] | None,
) -> list[tuple[int, int, str, int]]:
    marker_y, marker_x = _playback_marker_position(
        rows=rows,
        row_start=row_start,
        bar_x=bar_x,
        draw_pad=draw_pad,
        scaled_play_col=scaled_play_col,
        melody_row_base=melody_row_base,
    )
    ops: list[tuple[int, int, str, int]] = [(marker_y, marker_x, "^", A_BOLD)]
    if melody_row_base is None:
        return ops
    melody_col = _melody_playback_col(
        bar=bar,
        playback_col=playback_col,
        onset_cols=vocal_onset_cols,
        tuning_pitches=tuning_pitches,
    )
    if melody_col is None:
        return ops
    melody_x = bar_x + max(0, min(display_width - 1, melody_col))
    fallback = (melody_row_base, max(0, bar_x - 2))
    melody_op = _melody_marker_op(
        melody_col=melody_col,
        melody_row_base=melody_row_base,
        melody_x=melody_x,
        rendered_melody_rows=rendered_melody_rows,
        fallback=fallback,
        tab_marker=(marker_y, marker_x),
    )
    if melody_op is not None:
        ops.append(melody_op)
    return ops


def _playback_overlay_ops_for_bar(
    *,
    bar,
    playback_col: int,
    bar_width: int,
    grid_width: int,
    positions: list[tuple[int, int, bool]],
    src_to_dest: dict[int, int],
    draw_pad: int,
    display_width: int,
    row_start: int,
    rows: dict[str, int | None],
    system_display_strings: int,
    system_visual_indices: list[int],
    rendered_staff_rows: list[str],
    bar_x: int,
    tuning_pitches: list[int],
    melody_row_base: int | None,
    vocal_onset_cols: list[int],
    rendered_melody_rows: list[str] | None,
) -> list[tuple[int, int, str, int]]:
    if not _playback_in_range(bar, playback_col, bar_width):
        return []
    note_ops, scaled_play_col = _tab_playback_highlight_ops(
        bar=bar,
        playback_col=playback_col,
        bar_width=bar_width,
        grid_width=grid_width,
        positions=positions,
        src_to_dest=src_to_dest,
        draw_pad=draw_pad,
        display_width=display_width,
        row_start=row_start,
        rows=rows,
        system_display_strings=system_display_strings,
        system_visual_indices=system_visual_indices,
        rendered_staff_rows=rendered_staff_rows,
        bar_x=bar_x,
    )
    return note_ops + _playback_marker_ops(
        bar=bar,
        playback_col=playback_col,
        scaled_play_col=scaled_play_col,
        row_start=row_start,
        rows=rows,
        draw_pad=draw_pad,
        bar_x=bar_x,
        display_width=display_width,
        tuning_pitches=tuning_pitches,
        melody_row_base=melody_row_base,
        vocal_onset_cols=vocal_onset_cols,
        rendered_melody_rows=rendered_melody_rows,
    )
