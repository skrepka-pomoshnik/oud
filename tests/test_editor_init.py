from pathlib import Path

from oud.editor.init import init_state


def test_init_state_new_file_defaults_to_8_bars(tmp_path: Path) -> None:
    cfg = tmp_path / "config.toml"
    state = init_state(None, config_path=str(cfg))
    assert len(state.piece.bars) == 8


def test_init_state_missing_path_defaults_to_8_bars(tmp_path: Path) -> None:
    cfg = tmp_path / "config.toml"
    missing = tmp_path / "new_piece.ft3"
    state = init_state(str(missing), config_path=str(cfg))
    assert len(state.piece.bars) == 8


def test_init_state_preserves_inferred_ft3_extra_courses() -> None:
    state = init_state("lutemusic/pavan_01_8C.ft3", config_path="config.toml")
    assert state.piece.strings >= 8


def test_init_state_shows_import_warning_for_ft3_text_records() -> None:
    state = init_state("lutemusic/can_she_excuse.ft3", config_path="config.toml")
    assert "lyric/melody text records" in state.message
