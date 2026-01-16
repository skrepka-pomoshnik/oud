from ft3 import load_ft3, note_type_to_denominator


def test_load_minimal_ft3(tmp_path) -> None:
    path = tmp_path / "mini.ft3.gz"
    payload = b"CPiece\x04Test\x03\x80"
    import gzip

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
