import gzip

from oud.core.ft3 import (
    _fill_missing_time_signatures,
    _normalize_vocal_event_accidentals,
    load_ft3,
    note_type_to_denominator,
    parse_bar,
)
from oud.core.model import Bar, Chord, MelodyEvent, Note


def test_load_minimal_ft3(tmp_path) -> None:
    path = tmp_path / "mini.ft3.gz"
    payload = b"CPiece\x04Test\x03\x80"
    with gzip.open(path, "wb") as f:
        f.write(payload)

    piece = load_ft3(str(path))
    assert piece is not None
    assert len(piece.bars) > 0
    assert piece.title in (None, "Test")


def test_note_type_to_denominator() -> None:
    assert note_type_to_denominator(2) == 1
    assert note_type_to_denominator(3) == 2
    assert note_type_to_denominator(4) == 4
    assert note_type_to_denominator(5) == 8


def test_parse_bar_decodes_ft3_header_repeat_and_barline_markers() -> None:
    bar = parse_bar(bytes([0x80, 0x01]) + bytes(30))
    assert bar.barline == "||"
    assert bar.repeat is None

    bar = parse_bar(bytes([0x00, 0x10]) + bytes(30))
    assert bar.repeat == ".:"

    bar = parse_bar(bytes([0x90, 0x01]) + bytes(30))
    assert bar.barline == "||"
    assert bar.repeat == ":."

    bar = parse_bar(bytes([0x90, 0x12]) + bytes(30))
    assert bar.barline == "||"
    assert bar.repeat == ":|:"


def test_parse_bar_decodes_right_repeat_from_byte1_bit2_marker() -> None:
    bar = parse_bar(bytes([0x80, 0x03]) + bytes(30))
    assert bar.barline == "||"
    assert bar.repeat == ":."


def _ft3_bar_with_one_note(*, extras: int = 0) -> bytes:
    header = bytes(32)
    # chord header at 32: quarter (0 + 2), no dotted/grid
    chord = bytes([0x02, 0x00, 0x00, 0x00])
    # note at 36: string byte=2 -> internal string 1, fret byte='a' -> 0
    note = bytes([0x02, 0x61, extras & 0xFF, (extras >> 8) & 0xFF, 0x00])
    return header + chord + note


def test_parse_bar_skips_false_positive_invalid_note_type_headers() -> None:
    header = bytes(32)
    bogus_chord = bytes([0x78, 0x00, 0x00, 0x00])  # note_type=122 (invalid)
    bogus_note = bytes([0x02, 0x61, 0x00, 0x00, 0x00])
    valid_chord = bytes([0x02, 0x00, 0x00, 0x00])  # note_type=4
    valid_note = bytes([0x02, 0x62, 0x00, 0x00, 0x00])  # fret 1
    bar = parse_bar(header + bogus_chord + bogus_note + valid_chord + valid_note)
    assert len(bar.chords) == 1
    assert len(bar.notes) == 1
    assert bar.chords[0].note_type == 4
    assert bar.notes[0].fret == 1


def test_parse_bar_decodes_ft3_note_extras_fingerings_and_ornaments() -> None:
    # right thumb + left finger2 + right ornament hash
    bar = parse_bar(_ft3_bar_with_one_note(extras=0x0002 | 0x0040 | 0x0600))
    note = bar.notes[0]
    assert note.right_fingering == "thumb"
    assert note.left_fingering == "2"
    assert note.right_ornament == "#"
    assert note.left_ornament is None
    assert note.ft3_extras == 0x0642


def test_load_ft3_parses_bar_stream_from_cbar_body_not_metadata(tmp_path) -> None:
    # Metadata blob deliberately contains note-like bytes before CBar.
    fake_meta = bytes(32) + bytes([0x02, 0x00, 0x00, 0x00]) + bytes([0x02, 0x61, 0, 0, 0])
    payload = (
        b"CPieceTest" + fake_meta + b"\x03\x80" + b"CBar" + _ft3_bar_with_one_note() + b"\x03\x80"
    )
    path = tmp_path / "cbar_body.ft3"
    path.write_bytes(payload)
    piece = load_ft3(str(path))
    first_with_chord = next(bar for bar in piece.bars if bar.chords)
    assert len(first_with_chord.chords) == 1
    assert first_with_chord.notes[0].raw_pos == 36
    assert first_with_chord.notes[0].fret == 0


def test_fill_missing_time_signatures_backfills_leading_pickup_bar() -> None:
    bars = [
        Bar(chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)])]),
        Bar(
            time_sig="C|",
            chords=[Chord(note_type=5, dotted=False, grid=None, notes=[Note(1, 2, 0)])],
        ),
    ]
    _fill_missing_time_signatures(bars)
    assert bars[0].time_sig == "C|"


def test_parse_bar_decodes_ft3_right_hand_dot_fingering_variants() -> None:
    one = parse_bar(_ft3_bar_with_one_note(extras=0x0004)).notes[0]
    two = parse_bar(_ft3_bar_with_one_note(extras=0x0008)).notes[0]
    three = parse_bar(_ft3_bar_with_one_note(extras=0x0010)).notes[0]
    assert one.right_fingering == "dot1"
    assert two.right_fingering == "dot2"
    assert three.right_fingering == "dot3"


def test_parse_bar_decodes_ft3_left_bracket_ornament() -> None:
    bar = parse_bar(_ft3_bar_with_one_note(extras=0x3400))
    note = bar.notes[0]
    assert note.left_ornament == "brackets"


def test_parse_bar_decodes_ft3_extras_compositionally_with_residual_bits() -> None:
    bar = parse_bar(_ft3_bar_with_one_note(extras=0x3440 | 0x0001))
    note = bar.notes[0]
    assert note.left_fingering == "2"
    assert note.left_ornament == "brackets"
    assert note.ft3_extra_residual == 0x0001


def test_normalize_vocal_event_accidentals_uses_key_signature_and_explicit_natural() -> None:
    bar = Bar(
        melody_events=[
            MelodyEvent("f", 0),
            MelodyEvent("f", 1, accidental_flags=0x2000),
            MelodyEvent("b", 2),
            MelodyEvent("g", 3, accidental_flags=0x0002),
        ],
    )
    _normalize_vocal_event_accidentals(bar, key="GM")
    assert [ev.text for ev in bar.melody_events] == ["f#", "f", "b", "g#"]


def test_normalize_vocal_event_accidentals_applies_flat_key_defaults() -> None:
    bar = Bar(
        melody_events=[
            MelodyEvent("b", 0),
            MelodyEvent("e", 1),
            MelodyEvent("a", 2, accidental_flags=0x2000),
            MelodyEvent("b", 3, accidental_flags=0x1000),
        ],
    )
    _normalize_vocal_event_accidentals(bar, key="Fm")
    assert [ev.text for ev in bar.melody_events] == ["bb", "eb", "a", "bb"]


def test_load_ft3_strips_rtf_title(tmp_path) -> None:
    rtf = "{\\rtf1\\ansi Test Title}"
    payload = b"CPiece" + bytes([len(rtf)]) + rtf.encode("utf-8") + b"\x03\x80"
    path = tmp_path / "rtf.ft3.gz"
    with gzip.open(path, "wb") as f:
        f.write(payload)
    piece = load_ft3(str(path))
    assert piece.title == "Test Title"


def test_load_ft3_cpiece_length_prefix(tmp_path) -> None:
    rtf = "{\\rtf1\\ansi Fancy}"
    raw = bytes([0x00, 0x00, 0x00, 0x7C]) + rtf.encode("utf-8")
    payload = b"CPiece" + len(raw).to_bytes(4, "little") + raw + b"\x03\x80"
    path = tmp_path / "rtf_len.ft3.gz"
    with gzip.open(path, "wb") as f:
        f.write(payload)
    piece = load_ft3(str(path))
    assert piece.title == "Fancy"


def test_load_ft3_uses_filename_when_title_missing(tmp_path) -> None:
    path = tmp_path / "czarna_krowa.ft3"
    path.write_bytes(b"\x03\x80")
    piece = load_ft3(str(path))
    assert piece.title == "czarna krowa"


def test_frog_galliard_bar8_includes_bass() -> None:
    piece = load_ft3("lutemusic/23a_frogg_galliard_2.ft3")
    bar = piece.bars[7]
    assert any(note.string >= 7 for note in bar.notes)


def test_load_ft3_decodes_repeat_pair_from_bar_headers() -> None:
    piece = load_ft3("lutemusic/wu_sol_ich_mich_hin_keren.ft3")
    assert piece.bars[1].repeat == ".:"
    assert piece.bars[4].repeat == ":."
    assert piece.bars[4].barline == "||"


def test_load_ft3_decodes_internal_double_barlines() -> None:
    piece = load_ft3("lutemusic/23a_frogg_galliard_2.ft3")
    assert piece.bars[15].barline == "||"
    assert piece.bars[31].barline == "||"


def test_can_she_excuse_ft3_does_not_inflate_string_count_from_invalid_bass_byte() -> None:
    piece = load_ft3("lutemusic/can_she_excuse.ft3")
    assert piece.strings == 8
    assert max((note.string for bar in piece.bars for note in bar.notes), default=0) == 8


def test_can_she_excuse_ft3_skips_interleaved_lyric_text_records() -> None:
    piece = load_ft3("lutemusic/can_she_excuse.ft3")
    assert len(piece.bars) == 40
    assert all(bar.chords for bar in piece.bars)
    assert piece.import_warnings
    assert "structured records" in piece.import_warnings[0]
    assert any(bar.lyrics for bar in piece.bars)
    assert any(
        bar.melody_grid or bar.melody_events or bar.lyrics or bar.lyric_event_rows
        for bar in piece.bars
    )
    assert any(bar.lyric_event_rows for bar in piece.bars)
    first_with_lyrics = next(bar for bar in piece.bars if bar.lyrics)
    assert any("can" in line.lower() for line in first_with_lyrics.lyrics)
    assert [ev.text for ev in piece.bars[0].melody_events[:3]] == ["d", "a", "d'"]
    assert [ev.text for ev in piece.bars[1].melody_events[:3]] == ["c'", "bb", "a"]


def test_load_ft3_structured_lyric_records_emit_specific_warning(tmp_path) -> None:
    text_record = bytes(32) + b"\x01\x00\x03\x00\x08Can\r\nWas\x06she\r\nI\x07ex-\r\nso\r\n"
    payload = (
        b"CPieceTest\x03\x80CBar"
        + text_record
        + b"\x03\x80"
        + text_record
        + b"\x03\x80"
        + _ft3_bar_with_one_note()
        + b"\x03\x80"
    )
    path = tmp_path / "structured_text.ft3"
    path.write_bytes(payload)
    piece = load_ft3(str(path))
    assert piece.import_warnings
    assert "structured text records" in piece.import_warnings[0]


def test_load_ft3_attaches_single_structured_editorial_record_to_preceding_bar(tmp_path) -> None:
    text_record = bytes(32) + b"\x01Appendix\x0bOriginal\x17bars\x1fcommentary:\r\n"
    payload = (
        b"CPieceTest\x03\x80CBar"
        + _ft3_bar_with_one_note()
        + b"\x03\x80"
        + _ft3_bar_with_one_note()
        + b"\x03\x80"
        + text_record
        + b"\x03\x80"
        + _ft3_bar_with_one_note()
        + b"\x03\x80"
    )
    path = tmp_path / "single_comment.ft3"
    path.write_bytes(payload)
    piece = load_ft3(str(path))
    bars_with_chords = [bar for bar in piece.bars if bar.chords]
    assert len(bars_with_chords) == 3
    assert bars_with_chords[0].editorial_text == []
    assert bars_with_chords[1].editorial_text == ["Appendix Original bars commentary:"]
    assert bars_with_chords[2].editorial_text == []


def test_load_ft3_canonicalizes_con_metadata_into_source(tmp_path) -> None:
    payload = (
        b"CPiece{\\rtf1\\ansi Demo}\r\n~"
        b"\x00\x00source: main source\r\n"
        b"con: continuation text\r\n"
        b"CBar\x03\x80"
    )
    path = tmp_path / "meta_con.ft3"
    path.write_bytes(payload)
    piece = load_ft3(str(path))
    assert piece.source == "main source continuation text"
    assert piece.raw_metadata["con"] == "continuation text"


def test_load_ft3_builds_imported_score_for_text_layers(tmp_path) -> None:
    text_record = (
        bytes(32)
        + bytes.fromhex(
            "010000000001330500000000013308000000000400"
            "a338d7bf610bd63f0000004000000040040000000000000000000000010003000843616e",
        )
        + b"\r\nWas\x06she\r\nI\x07ex-\r\nso\r\n"
    )
    payload = (
        b"CPieceTest\x03\x80CBar"
        + text_record
        + b"\x03\x80"
        + _ft3_bar_with_one_note()
        + b"\x03\x80"
    )
    path = tmp_path / "imported_score.ft3"
    path.write_bytes(payload)
    piece = load_ft3(str(path))
    assert piece.imported_score is not None
    staffs = {staff.kind: staff for staff in piece.imported_score.staffs}
    assert "note" in staffs
    assert "lyrics" in staffs
    assert staffs["note"].bars[0].text_rows[0].kind == "vocal"
    assert staffs["lyrics"].bars[0].text_rows[0].kind == "lyrics"


def test_load_ft3_marks_unknown_non_tab_score_chunks_in_imported_score(tmp_path) -> None:
    unknown_bar = bytearray(64)
    unknown_bar[0] = 0x06
    unknown_bar[8] = 0x04
    unknown_bar[9] = 0x03
    unknown_bar[40:48] = b"\x99\x98\x97\x96\x95\x94\x93\x92"
    payload = b"CPiece\x04Test\x03\x80CBar" + bytes(unknown_bar) + b"\x03\x80"
    path = tmp_path / "unknown_score.ft3"
    path.write_bytes(payload)
    piece = load_ft3(str(path))
    assert piece.imported_score is not None
    staffs = {staff.kind: staff for staff in piece.imported_score.staffs}
    assert "barline" in staffs
    assert "unknown" not in staffs
    assert staffs["barline"].bars[0].source_bar_index == 0
    assert staffs["barline"].bars[0].raw_kind == "barline-raw"
    assert staffs["barline"].bars[0].time_sig == "3/4"
    assert not piece.import_warnings or "unknown staves" not in piece.import_warnings[-1]


def test_load_ft3_classifies_raw_note_staff_chunks_in_imported_score(tmp_path) -> None:
    chunk = bytearray(96)
    chunk[0] = 0x06
    chunk[32:46] = b"\x04\x00\x00\x00\x00\x01\x33\x06\x00\x00\x00\x00\x01\x34"
    payload = b"CPiece\x04Test\x03\x80CBar" + bytes(chunk) + b"\x03\x80"
    path = tmp_path / "raw_note_staff.ft3"
    path.write_bytes(payload)
    piece = load_ft3(str(path))
    assert piece.imported_score is not None
    staffs = {staff.kind: staff for staff in piece.imported_score.staffs}
    assert "note" in staffs
    assert "unknown" not in staffs
    note_bar = next(bar for bar in staffs["note"].bars if bar.raw_kind == "note-staff-raw")
    assert [event.text for event in note_bar.melody_events] == ["g", "b", "d"]


def test_load_ft3_decodes_raw_note_lyric_bars_into_note_and_lyric_staffs(tmp_path) -> None:
    chunk = (
        bytes(32)
        + bytes.fromhex("010000000001330500000000013308000000000400")
        + b"\x01\x00\x03\x00\x03Can\r\n"
    )
    payload = b"CPiece\x04Test\x03\x80CBar" + chunk + b"\x03\x80"
    path = tmp_path / "raw_note_lyric.ft3"
    path.write_bytes(payload)
    piece = load_ft3(str(path))
    assert piece.imported_score is not None
    staffs = {staff.kind: staff for staff in piece.imported_score.staffs}
    assert "note" in staffs
    assert "lyrics" in staffs
    assert "unknown" not in staffs
    note_bar = next(bar for bar in staffs["note"].bars if bar.raw_kind == "note-lyric-raw")
    lyric_bar = next(bar for bar in staffs["lyrics"].bars if bar.raw_kind == "note-lyric-raw")
    assert [event.text for event in note_bar.melody_events] == ["d", "a", "d'"]
    assert lyric_bar.lyrics == ["Can"]


def test_load_ft3_preserves_font_noise_rows_in_unknown_imported_staff(tmp_path) -> None:
    text_record = bytes(32) + b"\x01\x00\x03\x00\x08:Fe\r\n>fu\r\nTimes\x07New\x0eRoman\r\n%%%%\r\n"
    payload = (
        b"CPiece\x04Test\x03\x80CBar"
        + text_record
        + b"\x03\x80"
        + _ft3_bar_with_one_note()
        + b"\x03\x80"
    )
    path = tmp_path / "font_rows.ft3"
    path.write_bytes(payload)
    piece = load_ft3(str(path))
    assert piece.imported_score is not None
    unknown_staff = next(staff for staff in piece.imported_score.staffs if staff.kind == "unknown")
    assert any(row.kind == "font" for bar in unknown_staff.bars for row in bar.text_rows)


def test_load_ft3_does_not_create_unknown_staff_for_font_and_control_rows_only(tmp_path) -> None:
    text_record = bytes(32) + b"Times\x07New\x0eRoman\r\n" + b"\x013\x072\r\n" + b"}\r\n"
    payload = (
        b"CPiece\x04Test\x03\x80CBar"
        + text_record
        + b"\x03\x80"
        + _ft3_bar_with_one_note()
        + b"\x03\x80"
    )
    path = tmp_path / "font_control_only.ft3"
    path.write_bytes(payload)
    piece = load_ft3(str(path))
    assert piece.imported_score is None or all(
        staff.kind != "unknown" for staff in piece.imported_score.staffs
    )


def test_pavan_01_8c_infers_eight_courses() -> None:
    piece = load_ft3("lutemusic/pavan_01_8C.ft3")
    assert piece.strings == 8
    assert any(note.string >= 7 for bar in piece.bars for note in bar.notes)


def test_lachrimae_ft3_legacy_duration_fix_applied() -> None:
    piece = load_ft3("examples/26_lachrimae_galliard_in_G.ft3")
    bar = piece.bars[0]
    total = 0.0
    for chord in bar.chords:
        denom = note_type_to_denominator(chord.note_type)
        assert denom is not None
        value = 4.0 / denom
        if chord.dotted:
            value *= 1.5
        total += value
    assert abs(total - 3.0) < 0.01
    assert bar.time_sig == "O"


def test_forlorne_ft3_common_time_first_bar_is_metrically_consistent() -> None:
    piece = load_ft3("examples/02_forlorne_hope_8C.ft3")
    bar = piece.bars[0]
    total = 0.0
    for chord in bar.chords:
        denom = note_type_to_denominator(chord.note_type)
        assert denom is not None
        value = 4.0 / denom
        if chord.dotted:
            value *= 1.5
        total += value
    assert bar.time_sig in {"C", "C|"}
    assert abs(total - 2.0) < 0.01 or abs(total - 4.0) < 0.01


def test_load_ft3_extracts_section_metadata_from_real_file() -> None:
    piece = load_ft3("lutemusic/23a_frogg_galliard_2.ft3")
    assert piece.key == "GM"
    assert piece.piece_type == "galliard"
    assert piece.difficulty == "Challenge"
    assert piece.ensemble == "7-course"
    assert piece.title == "23a. The frog galliard"
    assert piece.composer == "John Dowland"


def test_load_ft3_extracts_arranger_from_real_file() -> None:
    piece = load_ft3("lutemusic/ich_bin_eine_blume_zu_saron_T.ft3")
    assert piece.composer == "Dietrich Buxtehude"
    assert piece.arranger == "Sarge Gerbode"


def test_load_ft3_felice_high_letter_frets_are_not_dropped() -> None:
    piece = load_ft3("lutemusic/01_felice_fu_quel_anon.ft3")
    # Regression: bars around 13-16 were parsed as empty because note scanning only
    # accepted a..f letter frets.
    for bar_idx in (12, 13, 14, 15):  # 1-based bars 13..16
        assert piece.bars[bar_idx].chords, bar_idx + 1


def test_load_ft3_parses_footnote_parts_from_annotation(tmp_path) -> None:
    payload = (
        b"CPiece{\\rtf1\\ansi Demo}\r\n~"
        b"\x00\x00footnote: src info  editor name  commentary here\r\n"
        b"source: source from annotation\r\n"
        b"CBar\x03\x80"
    )
    path = tmp_path / "meta.ft3"
    path.write_bytes(payload)
    piece = load_ft3(str(path))
    assert piece.footnote == "src info  editor name  commentary here"
    assert piece.footnote_source == "src info"
    assert piece.footnote_editor == "editor name"
    assert piece.footnote_comment == "commentary here"
    assert piece.source == "source from annotation"


def test_loaded_titles_do_not_contain_rtf_artifacts() -> None:
    paths = [
        "examples/example.ft3",
        "examples/26_lachrimae_galliard_in_G.ft3",
        "lutemusic/23a_frogg_galliard_2.ft3",
    ]
    for path in paths:
        piece = load_ft3(path)
        title = piece.title or ""
        assert "\\rtf" not in title
        assert "{" not in title
        assert "}" not in title


def test_ich_bin_blume_ft3_fills_missing_time_signatures_by_section() -> None:
    piece = load_ft3("lutemusic/ich_bin_eine_blume_zu_saron_T.ft3")
    # Early section is triple meter (sum=1.5) and should not render against default common time.
    assert piece.bars[0].time_sig in {"O", "3/4"}
    assert piece.bars[40].time_sig in {"O", "3/4"}
    # Explicit FT3 meter changes must remain and unlabeled bars between them inherit matching section meter.
    assert piece.bars[88].time_sig == "C|"
    assert piece.bars[100].time_sig == "C|"
    assert piece.bars[128].time_sig == "6/8"
    assert piece.bars[140].time_sig == "6/8"
    assert piece.bars[159].time_sig == "C|"
