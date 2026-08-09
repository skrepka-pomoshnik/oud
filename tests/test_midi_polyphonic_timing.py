from oud.exports.midi.projection import _timed_vocal_events
from oud.exports.midi.serialization import _scale_chord_events_to_bar
from petrucci.adapters.vocal import VocalEvent


def test_scale_chord_events_registers_imported_staff_to_tablature_bar() -> None:
    events = [(0, 120, 0, []), (120, 120, 1, []), (240, 240, 2, [])]

    assert _scale_chord_events_to_bar(events, 960) == [
        (0, 240, 0, []),
        (240, 240, 1, []),
        (480, 480, 2, []),
    ]


def test_explicit_staff_rhythm_scales_to_tablature_bar_without_snapping() -> None:
    events = [
        VocalEvent(onset_index=0, chord_index=0, pitch=60, note_type=4, dotted=False),
        VocalEvent(onset_index=1, chord_index=1, pitch=62, note_type=5, dotted=False),
        VocalEvent(onset_index=2, chord_index=2, pitch=64, note_type=5, dotted=False),
    ]

    assert [
        (start, duration)
        for _event, start, duration in _timed_vocal_events(
            events,
            [],
            has_explicit_melody=True,
            target_ticks=1920,
        )
    ] == [(0, 960), (960, 480), (1440, 480)]
