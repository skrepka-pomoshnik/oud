"""Tablature typing at the onset cursor.

Every edit is one ``apply_tab_transaction`` on the bar chords, so it is one undo
step. The cursor rests on an event onset or on the bar's append slot:

- A fret or rest at the append slot adds an event with the current duration; if
  that event would overflow the bar's meter, it goes to the next bar instead.
- A fret on an event sets that course's note and keeps the event's duration.
- A rest on an event turns the whole event into a rest.
- Duration and dot keys change the event under the cursor, or the bar's last
  event when the cursor is on the append slot (the event just typed).
- Deleting removes the course's note; an event left empty, or a rest, is removed.
"""

from __future__ import annotations

from fractions import Fraction

from oud.editor.core.coordinates import at_append_slot, bar_meter, cursor_event
from oud.editor.core.state import EditorState
from oud.editor.editing.primitives.edits import apply_tab_transaction
from oud.editor.navigation.motions import apply_motion_target, target_advance_next_bar_home
from petrucci.core.model import Chord
from petrucci.input.tablature.mutation import (
    TabDuration,
    TabEdit,
    TabEditIntent,
    TabEditTransaction,
    TabMutationError,
    TabPosition,
    bar_content_length,
)

NO_NOTE_TO_REPLACE = "No note to replace"
NO_EVENT = "No event here"


def _bar_chords(state: EditorState) -> list[Chord]:
    return state.piece.bars[state.cursor_bar].chords


def _apply(state: EditorState, *edits: TabEdit) -> bool:
    try:
        apply_tab_transaction(state, TabEditTransaction(edits))
    except TabMutationError as exc:
        state.message = f"Cannot edit: {exc}"
        return False
    return True


def _position(state: EditorState, course_index: int | None = None) -> TabPosition:
    course = None if course_index is None else course_index + 1
    return TabPosition(state.cursor_bar, state.cursor_onset, course)


def _move_past_full_bar(state: EditorState, duration: TabDuration) -> None:
    """Move to the next bar when a new event would not fit in this one."""

    meter = bar_meter(state, state.cursor_bar)
    length = bar_content_length(state.piece.bars[state.cursor_bar])
    if meter is not None and length + duration.whole_notes > meter and _bar_chords(state):
        apply_motion_target(state, target_advance_next_bar_home(state))


def current_duration(state: EditorState) -> TabDuration:
    return TabDuration(state.current_duration)


def _prepare_entry(state: EditorState, *, replace_only: bool) -> bool:
    """Check the target; a new event that would overflow moves to the next bar first."""

    if not 0 <= state.cursor_bar < len(state.piece.bars):
        return False
    if not at_append_slot(state):
        return True
    if replace_only:
        state.message = NO_NOTE_TO_REPLACE
        return False
    _move_past_full_bar(state, current_duration(state))
    return True


def type_fret(state: EditorState, course_index: int, fret: int, *, replace_only: bool = False) -> bool:
    """Enter ``fret`` on ``course_index`` at the cursor; True when the score changed."""

    if not _prepare_entry(state, replace_only=replace_only):
        return False
    if at_append_slot(state):
        edit = TabEdit(_position(state, course_index), TabEditIntent.NOTE, fret=fret, duration=current_duration(state))
        return _apply(state, edit)
    return _apply(state, TabEdit(_position(state, course_index), TabEditIntent.CHORD, fret=fret))


def type_rest(state: EditorState, *, replace_only: bool = False) -> bool:
    if not _prepare_entry(state, replace_only=replace_only):
        return False
    if at_append_slot(state):
        return _apply(state, TabEdit(_position(state), TabEditIntent.REST, duration=current_duration(state)))
    return _apply(state, TabEdit(_position(state), TabEditIntent.REST))


def _target_event(state: EditorState) -> tuple[Fraction, Chord] | None:
    """The event a duration or dot key changes, with its onset."""

    chords = _bar_chords(state)
    if not chords:
        return None
    index = cursor_event(state)
    if index == len(chords):
        index -= 1
    onset = sum((TabDuration.of(chord).whole_notes for chord in chords[:index]), Fraction(0))
    return onset, chords[index]


def _change_duration(state: EditorState, target: tuple[Fraction, Chord], duration: TabDuration) -> bool:
    onset, _chord = target
    on_append_slot = at_append_slot(state)
    edit = TabEdit(TabPosition(state.cursor_bar, onset), TabEditIntent.DURATION, duration=duration)
    if not _apply(state, edit):
        return False
    if on_append_slot:
        # The append slot moves with the length of the event before it.
        state.cursor_onset = bar_content_length(state.piece.bars[state.cursor_bar])
    return True


def set_duration(state: EditorState, denominator: int) -> bool:
    """Make ``denominator`` the current duration and apply it to the target event."""

    state.current_duration = denominator
    state.message = f"Duration {denominator}"
    target = _target_event(state) if 0 <= state.cursor_bar < len(state.piece.bars) else None
    if target is None:
        return False
    dotted = TabDuration.of(target[1]).dotted
    return _change_duration(state, target, TabDuration(denominator, dotted))


def toggle_dot(state: EditorState) -> bool:
    target = _target_event(state) if 0 <= state.cursor_bar < len(state.piece.bars) else None
    if target is None:
        state.message = NO_EVENT
        return False
    duration = TabDuration.of(target[1])
    if not _change_duration(state, target, TabDuration(duration.denominator, not duration.dotted)):
        return False
    state.message = "Dot off" if duration.dotted else "Dot on"
    return True


def delete_at_cursor(state: EditorState, course_index: int) -> bool:
    """Delete the course's note under the cursor; returns True when an event was removed."""

    if not 0 <= state.cursor_bar < len(state.piece.bars) or at_append_slot(state):
        return False
    chords = _bar_chords(state)
    chord = chords[cursor_event(state)]
    course = course_index + 1
    if chord.notes and all(note.string != course for note in chord.notes):
        return False
    count = len(chords)
    whole_event = not chord.notes or all(note.string == course for note in chord.notes)
    position = _position(state) if whole_event else _position(state, course_index)
    if not _apply(state, TabEdit(position, TabEditIntent.DELETE)):
        return False
    state.clamp()
    return len(_bar_chords(state)) < count
