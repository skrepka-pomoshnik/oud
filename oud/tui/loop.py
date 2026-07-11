from __future__ import annotations

import curses

from oud.editor.init import init_state
from oud.editor.playback import update_playback_animation
from oud.editor.status import status_line
from oud.editor.transient_message import decay_transient_message
from oud.editor.view_state import view_commit_frame, view_merge_dirty, view_resize
from oud.exports.export_tab import export_ascii
from oud.petrucci.duet_score import is_duet_score_piece
from oud.petrucci.framebuffer import (
    FrameBuffer,
    draw_frame_rows,
    frame_diff_rows,
    overlay_dirty_rows,
    overlay_frame,
)
from oud.petrucci.render import render_piece
from oud.tui.controller import handle_key as handle_key_impl
from oud.tui.input import handle_command as handle_command_input
from oud.tui.input import handle_search as handle_search_input
from oud.tui.keycodes import keycodes_from_curses
from oud.tui.viewport import ensure_cursor_visible
from oud.ui.adapter import CursesScreen, apply_theme_background, contrast_attr, theme_attr


def run_loop(
    stdscr: curses.window,
    path: str | None,
    *,
    config_path: str,
    handle_insert,
    handle_normal,
    apply_command,
    read_only: bool = False,
) -> int:
    curses.curs_set(0)
    stdscr.keypad(True)
    stdscr.timeout(50)

    state = init_state(path, config_path=config_path, read_only=read_only)
    state.keycodes = keycodes_from_curses()

    def suspend_tui() -> None:
        curses.def_prog_mode()
        curses.endwin()

    def resume_tui() -> None:
        curses.reset_prog_mode()
        stdscr.refresh()

    state.suspend_tui = suspend_tui
    state.resume_tui = resume_tui

    running = True
    needs_render = True
    while running:
        stdscr.timeout(20 if state.midi_proc is not None else 50)
        key = stdscr.getch()
        if key != -1:
            running = handle_key_impl(
                state,
                key,
                handle_insert=handle_insert,
                handle_normal=handle_normal,
                handle_command=lambda s, k: handle_command_input(
                    s,
                    k,
                    lambda st, cmd: apply_command(st, cmd, state.config_path),
                ),
                handle_search=handle_search_input,
            )
            needs_render = True

        message_changed = decay_transient_message(state)
        height, width = stdscr.getmaxyx()
        state.screen_height = height
        state.screen_width = width
        state.clamp()
        playback_changed = update_playback_animation(state)
        resized = view_resize(state, height=height, width=width)
        playback_only = (
            playback_changed
            and not needs_render
            and not message_changed
            and not resized
            and not state.dirty_rows
        )
        can_overlay_playback = (
            playback_only
            and state.last_base_frame is not None
            and state.playback_overlay_cache is not None
        )
        if needs_render or message_changed or playback_changed or resized or state.dirty_rows:
            prev_bar_offset = state.bar_offset
            ensure_cursor_visible(state, width, height)
            viewport_changed = state.bar_offset != prev_bar_offset
            theme_base = theme_attr(state.settings.get("theme", "auto"))
            apply_theme_background(stdscr, theme_base)
            base_attr = theme_base | contrast_attr(state.settings.get("contrast", "normal"))
            screen = CursesScreen(stdscr, base_attr=base_attr)
            if can_overlay_playback and not viewport_changed:
                prev_key = state.playback_overlay_key or (-1, -1)
                playback_key = (
                    state.playback_bar if state.playback_bar is not None else -1,
                    state.playback_col if state.playback_col is not None else -1,
                )
                prev_ops = state.playback_overlay_cache.get(prev_key, [])
                next_ops = state.playback_overlay_cache.get(playback_key, [])
                dirty = {y for y, _x, _text, _attr in prev_ops}
                dirty |= {y for y, _x, _text, _attr in next_ops}
                frame = overlay_dirty_rows(
                    state.last_frame or state.last_base_frame,
                    base_frame=state.last_base_frame,
                    ops=next_ops,
                    rows=dirty,
                )
                draw_frame_rows(screen, frame, dirty)
                screen.refresh()
                state.playback_overlay_key = playback_key
                view_commit_frame(state, frame)
                needs_render = False
                continue
            ascii_preview_lines = (
                export_ascii(
                    state.piece,
                    state.overrides,
                    state.durations,
                    state.bar_width,
                    settings=state.settings,
                    ornaments=state.ornaments,
                    annotations=state.annotations,
                    slurs=state.slurs,
                    ties=state.ties,
                    holds=state.holds,
                ).splitlines()
                if state.ascii_preview
                else None
            )
            frame_buffer = FrameBuffer(height, width)
            state.display_cursor_maps.clear()
            playback_cache: dict[tuple[int, int], list[tuple[int, int, str, int]]] | None = (
                {}
                if not is_duet_score_piece(state.piece)
                else None
            )
            render_piece(
                frame_buffer,
                state.piece,
                state.bar_offset,
                state.cursor_bar,
                state.cursor_string,
                state.cursor_col,
                state.bar_width,
                state.overrides,
                state.durations,
                state.ornaments,
                state.annotations,
                state.highlights,
                state.dotted,
                state.slurs,
                state.ties,
                state.holds,
                state.mode,
                state.cmdline,
                state.visible_message,
                status_line(state),
                state.searchline,
                state.settings,
                ascii_preview_lines,
                state.stave_breaks,
                state.plugin_title,
                [f"{item.title}{'/' if item.is_dir else ''}" for item in state.plugin_items],
                state.plugin_index,
                state.plugin_offset,
                state.info_offset
                if state.mode == "info"
                else state.notes_offset if state.mode == "notes" else state.help_offset,
                None if playback_cache is not None else state.playback_bar,
                None if playback_cache is not None else state.playback_col,
                playback_markers=state.playback.markers,
                playback_cache=playback_cache,
                cursor_display_maps=state.display_cursor_maps,
            )
            base_frame = frame_buffer.snapshot()
            state.last_base_frame = base_frame
            state.playback_overlay_cache = playback_cache
            if playback_cache is not None:
                playback_key = (
                    state.playback_bar if state.playback_bar is not None else -1,
                    state.playback_col if state.playback_col is not None else -1,
                )
                frame = overlay_frame(
                    base_frame,
                    playback_cache.get(playback_key, []),
                )
                state.playback_overlay_key = playback_key
            else:
                frame = base_frame
                state.playback_overlay_key = None
            dirty = frame_diff_rows(state.last_frame, frame)
            dirty = view_merge_dirty(state, dirty)
            draw_frame_rows(screen, frame, dirty)
            screen.refresh()
            view_commit_frame(state, frame)
            needs_render = False

    return 0
