from pathlib import Path

import pytest

from oud.exports.lilypond import lilypond_text
from oud.importers.ft3 import load_ft3
from oud.importers.ft3.text.codec import parse_ft3_text_record
from oud.importers.ft3.text.packed import decode_packed_lyrics
from petrucci.terminal.text.lyrics import piece_for_lyric_display


def _record(cells: list[str], *, rests: tuple[int, ...] = ()) -> bytes:
    notes = b"".join(
        bytes((1, 0x34, 1)) + (0x40 if index in rests else 0).to_bytes(4, "little") for index in range(len(cells))
    )
    encoded = [cell.encode("cp1252") for cell in cells]
    # Non-text geometry deliberately contains printable duration-code bytes.
    geometry = b"\x34\x00\x34\x00\x34\x00\x00\x00"
    text = b"".join(bytes((len(cell),)) + cell for cell in encoded)
    return bytes(30) + notes + geometry + len(cells).to_bytes(2, "little") + text + bytes(6)


def test_counted_cells_preserve_empty_anchors_and_repeated_syllables() -> None:
    record = parse_ft3_text_record(_record(["", "la", "la", "", "fin"], rests=(3,)))

    assert [(event.text, event.onset_index) for event in record.lyric_event_rows[0]] == [
        ("la", 1),
        ("la", 2),
        ("fin", 4),
    ]
    assert record.editorial_text == []
    assert len(record.melody_events) == 5
    assert record.melody_events[3].is_rest


def test_counted_cells_keep_stanza_slots_accents_and_elisions() -> None:
    record = parse_ft3_text_record(_record(["a\r\n", "me\r\npiù", "te_e\r\nme"]))

    assert [[event.text for event in row] for row in record.lyric_event_rows] == [
        ["a", "me", "te_e"],
        ["più", "me"],
    ]
    assert [event.onset_index for event in record.lyric_event_rows[1]] == [1, 2]
    assert [event.verse for event in record.lyric_event_rows[1]] == [1, 1]


def test_counted_cells_decode_hyphens_and_extenders_without_control_text() -> None:
    record = parse_ft3_text_record(_record(["gre -", "to", "_", "il", "cor"]))

    row = record.lyric_event_rows[0]
    assert [(event.text, event.syllabic) for event in row[:2]] == [("gre", "begin"), ("to", "end")]
    assert row[2].extender
    assert row[2].text == ""
    assert record.editorial_text == []
    assert all(text.kind == "lyrics" for text in record.structured_rows)


@pytest.mark.parametrize("suffix", [b"", b"\x00", b"\x01" * 6])
def test_counted_cells_reject_truncated_or_unknown_trailers(suffix: bytes) -> None:
    assert decode_packed_lyrics(_record(["Test"])[:-6] + suffix) is None


def test_counted_cells_do_not_guess_text_from_invalid_length_or_controls() -> None:
    source = _record(["hello"])
    assert decode_packed_lyrics(source[:-12] + b"\xffhello" + bytes(6)) is None
    assert decode_packed_lyrics(source.replace(b"hello", b"he\x01lo")) is None


def test_counted_cells_preserve_framed_commentary_without_singing_it() -> None:
    source = _record(["la", "fin"])
    text = b"Coda at end only."
    prefix = b"\x01\x00\x0fTimes New Roman\x01\x00" + bytes((len(text),)) + text
    record = parse_ft3_text_record(source[:30] + prefix + source[30:])

    assert record.editorial_text == ["Coda at end only."]
    assert record.lyrics == ["la fin"]
    assert [row.kind for row in record.structured_rows] == ["editorial", "lyrics"]


def test_counted_cells_preserve_literal_question_marks() -> None:
    record = parse_ft3_text_record(_record(["kind?\r\nme?"]))

    assert record.lyrics == ["kind?", "me?"]
    assert [row[0].text for row in record.lyric_event_rows] == ["kind?", "me?"]


def test_empty_counted_cells_do_not_turn_binary_geometry_into_lyrics() -> None:
    source = _record(["", ""]).replace(b"\x34\x00\x34\x00", b"Vz\x00\x00")
    record = parse_ft3_text_record(source)

    assert len(record.melody_events) == 2
    assert record.lyrics == [""]
    assert record.lyric_event_rows == [[]]
    assert record.editorial_text == []


def test_counted_cells_use_declared_source_count_with_numeric_music_font_cells() -> None:
    source = bytearray(_record(["=5", "6", ";"]))
    source[2:7] = b"\x04\x11\x00\x00\xff"
    source[28:30] = (2).to_bytes(2, "little")
    source[31] = 0x31  # Outside the current note-run decoder's duration subset.
    record = parse_ft3_text_record(bytes(source))

    assert record.lyrics == []
    assert record.lyric_event_rows == []
    assert record.structured_rows[0].kind == "control"
    assert record.structured_rows[0].tokens == ["=5", "6", ";"]


def test_empty_counted_cells_ignore_closing_record_metadata() -> None:
    source = _record(["", ""]) + b"C>950+" + bytes(10) + (24).to_bytes(2, "little")
    record = parse_ft3_text_record(source)

    assert record.lyrics == [""]
    assert record.lyric_event_rows == [[]]


def test_partial_note_grouping_does_not_promote_music_font_cells_to_lyrics() -> None:
    source = bytearray(_record(["7", "", ";"]))
    source[2:7] = b"\x04\x11\x00\x00\xff"
    source[28:30] = (1).to_bytes(2, "little")
    source[31] = source[38] = 0x31
    record = parse_ft3_text_record(bytes(source))

    assert record.lyrics == []
    assert record.lyric_event_rows == []
    assert record.structured_rows[0].tokens == ["7", "", ";"]


def test_load_preserves_empty_first_stanza_through_selection_and_export(tmp_path: Path) -> None:
    source = tmp_path / "sparse-stanzas.ft3"
    source.write_bytes(b"CPiece\x04Test\x03\x80CBar" + _record(["\r\nlate"]) + b"\x03\x80")
    piece = load_ft3(str(source))
    assert piece.imported_score is not None
    lyrics = next(staff for staff in piece.imported_score.staffs if staff.kind == "lyrics")

    assert lyrics.bars[0].lyrics == ["", "late"]
    assert len(lyrics.bars[0].lyric_event_rows) == 2
    assert lyrics.bars[0].lyric_event_rows[0] == []
    assert lyrics.bars[0].lyric_event_rows[1][0].verse == 1

    first = piece_for_lyric_display(piece, {"lyricmode": "first"})
    second = piece_for_lyric_display(piece, {"lyricmode": "current", "lyricverse": "2"})
    assert first.bars[0].lyrics == [""]
    assert second.bars[0].lyrics == ["late"]

    exported = lilypond_text(piece, {}, {}, 8)
    assert exported.count(r"\new Lyrics") == 2
    assert "\n  _\n}" in exported
    assert '\n  "late"\n}' in exported
