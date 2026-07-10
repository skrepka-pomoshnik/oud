from __future__ import annotations

from pathlib import Path

from oud.editor.file_ops import cmd_write
from oud.editor.init import init_state
from oud.exports.lilypond import export_lilypond
from oud.exports.midi import export_midi
from tests.helpers_keyscript import press_keys


def test_real_piece_edit_save_export_and_reopen(tmp_path: Path) -> None:
    config_path = str(tmp_path / "config.toml")
    state = init_state("lutemusic/pavan_01_8C.ft3", config_path=config_path)
    original_bar_count = len(state.piece.bars)

    press_keys(state, ["i", "a", 27, "h", "R", "b", 27])
    assert state.overrides[(0, 0, 0)] == "b"
    assert state.modified is True

    saved_tab = tmp_path / "edited.tab"
    midi_path = tmp_path / "edited.mid"
    lilypond_path = tmp_path / "edited.ly"
    cmd_write(state, str(saved_tab))
    export_midi(
        str(midi_path),
        state.piece,
        state.overrides,
        state.durations,
        state.bar_width,
        settings=state.settings,
        dotted=state.dotted,
        ornaments=state.ornaments,
    )
    export_lilypond(
        str(lilypond_path),
        state.piece,
        state.overrides,
        state.durations,
        state.bar_width,
        settings=state.settings,
    )

    assert state.modified is False
    assert midi_path.read_bytes().startswith(b"MThd")
    assert "\\new TabStaff" in lilypond_path.read_text(encoding="utf-8")

    reopened = init_state(str(saved_tab), config_path=config_path)
    assert reopened.path == str(saved_tab)
    assert len(reopened.piece.bars) == original_bar_count
    assert reopened.piece.title == state.piece.title
