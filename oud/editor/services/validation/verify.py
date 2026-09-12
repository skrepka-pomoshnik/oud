from __future__ import annotations

from itertools import pairwise

from oud.editor.core.state import EditorState
from oud.editor.editing.tab.assignment import AssignmentPolicy, assign_chord_pitches
from oud.editor.navigation.cursor_map import bar_content_width_for_cursor, cursor_display_map_for_bar
from oud.editor.services.validation.rules import BarRule, RuleContext, RuleIssue, run_rules
from petrucci.core.music.time import parse_time_signature_value
from petrucci.core.music.tuning import parse_tuning_pitches
from petrucci.rendering.primitives.utils import (
    bar_cells_from_chords,
    chord_slot_positions,
    note_type_to_denom,
)


def _chord_duration_sum(bar, default_duration: int) -> float:
    return sum(
        4.0 / (note_type_to_denom(chord.note_type) or default_duration) * (1.5 if chord.dotted else 1.0)
        for chord in bar.chords
    )


def _grid_column_denom(state: EditorState, bar_index: int, col: int) -> int | None:
    found = None
    for s_idx in range(state.piece.strings):
        key = (bar_index, s_idx, col)
        if key in state.durations:
            denom = state.durations[key]
            if found is None or denom > found:
                found = denom
    return found


def _grid_duration_sum(state: EditorState, bar_index: int, default_duration: int) -> float:
    last = None
    total = 0.0
    for col in range(state.bar_width):
        found = _grid_column_denom(state, bar_index, col)
        if found is None:
            found = default_duration
        if found != last:
            duration = 4.0 / found
            if (bar_index, col) in state.dotted:
                duration *= 1.5
            total += duration
            last = found
    return total


def bar_duration_sum(state: EditorState, bar_index: int, default_duration: int) -> float:
    if bar_index < 0 or bar_index >= len(state.piece.bars):
        return 0.0
    bar = state.piece.bars[bar_index]
    if bar.chords:
        return _chord_duration_sum(bar, default_duration)
    return _grid_duration_sum(state, bar_index, default_duration)


def _rule_time_signature(state: EditorState, _context: RuleContext) -> RuleIssue | None:
    parsed = parse_time_signature_value(state.settings.get("time", "C"))
    if parsed is None:
        return RuleIssue(code="time.invalid", message="No valid time signature")
    return None


def _rule_bar_duration(state: EditorState, context: RuleContext) -> RuleIssue | None:
    parsed = parse_time_signature_value(state.settings.get("time", "C"))
    if parsed is None:
        return None
    beats, unit = parsed
    expected = beats * (4.0 / unit)
    total = bar_duration_sum(state, context.bar_index, default_duration=4)
    delta = total - expected
    duration_tolerance = 0.01
    if abs(delta) < duration_tolerance:
        return None
    if delta > 0:
        return RuleIssue(
            code="duration.overfull",
            message=f"Overfull by {delta:.2f} beats",
        )
    return RuleIssue(
        code="duration.underfull",
        message=f"Underfull by {abs(delta):.2f} beats",
    )


def _assignment_policy_from_state(state: EditorState) -> AssignmentPolicy:
    minimum_fret = int(state.settings.get("minimumfret", "0") or "0")
    max_stretch_raw = int(state.settings.get("maxstretch", "0") or "0")
    max_stretch = max_stretch_raw if max_stretch_raw > 0 else None
    restrain_open = state.settings.get("restrainopenstrings", "off") == "on"
    return AssignmentPolicy(
        minimum_fret=minimum_fret,
        max_stretch=max_stretch,
        restrain_open_strings=restrain_open,
    )


def _assignment_issue_from_result(result) -> RuleIssue:
    msg = "Placement violates constraints."
    if result.diagnostics:
        msg = result.diagnostics[0].message
    return RuleIssue(
        code="assignment.constraints",
        message=f"Assignment constraints: {msg}",
        level="warning",
    )


def _note_pitch(note, tuning: list[int]) -> int | None:
    idx = note.string - 1
    if idx < 0 or idx >= len(tuning):
        return None
    return tuning[idx] + note.fret


def _assignment_issue_for_chord(
    chord,
    tuning: list[int],
    policy: AssignmentPolicy,
) -> RuleIssue | None:
    if not chord.notes:
        return None
    pitches: list[int] = []
    forced: dict[int, int] = {}
    for index, note in enumerate(chord.notes):
        pitch = _note_pitch(note, tuning)
        if pitch is None:
            return RuleIssue(
                code="assignment.string_out_of_range",
                message="Note string is outside current tuning.",
                level="warning",
            )
        pitches.append(pitch)
        forced[index] = note.string
    result = assign_chord_pitches(pitches, tuning, policy=policy, forced_strings=forced)
    return _assignment_issue_from_result(result) if not result.ok else None


def _assignment_issue_for_note(note, tuning: list[int], policy: AssignmentPolicy) -> RuleIssue | None:
    pitch = _note_pitch(note, tuning)
    if pitch is None:
        return RuleIssue(
            code="assignment.string_out_of_range",
            message="Note string is outside current tuning.",
            level="warning",
        )
    result = assign_chord_pitches(
        [pitch],
        tuning,
        policy=policy,
        forced_strings={0: note.string},
    )
    return _assignment_issue_from_result(result) if not result.ok else None


def _rule_assignment_constraints(
    state: EditorState,
    context: RuleContext,
) -> RuleIssue | None:
    if context.bar_index < 0 or context.bar_index >= len(state.piece.bars):
        return None
    tuning = parse_tuning_pitches(state.settings.get("tuning", ""))[: state.piece.strings]
    if not tuning:
        return None
    bar = state.piece.bars[context.bar_index]
    policy = _assignment_policy_from_state(state)

    for chord in bar.chords:
        issue = _assignment_issue_for_chord(chord, tuning, policy)
        if issue is not None:
            return issue
    for note in bar.notes:
        issue = _assignment_issue_for_note(note, tuning, policy)
        if issue is not None:
            return issue
    return None


def default_bar_rules() -> tuple[BarRule, ...]:
    return (_rule_time_signature, _rule_assignment_constraints, _rule_bar_duration)


def verify_bar_issues(state: EditorState, bar_index: int) -> list[RuleIssue]:
    return run_rules(state, default_bar_rules(), bar_index=bar_index)


def verify_bar(state: EditorState, bar_index: int) -> str:
    issues = verify_bar_issues(state, bar_index)
    if not issues:
        return "Measure ok"
    return issues[0].message


def _render_orphan_issue(state: EditorState, bar, positions) -> RuleIssue | None:
    if not positions:
        return None
    style = state.settings.get("style", "french")
    cells = bar_cells_from_chords(
        bar,
        state.piece.strings,
        state.bar_width,
        4,
        style,
        french_c_shape=state.settings.get("frenchc", "normal"),
        label_mode=state.settings.get("fretlabelmode", "auto"),
    )
    visible_cols = {
        col
        for col in range(state.bar_width)
        if any(cells[s_idx][col] not in ("-", " ") for s_idx in range(state.piece.strings))
    }
    for col, _denom, _dot in positions:
        if col not in visible_cols:
            return RuleIssue(
                code="render.orphan_flag",
                message=f"Flag without note under it at col {col + 1}",
            )
    return None


def _render_map_issues(state: EditorState, bar_index: int) -> list[RuleIssue]:
    content_width = max(1, bar_content_width_for_cursor(state, bar_index))
    mapping = cursor_display_map_for_bar(state, bar_index, content_width)
    if len(mapping) != state.bar_width:
        return [RuleIssue(code="render.map_width", message="Render cursor map width mismatch")]
    if any(left > right for left, right in pairwise(mapping)):
        return [RuleIssue(code="render.map_non_monotonic", message="Render map is non-monotonic")]
    if mapping and state.bar_width > 1 and len(set(mapping)) <= 1:
        return [
            RuleIssue(
                code="render.map_collapsed",
                message="Render map collapsed to one column",
                level="warning",
            ),
        ]
    return []


def verify_render_bar_issues(state: EditorState, bar_index: int) -> list[RuleIssue]:
    if bar_index < 0 or bar_index >= len(state.piece.bars):
        return [RuleIssue(code="render.out_of_range", message="Bar out of range")]
    bar = state.piece.bars[bar_index]
    positions = chord_slot_positions(bar, state.bar_width, default_duration=4)
    if bar.chords and not positions:
        return [RuleIssue(code="render.no_positions", message="No render positions for bar chords")]
    orphan_issue = _render_orphan_issue(state, bar, positions)
    if orphan_issue is not None:
        return [orphan_issue]
    return _render_map_issues(state, bar_index)


def verify_render_bar(state: EditorState, bar_index: int) -> str:
    issues = verify_render_bar_issues(state, bar_index)
    if not issues:
        return "Render ok"
    return issues[0].message
