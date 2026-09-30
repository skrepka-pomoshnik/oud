"""With no config file the score fills the terminal width."""

from __future__ import annotations

from pathlib import Path

from oud.editor.services.bootstrap import init_state
from oud.editor.services.screen.compose import compose_editor_frame
from oud.settings import DEFAULT_SETTINGS

WIDTH = 150


def _widest_line(tmp_path: Path, **overrides: str) -> int:
    state = init_state("examples/triste.tab", config_path=str(tmp_path / "missing.toml"))
    state.settings.update(overrides)
    state.screen_width, state.screen_height = WIDTH, 40
    lines = compose_editor_frame(state, height=40, width=WIDTH).frame.lines
    return max(len(line.rstrip()) for line in lines[:30])


def test_the_default_line_length_is_unlimited() -> None:
    assert DEFAULT_SETTINGS["linelen"] == "0"


def test_a_score_fills_the_terminal_width_by_default(tmp_path: Path) -> None:
    assert _widest_line(tmp_path) >= WIDTH - 2


def test_a_line_length_still_caps_the_width(tmp_path: Path) -> None:
    assert _widest_line(tmp_path, linelen="80") <= 80
