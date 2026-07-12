from pathlib import Path

from oud.core.ft3 import load_ft3
from oud.editor.init import init_state
from oud.editor.status import status_line
from oud.editor.view_focus import current_view_staff, visible_view_staffs
from oud.petrucci.duet_score import duet_bar_mapping
from oud.petrucci.imported_score import project_imported_staff
from tests.helpers_keyscript import press_keys

MIXED_FT3 = "lutemusic/can_she_excuse.ft3"
DUET_FT3 = "lutemusic/willoughby_duet.ft3"


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
        "examples/02_forlorne_hope_8C.ft3",
        config_path=str(tmp_path / "config.toml"),
        read_only=True,
    )
    assert len(visible_view_staffs(state.piece)) == 1

    press_keys(state, ["j"])

    assert state.cursor_string == 1


def test_polyphonic_ft3_focus_projects_the_selected_voice_without_mutating_piece() -> None:
    piece = load_ft3("lutemusic/05_can_she_excuse/can_she_excuse_4_part.ft3")
    staffs = visible_view_staffs(piece)
    soprano = next(staff for staff in staffs if staff.label == "soprano")
    bass = next(staff for staff in staffs if staff.label == "bass")
    soprano_piece = project_imported_staff(piece, soprano.source_index)
    bass_piece = project_imported_staff(piece, bass.source_index)
    assert soprano_piece.bars[0].melody_events != bass_piece.bars[0].melody_events
    assert piece.bars[0].melody_events == soprano_piece.bars[0].melody_events
