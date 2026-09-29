from __future__ import annotations

import pytest

from petrucci.core.music.time import parse_time_signature_value


@pytest.mark.parametrize(
    ("text", "expected"),
    [("C", (4, 4)), ("C|", (2, 2)), ("c|", (2, 2)), ("C/", (2, 2)), ("3/4", (3, 4)), ("6/8", (6, 8)), ("O", (3, 4))],
)
def test_meters_that_have_a_beat_structure_parse(text: str, expected: tuple[int, int]) -> None:
    assert parse_time_signature_value(text) == expected


@pytest.mark.parametrize("text", ["3", "", "x/4", "0/4", "3/0"])
def test_other_text_does_not_parse(text: str) -> None:
    assert parse_time_signature_value(text) is None
