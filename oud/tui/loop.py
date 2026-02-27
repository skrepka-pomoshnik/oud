from __future__ import annotations

import curses

from oud.editor.init import init_state
from oud.editor.playback import update_playback_animation
from oud.editor.status import status_line
from oud.editor.transient_message import decay_transient_message
from oud.editor.view_state import view_commit_frame, view_merge_dirty, view_resize
from oud.exports.export_tab import export_ascii
from oud.tui.controller import handle_key as handle_key_impl
from oud.tui.input import handle_command as handle_command_input
from oud.tui.input import handle_search as handle_search_input
from oud.tui.keycodes import keycodes_from_curses
from oud.tui.viewport import ensure_cursor_visible
from oud.ui.adapter import CursesScreen
from oud.ui.framebuffer import FrameBuffer, draw_frame_rows, frame_diff_rows
from oud.ui.render import render_piece


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

    screen = CursesScreen(stdscr)
    running = True
    while running:
        decay_transient_message(state)
        height, width = stdscr.getmaxyx()
        state.screen_height = height
        state.screen_width = width
        state.clamp()
        update_playback_animation(state)
        ensure_cursor_visible(state, width, height)
        frame_buffer = FrameBuffer(height, width)
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
            state.message,
            status_line(state),
            state.searchline,
            state.settings,
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
            else None,
            state.stave_breaks,
            state.plugin_title,
            [
                f"{item.title}{'/' if item.is_dir else ''}"
                for item in state.plugin_items
            ],
            state.plugin_index,
            state.plugin_offset,
            state.help_offset if state.mode != "info" else state.info_offset,
            state.playback_bar,
            state.playback_col,
        )
        frame = frame_buffer.snapshot()
        view_resize(state, height=height, width=width)
        dirty = frame_diff_rows(state.last_frame, frame)
        dirty = view_merge_dirty(state, dirty)
        draw_frame_rows(screen, frame, dirty)
        screen.refresh()
        view_commit_frame(state, frame)

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

    return 0
