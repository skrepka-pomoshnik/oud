from pathlib import Path

import pytest

from oud.importers.ft3 import load_ft3
from oud.importers.ft3.musical.note_records import decode_ft3_note_record
from petrucci import notation_score_from_piece


def _note_group(attributes: int, *, pitch_row: int = 5, duration: int = 0x34) -> bytes:
    return bytes([1, duration, pitch_row]) + attributes.to_bytes(4, "little")


@pytest.mark.parametrize(
    ("attributes", "grace", "courtesy"),
    [
        (0x00000000, False, False),
        (0x00008000, True, False),
        (0x00008002, True, False),
        (0x00038010, False, False),
        (0x000C8000, False, False),
        (0x00808000, True, False),
        (0x80002000, False, True),
        (0x80008000, True, True),
        (0x00002000, False, False),
    ],
)
def test_note_attributes_distinguish_full_tags_from_independent_flags(
    attributes: int,
    grace: bool,
    courtesy: bool,
) -> None:
    events = decode_ft3_note_record(bytes(32) + _note_group(attributes))

    assert len(events) == 1
    event = events[0]
    assert event.grace is grace
    assert event.courtesy_accidental is courtesy
    assert event.tie_from_previous is False
    assert event.accidental_flags == attributes & 0xFFFF
    assert event.ft3_layout_flags == ((attributes >> 16) or None)


def test_equal_neighboring_pitches_do_not_turn_a_grace_tag_into_a_tie() -> None:
    record = bytes(32) + _note_group(0) + _note_group(0x8000) + _note_group(0)
    events = decode_ft3_note_record(record)

    assert [event.text for event in events] == ["a", "a", "a"]
    assert [event.grace for event in events] == [False, True, False]
    assert not any(event.tie_from_previous for event in events)


def test_imported_initial_grace_has_no_incoming_tie_and_does_not_advance_time(tmp_path: Path) -> None:
    record = bytes(32) + b"".join(
        [
            _note_group(0x8000, pitch_row=6),
            _note_group(0, pitch_row=5, duration=0x33),
            _note_group(0, pitch_row=4, duration=0x33),
        ],
    )
    path = tmp_path / "initial-grace.ft3"
    path.write_bytes(b"CPiece{\\rtf1 Grace}\nensemble:bass\nCBar" + record)

    piece = load_ft3(str(path))
    score = notation_score_from_piece(piece)
    assert len(score.staffs) == 1
    assert len(score.staffs[0].measures) == 1
    events = score.staffs[0].measures[0].events
    assert len(events) == 3
    assert [event.grace for event in events] == [True, False, False]
    assert events[0].onset == events[1].onset == 0
    assert events[2].onset > 0
