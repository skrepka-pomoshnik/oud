"""System breaks read from the layout tail of FT3 tablature records."""

from __future__ import annotations

import struct
from pathlib import Path

from oud.importers.ft3 import load_ft3
from oud.importers.ft3.musical.layout import system_value
from tests.helpers_ft3 import chord, ft3_bar, write_ft3


def _bar(system: float | None) -> bytes:
    return ft3_bar([chord((1, 0)), chord((2, 1))], system=system)


def test_a_change_of_the_system_value_ends_a_system(tmp_path: Path) -> None:
    bars = [_bar(-4.3), _bar(-4.3), _bar(-5.5), _bar(-5.5), _bar(-5.5), _bar(-2.5)]

    piece = load_ft3(str(write_ft3(tmp_path / "systems.ft3", "Systems", bars)))

    assert [bar.system_break for bar in piece.bars] == [False, True, False, False, True, False]


def test_records_without_a_tail_get_no_breaks(tmp_path: Path) -> None:
    piece = load_ft3(str(write_ft3(tmp_path / "plain.ft3", "Plain", [_bar(None), _bar(None), _bar(None)])))

    assert not any(bar.system_break for bar in piece.bars)


def test_the_value_is_read_after_the_objects_and_the_tail_count() -> None:
    assert system_value(_bar(-4.3)) == struct.pack("<f", -4.3)
    assert system_value(_bar(None)) is None


def test_a_file_whose_value_changes_on_nearly_every_bar_gets_no_breaks(tmp_path: Path) -> None:
    bars = [_bar(-1.0 - index) for index in range(6)]

    piece = load_ft3(str(write_ft3(tmp_path / "per_bar.ft3", "Per bar", bars)))

    assert not any(bar.system_break for bar in piece.bars)
