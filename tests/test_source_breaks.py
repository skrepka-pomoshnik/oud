"""`sourcebreaks` decides whether a TAB file's own line breaks end a system."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from oud.editor.core.state import EditorState
from oud.editor.services.bootstrap import init_state
from oud.editor.services.screen.compose import compose_editor_frame
from oud.presentation.tui.commands import apply_command
from oud.settings import DEFAULT_SETTINGS

WIDTH = 98
SARABANDE = "examples/Sarabande_de_gautier.tab"  # authored breaks after bars 5, 9, 14, 19, ...


def _state(tmp_path: Path, **overrides: str) -> EditorState:
    config = str(tmp_path / "config.toml")
    shutil.copy("config.toml", config)  # never write the repository's config
    state = init_state(None, config_path=config)
    state.screen_width, state.screen_height = WIDTH, 40
    apply_command(state, f"e {SARABANDE}", config)
    state.settings.update(overrides)
    return state


def _first_system(state: EditorState) -> list[str]:
    lines = compose_editor_frame(state, height=40, width=WIDTH).frame.lines
    return [line for line in lines if re.match(r"^\s*\w?[+-]?\|-", line)][:1]


def _bars_in_first_system(state: EditorState) -> int:
    return _first_system(state)[0].count("|") - 1


def test_the_default_follows_the_lines_of_the_file() -> None:
    assert DEFAULT_SETTINGS["sourcebreaks"] == "on"


def test_a_system_ends_where_the_file_broke_the_line(tmp_path: Path) -> None:
    assert _bars_in_first_system(_state(tmp_path)) == 5


def test_turning_it_off_fills_the_width(tmp_path: Path) -> None:
    state = _state(tmp_path, sourcebreaks="off")

    assert _bars_in_first_system(state) >= 6
    assert len(_first_system(state)[0].rstrip()) >= WIDTH - 12


def test_the_setting_can_be_set_from_the_command_line(tmp_path: Path) -> None:
    state = _state(tmp_path)

    apply_command(state, "set sourcebreaks=off", state.config_path)

    assert state.settings["sourcebreaks"] == "off"
    assert _bars_in_first_system(state) >= 6


def test_a_bad_value_is_refused(tmp_path: Path) -> None:
    state = _state(tmp_path)

    apply_command(state, "set sourcebreaks=maybe", state.config_path)

    assert state.settings["sourcebreaks"] == "on"


def test_the_score_keeps_its_breaks_when_they_are_ignored(tmp_path: Path) -> None:
    state = _state(tmp_path, sourcebreaks="off")

    assert [i + 1 for i, bar in enumerate(state.piece.bars) if bar.system_break][:3] == [5, 9, 14]
