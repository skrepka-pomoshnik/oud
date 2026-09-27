from __future__ import annotations

import copy
import subprocess
import time
from dataclasses import replace
from pathlib import Path
from typing import TypeVar

from oud.editor.core.state import EditorState
from oud.editor.services.media.playback import (
    prime_playback_animation,
    reset_playback_animation,
    start_playback_clock,
)
from oud.exports.midi import build_playback_timeline, export_midi, play_midi
from oud.services.playback.timeline import PlaybackCursor
from petrucci.core.model import Piece

T = TypeVar("T")

# Bounded wait for a terminated player before it is killed and reaped.
PLAYER_STOP_TIMEOUT_S = 1.0


def midi_output_path(state: EditorState) -> str:
    base = "out"
    if state.path:
        base = str(Path(state.path).with_suffix(""))
    return base + ".mid"


def stop_midi(state: EditorState) -> None:
    if state.midi_proc is None:
        reset_playback_animation(state)
        return
    proc = state.midi_proc
    state.midi_proc = None
    reset_playback_animation(state)
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=PLAYER_STOP_TIMEOUT_S)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=PLAYER_STOP_TIMEOUT_S)
    state.message = "MIDI stopped"


def start_midi(
    state: EditorState,
    *,
    start_bar: int | None = None,
    path: str | None = None,
    bpm: int | None = None,
    end_bar: int | None = None,
    loop_count: int = 1,
) -> None:
    if state.midi_proc is not None and state.midi_proc.poll() is None:
        stop_midi(state)
    path = path or midi_output_path(state)
    start_bar = state.cursor_bar if start_bar is None else start_bar
    if bpm is None:
        try:
            bpm = int(state.settings.get("tempo", "90") or "90")
        except ValueError:
            bpm = 90
    (
        export_piece,
        export_overrides,
        export_durations,
        export_dotted,
        export_ornaments,
    ) = _playback_export_state(
        state,
        start_bar=start_bar,
        end_bar=end_bar,
        loop_count=loop_count,
    )
    state.message = export_midi(
        path,
        export_piece,
        export_overrides,
        export_durations,
        state.bar_width,
        settings=state.settings,
        bpm=bpm,
        start_bar=0,
        dotted=export_dotted,
        ornaments=export_ornaments,
    )
    timeline = build_playback_timeline(
        export_piece,
        export_overrides,
        export_durations,
        state.bar_width,
        settings=state.settings,
        bpm=bpm,
        start_bar=0,
        dotted=export_dotted,
    )
    effective_end = end_bar if end_bar is not None else max(start_bar, len(state.piece.bars) - 1)
    timeline = _remap_playback_timeline(
        timeline,
        start_bar=start_bar,
        span=max(1, effective_end - start_bar + 1),
    )
    prime_playback_animation(state, timeline)
    soundfont = state.settings.get("soundfont", "") or None
    launched_at = time.monotonic()
    state.message, state.midi_proc = play_midi(path, soundfont=soundfont)
    if state.midi_proc is not None:
        start_playback_clock(state, launched_at)


def _playback_export_state(
    state: EditorState,
    *,
    start_bar: int,
    end_bar: int | None,
    loop_count: int,
) -> tuple[
    Piece,
    dict[tuple[int, int, int], str],
    dict[tuple[int, int, int], int],
    set[tuple[int, int]],
    dict[tuple[int, int], str],
]:
    source_piece = state.piece
    total = len(source_piece.bars)
    if total == 0:
        return source_piece, state.overrides, state.durations, state.dotted, state.ornaments
    start = max(0, min(start_bar, total - 1))
    # No explicit end means "play to the end of the piece", not a single bar.
    end = (total - 1) if end_bar is None else max(start, min(end_bar, total - 1))
    loops = max(1, loop_count)
    if start == 0 and end == total - 1 and loops == 1:
        return source_piece, state.overrides, state.durations, state.dotted, state.ornaments

    source_indices = list(range(start, end + 1))
    repeated_indices = source_indices * loops
    piece = copy.deepcopy(source_piece)
    piece.bars = [copy.deepcopy(source_piece.bars[idx]) for idx in repeated_indices]
    _slice_imported_score(piece, repeated_indices)
    index_map = {source: pos for pos, source in enumerate(source_indices)}
    span = len(source_indices)

    overrides = _remap_bar_string_col_map(state.overrides, index_map, loops=loops, span=span)
    durations = _remap_bar_string_col_map(state.durations, index_map, loops=loops, span=span)
    dotted = _remap_bar_col_set(state.dotted, index_map, loops=loops, span=span)
    ornaments = _remap_bar_col_map(state.ornaments, index_map, loops=loops, span=span)
    return piece, overrides, durations, dotted, ornaments


def _slice_imported_score(piece: Piece, source_indices: list[int]) -> None:
    imported = piece.imported_score
    if imported is None:
        return
    staffs = []
    for staff in imported.staffs:
        bars_by_source = {bar.source_bar_index: bar for bar in staff.bars}
        bars = [
            replace(copy.deepcopy(bars_by_source[source]), source_bar_index=target)
            for target, source in enumerate(source_indices)
            if source in bars_by_source
        ]
        staffs.append(replace(copy.deepcopy(staff), bars=bars))
    records_by_source: dict[int, list] = {}
    for record in imported.source_records:
        records_by_source.setdefault(record.source_bar_index, []).append(record)
    records = [
        replace(copy.deepcopy(record), source_bar_index=target)
        for target, source in enumerate(source_indices)
        for record in records_by_source.get(source, ())
    ]
    piece.imported_score = replace(copy.deepcopy(imported), staffs=staffs, source_records=records)


def _remap_bar_string_col_map(
    source: dict[tuple[int, int, int], T],
    index_map: dict[int, int],
    *,
    loops: int,
    span: int,
) -> dict[tuple[int, int, int], T]:
    out: dict[tuple[int, int, int], T] = {}
    for loop_idx in range(loops):
        offset = loop_idx * span
        for (bar, string, col), value in source.items():
            if bar in index_map:
                out[(offset + index_map[bar], string, col)] = value
    return out


def _remap_bar_col_set(
    source: set[tuple[int, int]],
    index_map: dict[int, int],
    *,
    loops: int,
    span: int,
) -> set[tuple[int, int]]:
    out: set[tuple[int, int]] = set()
    for loop_idx in range(loops):
        offset = loop_idx * span
        for bar, col in source:
            if bar in index_map:
                out.add((offset + index_map[bar], col))
    return out


def _remap_bar_col_map(
    source: dict[tuple[int, int], T],
    index_map: dict[int, int],
    *,
    loops: int,
    span: int,
) -> dict[tuple[int, int], T]:
    out: dict[tuple[int, int], T] = {}
    for loop_idx in range(loops):
        offset = loop_idx * span
        for (bar, col), value in source.items():
            if bar in index_map:
                out[(offset + index_map[bar], col)] = value
    return out


def _remap_playback_timeline(
    timeline: list[PlaybackCursor],
    *,
    start_bar: int,
    span: int,
) -> list[PlaybackCursor]:
    if span <= 0:
        return timeline
    return [
        PlaybackCursor(
            start=cursor.start,
            end=cursor.end,
            bar=start_bar + (cursor.bar % span),
            col=cursor.col,
            staff=cursor.staff,
            voice=cursor.voice,
            verse=cursor.verse,
        )
        for cursor in timeline
    ]


def pause_midi(state: EditorState) -> None:
    proc = state.midi_proc
    if proc is None or proc.poll() is not None:
        state.midi_proc = None
        state.message = "MIDI not playing"
        return
    if state.playback.bar is not None:
        state.cursor_bar = max(0, state.playback.bar)
    if state.playback.col is not None:
        state.cursor_col = max(0, state.playback.col)
    state.clamp()
    state.midi_proc = None
    reset_playback_animation(state)
    if proc.poll() is None:
        proc.terminate()
    state.message = "MIDI paused"
