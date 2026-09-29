from pathlib import Path

import pytest

from oud.editor.navigation.view.focus import current_view_staff, visible_view_staffs
from oud.editor.services.bootstrap import init_state
from oud.editor.services.screen.status import status_line
from oud.importers.ft3 import load_ft3
from petrucci.adapters.duet import duet_bar_mapping
from petrucci.core.imported import project_imported_staff
from tests.helpers_keyscript import press_keys

MIXED_FT3 = "tests/fixtures/ft3/corpus/can_she_excuse.ft3"
DUET_FT3 = "tests/fixtures/ft3/corpus/willoughby_duet.ft3"


@pytest.mark.ft3_corpus
def test_mixed_view_staff_focus_cycles_visible_lanes(tmp_path: Path) -> None:
    state = init_state(MIXED_FT3, config_path=str(tmp_path / "config.toml"))
    labels = [staff.label for staff in visible_view_staffs(state.piece)]
    assert labels[:3] == ["Tab", "Melody", "Lyrics"]
    assert current_view_staff(state).label == "Tab"

    press_keys(state, ["j"])
    assert current_view_staff(state).label == "Melody"
    assert "focus:Melody" in status_line(state)

    press_keys(state, ["k"])
    assert current_view_staff(state).label == "Tab"


@pytest.mark.ft3_corpus
def test_duet_view_staff_focus_moves_cursor_to_matching_raw_staff(tmp_path: Path) -> None:
    state = init_state(DUET_FT3, config_path=str(tmp_path / "config.toml"))
    initial_staff, initial_logical = duet_bar_mapping(state.cursor_bar, piece=state.piece)
    assert initial_staff == 0

    press_keys(state, ["j"])

    staff, logical = duet_bar_mapping(state.cursor_bar, piece=state.piece)
    assert staff == 1
    assert logical == initial_logical
    assert current_view_staff(state).label == "Lute 2"
    assert "focus:Lute 2" in status_line(state)


def test_forced_single_staff_view_keeps_string_navigation(tmp_path: Path) -> None:
    state = init_state(
        "tests/fixtures/ft3/corpus/examples/02_forlorne_hope_8C.ft3",
        config_path=str(tmp_path / "config.toml"),
        read_only=True,
    )
    assert len(visible_view_staffs(state.piece)) == 1

    press_keys(state, ["j"])

    assert state.cursor_string == 1


@pytest.mark.ft3_corpus
def test_polyphonic_ft3_focus_projects_the_selected_voice_without_mutating_piece() -> None:
    piece = load_ft3("tests/fixtures/ft3/corpus/05_can_she_excuse/can_she_excuse_4_part.ft3")
    staffs = visible_view_staffs(piece)
    soprano = next(staff for staff in staffs if staff.label == "soprano")
    bass = next(staff for staff in staffs if staff.label == "bass")
    soprano_piece = project_imported_staff(piece, soprano.source_index)
    bass_piece = project_imported_staff(piece, bass.source_index)
    assert soprano_piece.bars[0].melody_events != bass_piece.bars[0].melody_events
    assert piece.bars[0].melody_events == soprano_piece.bars[0].melody_events
