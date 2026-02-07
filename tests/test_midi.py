from oud.core.model import Bar, Chord, Note, Piece
from oud.exports.midi import (
    BASE_NOTE_VELOCITY,
    _accent_velocity,
    _bar_chord_events,
    _collect_manual_chords,
    _duration_ticks,
    _fret_from_override,
    _meta_tempo,
    _note_off,
    _note_on,
    _parse_tuning,
    _program_change,
    _vlq,
    _write_track,
    build_playback_timeline,
    export_midi,
)


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


def test_parse_tuning_low_to_high() -> None:
    pitches = _parse_tuning("g2c3f3a3d4g4")
    assert pitches == [67, 62, 57, 53, 48, 43]


def test_duration_ticks_dotted() -> None:
    assert _duration_ticks(4, dotted=False) == 480
    assert _duration_ticks(4, dotted=True) == 720


def test_accent_velocity_for_4_4_beats() -> None:
    assert _accent_velocity(0, 4, 4) > BASE_NOTE_VELOCITY
    assert _accent_velocity(480, 4, 4) == BASE_NOTE_VELOCITY
    assert _accent_velocity(960, 4, 4) > BASE_NOTE_VELOCITY
    assert _accent_velocity(960, 4, 4) < _accent_velocity(0, 4, 4)


def test_accent_velocity_for_3_4_beats() -> None:
    assert _accent_velocity(0, 3, 4) > BASE_NOTE_VELOCITY
    assert _accent_velocity(480, 3, 4) == BASE_NOTE_VELOCITY
    assert _accent_velocity(960, 3, 4) == BASE_NOTE_VELOCITY


def test_fret_from_override() -> None:
    assert _fret_from_override("x", "italian") == 10
    assert _fret_from_override("4", "italian") == 4
    assert _fret_from_override("c", "french") == 2
    assert _fret_from_override("z", "french") is None


def test_collect_manual_chords_dotted_duration() -> None:
    overrides = {(0, 0, 0): "a", (0, 1, 0): "c"}
    durations = {(0, 0, 0): 4}
    events = _collect_manual_chords(
        bar_index=0,
        strings=6,
        bar_width=8,
        overrides=overrides,
        durations=durations,
        style="french",
        default_duration=4,
        dotted={(0, 0)},
    )
    assert len(events) == 1
    start, duration, _col, notes = events[0]
    assert start == 0
    assert duration == 720
    assert {note.fret for note in notes} == {0, 2}


def test_bar_chord_events_apply_overrides() -> None:
    bar = Bar(chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)])])
    overrides = {(0, 0, 0): "c"}
    events = _bar_chord_events(
        bar=bar,
        bar_index=0,
        strings=6,
        overrides=overrides,
        durations={},
        bar_width=8,
        style="french",
        default_duration=4,
        dotted=None,
    )
    assert events
    _start, _dur, _col, notes = events[0]
    assert notes[0].fret == 2


def test_build_playback_timeline_includes_bar_and_col() -> None:
    bar = Bar(chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)])])
    piece = Piece(title="T", bars=[bar], strings=6)
    timeline = build_playback_timeline(
        piece,
        overrides={},
        durations={},
        bar_width=8,
        settings={"style": "french"},
        bpm=120,
        start_bar=0,
        dotted=None,
    )
    assert timeline
    start, end, bar_index, col = timeline[0]
    assert start == 0.0
    assert end > start
    assert bar_index == 0
    assert col >= 0


def test_note_messages() -> None:
    assert _note_on(1, 60, 100) == bytes([0x91, 60, 100])
    assert _note_off(2, 60, 64) == bytes([0x82, 60, 64])
    assert _program_change(0, 24) == bytes([0xC0, 24])


def test_meta_tempo() -> None:
    assert _meta_tempo(120) == b"\xff\x51\x03\x07\xa1\x20"


def test_write_track_sorted() -> None:
    data = _write_track([(10, b"\x01"), (0, b"\x02")])
    assert data[:4] == b"MTrk"
    assert b"\xff\x2f\x00" in data
