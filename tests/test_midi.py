from oud.core.model import Bar, Chord, LyricEvent, MelodyEvent, Note, Piece
from oud.core.render_utils import chord_positions as render_chord_positions
from oud.exports.midi import (
    BASE_NOTE_VELOCITY,
    _accent_velocity,
    _bar_chord_events,
    _chord_positions,
    _collect_manual_chords,
    _duration_ticks,
    _fret_from_override,
    _meta_tempo,
    _note_off,
    _note_on,
    _parse_tuning,
    _program_change,
    _resolved_tuning_for_piece,
    _vlq,
    _write_track,
    build_playback_timeline,
    export_midi,
)


def _track_data(path) -> bytes:
    data = path.read_bytes()
    track_len = int.from_bytes(data[18:22], "big")
    return data[22 : 22 + track_len]


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


def test_export_midi_plays_note_ornament_when_enabled(tmp_path) -> None:
    bar = Bar(
        chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0, left_ornament="#")])],
    )
    piece = Piece(title="T", bars=[bar], strings=6)
    path = tmp_path / "orn_enabled.mid"
    export_midi(
        str(path),
        piece,
        overrides={},
        durations={},
        bar_width=8,
        settings={"showornaments": "on", "ft3ornaments": "both"},
    )
    track = _track_data(path)
    assert track.count(bytes([0x90])) == 2


def test_export_midi_skips_note_ornament_when_disabled(tmp_path) -> None:
    bar = Bar(
        chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0, left_ornament="#")])],
    )
    piece = Piece(title="T", bars=[bar], strings=6)
    path = tmp_path / "orn_disabled.mid"
    export_midi(
        str(path),
        piece,
        overrides={},
        durations={},
        bar_width=8,
        settings={"showornaments": "off", "ft3ornaments": "both"},
    )
    track = _track_data(path)
    assert track.count(bytes([0x90])) == 1


def test_export_midi_includes_vocal_channel_for_explicit_melody_bars(tmp_path) -> None:
    bar = Bar(
        chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)])],
        lyric_event_rows=[[LyricEvent("Can", 0)]],
        melody_events=[MelodyEvent("d", 0)],
    )
    piece = Piece(title="T", bars=[bar], strings=6)
    path = tmp_path / "vocal.mid"
    export_midi(
        str(path),
        piece,
        overrides={},
        durations={},
        bar_width=8,
        settings={"midivocalpatch": "54"},
    )
    track = _track_data(path)
    assert bytes([0xC1, 54]) in track
    assert bytes([0x91]) in track


def test_export_midi_skips_explicit_vocal_rest_events(tmp_path) -> None:
    bar = Bar(
        chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)])],
        lyric_event_rows=[[LyricEvent("Can", 0)]],
        melody_events=[MelodyEvent("r", 0, note_type=4, is_rest=True)],
    )
    piece = Piece(title="T", bars=[bar], strings=6)
    path = tmp_path / "vocal_rest.mid"
    export_midi(
        str(path),
        piece,
        overrides={},
        durations={},
        bar_width=8,
        settings={"midivocalpatch": "54"},
    )
    track = _track_data(path)
    assert bytes([0xC1, 54]) in track
    assert bytes([0x91]) not in track


def test_export_midi_skips_inferred_vocal_channel_by_default(tmp_path) -> None:
    bar = Bar(
        chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)])],
        lyric_event_rows=[[LyricEvent("Can", 0)]],
    )
    piece = Piece(title="T", bars=[bar], strings=6)
    path = tmp_path / "vocal_inferred_off.mid"
    export_midi(
        str(path),
        piece,
        overrides={},
        durations={},
        bar_width=8,
        settings={},
    )
    track = _track_data(path)
    assert bytes([0x91]) not in track


def test_export_midi_allows_inferred_vocal_channel_when_enabled(tmp_path) -> None:
    bar = Bar(
        chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)])],
        lyric_event_rows=[[LyricEvent("Can", 0)]],
    )
    piece = Piece(title="T", bars=[bar], strings=6)
    path = tmp_path / "vocal_inferred_on.mid"
    export_midi(
        str(path),
        piece,
        overrides={},
        durations={},
        bar_width=8,
        settings={"midivocalinfer": "on"},
    )
    track = _track_data(path)
    assert bytes([0x91]) in track


def test_export_midi_plays_bar_ornament_when_enabled(tmp_path) -> None:
    bar = Bar(chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)])])
    piece = Piece(title="T", bars=[bar], strings=6)
    path = tmp_path / "bar_orn_enabled.mid"
    export_midi(
        str(path),
        piece,
        overrides={},
        durations={},
        bar_width=8,
        settings={"showornaments": "on"},
        ornaments={(0, 0): "#"},
    )
    track = _track_data(path)
    assert track.count(bytes([0x90])) == 2


def test_parse_tuning_low_to_high() -> None:
    pitches = _parse_tuning("g2c3f3a3d4g4")
    assert pitches == [67, 62, 57, 53, 48, 43]


def test_resolved_tuning_prepends_default_bass_strings_when_missing() -> None:
    piece = Piece(title="T", bars=[Bar()], strings=7)
    tuning = _resolved_tuning_for_piece(piece, {"tuning": "g2c3f3a3d4g4", "bassstrings": ""})
    assert tuning.startswith("d2")


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


def test_build_playback_timeline_uses_chord_index_for_marker_col() -> None:
    bar = Bar(
        chords=[
            Chord(note_type=7, dotted=False, grid=None, notes=[Note(1, 0, 0)]),
            Chord(note_type=7, dotted=False, grid=None, notes=[Note(2, 1, 0)]),
            Chord(note_type=7, dotted=False, grid=None, notes=[Note(3, 2, 0)]),
            Chord(note_type=7, dotted=False, grid=None, notes=[Note(4, 3, 0)]),
        ],
    )
    piece = Piece(title="T", bars=[bar], strings=6)
    timeline = build_playback_timeline(
        piece,
        overrides={},
        durations={},
        bar_width=2,
        settings={"style": "french"},
        bpm=120,
        start_bar=0,
        dotted=None,
    )
    assert [cursor.col for cursor in timeline] == [0, 1, 2, 3]


def test_build_playback_timeline_duet_score_pairs_play_simultaneously() -> None:
    piece = Piece(
        title="Duet",
        bars=[
            # Sequential halves duet-score storage: top staff then bottom staff.
            Bar(chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)])]),
            Bar(chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 2, 0)])]),
            Bar(chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(2, 1, 0)])]),
            Bar(chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(3, 2, 0)])]),
        ],
        strings=6,
        style="french",
        ensemble="lute 1:6-course, lute 2:6-course",
        part="score",
    )
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
    assert len(timeline) >= 4
    # First logical pair (raw bars 0 and 2 in sequential-halves storage) must start together.
    first_pair = [c for c in timeline if c.bar in (0, 2)]
    assert len(first_pair) == 2
    assert first_pair[0].start == first_pair[1].start == 0.0
    # Second logical pair starts later, and raw bars 1 and 3 align to each other.
    second_pair = [c for c in timeline if c.bar in (1, 3)]
    assert len(second_pair) == 2
    assert second_pair[0].start == second_pair[1].start
    assert second_pair[0].start > 0.0


def test_build_playback_timeline_repeats_for_multiple_lyric_verses_when_enabled() -> None:
    piece = Piece(
        title="Verses",
        bars=[
            Bar(
                chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)])],
                lyric_event_rows=[
                    [LyricEvent("Can", 0, verse=0)],
                    [LyricEvent("Was", 0, verse=1)],
                ],
            ),
        ],
        strings=6,
    )
    timeline = build_playback_timeline(
        piece,
        overrides={},
        durations={},
        bar_width=8,
        settings={"style": "french", "playverses": "all"},
        bpm=120,
        start_bar=0,
        dotted=None,
    )
    assert len(timeline) == 2
    assert timeline[1].start >= timeline[0].end


def test_build_playback_timeline_plays_once_when_playverses_disabled() -> None:
    piece = Piece(
        title="Verses",
        bars=[
            Bar(
                chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)])],
                lyric_event_rows=[
                    [LyricEvent("Can", 0, verse=0)],
                    [LyricEvent("Was", 0, verse=1)],
                ],
            ),
        ],
        strings=6,
    )
    timeline = build_playback_timeline(
        piece,
        overrides={},
        durations={},
        bar_width=8,
        settings={"style": "french", "playverses": "once"},
        bpm=120,
        start_bar=0,
        dotted=None,
    )
    assert len(timeline) == 1


def test_build_playback_timeline_defaults_to_once_for_multiple_lyric_verses() -> None:
    piece = Piece(
        title="Verses",
        bars=[
            Bar(
                chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)])],
                lyric_event_rows=[
                    [LyricEvent("Can", 0, verse=0)],
                    [LyricEvent("Was", 0, verse=1)],
                ],
            ),
        ],
        strings=6,
    )
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
    assert len(timeline) == 1


def test_build_playback_timeline_unfolds_structural_repeats() -> None:
    piece = Piece(
        title="Repeats",
        bars=[
            Bar(
                repeat=".:",
                chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)])],
            ),
            Bar(chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 1, 0)])]),
            Bar(
                repeat=":.",
                chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 2, 0)])],
            ),
            Bar(chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 3, 0)])]),
        ],
        strings=6,
    )
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
    assert [cursor.bar for cursor in timeline] == [0, 1, 2, 0, 1, 2, 3]


def test_export_midi_repeats_structural_section_once(tmp_path) -> None:
    piece = Piece(
        title="Repeats",
        bars=[
            Bar(
                repeat=".:",
                chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)])],
            ),
            Bar(chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 1, 0)])]),
            Bar(
                repeat=":.",
                chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 2, 0)])],
            ),
            Bar(chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 3, 0)])]),
        ],
        strings=6,
    )
    path = tmp_path / "repeat.mid"
    export_midi(
        str(path),
        piece,
        overrides={},
        durations={},
        bar_width=8,
        settings={},
    )
    track = _track_data(path)
    assert track.count(bytes([0x90])) == 7


def test_build_playback_timeline_skips_first_ending_on_second_pass() -> None:
    piece = Piece(
        title="Volta",
        bars=[
            Bar(
                repeat=".:",
                chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)])],
            ),
            Bar(
                ending_numbers=(1,),
                repeat=":.",
                chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 1, 0)])],
            ),
            Bar(
                ending_numbers=(2,),
                chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 2, 0)])],
            ),
            Bar(chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 3, 0)])]),
        ],
        strings=6,
    )
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
    assert [cursor.bar for cursor in timeline] == [0, 1, 0, 2, 3]


def test_export_midi_respects_first_and_second_endings(tmp_path) -> None:
    piece = Piece(
        title="Volta",
        bars=[
            Bar(
                repeat=".:",
                chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 0, 0)])],
            ),
            Bar(
                ending_numbers=(1,),
                repeat=":.",
                chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 1, 0)])],
            ),
            Bar(
                ending_numbers=(2,),
                chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 2, 0)])],
            ),
            Bar(chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(1, 3, 0)])]),
        ],
        strings=6,
    )
    path = tmp_path / "volta.mid"
    export_midi(
        str(path),
        piece,
        overrides={},
        durations={},
        bar_width=8,
        settings={},
    )
    track = _track_data(path)
    assert track.count(bytes([0x90])) == 5


def test_midi_chord_positions_match_render_positions() -> None:
    bar = Bar(
        chords=[
            Chord(note_type=6, dotted=True, grid=None, notes=[Note(1, 0, 0)]),
            Chord(note_type=7, dotted=False, grid=None, notes=[Note(2, 2, 0)]),
            Chord(note_type=6, dotted=False, grid=None, notes=[Note(3, 4, 0)]),
            Chord(note_type=5, dotted=False, grid=None, notes=[Note(4, 5, 0)]),
            Chord(note_type=7, dotted=False, grid=None, notes=[Note(5, 7, 0)]),
        ],
    )
    bar_width = 16
    expected_cols = [col for (col, _den, _dot) in render_chord_positions(bar, bar_width, 4)]
    midi_cols = _chord_positions(bar.chords, bar_width, 4)
    assert midi_cols == expected_cols


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
