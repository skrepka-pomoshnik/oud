from __future__ import annotations

from pathlib import Path

import pytest

from oud.editor.editing.primitives.undo import redo, undo
from oud.editor.services.bootstrap import init_state
from oud.editor.services.io.files import cmd_write
from petrucci.render_utils import note_type_to_denom
from tests.helpers_keyscript import keyscript_state, press_keys


def _typed_cells(state) -> tuple[dict[tuple[int, int, int], str], dict[tuple[int, int, int], int]]:
    return (dict(state.overrides), dict(state.durations))


@pytest.mark.parametrize("key_profile", ["vim+arrows", "casual"])
def test_french_typing_contract_is_identical_across_key_profiles(key_profile: str) -> None:
    state = keyscript_state(strings=7, style="french", bar_width=12, settings_override={"keys": key_profile})
    left = state.keycodes.left
    right = state.keycodes.right
    down = state.keycodes.down

    press_keys(state, ["i", "4", "a", left, down, "c", left, ".", right, "r", "/", "a", 27])

    assert state.overrides == {
        (0, 0, 0): "a",
        (0, 1, 0): "c",
        (0, 1, 1): "r",
        (0, 6, 2): "a",
    }
    assert state.durations == {
        (0, 0, 0): 8,
        (0, 1, 0): 8,
        (0, 1, 1): 8,
        (0, 6, 2): 8,
    }
    assert state.dotted == {(0, 0)}
    assert (state.cursor_bar, state.cursor_string, state.cursor_col) == (0, 1, 3)


def test_replace_preserves_rhythm_and_onset_attachments_through_undo_redo() -> None:
    state = keyscript_state(style="french")
    state.overrides[(0, 0, 0)] = "a"
    state.durations[(0, 0, 0)] = 8
    state.dotted.add((0, 0))
    state.ornaments[(0, 0)] = "tr"
    state.annotations[(0, 0)] = "dolce"
    state.ties.append((0, 0, 0))

    press_keys(state, ["R", "c", 27])
    assert state.overrides[(0, 0, 0)] == "c"
    assert state.durations[(0, 0, 0)] == 8
    assert state.dotted == {(0, 0)}
    assert state.ornaments == {(0, 0): "tr"}
    assert state.annotations == {(0, 0): "dolce"}
    assert state.ties == [(0, 0, 0)]

    undo(state, config_path="config.toml")
    assert state.overrides[(0, 0, 0)] == "a"
    assert state.durations[(0, 0, 0)] == 8
    assert state.dotted == {(0, 0)}
    redo(state, config_path="config.toml")
    assert state.overrides[(0, 0, 0)] == "c"


def test_two_digit_italian_ten_round_trips_as_one_typed_note(tmp_path: Path) -> None:
    config_path = str(tmp_path / "config.toml")
    state = keyscript_state(
        style="italian",
        bar_width=12,
        settings_override={"italianmultifret": "on"},
    )

    press_keys(state, ["i", ";", "4", ",", "1", "0", 27])
    assert _typed_cells(state) == ({(0, 0, 0): "1", (0, 0, 1): "0"}, {(0, 0, 0): 8})

    path = tmp_path / "italian-12.tab"
    cmd_write(state, str(path))
    reopened = init_state(str(path), config_path=config_path)

    chord = reopened.piece.bars[0].chords[0]
    assert note_type_to_denom(chord.note_type) == 8
    assert [(note.string, note.fret) for note in chord.notes] == [(1, 10)]


def test_tab_save_rejects_unrepresentable_italian_fret_without_writing(tmp_path: Path) -> None:
    state = keyscript_state(style="italian", settings_override={"italianmultifret": "on"})
    press_keys(state, ["i", ",", "1", "2", 27])
    path = tmp_path / "italian-12.tab"

    assert cmd_write(state, str(path)) is False
    assert state.message == "Write failed: TAB cannot preserve Italian fret 12; export LilyPond, MIDI, or MusicXML"
    assert not path.exists()


def test_note_rest_note_typing_keeps_each_edit_atomic() -> None:
    state = keyscript_state(style="french")

    press_keys(state, ["i", "a", 27, "h", "R", "r", 27])
    assert state.overrides[(0, 0, 0)] == "r"
    assert state.durations[(0, 0, 0)] == 4

    undo(state, config_path="config.toml")
    assert state.overrides[(0, 0, 0)] == "a"
    undo(state, config_path="config.toml")
    assert state.overrides == {}
    assert state.durations == {}

    redo(state, config_path="config.toml")
    redo(state, config_path="config.toml")
    assert state.overrides[(0, 0, 0)] == "r"
    assert state.durations[(0, 0, 0)] == 4
