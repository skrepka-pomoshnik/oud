from __future__ import annotations

from oud.petrucci.duet_score import (
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
from oud.petrucci.model import Piece
from oud.petrucci.render_helpers import (
    apply_overrides as _apply_overrides_impl,
)
from oud.petrucci.render_helpers import (
    bass_strings_used as _bass_strings_used_impl,
)
from oud.petrucci.render_helpers import (
    clean_text as _clean_text,
)
from oud.petrucci.render_helpers import (
    render_help as _render_help,
)
from oud.petrucci.render_helpers import (
    render_info as _render_info,
)
from oud.petrucci.render_helpers import (
    render_notes as _render_notes,
)
from oud.petrucci.render_helpers import (
    render_plugin as _render_plugin,
)
from oud.petrucci.render_helpers import (
    safe_addstr as _safe_addstr,
)
from oud.petrucci.render_status import (
    bar_meter_integrity_marker,
    build_status_lines,
    resolve_duration_text,
)
from oud.petrucci.render_system import PlaybackOverlayCache, render_systems
from oud.petrucci.render_vocal import melody_row_count
from oud.petrucci.screen import A_REVERSE, Screen
from oud.petrucci.tab_style import resolve_tab_style_policy
from oud.petrucci.tuning_utils import default_bass_strings, parse_bass_strings, tuning_count
from oud.petrucci.view_model import _block_height, _next_system_start, _tuning_labels


def _duet_score_hint(piece: Piece) -> str | None:
    ensemble = (piece.ensemble or "").strip()
    part = (piece.part or "").strip().lower()
    if not ensemble or part != "score":
        return None
    lower = ensemble.lower()
    if "lute 1" in lower and "lute 2" in lower:
        return "Lute 1 / Lute 2"
    return None


def _split_duet_stave_breaks(
    piece: Piece,
    stave_breaks: set[int],
    *,
    staff_index: int,
) -> set[int]:
    out: set[int] = set()
    for raw in stave_breaks:
        if raw <= 0:
            continue
        raw_staff, logical = duet_bar_mapping(raw, piece=piece)
        if raw_staff != staff_index:
            continue
        out.add(logical)
    return out


def _duet_logical_stave_breaks(piece: Piece, stave_breaks: set[int]) -> set[int]:
    out: set[int] = set()
    for raw in stave_breaks:
        if raw <= 0:
            continue
        _staff, logical = duet_bar_mapping(raw, piece=piece)
        out.add(logical)
    return out


def _duet_brace(
    stdscr: Screen,
    *,
    x: int,
    top_y: int,
    bottom_y: int,
) -> None:
    if bottom_y < top_y:
        return
    for y in range(top_y, bottom_y + 1):
        _safe_addstr(stdscr, y, x, "|")
    mid = (top_y + bottom_y) // 2
    _safe_addstr(stdscr, mid, x, "{")


def _merge_duet_cursor_maps(
    target: dict[int, list[int]] | None,
    local: dict[int, list[int]] | None,
    *,
    piece: Piece,
    staff_index: int,
) -> None:
    if target is None or local is None:
        return
    for logical_bar, mapping in local.items():
        raw_bar = duet_raw_bar_index(staff_index, logical_bar, piece=piece)
        if 0 <= raw_bar < len(piece.bars):
            target[raw_bar] = mapping


def _collect_duet_playback_ops(
    target: PlaybackOverlayCache,
    local: PlaybackOverlayCache | None,
) -> None:
    if local is None:
        return
    for key, operations in local.items():
        target.setdefault(key, []).extend(operations)


def _publish_duet_playback_cache(
    target: PlaybackOverlayCache | None,
    logical: PlaybackOverlayCache,
    *,
    piece: Piece,
) -> None:
    if target is None:
        return
    for (logical_bar, col), operations in logical.items():
        for staff_index in (0, 1):
            raw_bar = duet_raw_bar_index(staff_index, logical_bar, piece=piece)
            if 0 <= raw_bar < len(piece.bars):
                target[(raw_bar, col)] = list(operations)


def _render_duet_score_view(  # noqa: C901, PLR0912
    stdscr: Screen,
    *,
    piece: Piece,
    width: int,
    height: int,
    header_row: int,
    left_margin: int,
    bar_offset: int,
    cursor_bar: int,
    cursor_string: int,
    cursor_col: int,
    bar_width: int,
    overrides: dict[tuple[int, int, int], str],
    durations: dict[tuple[int, int, int], int],
    ornaments: dict[tuple[int, int], str],
    annotations: dict[tuple[int, int], str],
    highlights: set[tuple[int, int, int]],
    dotted: set[tuple[int, int]],
    slurs: list[tuple[int, int, int]],
    ties: list[tuple[int, int, int]],
    holds: list[tuple[int, int, int]],
    glisses: list[tuple[int, int, int]] | None,
    settings: dict[str, str],
    stave_breaks: set[int],
    playback_bar: int | None,
    playback_col: int | None,
    playback_markers: list[tuple[int, int]] | None,
    playback_cache: PlaybackOverlayCache | None,
    cursor_display_maps: dict[int, list[int]] | None,
    include_meta: bool,
    show_dur: bool,
    show_extras: bool,
    show_tuplets: bool,
    show_tactus: bool,
    hide_redundant: bool,
    double_stems: bool,
    reverse_strings: bool,
    max_chords: int,
    bar_gap: int,
    barpad: int,
    usable_width: int,
    default_duration: int,
    tuning_labels: list[str],
    basslabels: str,
    chord_wrap_limit: int,
    lyric_rows_count: int = 0,
) -> bool:
    _ = lyric_rows_count
    if not is_duet_score_piece(piece):
        return False
    _offset_staff, duet_logical_offset = duet_bar_mapping(max(0, bar_offset), piece=piece)
    mode = duet_view_mode(settings)
    if mode == "auto":
        mode = "both"
    staff_labels = duet_staff_labels(piece)
    selected_staff: int | None = None
    if mode in {"1", "2"}:
        selected_staff = 0 if mode == "1" else 1

    def _split_payload(staff_index: int):
        subpiece = split_duet_piece_staff(piece, staff_index)
        return {
            "piece": subpiece,
            "overrides": split_duet_triplet_map(overrides, staff_index=staff_index, piece=piece),
            "durations": split_duet_triplet_map(durations, staff_index=staff_index, piece=piece),
            "ornaments": split_duet_pair_map(ornaments, staff_index=staff_index, piece=piece),
            "annotations": split_duet_pair_map(annotations, staff_index=staff_index, piece=piece),
            "highlights": split_duet_triplet_set(highlights, staff_index=staff_index, piece=piece),
            "dotted": split_duet_pair_set(dotted, staff_index=staff_index, piece=piece),
            "slurs": split_duet_span_list(slurs, staff_index=staff_index, piece=piece),
            "ties": split_duet_span_list(ties, staff_index=staff_index, piece=piece),
            "holds": split_duet_span_list(holds, staff_index=staff_index, piece=piece),
            "glisses": split_duet_span_list(glisses or [], staff_index=staff_index, piece=piece),
            "stave_breaks": _split_duet_stave_breaks(piece, stave_breaks, staff_index=staff_index),
        }

    # Keep paired staves aligned by forcing a shared packed plan in duet score view.
    duet_settings = dict(settings)
    duet_settings["layout"] = "packed"
    duet_settings["duetwidthlock"] = "on"
    spacing_mode = "packed"
    spacing_fill = settings.get("justify", "stretch")
    bars_per_line_limit = max(1, usable_width // max(1, (bar_width + bar_gap)))
    barsperline = settings.get("barsperline", "")
    if barsperline.isdigit():
        limit = int(barsperline)
        if limit > 0:
            bars_per_line_limit = limit
    maxbars = settings.get("maxbars", "")
    if maxbars.isdigit():
        limit = int(maxbars)
        if limit > 0:
            bars_per_line_limit = min(bars_per_line_limit, limit)

    if selected_staff is not None:
        payload = _split_payload(selected_staff)
        label_row = header_row + 2
        _safe_addstr(stdscr, label_row, 0, " " * max(0, width - 1))
        single_label = f"{staff_labels[selected_staff]} only"[: max(0, width - 1)]
        _safe_addstr(stdscr, label_row, max(0, left_margin + 1), single_label)
        total_strings = payload["piece"].strings
        content_block_h = _block_height(
            include_meta,
            min(6, total_strings),
            show_dur,
            show_extras,
            show_tuplets,
            show_tactus,
            double_stems,
            lyric_rows_count=0,
        )
        # Reserve one extra row per system for the playback marker (`^`) so it
        # does not collide with the next system/label in duet view.
        block_h = content_block_h + 1
        available = max(0, height - 2 - (header_row + 2))
        systems = max(1, available // block_h)
        mapped_cursor_bar = -1
        if cursor_bar >= 0:
            cur_staff, cur_logical = duet_bar_mapping(cursor_bar, piece=piece)
            if cur_staff == selected_staff:
                mapped_cursor_bar = cur_logical
        mapped_playback_bar = None
        mapped_playback_markers: list[tuple[int, int]] = []
        if playback_bar is not None:
            # Single-staff duet view should still show the paired logical playback
            # position even when the active MIDI event belongs to the hidden staff.
            _play_staff, play_logical = duet_bar_mapping(playback_bar, piece=piece)
            mapped_playback_bar = play_logical
        for marker_bar, marker_col in playback_markers or []:
            _marker_staff, marker_logical = duet_bar_mapping(marker_bar, piece=piece)
            mapped_playback_markers.append((marker_logical, marker_col))
        logical_breaks = _duet_logical_stave_breaks(piece, stave_breaks)
        local_playback_cache: PlaybackOverlayCache | None = (
            {} if playback_cache is not None else None
        )
        local_cursor_maps: dict[int, list[int]] | None = (
            {} if cursor_display_maps is not None else None
        )
        render_systems(
            stdscr,
            piece=payload["piece"],
            width=width,
            header_row=header_row + 1,
            left_margin=left_margin,
            block_h=block_h,
            systems=systems,
            total_strings=total_strings,
            display_indices=[],
            display_strings=0,
            bar_offset=duet_logical_offset,
            cursor_bar=mapped_cursor_bar,
            cursor_string=cursor_string,
            cursor_col=cursor_col,
            bar_width=bar_width,
            overrides=payload["overrides"],
            durations=payload["durations"],
            ornaments=payload["ornaments"],
            annotations=payload["annotations"],
            highlights=payload["highlights"],
            dotted=payload["dotted"],
            slurs=payload["slurs"],
            ties=payload["ties"],
            holds=payload["holds"],
            glisses=payload["glisses"],
            settings=duet_settings,
            stave_breaks=logical_breaks,
            playback_bar=mapped_playback_bar,
            playback_col=playback_col,
            playback_markers=mapped_playback_markers,
            include_meta=include_meta,
            show_dur=show_dur,
            show_extras=show_extras,
            show_tuplets=show_tuplets,
            show_tactus=show_tactus,
            hide_redundant=hide_redundant,
            double_stems=double_stems,
            reverse_strings=reverse_strings,
            max_chords=max_chords,
            spacing_mode=spacing_mode,
            spacing_fill=spacing_fill,
            bar_gap=bar_gap,
            barpad=barpad,
            usable_width=usable_width,
            bars_per_line_limit=bars_per_line_limit,
            default_duration=default_duration,
            tuning_labels=tuning_labels,
            basslabels=basslabels,
            chord_wrap_limit=chord_wrap_limit,
            lyric_rows_count=0,
            playback_cache=local_playback_cache,
            cursor_display_maps=local_cursor_maps,
        )
        _merge_duet_cursor_maps(
            cursor_display_maps,
            local_cursor_maps,
            piece=piece,
            staff_index=selected_staff,
        )
        logical_playback_ops: PlaybackOverlayCache = {}
        _collect_duet_playback_ops(logical_playback_ops, local_playback_cache)
        _publish_duet_playback_cache(playback_cache, logical_playback_ops, piece=piece)
        return True

    top = _split_payload(0)
    bottom = _split_payload(1)
    top_piece = top["piece"]
    bottom_piece = bottom["piece"]
    total_strings = piece.strings
    content_block_h = _block_height(
        include_meta,
        min(6, total_strings),
        show_dur,
        show_extras,
        show_tuplets,
        show_tactus,
        double_stems,
        lyric_rows_count=0,
    )
    # Reserve one playback-marker row per staff block in duet mode.
    block_h = content_block_h + 1
    pair_block_h = block_h * 2
    base_header = header_row + 1  # keep the global title/header row intact
    available = max(0, height - 2 - base_header)
    pair_systems = max(1, available // max(1, pair_block_h))
    current_logical = max(0, duet_logical_offset)
    total_logical = max(len(top_piece.bars), len(bottom_piece.bars))
    logical_breaks = _duet_logical_stave_breaks(piece, stave_breaks)
    logical_bars = (
        top_piece.bars
        if len(top_piece.bars) >= len(bottom_piece.bars)
        else bottom_piece.bars
    )
    logical_playback_ops: PlaybackOverlayCache = {}

    for sys_idx in range(pair_systems):
        if current_logical >= total_logical:
            break
        top_header = base_header + sys_idx * pair_block_h
        bottom_header = top_header + block_h
        system_end = _next_system_start(
            logical_bars,
            current_logical,
            bars_per_line_limit,
            logical_breaks,
        )
        for staff_index, payload, sub_header in (
            (0, top, top_header),
            (1, bottom, bottom_header),
        ):
            subpiece = payload["piece"]
            if current_logical >= len(subpiece.bars):
                continue
            mapped_cursor_bar = -1
            if cursor_bar >= 0:
                cur_staff, cur_logical = duet_bar_mapping(cursor_bar, piece=piece)
                if cur_staff == staff_index:
                    mapped_cursor_bar = cur_logical
            mapped_playback_bar = None
            mapped_playback_markers: list[tuple[int, int]] = []
            if playback_bar is not None:
                _play_staff, play_logical = duet_bar_mapping(playback_bar, piece=piece)
                # Playback state is a single cursor; mirror the logical position on
                # both staves so duet playback remains visually synchronized.
                mapped_playback_bar = play_logical
            for marker_bar, marker_col in playback_markers or []:
                marker_staff, marker_logical = duet_bar_mapping(marker_bar, piece=piece)
                if marker_staff == staff_index:
                    mapped_playback_markers.append((marker_logical, marker_col))
            local_playback_cache = {} if playback_cache is not None else None
            local_cursor_maps = {} if cursor_display_maps is not None else None
            render_systems(
                stdscr,
                piece=subpiece,
                width=width,
                header_row=sub_header,
                left_margin=left_margin,
                block_h=block_h,
                systems=1,
                total_strings=subpiece.strings,
                display_indices=[],
                display_strings=0,
                bar_offset=current_logical,
                cursor_bar=mapped_cursor_bar,
                cursor_string=cursor_string,
                cursor_col=cursor_col,
                bar_width=bar_width,
                overrides=payload["overrides"],
                durations=payload["durations"],
                ornaments=payload["ornaments"],
                annotations=payload["annotations"],
                highlights=payload["highlights"],
                dotted=payload["dotted"],
                slurs=payload["slurs"],
                ties=payload["ties"],
                holds=payload["holds"],
                glisses=payload["glisses"],
                settings=duet_settings,
                stave_breaks=logical_breaks,
                playback_bar=mapped_playback_bar,
                playback_col=playback_col,
                playback_markers=mapped_playback_markers,
                include_meta=include_meta,
                show_dur=show_dur,
                show_extras=show_extras,
                show_tuplets=show_tuplets,
                show_tactus=show_tactus,
                hide_redundant=hide_redundant,
                double_stems=double_stems,
                reverse_strings=reverse_strings,
                max_chords=max_chords,
                spacing_mode=spacing_mode,
                spacing_fill=spacing_fill,
                bar_gap=bar_gap,
                barpad=barpad,
                usable_width=usable_width,
                bars_per_line_limit=bars_per_line_limit,
                default_duration=default_duration,
                tuning_labels=tuning_labels,
                basslabels=basslabels,
                chord_wrap_limit=chord_wrap_limit,
                lyric_rows_count=0,
                playback_cache=local_playback_cache,
                cursor_display_maps=local_cursor_maps,
            )
            _merge_duet_cursor_maps(
                cursor_display_maps,
                local_cursor_maps,
                piece=piece,
                staff_index=staff_index,
            )
            _collect_duet_playback_ops(logical_playback_ops, local_playback_cache)
        top_row_start = top_header + 1
        bottom_row_start = bottom_header + 1
        label_x = max(0, left_margin + 1)
        label_w = max(0, width - label_x - 1)
        _safe_addstr(stdscr, top_header + 1, label_x, staff_labels[0][:label_w])
        _safe_addstr(stdscr, bottom_header + 1, label_x, staff_labels[1][:label_w])
        _duet_brace(
            stdscr,
            x=max(0, left_margin - 1),
            top_y=top_row_start,
            bottom_y=bottom_row_start + content_block_h - 1,
        )
        current_logical = max(current_logical + 1, system_end)
    _publish_duet_playback_cache(playback_cache, logical_playback_ops, piece=piece)
    return True


def _render_header_line(
    stdscr: Screen,
    *,
    width: int,
    piece: Piece,
    settings: dict[str, str],  # noqa: ARG001
) -> None:
    title = piece.title or "Untitled"
    right = _clean_text(piece.composer or "")
    title_text = _clean_text(title)
    if width <= 0:
        return
    if right:
        right = right[: max(0, width)]
        right_x = max(0, width - len(right))
        title_max = max(0, right_x - 1)
        if title_max > 0:
            centered = title_text[:title_max]
            title_x = max(0, (title_max - len(centered)) // 2)
            _safe_addstr(stdscr, 0, title_x, centered)
        _safe_addstr(stdscr, 0, right_x, right)
        return
    centered = title_text[:width]
    title_x = max(0, (width - len(centered)) // 2)
    _safe_addstr(stdscr, 0, title_x, centered)


def _bass_strings_used(piece: Piece, overrides: dict[tuple[int, int, int], str]) -> set[int]:
    return _bass_strings_used_impl(piece, overrides)


def _apply_overrides(
    cells: list[list[str]],
    overrides: dict[tuple[int, int, int], str],
    bar_index: int,
    strings: int,
    bar_width: int,
) -> None:
    _apply_overrides_impl(cells, overrides, bar_index, strings, bar_width)


def _piece_has_imported_ft3_extras(piece: Piece) -> bool:
    for bar in piece.bars:
        notes = list(bar.notes)
        if not notes and bar.chords:
            for chord in bar.chords:
                notes.extend(chord.notes)
        for note in notes:
            if (
                note.right_fingering
                or note.left_fingering
                or note.right_ornament
                or note.left_ornament
            ):
                return True
    return False


def _piece_has_lyrics(piece: Piece) -> bool:
    for bar in piece.bars:
        if any(line.strip() for line in bar.lyrics):
            return True
        for row in bar.lyric_event_rows:
            if any((event.text or "").strip() for event in row):
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
        for row in bar.lyric_event_rows:
            if any((event.text or "").strip() for event in row):
                return True
    return False


def _piece_lyric_row_count(piece: Piece, *, max_rows: int = 99) -> int:
    count = 0
    for bar in piece.bars:
        rows = 0
        if bar.lyric_event_rows:
            rows = sum(
                1
                for row in bar.lyric_event_rows
                if any((event.text or "").strip() for event in row)
            )
        if rows == 0:
            rows = len([line for line in bar.lyrics if line.strip()])
        if rows > 0:
            count = max(count, min(max_rows, rows))
            if count >= max_rows:
                return max_rows
    return count


def _render_ascii_preview(
    stdscr: Screen,
    ascii_lines: list[str],
    status_line: str,
    mode: str,
    status_attr: int,
) -> None:
    height, _width = stdscr.getmaxyx()
    for idx, line in enumerate(ascii_lines[: max(0, height - 1)]):
        _safe_addstr(stdscr, idx, 0, _clean_text(line))
    _safe_addstr(
        stdscr,
        height - 1,
        0,
        _clean_text(f"{status_line}  {mode}  ascii preview"),
        status_attr,
    )


def render_piece(  # noqa: C901, PLR0912
    stdscr: Screen,
    piece: Piece,
    bar_offset: int,
    cursor_bar: int,
    cursor_string: int,
    cursor_col: int,
    bar_width: int,
    overrides: dict[tuple[int, int, int], str],
    durations: dict[tuple[int, int, int], int],
    ornaments: dict[tuple[int, int], str],
    annotations: dict[tuple[int, int], str],
    highlights: set[tuple[int, int, int]],
    dotted: set[tuple[int, int]],
    slurs: list[tuple[int, int, int]],
    ties: list[tuple[int, int, int]],
    holds: list[tuple[int, int, int]],
    mode: str,
    cmdline: str,
    message: str,
    status_line: str,
    searchline: str,
    settings: dict[str, str],
    ascii_lines: list[str] | None,
    stave_breaks: set[int],
    plugin_title: str,
    plugin_items: list[str],
    plugin_index: int,
    plugin_offset: int,
    help_offset: int = 0,
    playback_bar: int | None = None,
    playback_col: int | None = None,
    glisses: list[tuple[int, int, int]] | None = None,
    playback_cache=None,
    playback_markers: list[tuple[int, int]] | None = None,
    cursor_display_maps: dict[int, list[int]] | None = None,
) -> None:
    stdscr.erase()
    height, width = stdscr.getmaxyx()
    total_strings = piece.strings

    status_attr = A_REVERSE
    if mode == "info":
        info_settings = dict(settings)
        info_settings["terminal"] = f"{width}x{height}"
        _render_info(stdscr, status_line, status_attr, help_offset, piece, info_settings)
        stdscr.refresh()
        return
    if mode == "notes":
        _render_notes(stdscr, status_line, status_attr, help_offset, piece)
        stdscr.refresh()
        return
    if mode == "plugin":
        _render_plugin(
            stdscr,
            "plugin  j/k move  h back  l/enter open  d download  q close",
            status_attr,
            plugin_title,
            plugin_items,
            plugin_index,
            plugin_offset,
            message,
        )
        stdscr.refresh()
        return
    if ascii_lines is not None:
        _render_ascii_preview(stdscr, ascii_lines, status_line, mode, status_attr)
        stdscr.refresh()
        return

    tuning_text = piece.tuning or settings.get("tuning", "")
    header_row = 0
    left_margin = 3
    spacing_mode = settings.get("layout", "packed")
    spacing_fill = settings.get("justify", "stretch")
    bargap = settings.get("bargap", "")
    if bargap.isdigit():
        bar_gap = max(0, int(bargap))
    else:
        bar_gap = 1 if spacing_mode in ("packed", "auto") else 3
    barpad = 1
    barpad_text = settings.get("barpad", "1")
    if barpad_text.isdigit():
        barpad = max(0, int(barpad_text))
    max_width = width
    right_padding = 1
    usable_width = max(0, max_width - left_margin - right_padding)
    linelen = settings.get("linelen", "")
    if linelen.isdigit():
        line_limit = int(linelen)
        if line_limit > 0:
            max_width = min(max_width, line_limit)
            usable_width = max(0, max_width - left_margin - right_padding)
    _render_header_line(
        stdscr,
        width=max(0, max_width - right_padding),
        piece=piece,
        settings=settings,
    )
    duet_hint = None if is_duet_score_piece(piece) else _duet_score_hint(piece)
    if duet_hint:
        _safe_addstr(stdscr, 1, 0, _clean_text(duet_hint)[: max(0, max_width - right_padding)])
        header_row = 1

    default_duration = 4
    include_meta = True
    policy = resolve_tab_style_policy(settings)
    show_dur = settings.get("showdur", "off") == "on"
    show_fingerings = policy.showfingerings
    show_ornaments = policy.showornaments
    imported_extras_visible = (
        show_fingerings or show_ornaments
    ) and _piece_has_imported_ft3_extras(piece)
    # Imported FT3 local extras render inline; they should not force reserve extra rows.
    _ = imported_extras_visible
    show_extras = settings.get("showspans", "off") == "on"
    show_tuplets = settings.get("showtuplets", "off") == "on"
    show_tactus = settings.get("showtactus", "off") == "on"
    vocal_pos = settings.get("vocalpos", "bottom")
    show_melody_text = settings.get("showmelody", "on") == "on" and _piece_has_melody_grid(piece)
    melody_rows_count = melody_row_count() if show_melody_text else 0
    show_lyric_text = settings.get("showlyrics", "on") == "on" and _piece_has_lyrics(piece)
    lyric_rows_count = _piece_lyric_row_count(piece, max_rows=99) if show_lyric_text else 0
    hide_redundant = settings.get("flagredundant", "on") == "on"
    # Stem height and stem width are different concerns.
    # Keep a second tablature stem row even for single-width stems.
    double_stems = True
    reverse_strings = policy.reverse_rows
    show_octaves = settings.get("tuninglabels", "relative") == "absolute"
    used_bass = _bass_strings_used(piece, overrides)
    bass_tokens = parse_bass_strings(settings.get("bassstrings", ""))
    if not bass_tokens:
        tuning_strings = tuning_count(tuning_text) if tuning_text else 0
        bass_tokens = default_bass_strings(max(0, total_strings - tuning_strings))
    base_strings = min(6, total_strings)
    display_indices = list(range(base_strings))
    display_indices.extend(
        idx for idx in sorted(used_bass) if base_strings <= idx < total_strings
    )
    display_strings = len(display_indices)
    tuning_labels = _tuning_labels(
        tuning_text,
        total_strings,
        show_octaves=show_octaves,
        bass=bass_tokens or None if used_bass else None,
    )
    basslabels = policy.basslabels
    block_h = _block_height(
        include_meta,
        display_strings,
        show_dur,
        show_extras,
        show_tuplets,
        show_tactus,
        double_stems,
        show_melody=show_melody_text,
        melody_rows_count=melody_rows_count,
        show_lyrics=show_lyric_text,
        lyric_rows_count=lyric_rows_count,
        vocal_pos=vocal_pos,
    )
    available = max(0, height - 2 - (header_row + 1))
    systems = max(1, available // block_h)
    max_chords = 0
    max_chords_text = settings.get("maxchords", "")
    if max_chords_text.isdigit():
        max_chords = int(max_chords_text)
    chord_wrap_limit = 0
    chord_wrap_text = settings.get("chordwrap", "")
    if chord_wrap_text.isdigit():
        chord_wrap_limit = int(chord_wrap_text)
    if spacing_mode == "auto":
        bars_per_line_limit = 0
    else:
        bars_per_line_limit = max(1, usable_width // (bar_width + bar_gap))
    barsperline = settings.get("barsperline", "")
    if barsperline.isdigit():
        limit = int(barsperline)
        if limit > 0:
            bars_per_line_limit = limit
    maxbars = settings.get("maxbars", "")
    if maxbars.isdigit():
        limit = int(maxbars)
        if limit > 0:
            bars_per_line_limit = (
                limit
                if bars_per_line_limit <= 0
                else min(bars_per_line_limit, limit)
            )

    rendered_duet = _render_duet_score_view(
        stdscr,
        piece=piece,
        width=width,
        height=height,
        header_row=header_row,
        left_margin=left_margin,
        bar_offset=bar_offset,
        cursor_bar=cursor_bar,
        cursor_string=cursor_string,
        cursor_col=cursor_col,
        bar_width=bar_width,
        overrides=overrides,
        durations=durations,
        ornaments=ornaments,
        annotations=annotations,
        highlights=highlights,
        dotted=dotted,
        slurs=slurs,
        ties=ties,
        holds=holds,
        glisses=glisses,
        settings=settings,
        stave_breaks=stave_breaks,
        playback_bar=playback_bar,
        playback_col=playback_col,
        playback_markers=playback_markers,
        playback_cache=playback_cache,
        cursor_display_maps=cursor_display_maps,
        include_meta=include_meta,
        show_dur=show_dur,
        show_extras=show_extras,
        show_tuplets=show_tuplets,
        show_tactus=show_tactus,
        hide_redundant=hide_redundant,
        double_stems=double_stems,
        reverse_strings=reverse_strings,
        max_chords=max_chords,
        bar_gap=bar_gap,
        barpad=barpad,
        usable_width=usable_width,
        default_duration=default_duration,
        tuning_labels=tuning_labels,
        basslabels=basslabels,
        chord_wrap_limit=chord_wrap_limit,
        lyric_rows_count=0,
    )
    if not rendered_duet:
        render_systems(
            stdscr,
            piece=piece,
            width=width,
            header_row=header_row,
            left_margin=left_margin,
            block_h=block_h,
            systems=systems,
            total_strings=total_strings,
            display_indices=display_indices,
            display_strings=display_strings,
            bar_offset=bar_offset,
            cursor_bar=cursor_bar,
            cursor_string=cursor_string,
            cursor_col=cursor_col,
            bar_width=bar_width,
            overrides=overrides,
            durations=durations,
            ornaments=ornaments,
            annotations=annotations,
            highlights=highlights,
            dotted=dotted,
            slurs=slurs,
            ties=ties,
            holds=holds,
            glisses=glisses,
            settings=settings,
            stave_breaks=stave_breaks,
            playback_bar=playback_bar,
            playback_col=playback_col,
            playback_markers=playback_markers,
            include_meta=include_meta,
            show_dur=show_dur,
            show_extras=show_extras,
            show_tuplets=show_tuplets,
            show_tactus=show_tactus,
            hide_redundant=hide_redundant,
            double_stems=double_stems,
            show_melody=show_melody_text,
            melody_rows_count=melody_rows_count,
            show_lyrics=show_lyric_text,
            lyric_rows_count=lyric_rows_count,
            vocal_pos=vocal_pos,
            reverse_strings=reverse_strings,
            max_chords=max_chords,
            spacing_mode=spacing_mode,
            spacing_fill=spacing_fill,
            bar_gap=bar_gap,
            barpad=barpad,
            usable_width=usable_width,
            bars_per_line_limit=bars_per_line_limit,
            default_duration=default_duration,
            tuning_labels=tuning_labels,
            basslabels=basslabels,
            chord_wrap_limit=chord_wrap_limit,
            playback_cache=playback_cache,
            cursor_display_maps=cursor_display_maps,
        )

    if display_strings > 0:
        cursor_index = min(cursor_string, display_strings - 1)
        if reverse_strings:
            actual_cursor_string = display_indices[display_strings - 1 - cursor_index]
        else:
            actual_cursor_string = display_indices[cursor_index]
    else:
        actual_cursor_string = cursor_string
    dur_text = resolve_duration_text(
        piece=piece,
        durations=durations,
        dotted=dotted,
        cursor_bar=cursor_bar,
        cursor_col=cursor_col,
        actual_cursor_string=actual_cursor_string,
        bar_width=bar_width,
        default_duration=default_duration,
    )
    status_line_text = build_status_lines(
        mode=mode,
        cmdline=cmdline,
        searchline=searchline,
        message=message,
        status_line=status_line,
        dur_text=dur_text,
        integrity_marker=bar_meter_integrity_marker(
            piece=piece,
            overrides=overrides,
            durations=durations,
            dotted=dotted,
            cursor_bar=cursor_bar,
            bar_width=bar_width,
            settings_time=settings.get("time", "C"),
            default_duration=default_duration,
        ),
    )
    _safe_addstr(stdscr, height - 1, 0, _clean_text(status_line_text), status_attr)

    if mode == "help":
        stdscr.erase()
        _render_help(stdscr, status_line_text, status_attr, help_offset)

    stdscr.refresh()
