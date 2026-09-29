from __future__ import annotations

from fractions import Fraction

from oud.editor.core.coordinates import bar_stops, cursor_event
from oud.editor.core.state import EditorState
from oud.editor.editing.primitives.undo import redo, undo
from oud.editor.services.screen.compose import compose_editor_frame
from petrucci.core.model import Bar, Chord, Note, Piece
from petrucci.input.tablature.mutation import TabDuration, event_onsets
from petrucci.terminal.canvas.screen import A_REVERSE
from tests.helpers_keyscript import keyscript_state, press_keys

ESC = 27
FRENCH_SIXTEENTH = "5"
FRENCH_THIRTY_SECOND = "6"
FRENCH_EIGHTH = "4"


def _state(*bars: Bar, width: int = 160, style: str = "french") -> EditorState:
    piece = Piece(title="T", bars=list(bars) or [Bar()], strings=6, style=style)
    return keyscript_state(piece=piece, width=width, height=30, style=style, settings_override={"time": "4/4"})


def _events(state: EditorState, bar: int = 0) -> list[tuple[TabDuration, list[tuple[int, int]]]]:
    return [
        (TabDuration.of(chord), [(note.string, note.fret) for note in chord.notes])
        for chord in state.piece.bars[bar].chords
    ]


def _cursor_x(state: EditorState) -> int:
    """Leftmost reverse-video cell above the status row: the drawn tablature cursor."""

    frame = compose_editor_frame(state, height=state.screen_height, width=state.screen_width).frame
    cells = [
        (x, y)
        for y, row in enumerate(frame.attrs[:-1])
        for x, attr in enumerate(row)
        if attr & A_REVERSE and frame.lines[y][x] not in " "
    ]
    assert cells, "cursor not drawn"
    return min(cells)[0]


def test_a_bar_of_sixteenths_and_a_bar_of_thirty_seconds_can_be_typed_and_visited() -> None:
    state = _state()
    frets = "abcdefgh"
    keys: list[int | str] = ["i", FRENCH_SIXTEENTH]
    keys += [frets[index % len(frets)] for index in range(16)]
    keys += [FRENCH_THIRTY_SECOND]
    keys += [frets[index % len(frets)] for index in range(32)]
    press_keys(state, [*keys, ESC])

    assert [duration for duration, _notes in _events(state, 0)] == [TabDuration(16)] * 16
    assert [duration for duration, _notes in _events(state, 1)] == [TabDuration(32)] * 32
    assert event_onsets(state.piece.bars[1]) == tuple(Fraction(index, 32) for index in range(32))
    assert [notes for _duration, notes in _events(state, 1)][:3] == [[(1, 0)], [(1, 1)], [(1, 2)]]

    for bar, count in ((0, 16), (1, 32)):
        state.cursor_bar, state.cursor_onset = bar, Fraction(0)
        positions = [_cursor_x(state)]
        events = [cursor_event(state)]
        for _ in range(count - 1):
            press_keys(state, ["l"])
            positions.append(_cursor_x(state))
            events.append(cursor_event(state))
        assert events == list(range(count))
        assert positions == sorted(set(positions)), f"bar {bar + 1} cursor columns repeat: {positions}"


def test_full_bar_has_no_append_slot_and_typing_moves_to_the_next_bar() -> None:
    state = _state()
    press_keys(state, ["i", "3", "a", "b", "c", "d"])

    assert len(state.piece.bars) == 2
    assert (state.cursor_bar, state.cursor_onset) == (1, Fraction(0))
    assert bar_stops(state, 0) == (Fraction(0), Fraction(1, 4), Fraction(1, 2), Fraction(3, 4))


def test_a_duration_key_after_a_note_changes_that_note() -> None:
    state = _state()
    press_keys(state, ["i", "a", FRENCH_EIGHTH, "b", ESC])

    assert _events(state) == [(TabDuration(8), [(1, 0)]), (TabDuration(8), [(1, 1)])]


def test_dot_applies_to_the_last_typed_note() -> None:
    state = _state()
    press_keys(state, ["i", "3", "a", ".", ESC])

    assert _events(state) == [(TabDuration(4, dotted=True), [(1, 0)])]


def test_chords_are_built_by_stepping_back_onto_the_event() -> None:
    state = _state()
    press_keys(state, ["i", "a", 260, 258, "c", ESC])

    assert _events(state) == [(TabDuration(4), [(1, 0), (2, 2)])]


def test_rest_key_appends_a_rest_and_turns_an_event_into_a_rest() -> None:
    state = _state(Bar(chords=[Chord(4, False, None, [Note(1, 0, 0)]), Chord(4, False, None, [Note(1, 1, 0)])]))
    press_keys(state, ["i", "z", ESC])
    assert _events(state)[0] == (TabDuration(4), [])

    state.cursor_onset = Fraction(1, 2)
    press_keys(state, ["i", "z", ESC])
    assert _events(state)[2] == (TabDuration(4), [])


def test_x_deletes_the_course_note_then_the_empty_event() -> None:
    state = _state(
        Bar(chords=[Chord(4, False, None, [Note(1, 0, 0), Note(2, 2, 0)]), Chord(5, False, None, [Note(1, 3, 0)])])
    )
    press_keys(state, ["x"])
    assert _events(state) == [(TabDuration(4), [(2, 2)]), (TabDuration(8), [(1, 3)])]

    press_keys(state, ["j", "x"])
    assert _events(state) == [(TabDuration(8), [(1, 3)])]
    assert state.piece.bars[0].notes == [note for chord in state.piece.bars[0].chords for note in chord.notes]


def test_replace_mode_changes_existing_notes_only() -> None:
    state = _state(Bar(chords=[Chord(4, False, None, [Note(1, 0, 0)])]))
    press_keys(state, ["R", "c", ESC])
    assert _events(state) == [(TabDuration(4), [(1, 2)])]

    state.cursor_onset = Fraction(1, 4)
    press_keys(state, ["R", "d", ESC])
    assert _events(state) == [(TabDuration(4), [(1, 2)])]
    assert state.message == "No note to replace"


def test_each_typed_note_is_one_undo_step() -> None:
    state = _state()
    press_keys(state, ["i", "a", "b", ESC])
    assert len(_events(state)) == 2

    undo(state, config_path="config.toml")
    assert _events(state) == [(TabDuration(4), [(1, 0)])]
    redo(state, config_path="config.toml")
    assert len(_events(state)) == 2


def test_imported_bars_keep_their_chords_when_edited() -> None:
    source = [Chord(5, True, "#", [Note(1, 0, 0), Note(3, 2, 0)]), Chord(6, False, "#", [Note(2, 1, 0)])]
    state = _state(Bar(chords=source))
    press_keys(state, ["j", "j", "i", "e", ESC])

    assert _events(state) == [
        (TabDuration(8, dotted=True), [(1, 0), (3, 4)]),
        (TabDuration(16), [(2, 1)]),
    ]
    assert state.overrides == {}


def test_italian_two_digit_frets_and_bass_courses_are_notes() -> None:
    state = _state(style="italian")
    press_keys(state, ["i", ",", "1", "2", ESC])
    assert _events(state) == [(TabDuration(4), [(1, 12)])]
