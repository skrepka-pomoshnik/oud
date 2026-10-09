"""Guitar tab shows its meter as numerator over denominator on two staff lines."""

from __future__ import annotations

import re
from pathlib import Path

from oud.editor.services.bootstrap import init_state
from oud.editor.services.screen.compose import compose_editor_frame
from petrucci.input.tablature.policy import time_cue_lane, time_sig_inline_rows
from tests.helpers_ft3 import write_galliard

STUDY = "tests/fixtures/musicxml/guitar_study_am.musicxml"


def test_a_fraction_is_stacked_on_two_lines() -> None:
    assert time_sig_inline_rows("3/4", "3/4", style_mode="stacked") == [" 3", " 4"]
    assert time_sig_inline_rows("12/8", "12/8", style_mode="stacked") == ["12", " 8"]


def test_common_and_cut_time_are_stacked_as_their_numbers() -> None:
    assert time_sig_inline_rows("C", "C", style_mode="stacked") == [" 4", " 4"]
    assert time_sig_inline_rows("C|", "C|", style_mode="stacked") == [" 2", " 2"]


def test_the_symbol_style_is_unchanged_for_lute_tablature() -> None:
    assert time_sig_inline_rows("3/4", "3/4", style_mode="symbol") == [" 3"]


def test_a_stacked_cue_reserves_a_gap_before_the_first_fret() -> None:
    assert time_cue_lane("4/4", show_time=True, scale_bar=True, style_mode="stacked") == 3
    assert time_cue_lane("4/4", show_time=True, scale_bar=True, style_mode="symbol") == 2
    assert time_cue_lane("4/4", show_time=False, scale_bar=True, style_mode="stacked") == 0


def _first_staff_rows(path: str, tmp_path: Path, **settings: str) -> list[str]:
    state = init_state(path, config_path=str(tmp_path / "config.toml"))
    state.settings.update(settings)
    state.screen_width, state.screen_height = 100, 40
    lines = compose_editor_frame(state, height=40, width=100).frame.lines
    return [line for line in lines if re.match(r"^\s*\w?[+-:]?[|:]-", line)][:6]


def test_a_guitar_file_shows_the_meter_stacked_with_a_gap_before_the_notes(tmp_path: Path) -> None:
    rows = _first_staff_rows(STUDY, tmp_path)

    stacked = [(index, row) for index, row in enumerate(rows) if re.search(r"[|:]- 4", row)]
    assert [index for index, _row in stacked] == [2, 3]
    # The fret that follows is not touching the 4 any more.
    assert not any(re.search(r"[|:]- 4\d", row) for row in rows)


def test_a_lute_file_keeps_the_single_mensuration_digit(tmp_path: Path) -> None:
    rows = _first_staff_rows(str(write_galliard(tmp_path)), tmp_path)

    assert sum(1 for row in rows if re.search(r"[|:]- *4", row)) <= 1
