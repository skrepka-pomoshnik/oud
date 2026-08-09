"""Duet-score projection for the legacy terminal renderer."""

from __future__ import annotations

from dataclasses import dataclass

from petrucci.adapters.duet import (
    duet_bar_mapping,
    duet_raw_bar_index,
    duet_staff_labels,
    duet_view_mode,
    is_duet_score_piece,
    split_duet_pair_map,
    split_duet_pair_set,
    split_duet_piece_staff,
    split_duet_span_list,
    split_duet_triplet_map,
    split_duet_triplet_set,
)
from petrucci.core.model import Piece
from petrucci.engraving.layout.map import LayoutBlockPolicy, block_height
from petrucci.rendering.primitives.helpers import safe_addstr
from petrucci.rendering.staff.playback import PlaybackOverlayCache
from petrucci.rendering.system.render import render_systems
from petrucci.terminal.canvas.screen import Screen
from petrucci.terminal.view.model import _next_system_start

Triplet = tuple[int, int, int]
Pair = tuple[int, int]


@dataclass(frozen=True)
class DuetRenderRequest:
    piece: Piece
    width: int
    height: int
    header_row: int
    left_margin: int
    bar_offset: int
    cursor_bar: int
    cursor_string: int
    cursor_col: int
    bar_width: int
    overrides: dict[Triplet, str]
    durations: dict[Triplet, int]
    ornaments: dict[Pair, str]
    annotations: dict[Pair, str]
    highlights: set[Triplet]
    dotted: set[Pair]
    slurs: list[Triplet]
    ties: list[Triplet]
    holds: list[Triplet]
    glisses: list[Triplet] | None
    settings: dict[str, str]
    stave_breaks: set[int]
    playback_bar: int | None
    playback_col: int | None
    playback_markers: list[Pair] | None
    playback_cache: PlaybackOverlayCache | None
    cursor_display_maps: dict[int, list[int]] | None
    include_meta: bool
    show_dur: bool
    show_extras: bool
    show_tuplets: bool
    show_tactus: bool
    hide_redundant: bool
    double_stems: bool
    reverse_strings: bool
    max_chords: int
    bar_gap: int
    barpad: int
    usable_width: int
    default_duration: int
    tuning_labels: list[str]
    basslabels: str
    chord_wrap_limit: int


@dataclass(frozen=True)
class _DuetPayload:
    piece: Piece
    overrides: dict[Triplet, str]
    durations: dict[Triplet, int]
    ornaments: dict[Pair, str]
    annotations: dict[Pair, str]
    highlights: set[Triplet]
    dotted: set[Pair]
    slurs: list[Triplet]
    ties: list[Triplet]
    holds: list[Triplet]
    glisses: list[Triplet]


@dataclass(frozen=True)
class _SystemState:
    header_row: int
    systems: int
    bar_offset: int
    cursor_bar: int
    playback_bar: int | None
    playback_markers: list[Pair]
    playback_cache: PlaybackOverlayCache | None
    cursor_maps: dict[int, list[int]] | None


@dataclass(frozen=True)
class _PairContext:
    duet_settings: dict[str, str]
    logical_breaks: set[int]
    bars_limit: int
    logical_playback: PlaybackOverlayCache


def duet_score_hint(piece: Piece) -> str | None:
    ensemble = (piece.ensemble or "").strip()
    part = (piece.part or "").strip().lower()
    if not ensemble or part != "score":
        return None
    lower = ensemble.lower()
    return "Lute 1 / Lute 2" if "lute 1" in lower and "lute 2" in lower else None


def _system_slots(available: int, height: int, *, allow_partial: bool = True) -> int:
    block_height = max(1, height)
    full_systems, remaining = divmod(max(0, available), block_height)
    if full_systems == 0:
        return 1
    meaningful_preview = allow_partial and remaining >= (block_height + 1) // 2
    return full_systems + int(meaningful_preview)


def _logical_stave_breaks(piece: Piece, stave_breaks: set[int]) -> set[int]:
    return {duet_bar_mapping(raw, piece=piece)[1] for raw in stave_breaks if raw > 0}


def _split_payload(request: DuetRenderRequest, staff_index: int) -> _DuetPayload:
    piece = request.piece
    return _DuetPayload(
        split_duet_piece_staff(piece, staff_index),
        split_duet_triplet_map(request.overrides, staff_index=staff_index, piece=piece),
        split_duet_triplet_map(request.durations, staff_index=staff_index, piece=piece),
        split_duet_pair_map(request.ornaments, staff_index=staff_index, piece=piece),
        split_duet_pair_map(request.annotations, staff_index=staff_index, piece=piece),
        split_duet_triplet_set(request.highlights, staff_index=staff_index, piece=piece),
        split_duet_pair_set(request.dotted, staff_index=staff_index, piece=piece),
        split_duet_span_list(request.slurs, staff_index=staff_index, piece=piece),
        split_duet_span_list(request.ties, staff_index=staff_index, piece=piece),
        split_duet_span_list(request.holds, staff_index=staff_index, piece=piece),
        split_duet_span_list(request.glisses or [], staff_index=staff_index, piece=piece),
    )


def _bars_per_line_limit(request: DuetRenderRequest) -> int:
    limit = max(1, request.usable_width // max(1, request.bar_width + request.bar_gap))
    barsperline = request.settings.get("barsperline", "")
    if barsperline.isdigit() and int(barsperline) > 0:
        limit = int(barsperline)
    maxbars = request.settings.get("maxbars", "")
    if maxbars.isdigit() and int(maxbars) > 0:
        limit = min(limit, int(maxbars))
    return limit


def _logical_cursor(request: DuetRenderRequest, staff_index: int) -> int:
    if request.cursor_bar < 0:
        return -1
    cursor_staff, logical = duet_bar_mapping(request.cursor_bar, piece=request.piece)
    return logical if cursor_staff == staff_index else -1


def _logical_playback(request: DuetRenderRequest) -> int | None:
    if request.playback_bar is None:
        return None
    return duet_bar_mapping(request.playback_bar, piece=request.piece)[1]


def _logical_markers(request: DuetRenderRequest, staff_index: int | None = None) -> list[Pair]:
    markers: list[Pair] = []
    for raw_bar, col in request.playback_markers or []:
        marker_staff, logical = duet_bar_mapping(raw_bar, piece=request.piece)
        if staff_index is None or marker_staff == staff_index:
            markers.append((logical, col))
    return markers


def _merge_cursor_maps(
    request: DuetRenderRequest,
    local: dict[int, list[int]] | None,
    staff_index: int,
) -> None:
    if request.cursor_display_maps is None or local is None:
        return
    for logical_bar, mapping in local.items():
        raw_bar = duet_raw_bar_index(staff_index, logical_bar, piece=request.piece)
        if 0 <= raw_bar < len(request.piece.bars):
            request.cursor_display_maps[raw_bar] = mapping


def _collect_playback(target: PlaybackOverlayCache, local: PlaybackOverlayCache | None) -> None:
    if local is None:
        return
    for key, operations in local.items():
        target.setdefault(key, []).extend(operations)


def _publish_playback(request: DuetRenderRequest, logical: PlaybackOverlayCache) -> None:
    if request.playback_cache is None:
        return
    for (logical_bar, col), operations in logical.items():
        for staff_index in (0, 1):
            raw_bar = duet_raw_bar_index(staff_index, logical_bar, piece=request.piece)
            if 0 <= raw_bar < len(request.piece.bars):
                request.playback_cache[(raw_bar, col)] = list(operations)


def _draw_brace(screen: Screen, *, x: int, top_y: int, bottom_y: int) -> None:
    if bottom_y < top_y:
        return
    for y in range(top_y, bottom_y + 1):
        safe_addstr(screen, y, x, "|")
    safe_addstr(screen, (top_y + bottom_y) // 2, x, "{")


def _render_payload(
    screen: Screen,
    request: DuetRenderRequest,
    payload: _DuetPayload,
    *,
    state: _SystemState,
    duet_settings: dict[str, str],
    logical_breaks: set[int],
    bars_per_line_limit: int,
) -> None:
    render_systems(
        screen,
        piece=payload.piece,
        width=request.width,
        header_row=state.header_row,
        left_margin=request.left_margin,
        systems=state.systems,
        total_strings=payload.piece.strings,
        display_indices=[],
        display_strings=0,
        bar_offset=state.bar_offset,
        cursor_bar=state.cursor_bar,
        cursor_string=request.cursor_string,
        cursor_col=request.cursor_col,
        bar_width=request.bar_width,
        overrides=payload.overrides,
        durations=payload.durations,
        ornaments=payload.ornaments,
        annotations=payload.annotations,
        highlights=payload.highlights,
        dotted=payload.dotted,
        slurs=payload.slurs,
        ties=payload.ties,
        holds=payload.holds,
        glisses=payload.glisses,
        settings=duet_settings,
        stave_breaks=logical_breaks,
        playback_bar=state.playback_bar,
        playback_col=request.playback_col,
        playback_markers=state.playback_markers,
        include_meta=request.include_meta,
        show_dur=request.show_dur,
        show_extras=request.show_extras,
        show_tuplets=request.show_tuplets,
        show_tactus=request.show_tactus,
        hide_redundant=request.hide_redundant,
        double_stems=request.double_stems,
        reverse_strings=request.reverse_strings,
        max_chords=request.max_chords,
        spacing_mode="packed",
        spacing_fill=request.settings.get("justify", "stretch"),
        bar_gap=request.bar_gap,
        barpad=request.barpad,
        usable_width=request.usable_width,
        bars_per_line_limit=bars_per_line_limit,
        default_duration=request.default_duration,
        tuning_labels=request.tuning_labels,
        basslabels=request.basslabels,
        chord_wrap_limit=request.chord_wrap_limit,
        lyric_rows_count=0,
        playback_cache=state.playback_cache,
        cursor_display_maps=state.cursor_maps,
    )


class _DuetRenderer:
    def __init__(self, screen: Screen, request: DuetRenderRequest) -> None:
        self.screen = screen
        self.request = request

    def render(self) -> bool:
        request = self.request
        if not is_duet_score_piece(request.piece):
            return False
        logical_offset = duet_bar_mapping(max(0, request.bar_offset), piece=request.piece)[1]
        mode = duet_view_mode(request.settings)
        if mode == "auto":
            mode = "both"
        selected_staff = {"1": 0, "2": 1}.get(mode)
        labels = duet_staff_labels(request.piece)
        duet_settings = {**request.settings, "layout": "packed", "duetwidthlock": "on"}
        bars_limit = _bars_per_line_limit(request)
        if selected_staff is not None:
            self._render_single(selected_staff, logical_offset, labels, duet_settings, bars_limit)
            return True
        self._render_pair(logical_offset, labels, duet_settings, bars_limit)
        return True

    def _render_single(
        self,
        staff_index: int,
        logical_offset: int,
        labels: tuple[str, str],
        duet_settings: dict[str, str],
        bars_limit: int,
    ) -> None:
        request = self.request
        payload = _split_payload(request, staff_index)
        label_row = request.header_row + 1
        safe_addstr(self.screen, label_row, 0, " " * max(0, request.width - 1))
        safe_addstr(
            self.screen,
            label_row,
            max(0, request.left_margin + 1),
            f"{labels[staff_index]} only"[: max(0, request.width - 1)],
        )
        content_height = block_height(
            LayoutBlockPolicy(
                strings=min(6, payload.piece.strings),
                include_meta=request.include_meta,
                show_dur=request.show_dur,
                show_extras=request.show_extras,
                show_tuplets=request.show_tuplets,
                show_tactus=request.show_tactus,
                double_stems=request.double_stems,
            )
        )
        available = max(0, request.height - 2 - (request.header_row + 2))
        local_playback: PlaybackOverlayCache | None = {} if request.playback_cache is not None else None
        local_maps: dict[int, list[int]] | None = {} if request.cursor_display_maps is not None else None
        state = _SystemState(
            request.header_row + 1,
            _system_slots(available, content_height),
            logical_offset,
            _logical_cursor(request, staff_index),
            _logical_playback(request),
            _logical_markers(request),
            local_playback,
            local_maps,
        )
        logical_breaks = _logical_stave_breaks(request.piece, request.stave_breaks)
        _render_payload(
            self.screen,
            request,
            payload,
            state=state,
            duet_settings=duet_settings,
            logical_breaks=logical_breaks,
            bars_per_line_limit=bars_limit,
        )
        _merge_cursor_maps(request, local_maps, staff_index)
        logical_playback: PlaybackOverlayCache = {}
        _collect_playback(logical_playback, local_playback)
        _publish_playback(request, logical_playback)

    def _render_pair_staff(
        self,
        staff_index: int,
        payload: _DuetPayload,
        header_row: int,
        logical_offset: int,
        context: _PairContext,
    ) -> None:
        request = self.request
        if logical_offset >= len(payload.piece.bars):
            return
        local_playback: PlaybackOverlayCache | None = {} if request.playback_cache is not None else None
        local_maps: dict[int, list[int]] | None = {} if request.cursor_display_maps is not None else None
        state = _SystemState(
            header_row,
            1,
            logical_offset,
            _logical_cursor(request, staff_index),
            _logical_playback(request),
            _logical_markers(request, staff_index),
            local_playback,
            local_maps,
        )
        _render_payload(
            self.screen,
            request,
            payload,
            state=state,
            duet_settings=context.duet_settings,
            logical_breaks=context.logical_breaks,
            bars_per_line_limit=context.bars_limit,
        )
        _merge_cursor_maps(request, local_maps, staff_index)
        _collect_playback(context.logical_playback, local_playback)

    def _render_pair(
        self,
        logical_offset: int,
        labels: tuple[str, str],
        duet_settings: dict[str, str],
        bars_limit: int,
    ) -> None:
        request = self.request
        payloads = (_split_payload(request, 0), _split_payload(request, 1))
        total_strings = request.piece.strings
        content_height = block_height(
            LayoutBlockPolicy(
                strings=min(6, total_strings),
                include_meta=request.include_meta,
                show_dur=request.show_dur,
                show_extras=request.show_extras,
                show_tuplets=request.show_tuplets,
                show_tactus=request.show_tactus,
                double_stems=request.double_stems,
            )
        )
        block = content_height + 1
        pair_height = block * 2
        base_header = request.header_row + 1
        available = max(0, request.height - 2 - base_header)
        systems = _system_slots(available, pair_height, allow_partial=False)
        current = max(0, logical_offset)
        total = max(len(payload.piece.bars) for payload in payloads)
        logical_breaks = _logical_stave_breaks(request.piece, request.stave_breaks)
        logical_bars = max((payload.piece.bars for payload in payloads), key=len)
        logical_playback: PlaybackOverlayCache = {}
        context = _PairContext(duet_settings, logical_breaks, bars_limit, logical_playback)
        for system_index in range(systems):
            if current >= total:
                break
            top_header = base_header + system_index * pair_height
            bottom_header = top_header + block
            system_end = _next_system_start(logical_bars, current, bars_limit, logical_breaks)
            for staff_index, payload, header in (
                (0, payloads[0], top_header),
                (1, payloads[1], bottom_header),
            ):
                self._render_pair_staff(
                    staff_index,
                    payload,
                    header,
                    current,
                    context,
                )
            label_x = max(0, request.left_margin + 1)
            label_width = max(0, request.width - label_x - 1)
            safe_addstr(self.screen, top_header, label_x, labels[0][:label_width])
            safe_addstr(self.screen, bottom_header, label_x, labels[1][:label_width])
            _draw_brace(
                self.screen,
                x=max(0, request.left_margin - 1),
                top_y=top_header + 1,
                bottom_y=bottom_header + 1 + content_height - 1,
            )
            current = max(current + 1, system_end)
        _publish_playback(request, logical_playback)


def render_duet_score_view(screen: Screen, request: DuetRenderRequest) -> bool:
    return _DuetRenderer(screen, request).render()


__all__ = ["DuetRenderRequest", "duet_score_hint", "render_duet_score_view"]
