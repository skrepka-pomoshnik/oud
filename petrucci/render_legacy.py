"""Legacy tablature rendering behind a typed request boundary."""

from __future__ import annotations

from dataclasses import dataclass

from petrucci.duet_score import is_duet_score_piece
from petrucci.layout_map import LayoutBlockPolicy, block_height
from petrucci.model import Piece
from petrucci.render_duet_view import (
    DuetRenderRequest,
    duet_score_hint,
    render_duet_score_view,
)
from petrucci.render_helpers import bass_strings_used, clean_text, render_help, safe_addstr
from petrucci.render_playback import PlaybackOverlayCache
from petrucci.render_status import bar_meter_integrity_marker, build_status_lines, resolve_duration_text
from petrucci.render_system import render_systems
from petrucci.render_vocal import melody_row_count
from petrucci.screen import Screen
from petrucci.tab_style import resolve_tab_style_policy
from petrucci.tuning_utils import default_bass_strings, parse_bass_strings, tuning_count
from petrucci.view_model import _tuning_labels

Triplet = tuple[int, int, int]
Pair = tuple[int, int]


@dataclass(frozen=True)
class LegacyRenderRequest:
    piece: Piece
    width: int
    height: int
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
    mode: str
    cmdline: str
    message: str
    status_line: str
    searchline: str
    settings: dict[str, str]
    stave_breaks: set[int]
    help_offset: int
    playback_bar: int | None
    playback_col: int | None
    playback_cache: PlaybackOverlayCache | None
    playback_markers: list[Pair] | None
    cursor_display_maps: dict[int, list[int]] | None
    status_attr: int


@dataclass(frozen=True)
class _WidthPlan:
    max_width: int
    usable_width: int
    bar_gap: int
    barpad: int


@dataclass(frozen=True)
class _DisplayPlan:
    show_dur: bool
    show_extras: bool
    show_tuplets: bool
    show_tactus: bool
    vocal_pos: str
    show_melody: bool
    melody_rows: int
    show_lyrics: bool
    lyric_rows: int
    hide_redundant: bool
    reverse_strings: bool
    base_strings: int
    display_indices: list[int]
    tuning_labels: list[str]
    basslabels: str
    minimum_height: int


@dataclass(frozen=True)
class _LimitPlan:
    systems: int
    max_chords: int
    chord_wrap_limit: int
    bars_per_line: int


def _piece_has_lyrics(piece: Piece) -> bool:
    for bar in piece.bars:
        if any(line.strip() for line in bar.lyrics):
            return True
        if any((event.text or "").strip() for row in bar.lyric_event_rows for event in row):
            return True
    return False


def _piece_has_melody_grid(piece: Piece) -> bool:
    for bar in piece.bars:
        if (bar.melody_grid or "").strip():
            return True
        if any((event.text or "").strip() for event in bar.melody_events):
            return True
        if any(line.strip() for line in bar.lyrics):
            return True
        if any((event.text or "").strip() for row in bar.lyric_event_rows for event in row):
            return True
    return False


def _piece_lyric_row_count(piece: Piece, *, max_rows: int = 99) -> int:
    count = 0
    for bar in piece.bars:
        rows = sum(1 for row in bar.lyric_event_rows if any((event.text or "").strip() for event in row))
        if rows == 0:
            rows = sum(bool(line.strip()) for line in bar.lyrics)
        count = max(count, min(max_rows, rows))
        if count >= max_rows:
            return max_rows
    return count


def _render_header(screen: Screen, width: int, piece: Piece) -> None:
    title = clean_text(piece.title or "Untitled")
    right = clean_text(piece.composer or "")
    if width <= 0:
        return
    if right:
        right = right[:width]
        right_x = max(0, width - len(right))
        title_max = max(0, right_x - 1)
        if title_max > 0:
            centered = title[:title_max]
            safe_addstr(screen, 0, max(0, (title_max - len(centered)) // 2), centered)
        safe_addstr(screen, 0, right_x, right)
        return
    centered = title[:width]
    safe_addstr(screen, 0, max(0, (width - len(centered)) // 2), centered)


def _system_slots(available: int, height: int) -> int:
    block_height = max(1, height)
    full_systems, remaining = divmod(max(0, available), block_height)
    if full_systems == 0:
        return 1
    return full_systems + int(remaining >= (block_height + 1) // 2)


def _width_plan(width: int, settings: dict[str, str]) -> _WidthPlan:
    left_margin = 3
    right_padding = 1
    spacing_mode = settings.get("layout", "packed")
    bargap = settings.get("bargap", "")
    bar_gap = max(0, int(bargap)) if bargap.isdigit() else 1 if spacing_mode in {"packed", "auto"} else 3
    barpad_text = settings.get("barpad", "1")
    barpad = max(0, int(barpad_text)) if barpad_text.isdigit() else 1
    max_width = width
    usable_width = max(0, max_width - left_margin - right_padding)
    linelen = settings.get("linelen", "")
    if linelen.isdigit() and int(linelen) > 0:
        max_width = min(max_width, int(linelen))
        usable_width = max(0, max_width - left_margin - right_padding)
    return _WidthPlan(max_width, usable_width, bar_gap, barpad)


def _display_plan(request: LegacyRenderRequest, tuning_text: str) -> _DisplayPlan:
    piece = request.piece
    settings = request.settings
    policy = resolve_tab_style_policy(settings)
    show_dur = settings.get("showdur", "off") == "on"
    show_extras = settings.get("showspans", "off") == "on"
    show_tuplets = settings.get("showtuplets", "off") == "on"
    show_tactus = settings.get("showtactus", "off") == "on"
    vocal_pos = settings.get("vocalpos", "bottom")
    show_melody = settings.get("showmelody", "on") == "on" and _piece_has_melody_grid(piece)
    melody_rows = melody_row_count() if show_melody else 0
    show_lyrics = settings.get("showlyrics", "on") == "on" and _piece_has_lyrics(piece)
    lyric_rows = _piece_lyric_row_count(piece) if show_lyrics else 0
    used_bass = bass_strings_used(piece, request.overrides)
    bass_tokens = parse_bass_strings(settings.get("bassstrings", ""))
    if not bass_tokens:
        tuning_strings = tuning_count(tuning_text) if tuning_text else 0
        bass_tokens = default_bass_strings(max(0, piece.strings - tuning_strings))
    base_strings = min(6, piece.strings)
    display_indices = list(range(base_strings))
    display_indices.extend(index for index in sorted(used_bass) if base_strings <= index < piece.strings)
    tuning_labels = _tuning_labels(
        tuning_text,
        piece.strings,
        show_octaves=settings.get("tuninglabels", "relative") == "absolute",
        bass=(bass_tokens or None) if used_bass else None,
    )
    minimum_height = block_height(
        LayoutBlockPolicy(
            strings=base_strings,
            include_meta=True,
            show_dur=show_dur,
            show_extras=show_extras,
            show_tuplets=show_tuplets,
            show_tactus=show_tactus,
            double_stems=True,
            show_melody=show_melody,
            melody_rows_count=melody_rows,
            show_lyrics=show_lyrics,
            lyric_rows_count=lyric_rows,
            vocal_pos=vocal_pos,
        )
    )
    return _DisplayPlan(
        show_dur,
        show_extras,
        show_tuplets,
        show_tactus,
        vocal_pos,
        show_melody,
        melody_rows,
        show_lyrics,
        lyric_rows,
        settings.get("flagredundant", "on") == "on",
        policy.reverse_rows,
        base_strings,
        display_indices,
        tuning_labels,
        policy.basslabels,
        minimum_height,
    )


def _setting_int(settings: dict[str, str], name: str) -> int:
    value = settings.get(name, "")
    return int(value) if value.isdigit() else 0


def _limit_plan(
    request: LegacyRenderRequest,
    width: _WidthPlan,
    display: _DisplayPlan,
    header_row: int,
) -> _LimitPlan:
    available = max(0, request.height - 2 - (header_row + 1))
    systems = _system_slots(available, display.minimum_height)
    spacing_mode = request.settings.get("layout", "packed")
    bars_per_line = 0 if spacing_mode == "auto" else max(1, width.usable_width // (request.bar_width + width.bar_gap))
    explicit = _setting_int(request.settings, "barsperline")
    if explicit > 0:
        bars_per_line = explicit
    maxbars = _setting_int(request.settings, "maxbars")
    if maxbars > 0:
        bars_per_line = maxbars if bars_per_line <= 0 else min(bars_per_line, maxbars)
    return _LimitPlan(
        systems,
        _setting_int(request.settings, "maxchords"),
        _setting_int(request.settings, "chordwrap"),
        bars_per_line,
    )


def _actual_cursor_string(request: LegacyRenderRequest, display: _DisplayPlan) -> int:
    count = len(display.display_indices)
    if count <= 0:
        return request.cursor_string
    cursor_index = min(request.cursor_string, count - 1)
    if display.reverse_strings:
        return display.display_indices[count - 1 - cursor_index]
    return display.display_indices[cursor_index]


class _LegacyRenderer:
    def __init__(self, screen: Screen, request: LegacyRenderRequest) -> None:
        self.screen = screen
        self.request = request

    def render(self) -> None:
        request = self.request
        piece = request.piece
        width = _width_plan(request.width, request.settings)
        _render_header(self.screen, max(0, width.max_width - 1), piece)
        header_row = 0
        hint = None if is_duet_score_piece(piece) else duet_score_hint(piece)
        if hint:
            safe_addstr(self.screen, 1, 0, clean_text(hint)[: max(0, width.max_width - 1)])
            header_row = 1
        tuning_text = piece.tuning or request.settings.get("tuning", "")
        display = _display_plan(request, tuning_text)
        limits = _limit_plan(request, width, display, header_row)
        duet_request = self._duet_request(width, display, limits, header_row)
        rendered_duet = render_duet_score_view(self.screen, duet_request)
        if not rendered_duet:
            self._render_systems(width, display, limits, header_row)
        status_text = self._render_status(display)
        safe_addstr(
            self.screen,
            request.height - 1,
            0,
            clean_text(status_text),
            request.status_attr,
        )
        if request.mode == "help":
            self.screen.erase()
            render_help(self.screen, status_text, request.status_attr, request.help_offset)
        self.screen.refresh()

    def _duet_request(
        self,
        width: _WidthPlan,
        display: _DisplayPlan,
        limits: _LimitPlan,
        header_row: int,
    ) -> DuetRenderRequest:
        request = self.request
        return DuetRenderRequest(
            request.piece,
            request.width,
            request.height,
            header_row,
            3,
            request.bar_offset,
            request.cursor_bar,
            request.cursor_string,
            request.cursor_col,
            request.bar_width,
            request.overrides,
            request.durations,
            request.ornaments,
            request.annotations,
            request.highlights,
            request.dotted,
            request.slurs,
            request.ties,
            request.holds,
            request.glisses,
            request.settings,
            request.stave_breaks,
            request.playback_bar,
            request.playback_col,
            request.playback_markers,
            request.playback_cache,
            request.cursor_display_maps,
            True,
            display.show_dur,
            display.show_extras,
            display.show_tuplets,
            display.show_tactus,
            display.hide_redundant,
            True,
            display.reverse_strings,
            limits.max_chords,
            width.bar_gap,
            width.barpad,
            width.usable_width,
            4,
            display.tuning_labels,
            display.basslabels,
            limits.chord_wrap_limit,
        )

    def _render_systems(
        self,
        width: _WidthPlan,
        display: _DisplayPlan,
        limits: _LimitPlan,
        header_row: int,
    ) -> None:
        request = self.request
        render_systems(
            self.screen,
            piece=request.piece,
            width=request.width,
            header_row=header_row,
            left_margin=3,
            systems=limits.systems,
            total_strings=request.piece.strings,
            display_indices=display.display_indices,
            display_strings=len(display.display_indices),
            bar_offset=request.bar_offset,
            cursor_bar=request.cursor_bar,
            cursor_string=request.cursor_string,
            cursor_col=request.cursor_col,
            bar_width=request.bar_width,
            overrides=request.overrides,
            durations=request.durations,
            ornaments=request.ornaments,
            annotations=request.annotations,
            highlights=request.highlights,
            dotted=request.dotted,
            slurs=request.slurs,
            ties=request.ties,
            holds=request.holds,
            glisses=request.glisses,
            settings=request.settings,
            stave_breaks=request.stave_breaks,
            playback_bar=request.playback_bar,
            playback_col=request.playback_col,
            playback_markers=request.playback_markers,
            include_meta=True,
            show_dur=display.show_dur,
            show_extras=display.show_extras,
            show_tuplets=display.show_tuplets,
            show_tactus=display.show_tactus,
            hide_redundant=display.hide_redundant,
            double_stems=True,
            show_melody=display.show_melody,
            melody_rows_count=display.melody_rows,
            show_lyrics=display.show_lyrics,
            lyric_rows_count=display.lyric_rows,
            vocal_pos=display.vocal_pos,
            reverse_strings=display.reverse_strings,
            max_chords=limits.max_chords,
            spacing_mode=request.settings.get("layout", "packed"),
            spacing_fill=request.settings.get("justify", "stretch"),
            bar_gap=width.bar_gap,
            barpad=width.barpad,
            usable_width=width.usable_width,
            bars_per_line_limit=limits.bars_per_line,
            default_duration=4,
            tuning_labels=display.tuning_labels,
            basslabels=display.basslabels,
            chord_wrap_limit=limits.chord_wrap_limit,
            playback_cache=request.playback_cache,
            cursor_display_maps=request.cursor_display_maps,
        )

    def _render_status(self, display: _DisplayPlan) -> str:
        request = self.request
        duration = resolve_duration_text(
            piece=request.piece,
            durations=request.durations,
            dotted=request.dotted,
            cursor_bar=request.cursor_bar,
            cursor_col=request.cursor_col,
            actual_cursor_string=_actual_cursor_string(request, display),
            bar_width=request.bar_width,
            default_duration=4,
        )
        return build_status_lines(
            mode=request.mode,
            cmdline=request.cmdline,
            searchline=request.searchline,
            message=request.message,
            status_line=request.status_line,
            dur_text=duration,
            integrity_marker=bar_meter_integrity_marker(
                piece=request.piece,
                overrides=request.overrides,
                durations=request.durations,
                dotted=request.dotted,
                cursor_bar=request.cursor_bar,
                bar_width=request.bar_width,
                settings_time=request.settings.get("time", "C"),
                default_duration=4,
            ),
        )


def render_legacy_piece(screen: Screen, request: LegacyRenderRequest) -> None:
    _LegacyRenderer(screen, request).render()


__all__ = ["LegacyRenderRequest", "render_legacy_piece"]
