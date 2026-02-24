import gzip

from oud.core.ft3 import load_ft3, note_type_to_denominator


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


def test_forlorne_ft3_common_time_halfbar_fix_applied() -> None:
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
    assert abs(total - 4.0) < 0.01
    assert bar.time_sig == "C"


def test_load_ft3_extracts_section_metadata_from_real_file() -> None:
    piece = load_ft3("lutemusic/23a_frogg_galliard_2.ft3")
    assert piece.key == "GM"
    assert piece.piece_type == "galliard"
    assert piece.difficulty == "Challenge"
    assert piece.ensemble == "7-course"
    assert piece.title == "23a. The frog galliard"
    assert piece.composer == "John Dowland"


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
