from oud.core.ft3_text import is_ft3_text_record, parse_ft3_text_record


def _text_chunk(*lines: str) -> bytes:
    body = ("\r\n".join(lines) + "\r\n").encode("ascii", errors="ignore")
    return bytes(32) + body


def _structured_chunk(*rows: bytes) -> bytes:
    body = b"\r\n".join(rows) + b"\r\n"
    return bytes(32) + body


def test_is_ft3_text_record_detects_multiline_ascii_payload() -> None:
    chunk = _text_chunk("  3   3   8 a", "Can she", "Was I")
    assert is_ft3_text_record(chunk) is True


def test_parse_ft3_text_record_extracts_melody_and_lyrics_and_drops_noise() -> None:
    chunk = _text_chunk(
        "      3      3        8  a  ?   @   @      Can",
        "      4      3       H    8 ?\"\" @   ?      cuse",
        "Was she ex-",
        "!    @@",
    )
    record = parse_ft3_text_record(chunk)
    assert record.melody_grid is not None
    assert "3" in record.melody_grid
    assert "Can" in record.lyrics
    assert "cuse" in record.lyrics
    assert all("@@" not in line for line in record.lyrics)
    assert record.melody_events
    assert record.melody_events[0].onset_index == 0
    assert any(ev.text == "3" for ev in record.melody_events)
    assert record.lyric_event_rows
    assert any(ev.text.lower().startswith("can") for ev in record.lyric_event_rows[0])
    assert record.parse_mode == "ascii"


def test_parse_ft3_text_record_infers_basic_lyric_syllabic_chain() -> None:
    chunk = _text_chunk("Can ex- cuse", "with vir- tue's cloak")
    record = parse_ft3_text_record(chunk)
    assert len(record.lyric_event_rows) >= 1
    row = record.lyric_event_rows[0]
    syllabics = [(ev.text, ev.syllabic) for ev in row if ev.text]
    assert ("Can", "single") in syllabics
    assert ("ex", "begin") in syllabics
    assert ("cuse", "end") in syllabics


def test_parse_ft3_structured_text_record_builds_ordered_verses() -> None:
    chunk = _structured_chunk(
        b"\x01\x00\x03\x00\x08Can",
        b"Was\x06she",
        b"I\x07ex-",
        b"so",
    )
    record = parse_ft3_text_record(chunk)
    assert record.parse_mode == "structured"
    assert record.melody_grid is None
    assert record.lyrics == ["Can she ex-", "Was I so"]
    assert [ev.verse for ev in record.lyric_event_rows[0]] == [0, 0, 0]
    assert [ev.verse for ev in record.lyric_event_rows[1]] == [1, 1, 1]


def test_parse_ft3_structured_text_record_keeps_explicit_extender_tokens() -> None:
    chunk = _structured_chunk(
        b"\x01\x00\x05\x00\x08A",
        b"_",
        b"men",
    )
    record = parse_ft3_text_record(chunk)
    row = record.lyric_event_rows[0]
    assert row[1].extender is True
    assert row[1].text == ""
