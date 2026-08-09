from pathlib import Path

import pytest

from oud.presentation.command_io import OutputExistsError, atomic_export, atomic_output_path, atomic_write_text


def test_atomic_write_refuses_overwrite_and_preserves_existing_data(tmp_path: Path) -> None:
    target = tmp_path / "score.txt"
    target.write_text("original", encoding="utf-8")

    with pytest.raises(OutputExistsError, match="refusing to overwrite"):
        atomic_write_text(target, "replacement", overwrite=False)

    assert target.read_text(encoding="utf-8") == "original"


def test_atomic_write_replaces_only_with_explicit_authorization(tmp_path: Path) -> None:
    target = tmp_path / "score.txt"
    target.write_text("original", encoding="utf-8")

    atomic_write_text(target, "replacement", overwrite=True)

    assert target.read_text(encoding="utf-8") == "replacement"


def test_atomic_export_cleans_interrupted_temporary_file(tmp_path: Path) -> None:
    target = tmp_path / "score.mid"

    def interrupted(path: str) -> None:
        Path(path).write_bytes(b"partial")
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        atomic_export(target, interrupted, overwrite=False)

    assert not target.exists()
    assert list(tmp_path.iterdir()) == []


def test_atomic_publish_detects_output_created_during_export(tmp_path: Path) -> None:
    target = tmp_path / "score.txt"

    with pytest.raises(OutputExistsError), atomic_output_path(target, overwrite=False) as temporary:
        temporary.write_text("new", encoding="utf-8")
        target.write_text("racing writer", encoding="utf-8")

    assert target.read_text(encoding="utf-8") == "racing writer"
    assert sorted(path.name for path in tmp_path.iterdir()) == ["score.txt"]
