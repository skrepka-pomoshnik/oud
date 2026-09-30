"""Guitar-style rhythm: stems and flags below the staff (`flagstyle=guitar`, `flagplace=below`)."""

from __future__ import annotations

from pathlib import Path

from oud.editor.services.bootstrap import init_state
from oud.editor.services.screen.compose import compose_editor_frame
from oud.settings import DEFAULT_SETTINGS
from petrucci.engraving.layout.map import LayoutBlockPolicy, block_height, layout_block_rows
from petrucci.rendering.primitives.helpers import flag_symbols
from tests.helpers_ft3 import write_galliard
from tests.helpers_keyscript import keyscript_state

STUDY = "tests/fixtures/musicxml/guitar_study_am.musicxml"


def _policy(*, below: bool, lyric_rows: int = 0) -> LayoutBlockPolicy:
    return LayoutBlockPolicy(
        strings=6,
        include_meta=True,
        show_dur=False,
        show_extras=False,
        show_tuplets=False,
        show_tactus=False,
        double_stems=True,
        show_lyrics=lyric_rows > 0,
        lyric_rows_count=lyric_rows,
        flags_below=below,
    )


def _rows(policy: LayoutBlockPolicy) -> dict[str, int]:
    rows = layout_block_rows(policy)
    return {key: value for key, value in rows.items() if value is not None}


def test_flag_rows_sit_above_the_staff_by_default() -> None:
    rows = _rows(_policy(below=False))

    assert rows["flag"] < rows["flag2"] < rows["staff"]


def test_below_the_stems_touch_the_staff_and_the_flags_hang_under_them() -> None:
    rows = _rows(_policy(below=True))

    assert rows["flag2"] == rows["staff"] + 6
    assert rows["flag"] == rows["flag2"] + 1


def test_the_block_is_as_tall_either_way() -> None:
    assert block_height(_policy(below=True)) == block_height(_policy(below=False))


def test_lyrics_below_the_staff_move_under_the_flags() -> None:
    rows = _rows(_policy(below=True, lyric_rows=1))

    assert rows["lyric"] == rows["flag"] + 1


def test_the_guitar_flag_style_draws_a_stem_and_an_underscore() -> None:
    assert flag_symbols("guitar") == ("|", "_")


def _frame(place: str) -> list[str]:
    from oud.importers.musicxml import load_musicxml  # noqa: PLC0415

    state = keyscript_state(
        piece=load_musicxml(STUDY),
        width=100,
        height=24,
        settings_override={"flagstyle": "guitar", "flagplace": place, "style": "italian"},
    )
    return compose_editor_frame(state, height=24, width=100).frame.lines


def test_the_rendered_flags_follow_the_setting() -> None:
    above, below = _frame("above"), _frame("below")
    staff_row = next(i for i, line in enumerate(above) if line.lstrip().startswith("e|"))
    below_staff_row = next(i for i, line in enumerate(below) if line.lstrip().startswith("e|"))

    assert any("_" in line and "-" not in line for line in above[:staff_row])
    assert not any("_" in line and "-" not in line for line in below[:below_staff_row])
    assert any("_" in line and "-" not in line for line in below[below_staff_row : below_staff_row + 9])


def test_an_imported_guitar_file_opens_with_guitar_flags_below(tmp_path: Path) -> None:
    state = init_state(STUDY, config_path=str(tmp_path / "config.toml"))

    assert (state.settings["flagstyle"], state.settings["flagplace"]) == ("guitar", "below")


def test_a_lute_file_keeps_the_lute_flags(tmp_path: Path) -> None:
    state = init_state(str(write_galliard(tmp_path)), config_path=str(tmp_path / "config.toml"))

    assert (state.settings["flagstyle"], state.settings["flagplace"]) == (
        DEFAULT_SETTINGS["flagstyle"],
        DEFAULT_SETTINGS["flagplace"],
    )
