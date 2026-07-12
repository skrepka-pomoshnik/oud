import gzip

from oud.core.ft3 import (
    _decode_ft3_note_position,
    _fill_missing_time_signatures,
    _normalize_vocal_event_accidentals,
    _parallel_mixed_score_prefix_count,
    _parallel_raw_bar_targets,
    load_ft3,
    note_type_to_denominator,
    parse_bar,
)
from oud.petrucci.model import Bar, Chord, ImportedTextRow, MelodyEvent, Note


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


def test_parse_bar_decodes_ft3_second_ending_flag() -> None:
    bar = parse_bar(bytes([0x40, 0x00]) + bytes(30))
    assert bar.ending_numbers == (2,)
    assert bar.system_break is False
    assert bar.barline is None
    assert bar.repeat is None


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
    payload = b"CPieceTest" + fake_meta + b"\x03\x80" + b"CBar" + _ft3_bar_with_one_note() + b"\x03\x80"
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


def test_parse_bar_decodes_ft3_confirmed_exact_extras_subset() -> None:
    note = parse_bar(_ft3_bar_with_one_note(extras=0x0020 | 0x0400)).notes[0]
    assert note.left_fingering == "1"
    assert note.left_ornament == "#"
    assert note.right_ornament is None

    note = parse_bar(_ft3_bar_with_one_note(extras=0x0600)).notes[0]
    assert note.right_ornament == "#"
    assert note.left_ornament is None

    note = parse_bar(_ft3_bar_with_one_note(extras=0x4A00)).notes[0]
    assert note.arpeggio == "bottom"
    assert note.left_ornament is None

    note = parse_bar(_ft3_bar_with_one_note(extras=0x0E00)).notes[0]
    assert note.right_ornament == "x"


def test_parse_bar_decodes_ft3_left_bracket_ornament() -> None:
    bar = parse_bar(_ft3_bar_with_one_note(extras=0x3400))
    note = bar.notes[0]
    assert note.barre is True
    assert note.left_ornament is None


def test_parse_bar_decodes_ft3_extras_compositionally_with_residual_bits() -> None:
    bar = parse_bar(_ft3_bar_with_one_note(extras=0x3440 | 0x0001))
    note = bar.notes[0]
    assert note.barre is True
    assert note.left_fingering == "2"
    assert note.left_ornament is None
    assert note.ft3_extra_residual == 0x0001


def test_parse_bar_uses_declared_object_count_instead_of_scanning_trailing_bytes() -> None:
    chord = b"\x02\x00\x02\x00\x00\x00\x02a\x00\x00\x00"
    bar = parse_bar(bytes(28) + b"\x00\x00" + chord + b"\x02aASCII\x02bTAIL")
    assert len(bar.chords) == 1
    assert [(note.string, note.fret) for note in bar.notes] == [(1, 0)]


def test_parse_bar_decodes_leading_performance_text_without_fake_notes() -> None:
    annotation = b"\x00\x00\x01\x00\x00\x00\x01\x00\x00\x01\x00\x02mf\x00\x00"
    chord = b"\x02\x00\x02\x00\x00\x00\x02a\x00\x00\x00"
    bar_data = bytes(28) + b"\x01\x00" + annotation + chord
    bar = parse_bar(bar_data)
    assert bar.dynamic == "mf"
    assert len(bar.chords) == 1
    assert bar.notes[0].ft3_extra_residual is None


def test_parse_bar_does_not_interpret_standard_staff_text_as_tablature() -> None:
    score_record = bytes(28) + b"\x01\x00\x01\x33" + b"\x05header\x02aASCII"
    bar = parse_bar(score_record)
    assert bar.chords == []
    assert bar.notes == []


def test_real_can_she_excuse_combines_barre_and_left_fingering_without_residual() -> None:
    piece = load_ft3("lutemusic/05_can_she_excuse/can_she_excuse.ft3")
    combined = [note for bar in piece.bars for chord in bar.chords for note in chord.notes if note.ft3_extras == 0x3500]
    assert len(combined) == 2
    assert all(note.barre and note.left_fingering == "4" for note in combined)
    assert all(note.ft3_extra_residual is None for note in combined)


def test_real_ft3_arpeggio_segments_and_right_x_have_no_residuals() -> None:
    ich = load_ft3("lutemusic/ich_bin_eine_blume_zu_saron_T.ft3")
    arpeggios = [
        note.arpeggio for bar in ich.bars for chord in bar.chords for note in chord.notes if note.arpeggio is not None
    ]
    assert arpeggios.count("top") == 5
    assert arpeggios.count("middle") == 5
    assert arpeggios.count("bottom") == 5

    willoughby = load_ft3("lutemusic/willoughby_duet.ft3")
    assert willoughby.bars[1].chords[0].notes[0].arpeggio == "single"

    ricercar = load_ft3("lutemusic/ricercar_galileiG.ft3")
    right_x = [
        note for bar in ricercar.bars for chord in bar.chords for note in chord.notes if note.right_ornament == "x"
    ]
    assert len(right_x) == 5
    assert all(note.ft3_extra_residual is None for note in right_x)


def test_real_ft3_ending_flags_match_published_first_and_second_endings() -> None:
    piece = load_ft3("lutemusic/01_unquiet_thoughts/unquiet_thoughts_T.ft3")
    assert piece.bars[23].ending_numbers == (1,)
    assert piece.bars[24].ending_numbers == (2,)
    assert not any(bar.system_break for bar in piece.bars)


def test_real_ft3_annotation_groups_anchor_to_following_bar() -> None:
    piece = load_ft3("lutemusic/ich_bin_eine_blume_zu_saron_T.ft3")
    assert piece.bars[85].dynamic == "p"
    assert piece.bars[85].editorial_text == ["cresc. - - - ->"]
    assert not any(bar.system_break for bar in piece.bars)
    assert piece.imported_score is not None
    assert [record.kind for record in piece.imported_score.source_records] == ["annotation-group"] * 3


def test_parse_bar_feature_matrix_decodes_known_header_bits() -> None:
    bar = parse_bar(bytes([0xE0, 0x13]) + bytes(30))
    assert bar.barline == "||"
    assert bar.repeat == ":|:"
    assert bar.ending_numbers == (1, 2)
    assert bar.system_break is False


def test_parse_bar_feature_matrix_decodes_first_ending_flag() -> None:
    bar = parse_bar(bytes([0x20, 0x00]) + bytes(30))
    assert bar.barline is None
    assert bar.repeat is None
    assert bar.ending_numbers == (1,)
    assert bar.system_break is False


def test_decode_ft3_note_position_uses_confirmed_bass_discriminator_masks() -> None:
    assert _decode_ft3_note_position(0x08, ord("a"), 0x00) == (7, 0)
    assert _decode_ft3_note_position(0x08, ord("1"), 0x20) == (8, 0)
    assert _decode_ft3_note_position(0x08, ord("0"), 0x22) == (7, 0)
    assert _decode_ft3_note_position(0x08, ord("c"), 0x48) == (8, 2)
    assert _decode_ft3_note_position(0x08, ord("c"), 0x49) == (8, 2)
    assert _decode_ft3_note_position(0x08, ord("1"), 0x10) is None


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


def test_normalize_vocal_event_accidentals_ignores_raw_fallback_2000_natural_hint() -> None:
    bar = Bar(
        melody_events=[MelodyEvent("f", 0, accidental_flags=0x2000)],
        structured_text_rows=[ImportedTextRow(0, "vocal", text="3 raw cue", tokens=["raw"])],
    )
    _normalize_vocal_event_accidentals(bar, key="GM", raw_fallback=True)
    assert [ev.text for ev in bar.melody_events] == ["f#"]


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


def test_can_she_excuse_ft3_drops_noise_token_from_second_verse_bar_38() -> None:
    piece = load_ft3("lutemusic/can_she_excuse.ft3")
    bar = piece.bars[37]
    lyric_rows = [[ev.text for ev in row] for row in bar.lyric_event_rows]
    assert lyric_rows == [["come", "her", "will", "Thy"], ["it", "was", "I", "Who"]]
    assert all("WN" not in text for row in lyric_rows for text in row)
    assert piece.import_warnings == []
    assert any(bar.lyrics for bar in piece.bars)
    assert any(bar.melody_grid or bar.melody_events or bar.lyrics or bar.lyric_event_rows for bar in piece.bars)
    assert any(bar.lyric_event_rows for bar in piece.bars)
    first_with_lyrics = next(bar for bar in piece.bars if bar.lyrics)
    assert any("can" in line.lower() for line in first_with_lyrics.lyrics)
    assert [ev.text for ev in piece.bars[0].melody_events[:3]] == ["d", "a", "d'"]
    assert [ev.text for ev in piece.bars[1].melody_events[:3]] == ["c'", "bb", "a"]


def test_load_ft3_structured_lyric_records_do_not_warn_when_represented(tmp_path) -> None:
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
    assert piece.import_warnings == []
    assert any(bar.lyric_event_rows for bar in piece.bars)


def test_load_ft3_decodes_standalone_first_ending_marker(tmp_path) -> None:
    payload = b"CPieceTest\x03\x80CBar" + bytes([0x20, 0x00]) + bytes(30) + b"\x03\x80"
    path = tmp_path / "header_markers.ft3"
    path.write_bytes(payload)
    piece = load_ft3(str(path))
    assert piece.import_warnings == []
    assert piece.bars[0].ending_numbers == (1,)


def test_load_ft3_decodes_first_ending_repeat_boundary(tmp_path) -> None:
    payload = b"CPieceTest\x03\x80CBar" + bytes([0xB0, 0x00]) + bytes(30) + b"\x03\x80"
    path = tmp_path / "known_header_markers.ft3"
    path.write_bytes(payload)
    piece = load_ft3(str(path))
    assert not any("additional bar header markers" in warning for warning in piece.import_warnings)
    assert piece.bars[0].repeat == ":."
    assert piece.bars[0].barline == "||"
    assert piece.bars[0].ending_numbers == (1,)


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
    payload = b"CPiece{\\rtf1\\ansi Demo}\r\n~\x00\x00source: main source\r\ncon: continuation text\r\nCBar\x03\x80"
    path = tmp_path / "meta_con.ft3"
    path.write_bytes(payload)
    piece = load_ft3(str(path))
    assert piece.source == "main source continuation text"
    assert piece.raw_metadata["con"] == "continuation text"


def test_merge_lyric_record_filters_noise_only_lines(tmp_path) -> None:
    text_record = bytes(32) + b";F     @   ?\r\n_\x01C950\r\n"
    payload = b"CPieceTest\x03\x80CBar" + text_record + b"\x03\x80" + _ft3_bar_with_one_note() + b"\x03\x80"
    path = tmp_path / "noise_lyrics.ft3"
    path.write_bytes(payload)
    piece = load_ft3(str(path))
    bars_with_chords = [bar for bar in piece.bars if bar.chords]
    assert bars_with_chords
    assert bars_with_chords[0].lyrics == []


def test_load_ft3_builds_imported_score_for_text_layers(tmp_path) -> None:
    text_record = (
        bytes(32)
        + bytes.fromhex(
            "010000000001330500000000013308000000000400"
            "a338d7bf610bd63f0000004000000040040000000000000000000000010003000843616e",
        )
        + b"\r\nWas\x06she\r\nI\x07ex-\r\nso\r\n"
    )
    payload = b"CPieceTest\x03\x80CBar" + text_record + b"\x03\x80" + _ft3_bar_with_one_note() + b"\x03\x80"
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
    assert piece.imported_score.source_records[0].kind == "barline"
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
    note_bar = staffs["note"].bars[0]
    assert [event.text for event in note_bar.melody_events] == ["g", "b", "d"]
    assert piece.imported_score.source_records[0].kind == "note"


def test_load_ft3_classifies_note_marker_crossing_header_boundary(tmp_path) -> None:
    chunk = bytearray(68)
    chunk[30:32] = b"\x01\x31"
    chunk[32:48] = b"\xff" * 16
    payload = b"CPiece\x04Test\x03\x80CBar" + bytes(chunk) + b"\x03\x80"
    path = tmp_path / "header_boundary_note_staff.ft3"
    path.write_bytes(payload)
    piece = load_ft3(str(path))
    assert piece.imported_score is not None
    staffs = {staff.kind: staff for staff in piece.imported_score.staffs}
    assert "note" in staffs
    assert "unknown" not in staffs
    assert piece.imported_score.source_records[0].kind == "note"


def test_load_ft3_preserves_score_settings_record_as_layout_staff() -> None:
    piece = load_ft3("lutemusic/32_passacaglia.ft3")
    assert piece.imported_score is not None
    staffs = {staff.kind: staff for staff in piece.imported_score.staffs}
    assert "unknown" not in staffs
    assert staffs["layout"].bars[0].source_bar_index == 27
    assert piece.imported_score.source_records[0].kind == "score-terminator"
    assert piece.imported_score.source_records[0].size == 117


def test_load_ft3_decodes_embedded_appendix_page_and_editorial_note() -> None:
    piece = load_ft3("lutemusic/32_passacaglia.ft3")
    assert piece.bars[14].editorial_text == [
        "Original 2 bars seem too discordant.  For originals see Appendix.",
    ]
    assert piece.bars[25].system_break is True
    assert piece.bars[26].page_break_before is True
    assert piece.bars[26].section_title == "Appendix"
    assert piece.bars[26].section_subtitle == "Original bars 14-15"


def test_load_ft3_builds_complete_logical_bars_for_every_polyphonic_staff() -> None:
    piece = load_ft3("lutemusic/05_can_she_excuse/can_she_excuse_4_part.ft3")
    assert piece.imported_score is not None
    note_staffs = [staff for staff in piece.imported_score.staffs if staff.kind == "note"]
    assert [staff.label for staff in note_staffs] == ["soprano", "alto", "tenor", "bass"]
    assert all(len(staff.bars) == len(piece.bars) == 24 for staff in note_staffs)


def test_load_ft3_warns_when_mixed_tab_retains_unknown_staff(tmp_path) -> None:
    unknown = bytes(32) + (b"\xff" * 16)
    payload = b"CPiece\x04Test\x03\x80CBar" + unknown + b"\x03\x80" + _ft3_bar_with_one_note() + b"\x03\x80"
    path = tmp_path / "mixed_unknown.ft3"
    path.write_bytes(payload)
    piece = load_ft3(str(path))
    assert any(bar.chords for bar in piece.bars)
    assert piece.imported_score is not None
    assert any(staff.kind == "unknown" for staff in piece.imported_score.staffs)
    assert any("unknown staves" in warning for warning in piece.import_warnings)


def test_load_ft3_decodes_raw_note_lyric_bars_into_note_and_lyric_staffs(tmp_path) -> None:
    chunk = bytes(32) + bytes.fromhex("010000000001330500000000013308000000000400") + b"\x01\x00\x03\x00\x03Can\r\n"
    payload = b"CPiece\x04Test\x03\x80CBar" + chunk + b"\x03\x80"
    path = tmp_path / "raw_note_lyric.ft3"
    path.write_bytes(payload)
    piece = load_ft3(str(path))
    assert piece.imported_score is not None
    staffs = {staff.kind: staff for staff in piece.imported_score.staffs}
    assert "note" in staffs
    assert "lyrics" in staffs
    assert "unknown" not in staffs
    note_bar = staffs["note"].bars[0]
    lyric_bar = staffs["lyrics"].bars[0]
    assert [event.text for event in note_bar.melody_events] == ["d", "a", "d'"]
    assert lyric_bar.lyrics == ["Can"]
    assert piece.imported_score.source_records[0].kind == "note-lyrics"


def test_load_ft3_preserves_unclassified_text_rows_as_comments(tmp_path) -> None:
    text_record = bytes(32) + b"\x01\x00\x03\x00\x08:Fe\r\n>fu\r\nTimes\x07New\x0eRoman\r\n%%%%\r\n"
    payload = b"CPiece\x04Test\x03\x80CBar" + text_record + b"\x03\x80" + _ft3_bar_with_one_note() + b"\x03\x80"
    path = tmp_path / "font_rows.ft3"
    path.write_bytes(payload)
    piece = load_ft3(str(path))
    assert piece.imported_score is not None
    staffs = {staff.kind: staff for staff in piece.imported_score.staffs}
    assert "unknown" not in staffs
    assert any(row.kind == "font" for bar in staffs["comment"].bars for row in bar.text_rows)


def test_load_ft3_does_not_create_unknown_staff_for_font_and_control_rows_only(tmp_path) -> None:
    text_record = bytes(32) + b"Times\x07New\x0eRoman\r\n" + b"\x013\x072\r\n" + b"}\r\n"
    payload = b"CPiece\x04Test\x03\x80CBar" + text_record + b"\x03\x80" + _ft3_bar_with_one_note() + b"\x03\x80"
    path = tmp_path / "font_control_only.ft3"
    path.write_bytes(payload)
    piece = load_ft3(str(path))
    assert piece.imported_score is None or all(staff.kind != "unknown" for staff in piece.imported_score.staffs)


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
    assert bar.time_sig in {"O", "3/4"}


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


def test_load_ft3_maps_metadata_alias_matrix_and_style_tuning_fields(tmp_path) -> None:
    payload = (
        b"CPiece{\\rtf1\\ansi Demo}\r\n~"
        b"\x00\x00hkey: Gm\r\n"
        b"typ: fantasy\r\n"
        b"ens: 7-course\r\n"
        b"part: score\r\n"
        b"style: french\r\n"
        b"tuning: g2c3f3a3d4g4\r\n"
        b"library: Folger\r\n"
        b"CBar\x03\x80"
    )
    path = tmp_path / "meta_alias_matrix.ft3"
    path.write_bytes(payload)
    piece = load_ft3(str(path))
    assert piece.key == "Gm"
    assert piece.piece_type == "fantasy"
    assert piece.ensemble == "7-course"
    assert piece.part == "score"
    assert piece.style == "french"
    assert piece.tuning == "g2c3f3a3d4g4"
    assert piece.publisher == "Folger"
    assert piece.raw_metadata["library"] == "Folger"


def test_load_ft3_maps_extended_metadata_aliases_for_instrument_style_and_tuning(tmp_path) -> None:
    payload = (
        b"CPiece\x03Raw\x03\x80"
        b"piece: Prelude\r\n"
        b"instrument: voice and lute\r\n"
        b"styl: italian\r\n"
        b"tun: a2d3g3b3e4a4\r\n"
        b"dif: Medium\r\n"
        b"ens: 6-course, soprano\r\n"
        b"publisher/library: KHM\r\n"
        b"page: 12r\r\n"
        b"CBar" + _ft3_bar_with_one_note() + b"\x03\x80"
    )
    path = tmp_path / "meta_extra.ft3"
    path.write_bytes(payload)
    piece = load_ft3(str(path))
    assert piece.instrumentation == "voice and lute"
    assert piece.style == "italian"
    assert piece.tuning == "a2d3g3b3e4a4"
    assert piece.difficulty == "Medium"
    assert piece.ensemble == "6-course, soprano"
    assert piece.publisher == "KHM"
    assert piece.page == "12r"


def test_load_ft3_extracts_preamble_notes_from_prefix(tmp_path) -> None:
    payload = (
        b"Times New Roman\x00\x00- # -@Ayres, v.1 (1597), f. c2v.  "
        b"Encoded and edited by Sarge Gerbode.2"
        b"CPiece{\\rtf1\\ansi Demo}\r\n~"
        b"CBar\x03\x80"
    )
    path = tmp_path / "preamble.ft3"
    path.write_bytes(payload)
    piece = load_ft3(str(path))
    assert piece.notes == ["Ayres, v.1 (1597), f. c2v. Encoded and edited by Sarge Gerbode."]
    assert piece.source == "Ayres, v.1 (1597)"
    assert piece.page == "c2v"
    assert piece.editor == "Sarge Gerbode"


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
