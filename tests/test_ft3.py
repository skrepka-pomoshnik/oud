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


def test_frog_galliard_bar8_includes_bass() -> None:
    piece = load_ft3("lutemusic/23a_frogg_galliard_2.ft3")
    bar = piece.bars[7]
    assert any(note.string >= 7 for note in bar.notes)


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
