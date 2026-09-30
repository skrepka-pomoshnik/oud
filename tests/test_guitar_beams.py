"""Guitar-style rhythm rows: beams join runs of short notes within a beat."""

from __future__ import annotations

import re
from pathlib import Path

from oud.editor.services.bootstrap import init_state
from oud.editor.services.screen.compose import compose_editor_frame
from petrucci.rendering.bar.beams import beam_groups, beam_level, guitar_rows
from tests.helpers_ft3 import write_galliard

Position = tuple[int, int, bool]


def _cols(groups: list[list[Position]]) -> list[list[int]]:
    return [[col for col, _denom, _dot in group] for group in groups]


def test_beam_levels_follow_the_note_value() -> None:
    assert [beam_level(denom) for denom in (1, 2, 4, 8, 16, 32)] == [0, 0, 0, 1, 2, 2]


def test_eighths_are_grouped_by_the_beat() -> None:
    eighths: list[Position] = [(0, 8, False), (2, 8, False), (4, 8, False), (6, 8, False)]

    assert _cols(beam_groups(eighths)) == [[0, 2], [4, 6]]


def test_a_quarter_note_breaks_a_run_and_carries_no_beam() -> None:
    notes: list[Position] = [(0, 8, False), (2, 8, False), (4, 4, False), (8, 8, False), (10, 8, False)]

    assert _cols(beam_groups(notes)) == [[0, 2], [8, 10]]


def test_a_dotted_eighth_and_a_sixteenth_share_a_beat() -> None:
    notes: list[Position] = [(0, 8, True), (5, 16, False)]

    assert _cols(beam_groups(notes)) == [[0, 5]]


def test_two_eighths_are_joined_by_a_single_beam_under_their_stems() -> None:
    beams, stems = guitar_rows([(2, 8, False), (6, 8, False)], 10)

    assert "".join(stems) == "  |   |   "
    assert "".join(beams) == "  _____   "


def test_sixteenths_are_joined_by_a_double_beam() -> None:
    beams, _stems = guitar_rows([(0, 16, False), (3, 16, False)], 6)

    assert "".join(beams) == "====  "


def test_an_eighth_beside_a_sixteenth_keeps_the_single_beam() -> None:
    beams, _stems = guitar_rows([(0, 8, True), (5, 16, False)], 8)

    assert "".join(beams) == "______  "


def test_a_lone_short_note_gets_its_flag_beside_the_stem() -> None:
    beams, stems = guitar_rows([(3, 8, False), (6, 4, False), (9, 16, False)], 12)

    assert "".join(stems) == "   |  |  |  "
    assert "".join(beams) == "    _     = "


def test_a_dotted_note_shows_its_dot_after_the_stem() -> None:
    _beams, stems = guitar_rows([(1, 4, True)], 5)

    assert "".join(stems) == " |.  "


def test_a_whole_note_has_no_stem() -> None:
    beams, stems = guitar_rows([(0, 1, False)], 4)

    assert ("".join(stems), "".join(beams)) == ("    ", "    ")


def test_repeated_durations_keep_every_stem_in_guitar_style(tmp_path: Path) -> None:
    state = init_state(str(write_galliard(tmp_path)), config_path=str(tmp_path / "config.toml"))
    state.settings.update(flagstyle="guitar", flagplace="below", flagredundant="on", style="italian")
    state.screen_width, state.screen_height = 110, 40
    lines = compose_editor_frame(state, height=40, width=110).frame.lines
    staff_lines = [i for i, line in enumerate(lines[:12]) if re.match(r"^\s*\w?[|:]-", line)]
    stems = lines[staff_lines[0] + 6]  # the row under the sixth course

    # With hidden repeats only the changes of duration would keep a stem.
    assert stems.count("|") >= 6
