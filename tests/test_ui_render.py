from ui.render import _inline_bass_row, _parse_time_signature, _tactus_row, _tuning_labels


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


def test_inline_bass_row_renders_dashes() -> None:
    row = ["-", "-", "a", "-", "-", "-", "b", "-"]
    inline = _inline_bass_row(row)
    assert inline[1] == "-"
    assert inline[2] == "a"
    assert inline[3] == "-"
    assert inline[5] == "-"
    assert inline[6] == "b"
    assert inline[7] == "-"
