from oud.core.model import Bar, Chord, Note, Piece
from oud.core.view_model import (
    _bar_display_width,
    _bars_fit,
    _inline_bass_row,
    _parse_time_signature,
    _scale_col,
    _scale_row,
    _string_label,
    _tactus_row,
    _tuning_labels,
)
from oud.ui.render import _apply_overrides, _bass_strings_used


def test_parse_time_signature() -> None:
    assert _parse_time_signature("C") == (4, 4, "C")
    assert _parse_time_signature("3/4") == (3, 4, "O")
    assert _parse_time_signature("6/8") == (6, 8, "6/8")
    assert _parse_time_signature("bad") == (0, 0, "")


def test_tactus_row_marks_beats() -> None:
    row = _tactus_row(8, 4)
    assert row[0] == "|"
    assert row[2] == "|"
    assert row[4] == "|"
    assert row[6] == "|"


def test_tuning_labels_relative_and_absolute() -> None:
    tuning = "g2c3f3a3d4g4"
    relative = _tuning_labels(tuning, 6, show_octaves=False)
    absolute = _tuning_labels(tuning, 6, show_octaves=True)
    assert relative == ["g", "d", "a", "f", "c", "g"]
    assert absolute == ["g4", "d4", "a3", "f3", "c3", "g2"]


def test_tuning_labels_do_not_append_numbers_when_short() -> None:
    tuning = "g2c3f3a3d4g4"
    labels = _tuning_labels(tuning, 7, show_octaves=False)
    assert labels[-1] == ""
    assert labels[:-1] == ["g", "d", "a", "f", "c", "g"]


def test_tuning_labels_include_bass_tokens() -> None:
    tuning = "g2c3f3a3d4g4"
    labels = _tuning_labels(
        tuning,
        7,
        show_octaves=False,
        bass=["f2"],
    )
    assert labels == ["g", "d", "a", "f", "c", "g", "f"]


def test_tuning_labels_bass_order_high_to_low() -> None:
    tuning = "g2c3f3a3d4g4"
    labels = _tuning_labels(
        tuning,
        9,
        show_octaves=False,
        bass=["f2", "d2", "c2"],
    )
    assert labels == ["g", "d", "a", "f", "c", "g", "f", "d", "c"]


def test_inline_bass_row_renders_dashes() -> None:
    row = ["-", "-", "a", "-", "-", "-", "b", "-"]
    inline = _inline_bass_row(row)
    assert inline[1] == "-"
    assert inline[2] == "a"
    assert inline[3] == "-"
    assert inline[5] == "-"
    assert inline[6] == "b"
    assert inline[7] == "-"


def test_bass_strings_used_tracks_overrides_and_chords() -> None:
    piece = Piece(strings=7)
    chord = Chord(note_type=4, dotted=False, grid=None, notes=[Note(string=7, fret=3, raw_pos=0)])
    piece.bars = [Bar(chords=[chord])]
    overrides = {(0, 6, 0): "a"}
    used = _bass_strings_used(piece, overrides)
    assert used == {6}


def test_apply_overrides_renders_rest_marker() -> None:
    cells = [["-"] * 4 for _ in range(6)]
    overrides = {(0, 0, 1): "r"}
    _apply_overrides(cells, overrides, 0, 6, 4)
    assert cells[0][1] == "_"
    assert cells[0][2] == "."


def test_scale_col_maps_endpoints() -> None:
    assert _scale_col(0, 5, 9) == 0
    assert _scale_col(4, 5, 9) == 8


def test_scale_row_spreads_notes_with_min_gap() -> None:
    row = ["-", "a", "-", "b", "-"]
    scaled = _scale_row(row, 10, "-")
    positions = [idx for idx, ch in enumerate(scaled) if ch != "-"]
    assert len(positions) == 2
    assert positions[1] - positions[0] >= 2


def test_bar_display_width_accounts_for_notes_and_flags() -> None:
    bar = Bar()
    overrides = {(0, 0, 0): "a", (0, 0, 3): "b"}
    durations = {(0, 0, 0): 32}
    width = _bar_display_width(
        bar,
        bar_index=0,
        bar_width=8,
        overrides=overrides,
        durations=durations,
        default_duration=4,
    )
    assert width >= 5


def test_bars_fit_respects_usable_width() -> None:
    bars = [Bar(), Bar(), Bar()]
    overrides = {(0, 0, 0): "a", (1, 0, 0): "b", (2, 0, 0): "c"}
    durations: dict[tuple[int, int, int], int] = {}
    fit_two = _bars_fit(
        bars,
        bar_offset=0,
        bar_gap=1,
        usable_width=7,
        bar_width=8,
        overrides=overrides,
        durations=durations,
        default_duration=4,
        dotted=None,
    )
    fit_one = _bars_fit(
        bars,
        bar_offset=0,
        bar_gap=1,
        usable_width=3,
        bar_width=8,
        overrides=overrides,
        durations=durations,
        default_duration=4,
        dotted=None,
    )
    assert fit_two == 2
    assert fit_one == 1


def test_string_label_bass_numeric_and_slash() -> None:
    labels = ["g", "d", "a", "f", "c", "g", "f"]
    assert _string_label(6, 7, labels, "numeric").strip() == "7"
    assert _string_label(6, 7, labels, "slash").strip() == "/"
    assert _string_label(7, 8, [*labels, "e"], "slash").strip() == "//"


def test_string_label_uses_bass_styles() -> None:
    tuning_labels = ["g", "d", "a", "f", "c", "g", "f"]
    assert _string_label(6, 7, tuning_labels, "numeric") == " 7"
    assert _string_label(6, 7, tuning_labels, "slash") == " /"
    assert _string_label(6, 7, tuning_labels, "tuning") == " f"
