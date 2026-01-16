from render_utils import format_fret


def test_format_fret_french_excludes_j() -> None:
    assert format_fret("french", 9) == "k"


def test_format_fret_french_alt_c() -> None:
    assert format_fret("french", 2, french_c="alt") == "r"


def test_format_fret_french_tail_e() -> None:
    assert format_fret("french", 4, french_e="tail") == "E"
