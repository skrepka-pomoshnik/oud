from oud.importers.ft3 import load_ft3
from oud.importers.ft3.musical.tab import parse_bar
from oud.importers.ft3.score import (
    _parallel_mixed_score_prefix_count,
    _parallel_raw_bar_targets,
)

def _ft3_bar_with_one_note() -> bytes:
    header = bytes(32)
    chord = bytes([0x02, 0x00, 0x00, 0x00])
    note = bytes([0x02, 0x61, 0x00, 0x00, 0x00])
    return header + chord + note

def test_parse_time_signature_ft3_single_triple_code_is_numeric() -> None:
    assert parse_bar(bytes([0x03, 0x00]) + bytes(30)).time_sig == "3/4"


def test_parallel_mixed_score_prefix_count_detects_raw_prefix_and_tab_suffix() -> None:
    assert _parallel_mixed_score_prefix_count(["raw", "raw", "tab", "tab"]) == 2
    assert _parallel_mixed_score_prefix_count(["raw", "tab", "raw", "tab"]) is None
    assert _parallel_mixed_score_prefix_count(["raw", "raw", "tab"]) is None


def test_parallel_raw_bar_targets_advance_per_raw_record() -> None:
    targets = _parallel_raw_bar_targets(
        ["barline-raw", "note-lyric-raw", "note-lyric-raw", "barline-raw", "text-score-raw"],
        bar_count=5,
    )
    assert targets == [0, 1, 2, 3, 4]


def test_load_ft3_merges_barline_raw_vocal_fragment_into_target_bar(tmp_path) -> None:
    chunk0 = bytearray(
        bytes(32) + bytes.fromhex("010000000001330500000000013308000000000400") + b"\x01\x00\x03\x00\x03Now\r\n",
    )
    chunk0[0] = 0x06
    chunk0[8] = 0x04
    chunk0[9] = 0x03
    chunk1 = bytes(32) + bytes.fromhex("010000000001330500000000013308000000000400") + b"\x01\x00\x03\x00\x03She\r\n"
    payload = (
        b"CPiece\x04Test\x03\x80CBar"
        + bytes(chunk0)
        + b"\x03\x80"
        + chunk1
        + b"\x03\x80"
        + _ft3_bar_with_one_note()
        + b"\x03\x80"
        + _ft3_bar_with_one_note()
    )
    path = tmp_path / "parallel_merge.ft3"
    path.write_bytes(payload)
    piece = load_ft3(str(path))
    bar0 = piece.bars[0]
    bar1 = piece.bars[1]
    assert len(bar0.melody_events) == 3
    assert [event.onset_index for event in bar0.melody_events] == [0, 1, 2]
    assert bar0.lyrics
    assert len(bar1.melody_events) == 3
    assert [event.onset_index for event in bar1.melody_events] == [0, 1, 2]
    assert bar1.lyrics
    assert bar0.lyrics[0].startswith("Now")
    assert bar1.lyrics[0].startswith("She")
    assert piece.imported_score is not None
    staffs = {staff.kind: staff for staff in piece.imported_score.staffs}
    assert {bar.source_bar_index for bar in staffs["note"].bars} >= {0, 1}
    assert {bar.source_bar_index for bar in staffs["lyrics"].bars} >= {0, 1}
