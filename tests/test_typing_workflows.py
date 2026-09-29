from __future__ import annotations

from fractions import Fraction
from pathlib import Path

import pytest

from oud.editor.editing.primitives.undo import redo, undo
from oud.editor.services.bootstrap import init_state
from oud.editor.services.io.files import cmd_write
from petrucci.core.model import Chord, Note
from petrucci.rendering.primitives.utils import note_type_to_denom
from tests.helpers_keyscript import keyscript_state, press_keys, tab_events


@pytest.mark.parametrize("key_profile", ["vim+arrows", "casual"])
def test_french_typing_contract_is_identical_across_key_profiles(key_profile: str) -> None:
    state = keyscript_state(strings=7, style="french", bar_width=12, settings_override={"keys": key_profile})
    left = state.keycodes.left
    right = state.keycodes.right
    down = state.keycodes.down

    press_keys(state, ["i", "4", "a", left, down, "c", left, ".", right, "z", "/", "a", 27])

    assert tab_events(state) == [("8.", [(1, 0), (2, 2)]), ("8", []), ("8", [(7, 0)])]
    assert state.overrides == {}
    assert (state.cursor_bar, state.cursor_string, state.cursor_onset) == (0, 1, Fraction(7, 16))


def test_replace_preserves_rhythm_and_onset_attachments_through_undo_redo() -> None:
    state = keyscript_state(style="french")
    state.piece.bars[0].chords = [Chord(5, True, None, [Note(1, 0, 0, left_fingering="1")])]
    state.ornaments[(0, 0)] = "tr"
    state.annotations[(0, 0)] = "dolce"
    state.ties.append((0, 0, 0))

    press_keys(state, ["R", "c", 27])
    assert tab_events(state) == [("8.", [(1, 2)])]
    assert state.piece.bars[0].chords[0].notes[0].left_fingering == "1"
    assert state.ornaments == {(0, 0): "tr"}
    assert state.annotations == {(0, 0): "dolce"}
    assert state.ties == [(0, 0, 0)]

    undo(state, config_path="config.toml")
    assert tab_events(state) == [("8.", [(1, 0)])]
    redo(state, config_path="config.toml")
    assert tab_events(state) == [("8.", [(1, 2)])]


def test_two_digit_italian_ten_round_trips_as_one_typed_note(tmp_path: Path) -> None:
    config_path = str(tmp_path / "config.toml")
    state = keyscript_state(
        style="italian",
        bar_width=12,
        settings_override={"italianmultifret": "on"},
    )

    press_keys(state, ["i", ";", "4", ",", "1", "0", 27])
    assert tab_events(state) == [("8", [(1, 10)])]

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

    press_keys(state, ["i", "a", 27, "h", "R", "z", 27])
    assert tab_events(state) == [("4", [])]

    undo(state, config_path="config.toml")
    assert tab_events(state) == [("4", [(1, 0)])]
    undo(state, config_path="config.toml")
    assert tab_events(state) == []

    redo(state, config_path="config.toml")
    redo(state, config_path="config.toml")
    assert tab_events(state) == [("4", [])]
