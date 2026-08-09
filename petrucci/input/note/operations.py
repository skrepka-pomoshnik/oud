"""Atomic standard-note entry for Petrucci's canonical score model."""

from __future__ import annotations

from dataclasses import replace
from fractions import Fraction

from petrucci.input.note.draft import (
    EventLocation,
    ScoreDraft,
    ensure_event_position,
    events_at,
    previous_events,
    remove_event_attachments,
    remove_event_spans,
)
from petrucci.input.note.types import (
    AddLyric,
    AddSlur,
    AddTie,
    ChangeDuration,
    DeleteEvent,
    EnterNote,
    EnterRest,
    EventInputStyle,
    InputPitch,
    NotatedDuration,
    NoteInputChange,
    NoteInputChangeKind,
    NoteInputContext,
    NoteInputError,
    NoteInputOperation,
    NoteInputResult,
    NoteInputTransaction,
    RemoveLyric,
    RemoveSlur,
    RemoveTie,
    ReplacePitch,
)
from petrucci.core.score import (
    EventKind,
    LyricSyllable,
    NotationEvent,
    NotationScore,
    NotationSpan,
    ScoreValidationError,
    SpanKind,
    TupletRatio,
    WrittenPitch,
)


def apply_note_input(score: NotationScore, transaction: NoteInputTransaction) -> NoteInputResult:
    """Apply every operation atomically and return a new validated score."""

    draft = ScoreDraft.from_score(score)
    context = transaction.context
    changes: list[NoteInputChange] = []
    for index, operation in enumerate(transaction.operations):
        try:
            context, operation_changes = _apply_operation(draft, context, operation)
        except NoteInputError as exc:
            raise exc.at_operation(index) from exc
        except ScoreValidationError as exc:
            raise NoteInputError("invalid-event", str(exc), operation_index=index) from exc
        changes.extend(operation_changes)
    try:
        committed = draft.commit()
    except ScoreValidationError as exc:
        raise NoteInputError("invalid-score", str(exc), operation_index=len(transaction.operations) - 1) from exc
    return NoteInputResult(committed, context, tuple(changes))


def _apply_operation(
    draft: ScoreDraft,
    context: NoteInputContext,
    operation: NoteInputOperation,
) -> tuple[NoteInputContext, list[NoteInputChange]]:
    if isinstance(operation, EnterNote):
        return _enter_note(draft, context, operation)
    if isinstance(operation, EnterRest):
        return _enter_rest(draft, context, operation)
    if isinstance(operation, ReplacePitch):
        return _replace_pitch(draft, context, operation)
    if isinstance(operation, ChangeDuration):
        return _change_duration(draft, context, operation)
    return _apply_structural_operation(draft, context, operation)


def _apply_structural_operation(
    draft: ScoreDraft,
    context: NoteInputContext,
    operation: NoteInputOperation,
) -> tuple[NoteInputContext, list[NoteInputChange]]:
    if isinstance(operation, DeleteEvent):
        return context, _delete_event(draft, operation)
    if isinstance(operation, AddTie):
        return context, [_add_tie(draft, operation)]
    if isinstance(operation, RemoveTie):
        return context, [_remove_tie(draft, operation)]
    return _apply_annotation_operation(draft, context, operation)


def _apply_annotation_operation(
    draft: ScoreDraft,
    context: NoteInputContext,
    operation: NoteInputOperation,
) -> tuple[NoteInputContext, list[NoteInputChange]]:
    if isinstance(operation, AddSlur):
        return context, [_add_slur(draft, operation)]
    if isinstance(operation, RemoveSlur):
        return context, [_remove_slur(draft, operation)]
    if isinstance(operation, AddLyric):
        return context, [_add_lyric(draft, operation)]
    if isinstance(operation, RemoveLyric):
        return context, [_remove_lyric(draft, operation)]
    raise NoteInputError("unsupported-operation", f"unsupported note-input operation {type(operation).__name__}")


def _enter_note(
    draft: ScoreDraft,
    context: NoteInputContext,
    operation: EnterNote,
) -> tuple[NoteInputContext, list[NoteInputChange]]:
    staff, measure = draft.position(operation.position)
    pitch = resolve_input_pitch(operation.pitch, anchor=context.pitch_anchor)
    if operation.replace_event_id is not None:
        change = _replace_with_note(draft, operation, pitch)
    elif operation.chord:
        change = _stack_pitch(draft, operation, pitch)
    else:
        if events_at(measure, operation.position):
            raise NoteInputError("event-collision", "an event already exists at the requested onset and voice")
        duration = operation.duration or context.duration
        event_id = draft.reserve_id(operation.event_id, prefix="event")
        event = _new_event(event_id, operation, pitch, duration)
        draft.insert_event(measure, event)
        change = NoteInputChange(NoteInputChangeKind.INSERT_EVENT, event.id, staff.source.id, measure.source.id)
    context = _updated_context(context, duration=operation.duration, pitch=pitch)
    changes = [change]
    if operation.tie_from_previous:
        changes.append(_tie_entered_pitch(draft, change.element_id, pitch))
    return context, changes


def _new_event(
    event_id: str,
    operation: EnterNote,
    pitch: WrittenPitch,
    duration: NotatedDuration,
) -> NotationEvent:
    style = operation.style or EventInputStyle()
    return NotationEvent(
        id=event_id,
        onset=operation.position.onset,
        duration=duration.duration,
        kind=EventKind.NOTE,
        pitches=(pitch,),
        voice=operation.position.voice,
        stem=style.stem,
        beam=style.beam,
        tuplet=duration.tuplet,
        fermata=style.fermata,
        dynamic=style.dynamic,
        ornament=style.ornament,
        editorial_brackets=style.editorial_brackets,
        grace=style.grace,
    )


def _replace_with_note(draft: ScoreDraft, operation: EnterNote, pitch: WrittenPitch) -> NoteInputChange:
    assert operation.replace_event_id is not None
    location = draft.event(operation.replace_event_id)
    ensure_event_position(location, operation.position)
    event = location.event
    duration, tuplet = _replacement_duration(event, operation.duration)
    values = _style_values(operation.style, event)
    replacement = replace(
        event,
        duration=duration,
        kind=EventKind.NOTE,
        pitches=(pitch,),
        tuplet=tuplet,
        **values,
    )
    location.measure.events[location.event_index] = replacement
    return _change_for_location(NoteInputChangeKind.REPLACE_EVENT, location)


def _stack_pitch(draft: ScoreDraft, operation: EnterNote, pitch: WrittenPitch) -> NoteInputChange:
    _staff, measure = draft.position(operation.position)
    candidates = events_at(measure, operation.position)
    if len(candidates) != 1:
        raise NoteInputError("chord-target", "chord entry requires exactly one event at the requested position")
    location = draft.event(candidates[0].id)
    event = location.event
    if event.kind is not EventKind.NOTE:
        raise NoteInputError("chord-target", "cannot stack a pitch onto a rest")
    if pitch in event.pitches:
        raise NoteInputError("duplicate-pitch", f"event {event.id!r} already contains {pitch!r}")
    duration, tuplet = _replacement_duration(event, operation.duration)
    values = _style_values(operation.style, event)
    replacement = replace(event, duration=duration, pitches=(*event.pitches, pitch), tuplet=tuplet, **values)
    location.measure.events[location.event_index] = replacement
    return _change_for_location(NoteInputChangeKind.STACK_PITCH, location)


def _enter_rest(
    draft: ScoreDraft,
    context: NoteInputContext,
    operation: EnterRest,
) -> tuple[NoteInputContext, list[NoteInputChange]]:
    _validate_rest_style(operation.style)
    staff, measure = draft.position(operation.position)
    if operation.replace_event_id is not None:
        location = draft.event(operation.replace_event_id)
        ensure_event_position(location, operation.position)
        event = location.event
        duration, tuplet = _replacement_duration(event, operation.duration)
        values = _rest_style_values(operation.style, event)
        location.measure.events[location.event_index] = replace(
            event,
            duration=duration,
            kind=EventKind.REST,
            pitches=(),
            tuplet=tuplet,
            **values,
        )
        change = _change_for_location(NoteInputChangeKind.REPLACE_EVENT, location)
        removed_span_changes = _span_removal_changes(location, remove_event_spans(location, event.id))
    else:
        if events_at(measure, operation.position):
            raise NoteInputError("event-collision", "an event already exists at the requested onset and voice")
        duration = operation.duration or context.duration
        event_id = draft.reserve_id(operation.event_id, prefix="event")
        style = operation.style or EventInputStyle()
        event = NotationEvent(
            id=event_id,
            onset=operation.position.onset,
            duration=duration.duration,
            kind=EventKind.REST,
            voice=operation.position.voice,
            stem=style.stem,
            beam=style.beam,
            tuplet=duration.tuplet,
            fermata=style.fermata,
            dynamic=style.dynamic,
        )
        draft.insert_event(measure, event)
        change = NoteInputChange(NoteInputChangeKind.INSERT_EVENT, event.id, staff.source.id, measure.source.id)
        removed_span_changes = []
    return _updated_context(context, duration=operation.duration), [change, *removed_span_changes]


def _validate_rest_style(style: EventInputStyle | None) -> None:
    if style is None:
        return
    if style.ornament is not None or style.editorial_brackets or style.grace:
        raise NoteInputError(
            "invalid-rest-style",
            "rests cannot carry ornaments, editorial brackets, or grace-note style",
        )


def _replace_pitch(
    draft: ScoreDraft,
    context: NoteInputContext,
    operation: ReplacePitch,
) -> tuple[NoteInputContext, list[NoteInputChange]]:
    location = draft.event(operation.event_id)
    ensure_event_position(location, operation.position)
    event = location.event
    if event.kind is not EventKind.NOTE:
        raise NoteInputError("not-a-note", f"event {event.id!r} is a rest")
    if not 0 <= operation.pitch_index < len(event.pitches):
        raise NoteInputError("pitch-index", f"event {event.id!r} has no pitch index {operation.pitch_index}")
    pitch = resolve_input_pitch(operation.pitch, anchor=context.pitch_anchor)
    pitches = list(event.pitches)
    if pitch in pitches and pitches[operation.pitch_index] != pitch:
        raise NoteInputError("duplicate-pitch", f"event {event.id!r} already contains {pitch!r}")
    pitches[operation.pitch_index] = pitch
    location.measure.events[location.event_index] = replace(event, pitches=tuple(pitches))
    change = _change_for_location(NoteInputChangeKind.REPLACE_PITCH, location)
    return replace(context, pitch_anchor=pitch), [change]


def _change_duration(
    draft: ScoreDraft,
    context: NoteInputContext,
    operation: ChangeDuration,
) -> tuple[NoteInputContext, list[NoteInputChange]]:
    location = draft.event(operation.event_id)
    ensure_event_position(location, operation.position)
    location.measure.events[location.event_index] = replace(
        location.event,
        duration=operation.duration.duration,
        tuplet=operation.duration.tuplet,
    )
    change = _change_for_location(NoteInputChangeKind.CHANGE_DURATION, location)
    return replace(context, duration=operation.duration), [change]


def _delete_event(draft: ScoreDraft, operation: DeleteEvent) -> list[NoteInputChange]:
    location = draft.event(operation.event_id)
    ensure_event_position(location, operation.position)
    change = _change_for_location(NoteInputChangeKind.DELETE_EVENT, location)
    spans, lyrics = remove_event_attachments(location, operation.event_id)
    attachment_changes = _span_removal_changes(location, spans)
    attachment_changes.extend(
        NoteInputChange(
            NoteInputChangeKind.REMOVE_LYRIC,
            lyric.id,
            location.staff.source.id,
            location.measure.source.id,
        )
        for lyric in lyrics
    )
    draft.delete_event(location)
    return [change, *attachment_changes]


def _span_removal_changes(
    location: EventLocation,
    spans: tuple[NotationSpan, ...],
) -> list[NoteInputChange]:
    return [
        NoteInputChange(
            NoteInputChangeKind.REMOVE_TIE if span.kind is SpanKind.TIE else NoteInputChangeKind.REMOVE_SLUR,
            span.id,
            location.staff.source.id,
            location.measure.source.id,
        )
        for span in spans
    ]


def _add_tie(draft: ScoreDraft, operation: AddTie) -> NoteInputChange:
    start = draft.event(operation.start_event_id)
    end = draft.event(operation.end_event_id)
    return _add_span_between(draft, start, end, kind=SpanKind.TIE, span_id=operation.span_id)


def _add_span_between(
    draft: ScoreDraft,
    start: EventLocation,
    end: EventLocation,
    *,
    kind: SpanKind,
    span_id: str | None = None,
) -> NoteInputChange:
    if start.staff is not end.staff:
        raise NoteInputError(f"invalid-{kind.value}", f"{kind.value} endpoints must belong to the same staff")
    if (start.measure_index, start.event_index) >= (end.measure_index, end.event_index):
        raise NoteInputError(f"invalid-{kind.value}", f"{kind.value} end must follow its start")
    if kind is SpanKind.TIE:
        _validate_tie(start, end)
    if kind is SpanKind.SLUR and EventKind.REST in {start.event.kind, end.event.kind}:
        raise NoteInputError("invalid-slur", "slur endpoints must be notes")
    resolved_id = draft.reserve_id(span_id, prefix=kind.value)
    start.staff.spans.append(NotationSpan(resolved_id, kind, start.event.id, end.event.id))
    change_kind = NoteInputChangeKind.ADD_TIE if kind is SpanKind.TIE else NoteInputChangeKind.ADD_SLUR
    return NoteInputChange(change_kind, resolved_id, start.staff.source.id, end.measure.source.id)


def _events_share_tie_pitch(start: NotationEvent, end: NotationEvent) -> bool:
    sounding_pitches = {pitch.midi for pitch in start.pitches}
    return any(pitch.midi in sounding_pitches for pitch in end.pitches)


def _validate_tie(start: EventLocation, end: EventLocation) -> None:
    if start.event.voice != end.event.voice:
        raise NoteInputError("invalid-tie", "tie endpoints must belong to the same voice")
    prior_in_voice = [event for event in previous_events(end) if event.voice == end.event.voice]
    if not prior_in_voice or prior_in_voice[-1].id != start.event.id:
        raise NoteInputError("invalid-tie", "tie endpoints must be consecutive events in their voice")
    if not _events_share_tie_pitch(start.event, end.event):
        raise NoteInputError("invalid-tie", "tie endpoints must share a sounding pitch")


def _tie_entered_pitch(draft: ScoreDraft, event_id: str, pitch: WrittenPitch) -> NoteInputChange:
    end = draft.event(event_id)
    previous = [event for event in previous_events(end) if event.voice == end.event.voice]
    if not previous or not any(candidate.midi == pitch.midi for candidate in previous[-1].pitches):
        raise NoteInputError(
            "invalid-tie",
            f"the preceding event in voice {end.event.voice} does not contain {pitch!r}",
        )
    start = draft.event(previous[-1].id)
    return _add_span_between(draft, start, end, kind=SpanKind.TIE)


def _remove_tie(draft: ScoreDraft, operation: RemoveTie) -> NoteInputChange:
    staff, index = draft.span(operation.span_id)
    span = staff.spans[index]
    if span.kind is not SpanKind.TIE:
        raise NoteInputError("not-a-tie", f"span {span.id!r} is not a tie")
    del staff.spans[index]
    return NoteInputChange(NoteInputChangeKind.REMOVE_TIE, span.id, staff.source.id)


def _add_slur(draft: ScoreDraft, operation: AddSlur) -> NoteInputChange:
    start = draft.event(operation.start_event_id)
    end = draft.event(operation.end_event_id)
    return _add_span_between(draft, start, end, kind=SpanKind.SLUR, span_id=operation.span_id)


def _remove_slur(draft: ScoreDraft, operation: RemoveSlur) -> NoteInputChange:
    staff, index = draft.span(operation.span_id)
    span = staff.spans[index]
    if span.kind is not SpanKind.SLUR:
        raise NoteInputError("not-a-slur", f"span {span.id!r} is not a slur")
    del staff.spans[index]
    return NoteInputChange(NoteInputChangeKind.REMOVE_SLUR, span.id, staff.source.id)


def _add_lyric(draft: ScoreDraft, operation: AddLyric) -> NoteInputChange:
    location = draft.event(operation.event_id)
    if any(lyric.event_id == operation.event_id and lyric.verse == operation.verse for lyric in location.staff.lyrics):
        raise NoteInputError(
            "lyric-collision",
            f"event {operation.event_id!r} already has a lyric in verse {operation.verse}",
        )
    lyric_id = draft.reserve_id(operation.lyric_id, prefix="lyric")
    location.staff.lyrics.append(
        LyricSyllable(
            lyric_id,
            operation.event_id,
            operation.text,
            operation.verse,
            operation.syllabic,
            operation.extender,
        ),
    )
    return NoteInputChange(
        NoteInputChangeKind.ADD_LYRIC,
        lyric_id,
        location.staff.source.id,
        location.measure.source.id,
    )


def _remove_lyric(draft: ScoreDraft, operation: RemoveLyric) -> NoteInputChange:
    staff, index = draft.lyric(operation.lyric_id)
    lyric = staff.lyrics[index]
    location = draft.event(lyric.event_id)
    del staff.lyrics[index]
    return NoteInputChange(
        NoteInputChangeKind.REMOVE_LYRIC,
        lyric.id,
        staff.source.id,
        location.measure.source.id,
    )


def resolve_input_pitch(value: InputPitch | WrittenPitch, *, anchor: WrittenPitch) -> WrittenPitch:
    """Resolve an explicit or nearest-octave pitch and enforce MIDI range."""

    if isinstance(value, WrittenPitch):
        pitch = value
    elif value.octave is not None:
        pitch = WrittenPitch(value.step, value.octave, value.alter, value.accidental)
    else:
        candidates = [WrittenPitch(value.step, octave, value.alter, value.accidental) for octave in range(-1, 10)]
        in_range = [candidate for candidate in candidates if 0 <= candidate.midi <= 127]
        pitch = min(in_range, key=lambda candidate: (abs(candidate.midi - anchor.midi), candidate.midi < anchor.midi))
    if not 0 <= pitch.midi <= 127:
        raise NoteInputError("pitch-out-of-range", f"written pitch resolves outside MIDI range: {pitch!r}")
    return pitch


def _replacement_duration(
    event: NotationEvent,
    duration: NotatedDuration | None,
) -> tuple[Fraction, TupletRatio | None]:
    if duration is None:
        return event.duration, event.tuplet
    return duration.duration, duration.tuplet


def _style_values(style: EventInputStyle | None, event: NotationEvent) -> dict[str, object]:
    if style is None:
        return {
            "stem": event.stem,
            "beam": event.beam,
            "fermata": event.fermata,
            "dynamic": event.dynamic,
            "ornament": event.ornament,
            "editorial_brackets": event.editorial_brackets,
            "grace": event.grace,
        }
    return {
        "stem": style.stem,
        "beam": style.beam,
        "fermata": style.fermata,
        "dynamic": style.dynamic,
        "ornament": style.ornament,
        "editorial_brackets": style.editorial_brackets,
        "grace": style.grace,
    }


def _rest_style_values(style: EventInputStyle | None, event: NotationEvent) -> dict[str, object]:
    values = _style_values(style, event)
    values["ornament"] = None
    values["editorial_brackets"] = False
    values["grace"] = False
    return values


def _updated_context(
    context: NoteInputContext,
    *,
    duration: NotatedDuration | None = None,
    pitch: WrittenPitch | None = None,
) -> NoteInputContext:
    return replace(
        context,
        duration=duration or context.duration,
        pitch_anchor=pitch or context.pitch_anchor,
    )


def _change_for_location(kind: NoteInputChangeKind, location: EventLocation) -> NoteInputChange:
    return NoteInputChange(kind, location.event.id, location.staff.source.id, location.measure.source.id)


__all__ = ["apply_note_input", "resolve_input_pitch"]
