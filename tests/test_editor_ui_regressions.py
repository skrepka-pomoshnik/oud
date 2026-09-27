"""Regressions for the editor UI audit, docs/ui-fix-plan.md phase 1."""

from __future__ import annotations

import curses
import os
import signal
from pathlib import Path
from typing import cast

import pytest
from helpers_keyscript import keyscript_state, press_keys

from oud.editor.core.feedback.messages import READ_ONLY_VIEWER
from oud.editor.core.state import EditorState
from oud.editor.editing.primitives.undo import redo, undo
from oud.editor.interaction.dispatch import actions
from oud.editor.interaction.dispatch.controller import handle_key
from oud.editor.services.io.files import cmd_write
from oud.editor.services.status import status_line
from oud.exports.export_tab import export_tab
from oud.exports.midi.projection import build_playback_timeline
from oud.presentation.tui import loop
from oud.presentation.tui.commands import apply_command
from oud.settings import SettingsFileError, load_settings, save_settings
from petrucci.input.tablature.input import REST_OVERRIDE, editor_fret_at

CTRL_A = 1
CTRL_C = 3


def _press(state: EditorState, key: int | str) -> bool:
    code = key if isinstance(key, int) else ord(key)
    return handle_key(
        state,
        code,
        handle_insert=actions.handle_insert,
        handle_normal=actions.handle_normal,
        handle_command=lambda _state, _key: True,
        handle_search=lambda _state, _key: True,
    )


@pytest.mark.parametrize(("fret", "value"), [("q", 15), ("r", 16), ("s", 17), ("t", 18)])
def test_insert_types_high_french_frets_without_quitting(fret: str, value: int) -> None:
    state = keyscript_state(style="french")
    _press(state, "i")

    assert _press(state, fret) is True
    assert state.mode == "insert"
    decoded = editor_fret_at(state.overrides, state.durations, bar_index=0, string_index=0, column=0, style="french")
    assert decoded == value


@pytest.mark.parametrize("style", ["french", "italian"])
def test_insert_z_is_the_rest_key_in_every_style(style: str) -> None:
    state = keyscript_state(style=style)
    press_keys(state, ["i", "z"])

    assert state.overrides[(0, 0, 0)] == REST_OVERRIDE
    assert state.durations[(0, 0, 0)] == state.current_duration


def test_insert_ctrl_c_still_quits_an_unmodified_buffer() -> None:
    state = keyscript_state()
    _press(state, "i")

    assert _press(state, CTRL_C) is False


def test_italian_ctrl_letters_are_not_durations() -> None:
    state = keyscript_state(style="italian")
    press_keys(state, ["i", CTRL_A])

    assert state.durations == {}
    press_keys(state, [";", "3"])
    assert state.current_duration == 4


def test_french_rest_is_written_as_flag_only_tab_line() -> None:
    state = keyscript_state(style="french")
    press_keys(state, ["i", "z", "a"])

    text = export_tab(state.piece, state.overrides, state.durations, state.bar_width, settings=state.settings)

    lines = text.splitlines()
    assert "0------" in lines
    assert "0a-----" in lines
    assert "0r-----" not in lines


def test_french_rest_advances_playback_time() -> None:
    state = keyscript_state(style="french")
    press_keys(state, ["i", "z", "a"])

    timeline = build_playback_timeline(
        state.piece,
        state.overrides,
        state.durations,
        state.bar_width,
        state.settings,
        bpm=60,
    )

    assert len(timeline) == 1
    start, _end, _bar, _col = timeline[0]
    assert start == pytest.approx(1.0)


def test_read_only_viewer_applies_display_settings(tmp_path: Path) -> None:
    state = keyscript_state()
    state.read_only = True

    apply_command(state, "set scoreview=staff showlyrics=off", str(tmp_path / "cfg.toml"))

    assert state.settings["scoreview"] == "staff"
    assert state.settings["showlyrics"] == "off"


@pytest.mark.parametrize("token", ["tuning=ren7", "strings=7", "time=3/4", "style=italian", "title=X", "lute"])
def test_read_only_viewer_rejects_document_settings(tmp_path: Path, token: str) -> None:
    state = keyscript_state()
    state.read_only = True
    before = dict(state.settings)
    strings = state.piece.strings

    apply_command(state, f"set {token}", str(tmp_path / "cfg.toml"))

    assert state.settings == before
    assert state.piece.strings == strings
    assert state.piece.title == "T"
    assert state.message.startswith(READ_ONLY_VIEWER)


def test_set_persists_only_changed_preferences(tmp_path: Path) -> None:
    config = tmp_path / "cfg.toml"
    state = keyscript_state()
    state.settings.update({"time": "6/4", "tuning": "ren7", "tempo": "120", "filepath": "/music/x.tab"})

    apply_command(state, "dark", str(config))

    text = config.read_text(encoding="utf-8")
    assert 'theme = "dark"' in text
    for leaked in ("6/4", "ren7", "120", "/music/x.tab", "filepath"):
        assert leaked not in text


def test_set_document_keys_apply_to_session_only(tmp_path: Path) -> None:
    config = tmp_path / "cfg.toml"
    state = keyscript_state()

    apply_command(state, "set time=3/4", str(config))

    assert state.settings["time"] == "3/4"
    assert not config.exists()


def test_rejected_set_writes_nothing(tmp_path: Path) -> None:
    config = tmp_path / "cfg.toml"
    state = keyscript_state()

    apply_command(state, "set nosuchkey=1", str(config))

    assert not config.exists()


def test_exports_and_playback_do_not_write_settings(tmp_path: Path) -> None:
    config = tmp_path / "cfg.toml"
    state = keyscript_state()
    press_keys(state, ["i", "a", 27])

    apply_command(state, f"midi {tmp_path / 'out.mid'}", str(config))
    apply_command(state, f"lilypond {tmp_path / 'out.ly'}", str(config))

    assert not config.exists()


def test_default_config_is_created_under_xdg_not_working_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.chdir(work)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    save_settings("config.toml", {"theme": "dark"})

    assert not (work / "config.toml").exists()
    assert 'theme = "dark"' in (tmp_path / "xdg" / "oud" / "config.toml").read_text(encoding="utf-8")


def test_foreign_working_directory_config_is_ignored_and_preserved(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    work = tmp_path / "work"
    work.mkdir()
    foreign = work / "config.toml"
    foreign.write_text('baseURL = "https://example.org"\ntheme = "ananke"\n', encoding="utf-8")
    monkeypatch.chdir(work)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    assert load_settings("config.toml")["theme"] == "auto"
    save_settings("config.toml", {"theme": "dark"})

    assert foreign.read_text(encoding="utf-8") == 'baseURL = "https://example.org"\ntheme = "ananke"\n'


def test_settings_file_with_other_tables_is_never_rewritten(tmp_path: Path) -> None:
    config = tmp_path / "cfg.toml"
    original = '[settings]\ntheme = "light"\n\n[other]\nvalue = 1\n'
    config.write_text(original, encoding="utf-8")

    with pytest.raises(SettingsFileError):
        save_settings(str(config), {"theme": "dark"})

    assert config.read_text(encoding="utf-8") == original


def test_set_reports_settings_file_errors(tmp_path: Path) -> None:
    config = tmp_path / "cfg.toml"
    config.write_text("[settings]\n\n[other]\nvalue = 1\n", encoding="utf-8")
    state = keyscript_state()

    apply_command(state, "dark", str(config))

    assert state.settings["theme"] == "dark"
    assert "not saved" in state.message


class _EscWindow:
    def __init__(self) -> None:
        self.keys = [ord("q")]

    def keypad(self, _flag: bool) -> None:
        return None

    def timeout(self, _delay: int) -> None:
        return None

    def getch(self) -> int:
        return self.keys.pop(0) if self.keys else -1

    def getmaxyx(self) -> tuple[int, int]:
        return (1, 1)


class _ScreenWindow(_EscWindow):
    def getmaxyx(self) -> tuple[int, int]:
        return (12, 60)

    def erase(self) -> None:
        return None

    def refresh(self) -> None:
        return None

    def addstr(self, *_args: object) -> None:
        return None

    def bkgd(self, *_args: object) -> None:
        return None


class _QuitWindow(_ScreenWindow):
    def __init__(self) -> None:
        self.keys = [ord(":"), ord("q"), ord("!"), 10]


class _SignalWindow(_ScreenWindow):
    def __init__(self) -> None:
        self.keys = []
        self.renders = 0

    def refresh(self) -> None:
        # A real terminal delivers Ctrl-C whenever it likes, e.g. mid-render.
        self.renders += 1
        if self.renders == 1:
            os.kill(os.getpid(), signal.SIGINT)


def test_terminal_escape_delay_is_short(monkeypatch: pytest.MonkeyPatch) -> None:
    delays: list[int] = []
    monkeypatch.delenv("ESCDELAY", raising=False)
    monkeypatch.setattr(curses, "set_escdelay", delays.append)
    monkeypatch.setattr(curses, "curs_set", lambda _visibility: None)

    loop.configure_terminal(cast(curses.window, _EscWindow()))

    assert delays == [loop.ESCAPE_DELAY_MS]


def test_terminal_escape_delay_respects_user_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    delays: list[int] = []
    monkeypatch.setenv("ESCDELAY", "100")
    monkeypatch.setattr(curses, "set_escdelay", delays.append)
    monkeypatch.setattr(curses, "curs_set", lambda _visibility: None)

    loop.configure_terminal(cast(curses.window, _EscWindow()))

    assert delays == []


def test_delete_on_empty_cell_is_not_a_modification() -> None:
    state = keyscript_state()

    _press(state, "x")

    assert state.modified is False
    assert state.undo_stack == []


def test_add_bass_course_is_undoable() -> None:
    state = keyscript_state(settings_override={"bassstrings": "d2", "tuning": "g2c3f3a3d4g4"})
    state.piece.strings = 6

    press_keys(state, ["g", "b"])
    assert state.piece.strings == 7
    assert state.settings["tuning"] == "g2c3f3a3d4g4d2"

    undo(state, config_path="unused.toml")
    assert state.piece.strings == 6
    assert state.settings["tuning"] == "g2c3f3a3d4g4"
    assert state.modified is False

    redo(state, config_path="unused.toml")
    assert state.piece.strings == 7
    assert state.settings["tuning"] == "g2c3f3a3d4g4d2"


def test_status_name_follows_native_save_as_target(tmp_path: Path) -> None:
    source = tmp_path / "source.tab"
    state = keyscript_state()
    state.path = str(source)
    state.write_path = str(source)
    state.source_format = "tab"

    assert cmd_write(state, str(tmp_path / "copy.tab"))

    assert status_line(state).startswith("copy.tab ")


def test_visual_mode_is_reported_once() -> None:
    state = keyscript_state()

    _press(state, "v")

    assert state.mode == "visual"
    assert state.message == ""


@pytest.mark.parametrize(("keys", "fret"), [("vim+arrows", "h"), ("vim+arrows", "l"), ("casual", "a"), ("casual", "d")])
def test_replace_mode_letters_replace_frets_instead_of_moving(keys: str, fret: str) -> None:
    state = keyscript_state(style="french", settings_override={"keys": keys})
    press_keys(state, ["i", "c", 27])
    state.cursor_col = 0

    press_keys(state, ["R", fret])

    assert state.overrides[(0, 0, 0)] == fret


def _tab_file(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "rests.tab"
    path.write_text("-C\nb\n" + body + "e\n", encoding="utf-8")
    return path


def test_tab_flag_only_line_imports_as_timed_rest(tmp_path: Path) -> None:
    from oud.importers.tab import load_tab  # noqa: PLC0415

    piece = load_tab(str(_tab_file(tmp_path, "1\n0a-----\n0-c----\n")))

    chords = piece.bars[0].chords
    # Flag 1 is an eighth, 0 a quarter.
    assert [(chord.note_type, [(n.string, n.fret) for n in chord.notes]) for chord in chords] == [
        (5, []),
        (4, [(1, 0)]),
        (4, [(2, 2)]),
    ]


def test_tab_rest_round_trips_through_save_and_reopen(tmp_path: Path) -> None:
    from oud.editor.services.bootstrap import init_state  # noqa: PLC0415

    state = init_state(None, config_path=str(tmp_path / "cfg.toml"))
    press_keys(state, ["i", "3", "z", "a", 27])
    target = tmp_path / "saved.tab"
    assert cmd_write(state, str(target))

    reopened = init_state(str(target), config_path=str(tmp_path / "cfg.toml"))

    chords = reopened.piece.bars[0].chords
    assert [len(chord.notes) for chord in chords] == [0, 1]
    resaved = export_tab(
        reopened.piece, reopened.overrides, reopened.durations, reopened.bar_width, settings=reopened.settings
    )
    for text in (target.read_text(encoding="utf-8"), resaved):
        assert "\nb\nSc\n0------\n0a-----\n" in text


def test_imported_tab_rest_delays_following_notes_in_playback(tmp_path: Path) -> None:
    from oud.importers.tab import load_tab  # noqa: PLC0415

    piece = load_tab(str(_tab_file(tmp_path, "0\n0a-----\n")))

    timeline = build_playback_timeline(piece, {}, {}, 12, {"style": "french"}, bpm=60)

    assert timeline[0].start == pytest.approx(1.0)


def test_imported_tab_rest_shows_its_flag_over_an_empty_column(tmp_path: Path) -> None:
    from helpers_keyscript import render_lines  # noqa: PLC0415

    from oud.importers.tab import load_tab  # noqa: PLC0415

    piece = load_tab(str(_tab_file(tmp_path, "0a-----\n1\n1a-----\n")))
    state = keyscript_state(piece=piece, width=40, height=12)

    lines = render_lines(state)
    flag_row = next(line for line in lines if "|" in line and "\\\\" in line)
    top_course = next(line for line in lines if line.lstrip().startswith("g|"))

    rest_col = flag_row.index("|\\\\")
    assert top_course[rest_col] == "-"
    assert flag_row.count("|") == 2  # quarter flag and the rest flag; the repeated eighth is omitted


def _dispatch(state: EditorState, key: int | str) -> bool:
    from oud.presentation.tui.input import handle_command, handle_search  # noqa: PLC0415

    code = key if isinstance(key, int) else ord(key)
    return handle_key(
        state,
        code,
        handle_insert=actions.handle_insert,
        handle_normal=actions.handle_normal,
        handle_command=lambda s, k: handle_command(s, k, lambda _s, _cmd: None),
        handle_search=handle_search,
    )


class _IdleWindow:
    def timeout(self, _delay: int) -> None:
        return None

    def getch(self) -> int:
        return -1


def test_latched_sigint_becomes_the_ctrl_c_key() -> None:
    latch = loop.InterruptLatch()
    latch(signal.SIGINT, None)

    assert loop._read_input_batch(cast(curses.window, _IdleWindow()), 50, latch) == (CTRL_C,)
    assert loop._read_input_batch(cast(curses.window, _IdleWindow()), 50, latch) == ()


def test_sigint_at_any_point_is_a_key_not_an_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(curses, "curs_set", lambda _visibility: None)
    monkeypatch.setattr(curses, "set_escdelay", lambda _delay: None)
    previous = signal.getsignal(signal.SIGINT)

    result = loop.run_loop(
        cast(curses.window, _SignalWindow()),
        None,
        config_path="unused.toml",
        handle_insert=actions.handle_insert,
        handle_normal=actions.handle_normal,
        apply_command=apply_command,
    )

    assert result == 0
    assert signal.getsignal(signal.SIGINT) is previous


def test_ctrl_c_asks_before_discarding_unsaved_edits() -> None:
    state = keyscript_state()
    press_keys(state, ["i", "a", 27])

    assert _dispatch(state, CTRL_C) is True
    assert state.pending_quit is True
    assert _dispatch(state, CTRL_C) is False


@pytest.mark.parametrize("opening", [[":", "w"], ["/", "1"]])
def test_ctrl_c_cancels_prompts(opening: list[str]) -> None:
    state = keyscript_state()
    for key in opening:
        _dispatch(state, key)

    assert _dispatch(state, CTRL_C) is True

    assert state.mode == "normal"
    assert (state.cmdline, state.searchline) == ("", "")


def test_ctrl_c_closes_help_page() -> None:
    state = keyscript_state()
    _dispatch(state, "g")
    _dispatch(state, "h")

    _dispatch(state, CTRL_C)

    assert state.mode == "normal"


def test_every_loop_exit_stops_playback(monkeypatch: pytest.MonkeyPatch) -> None:
    stopped: list[EditorState] = []
    monkeypatch.setattr(loop, "stop_midi", stopped.append)
    monkeypatch.setattr(curses, "curs_set", lambda _visibility: None)
    monkeypatch.setattr(curses, "set_escdelay", lambda _delay: None)

    with pytest.raises(SystemExit):
        loop.run_loop(
            cast(curses.window, _QuitWindow()),
            None,
            config_path="unused.toml",
            handle_insert=actions.handle_insert,
            handle_normal=actions.handle_normal,
            apply_command=apply_command,
        )

    assert len(stopped) == 1


def test_capital_p_pastes_bars_before_and_never_builds_pdf() -> None:
    state = keyscript_state()
    state.piece.bars.extend(type(state.piece.bars[0])() for _ in range(2))
    press_keys(state, ["i", "a", 27, "y", "y", "l", "w"])
    assert state.cursor_bar == 1

    press_keys(state, ["P"])

    assert len(state.piece.bars) == 4
    assert state.overrides[(1, 0, 0)] == "a"
    assert state.pdf_job is None


def test_gb_adds_bass_course_and_gj_is_not_an_edit() -> None:
    state = keyscript_state(settings_override={"bassstrings": "d2", "tuning": "g2c3f3a3d4g4"})
    state.piece.strings = 6

    press_keys(state, ["g", "j"])
    assert state.piece.strings == 6

    press_keys(state, ["g", "b"])
    assert state.piece.strings == 7


def test_casual_brackets_only_jump_sections() -> None:
    state = keyscript_state(settings_override={"keys": "casual"})
    press_keys(state, ["i", "a", "b", "a", 27, "0", "f", "a"])
    col = state.cursor_col

    press_keys(state, ["]"])

    assert state.cursor_col == col


def test_stopping_a_stuck_player_kills_and_reaps_it() -> None:
    import subprocess  # noqa: PLC0415

    from oud.editor.services.media.midi import stop_midi  # noqa: PLC0415

    class _StuckPlayer:
        def __init__(self) -> None:
            self.calls: list[str] = []

        def poll(self) -> None:
            return None

        def terminate(self) -> None:
            self.calls.append("terminate")

        def kill(self) -> None:
            self.calls.append("kill")

        def wait(self, timeout: float) -> int:
            self.calls.append(f"wait {timeout}")
            if "kill" not in self.calls:
                raise subprocess.TimeoutExpired("player", timeout)
            return -9

    state = keyscript_state()
    player = _StuckPlayer()
    state.midi_proc = cast(subprocess.Popen[bytes], player)

    stop_midi(state)

    assert player.calls == ["terminate", "wait 1.0", "kill", "wait 1.0"]
    assert state.midi_proc is None


def test_new_score_keeps_its_empty_bars_through_save_and_reopen(tmp_path: Path) -> None:
    from oud.editor.services.bootstrap import init_state  # noqa: PLC0415

    state = init_state(None, config_path=str(tmp_path / "cfg.toml"))
    press_keys(state, ["i", "a", 27])
    bars = len(state.piece.bars)
    target = tmp_path / "new.tab"
    assert cmd_write(state, str(target))

    reopened = init_state(str(target), config_path=str(tmp_path / "cfg.toml"))

    assert len(reopened.piece.bars) == bars


def test_bare_barlines_do_not_create_empty_bars(tmp_path: Path) -> None:
    from oud.importers.tab import load_tab  # noqa: PLC0415

    path = tmp_path / "hand.tab"
    path.write_text("b\nb\n0a-----\nb\nb\n0c-----\ne\n", encoding="utf-8")

    assert len(load_tab(str(path)).bars) == 2
