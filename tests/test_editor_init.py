from pathlib import Path

import pytest

from oud.editor.services.bootstrap import init_state
from petrucci.core.model import Piece


def test_init_state_new_file_defaults_to_8_bars(tmp_path: Path) -> None:
    cfg = tmp_path / "config.toml"
    state = init_state(None, config_path=str(cfg))
    assert len(state.piece.bars) == 8
    assert state.visible_message == ""


def test_init_state_missing_path_defaults_to_8_bars(tmp_path: Path) -> None:
    cfg = tmp_path / "config.toml"
    missing = tmp_path / "new_piece.ft3"
    state = init_state(str(missing), config_path=str(cfg))
    assert len(state.piece.bars) == 8


def test_init_state_missing_tab_path_starts_a_new_document(tmp_path: Path) -> None:
    cfg = tmp_path / "config.toml"
    missing = tmp_path / "new_piece.tab"
    state = init_state(str(missing), config_path=str(cfg))
    assert len(state.piece.bars) == 8
    assert state.tab_data is None
    assert state.piece.import_warnings == [f"Missing file: {missing}"]
    assert not missing.exists()


@pytest.mark.ft3_corpus
def test_init_state_preserves_inferred_ft3_extra_courses() -> None:
    state = init_state("tests/fixtures/ft3/corpus/pavan_01_8C.ft3", config_path="config.toml")
    assert state.piece.strings >= 8


@pytest.mark.ft3_corpus
def test_init_state_loads_represented_ft3_text_without_warning() -> None:
    state = init_state("tests/fixtures/ft3/corpus/can_she_excuse.ft3", config_path="config.toml")
    assert state.message == ""
    assert state.piece.import_warnings == []
    assert state.read_only is True
    assert state.visible_message == ""
    assert any(bar.lyric_event_rows for bar in state.piece.bars)


def test_init_state_marks_read_only_viewer_mode(tmp_path: Path) -> None:
    cfg = tmp_path / "config.toml"
    state = init_state(None, config_path=str(cfg), read_only=True)
    assert state.read_only is True
    assert "Read-only" in state.message


def test_init_state_directory_path_falls_back_to_new_piece_with_warning(tmp_path: Path) -> None:
    cfg = tmp_path / "config.toml"
    folder = tmp_path / "scores"
    folder.mkdir()
    state = init_state(str(folder), config_path=str(cfg))
    assert state.path is None
    assert len(state.piece.bars) == 8
    assert "Ignored directory path" in state.message


def test_init_state_invalid_file_falls_back_to_new_piece_with_warning(
    tmp_path: Path,
    monkeypatch,
) -> None:
    cfg = tmp_path / "config.toml"
    broken = tmp_path / "broken.ft3"
    broken.write_text("not a real ft3", encoding="utf-8")
    warned = Piece(title="broken", bars=[])
    warned.import_warnings.append("Could not open broken.ft3: bad parse")
    monkeypatch.setattr("oud.editor.services.bootstrap.load_piece_data", lambda _path: (warned, {}, {}, set(), None))
    state = init_state(str(broken), config_path=str(cfg))
    assert state.path is None
    assert len(state.piece.bars) == 8
    assert "Could not open broken.ft3" in state.message


def test_init_state_empty_tab_falls_back_with_visible_warning(tmp_path: Path) -> None:
    cfg = tmp_path / "config.toml"
    broken = tmp_path / "broken.tab"
    broken.write_text("not tablature\n", encoding="utf-8")

    state = init_state(str(broken), config_path=str(cfg))

    assert state.path is None
    assert len(state.piece.bars) == 8
    assert "no recoverable bars" in state.message
    assert ":info" in state.message
