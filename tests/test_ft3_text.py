from oud.core.ft3_text import (
    _structured_lyric_rows_from_positioned_rows,
    decode_ft3_annotation_group,
    decode_ft3_vocal_events,
    is_ft3_text_record,
    parse_ft3_text_record,
    refine_ft3_raw_text_record,
)


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
        '      4      3       H    8 ?"" @   ?      cuse',
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


def test_refine_ft3_raw_text_record_clusters_raw_fallback_lanes() -> None:
    chunk = _structured_chunk(
        b"\x08Now",
        b"\x01I",
        b"\x01I\x08I",
        b"\x01am",
        b"\x01do",
    )
    record = refine_ft3_raw_text_record(parse_ft3_text_record(chunk), chunk)
    assert record.parse_mode == "structured"
    assert record.lyrics == ["Now I", "I am do"]
    assert [len(row) for row in record.lyric_event_rows] == [2, 3]


def test_refine_ft3_raw_text_record_coalesces_split_primary_lane() -> None:
    chunk = _structured_chunk(
        bytes.fromhex("0100000000013305000000000300") + b"\x12Now",
        b"Dear",
        b"Dear\x0bO",
        b"when",
        b"if",
    )
    record = refine_ft3_raw_text_record(parse_ft3_text_record(chunk), chunk)
    assert record.lyrics == ["Now O", "Dear when", "Dear if"]
    assert [len(row) for row in record.lyric_event_rows] == [2, 2, 2]


def test_refine_ft3_raw_text_record_reconstructs_three_verses() -> None:
    chunk = _structured_chunk(
        bytes.fromhex("060000000001330500000000030009bcfdbf8b9df83f0000803f030000000000000000000001000200124e6f772c"),
        b"Dear,",
        b"Dear,\x0bO",
        b"when",
        b"if",
    )
    record = refine_ft3_raw_text_record(parse_ft3_text_record(chunk), chunk)
    assert record.lyrics == ["Now O", "Dear when", "Dear if"]
    assert [len(row) for row in record.lyric_event_rows] == [2, 2, 2]


def test_refine_ft3_raw_text_record_drops_vocal_pitch_tail_token() -> None:
    chunk = _structured_chunk(
        b"\x01\x00\x03\x00\x05a\x08Can",
        b"Was\x06she",
        b"I\x07ex-",
        b"so",
    )
    record = refine_ft3_raw_text_record(parse_ft3_text_record(chunk), chunk)
    assert record.lyrics == ["Can she ex-", "Was I so"]


def test_parse_ft3_text_record_accepts_half_note_vocal_code_0x32() -> None:
    row = bytes.fromhex("070000000001330700000000013207000000000400")
    events = decode_ft3_vocal_events(row)
    assert [(ev.text, ev.note_type) for ev in events] == [("c'", None), ("c'", 4), ("c'", 3)]


def test_decode_ft3_vocal_events_treats_0x40_flag_as_rest() -> None:
    row = bytes.fromhex("0500000000013306400000000300")
    events = decode_ft3_vocal_events(row)
    assert [(ev.text, ev.note_type, ev.is_rest) for ev in events] == [("a", None, False), ("r", 4, True)]


def test_decode_ft3_vocal_events_decodes_beam_chain_and_fermata() -> None:
    row = bytes.fromhex("050001000001350604000000013507080000000400")
    events = decode_ft3_vocal_events(row)
    assert [event.beam for event in events] == ["start", "continue", "end"]
    assert [event.fermata for event in events] == [True, False, False]


def test_decode_ft3_annotation_group_extracts_length_prefixed_edition_text() -> None:
    chunk = bytes(32) + b"\x01p\x0fcresc. - - - ->" + bytes(16)
    record = decode_ft3_annotation_group(chunk)
    assert record.editorial_text == ["p", "cresc. - - - ->"]


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


def test_parse_ft3_structured_text_record_strips_control_prefix_and_font_row() -> None:
    chunk = _structured_chunk(
        b"\x01\x00\x03\x00\x08:Fe",
        b">fu",
        b"Times\x07New\x0eRoman",
    )
    record = parse_ft3_text_record(chunk)
    words = [ev.text.lower() for row in record.lyric_event_rows for ev in row if ev.text]
    assert "fe" in words
    assert "fu" in words
    assert "times" not in words
    assert "roman" not in words
    assert [row.kind for row in record.structured_rows] == ["lyrics", "lyrics", "font"]


def test_parse_ft3_structured_text_record_falls_back_to_legacy_lyric_punctuation() -> None:
    chunk = _structured_chunk(
        b"\x01\x00\x03\x00\x08Fe-:li-",
        b"li-<ce",
        b"quan-:to.",
    )
    record = parse_ft3_text_record(chunk)
    assert record.parse_mode == "structured"
    assert record.lyrics == ["Fe-li- li-ce quan-to."]
    assert [row.kind for row in record.structured_rows] == ["lyrics", "lyrics", "lyrics"]


def test_parse_ft3_structured_text_record_classifies_placeholder_rows_as_control() -> None:
    chunk = _structured_chunk(
        b"\x013\x072",
        b"@@?",
        b"-",
    )
    record = parse_ft3_text_record(chunk)
    assert record is not None
    assert [row.kind for row in record.structured_rows] == ["control", "control", "lyrics"]


def test_parse_ft3_structured_text_record_decodes_vocal_prefix_notes() -> None:
    chunk = _structured_chunk(
        bytes.fromhex(
            "010000000001330500000000013308000000000400"
            "a338d7bf610bd63f0000004000000040040000000000000000000000010003000843616e",
        ),
        b"Was\x06she",
        b"I\x07ex-",
        b"so",
    )
    record = parse_ft3_text_record(chunk)
    assert [ev.text for ev in record.melody_events] == ["d", "a", "d'"]
    assert [ev.onset_index for ev in record.melody_events] == [0, 1, 2]
    assert [row.kind for row in record.structured_rows] == ["vocal", "lyrics", "lyrics", "lyrics"]


def test_parse_ft3_structured_text_record_keeps_vocal_accidental_flags() -> None:
    chunk = _structured_chunk(
        bytes.fromhex(
            "06001000000200"  # first note: bb from 0x1000
            "010003000854657374",
        ),
        b"lyric",
    )
    record = parse_ft3_text_record(chunk)
    assert record.melody_events[0].text == "bb"
    assert record.melody_events[0].accidental_flags == 0x1000


def test_parse_ft3_structured_text_record_classifies_single_prose_row_as_editorial() -> None:
    chunk = _structured_chunk(
        b"\x01Appendix\x0bOriginal\x17bars\x1fcommentary:",
    )
    record = parse_ft3_text_record(chunk)
    assert record.parse_mode == "structured"
    assert record.editorial_text == ["Appendix Original bars commentary:"]
    assert record.lyrics == []
    assert record.lyric_event_rows == []
    assert [row.kind for row in record.structured_rows] == ["editorial"]


def test_raw_positioned_lyric_rows_prefer_cluster_merges_nearby_lanes() -> None:
    rows = [
        [(11, "Ab-")],
        [(0, "I")],
        [(0, "For"), (16, "sence")],
        [(0, "lov'd")],
        [(0, "my")],
    ]
    assert _structured_lyric_rows_from_positioned_rows(rows, prefer_cluster=True) == [
        ["Ab-", "sence"],
        ["I", "For", "lov'd", "my"],
    ]
