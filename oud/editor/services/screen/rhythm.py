"""Cursor duration and bar-meter diagnostics for the tablature status row."""

from __future__ import annotations

from oud.editor.core.coordinates import at_append_slot, bar_meter, cursor_event, effective_time_signature
from oud.editor.core.state import EditorState
from petrucci.core.music.time import parse_time_signature_value
from petrucci.input.tablature.mutation import TabDuration, bar_content_length

METER_SEGMENT = "meter:{content} of {meter}"


def _duration_text(duration: TabDuration) -> str:
    return f"{duration.denominator}." if duration.dotted else str(duration.denominator)


def cursor_duration_text(state: EditorState) -> str | None:
    """Written duration of the event under the cursor; the typing duration on the append slot."""

    if not 0 <= state.cursor_bar < len(state.piece.bars):
        return None
    if at_append_slot(state):
        return str(state.current_duration)
    chord = state.piece.bars[state.cursor_bar].chords[cursor_event(state)]
    return _duration_text(TabDuration.of(chord))


def bar_meter_marker(state: EditorState) -> str | None:
    """``meter:<length> of <meter>`` when the cursor bar's events do not fill its meter, otherwise ``None``.

    The length is in whole notes, so ``meter:1/2 of 3/4`` is a 3/4 bar holding two quarters.
    """

    if not 0 <= state.cursor_bar < len(state.piece.bars):
        return None
    bar = state.piece.bars[state.cursor_bar]
    meter = bar_meter(state, state.cursor_bar)
    if not bar.chords or meter is None:
        return None
    content = bar_content_length(bar)
    if content == meter:
        return None
    beats, unit = parse_time_signature_value(effective_time_signature(state, state.cursor_bar)) or (0, 0)
    return METER_SEGMENT.format(content=f"{content.numerator}/{content.denominator}", meter=f"{beats}/{unit}")
