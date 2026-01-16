from midi import _vlq, export_midi
from model import Bar, Chord, Note, Piece


def test_vlq_encoding() -> None:
    assert _vlq(0) == b"\x00"
    assert _vlq(127) == b"\x7f"
    assert _vlq(128) == b"\x81\x00"
    assert _vlq(8192) == b"\xc0\x00"


def test_export_midi_writes_track_and_eot(tmp_path) -> None:
    bar = Bar(chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)])])
    piece = Piece(title="T", bars=[bar], strings=6)
    path = tmp_path / "out.mid"
    msg = export_midi(str(path), piece, overrides={}, durations={}, bar_width=8, settings={})
    assert "Wrote" in msg
    data = path.read_bytes()
    assert data[:4] == b"MThd"
    assert data[14:18] == b"MTrk"
    track_len = int.from_bytes(data[18:22], "big")
    track_data = data[22:]
    assert len(track_data) == track_len
    assert track_data[-4:] == b"\x00\xff\x2f\x00"


def test_export_midi_start_bar_and_tempo(tmp_path) -> None:
    bar0 = Bar(chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)])])
    bar1 = Bar(chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 2, 0)])])
    piece = Piece(title="T", bars=[bar0, bar1], strings=6)
    path = tmp_path / "out.mid"
    msg = export_midi(
        str(path),
        piece,
        overrides={},
        durations={},
        bar_width=8,
        settings={},
        bpm=120,
        start_bar=1,
    )
    assert "Wrote" in msg
    data = path.read_bytes()
    assert b"\xff\x51\x03\x07\xa1\x20" in data
