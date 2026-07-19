from petrucci.model import Bar, Chord, LyricEvent, MelodyEvent, Note
from petrucci.vocal_line import infer_vocal_events


def test_infer_vocal_events_without_explicit_melody_uses_all_chord_onsets() -> None:
    bar = Bar(
        chords=[
            Chord(note_type=5, dotted=False, grid=None, notes=[Note(1, 0, 0)]),
            Chord(note_type=6, dotted=False, grid=None, notes=[Note(2, 0, 0)]),
            Chord(note_type=6, dotted=False, grid=None, notes=[Note(3, 0, 0)]),
            Chord(note_type=6, dotted=False, grid=None, notes=[Note(4, 0, 0)]),
            Chord(note_type=6, dotted=False, grid=None, notes=[Note(5, 0, 0)]),
        ],
        lyric_event_rows=[
            [LyricEvent("Can", 0), LyricEvent("she", 1), LyricEvent("ex", 2, syllabic="begin")],
        ],
    )
    events = infer_vocal_events(bar, tuning_pitches=[67, 62, 57, 53, 48, 43])
    assert [event.chord_index for event in events] == [0, 1, 2, 3, 4]
    assert [event.onset_index for event in events] == [0, 1, 2, 3, 4]


def test_infer_vocal_events_prefers_explicit_melody_pitch_tokens() -> None:
    bar = Bar(
        chords=[Chord(note_type=4, dotted=False, grid=None, notes=[Note(6, 0, 0)])],
        melody_events=[MelodyEvent("e'", 0)],
    )
    events = infer_vocal_events(bar, tuning_pitches=[67, 62, 57, 53, 48, 43])
    assert len(events) == 1
    assert events[0].pitch is not None
    assert events[0].pitch > 64
