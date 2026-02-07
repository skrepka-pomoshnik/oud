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
