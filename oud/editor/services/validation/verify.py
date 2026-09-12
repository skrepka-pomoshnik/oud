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


def bar_duration_sum(state: EditorState, bar_index: int, default_duration: int) -> float:  # noqa: C901
    if bar_index < 0 or bar_index >= len(state.piece.bars):
        return 0.0
    bar = state.piece.bars[bar_index]
    total = 0.0
    if bar.chords:
        for chord in bar.chords:
            denom = note_type_to_denom(chord.note_type) or default_duration
            duration = 4.0 / denom
            if chord.dotted:
                duration *= 1.5
            total += duration
        return total
    last = None
    for col in range(state.bar_width):
        found = None
        for s_idx in range(state.piece.strings):
            key = (bar_index, s_idx, col)
            if key in state.durations:
                denom = state.durations[key]
                if found is None or denom > found:
                    found = denom
        if found is None:
            found = default_duration
        if found != last:
            duration = 4.0 / found
            if (bar_index, col) in state.dotted:
                duration *= 1.5
            total += duration
            last = found
    return total


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


def _rule_assignment_constraints(  # noqa: C901, PLR0911
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

    def _note_pitch(note) -> int | None:
        idx = note.string - 1
        if idx < 0 or idx >= len(tuning):
            return None
        return tuning[idx] + note.fret

    for chord in bar.chords:
        if not chord.notes:
            continue
        pitches: list[int] = []
        forced: dict[int, int] = {}
        for i, note in enumerate(chord.notes):
            pitch = _note_pitch(note)
            if pitch is None:
                return RuleIssue(
                    code="assignment.string_out_of_range",
                    message="Note string is outside current tuning.",
                    level="warning",
                )
            pitches.append(pitch)
            forced[i] = note.string
        result = assign_chord_pitches(pitches, tuning, policy=policy, forced_strings=forced)
        if not result.ok:
            return _assignment_issue_from_result(result)
    for note in bar.notes:
        pitch = _note_pitch(note)
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
        if not result.ok:
            return _assignment_issue_from_result(result)
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


def verify_render_bar_issues(state: EditorState, bar_index: int) -> list[RuleIssue]:  # noqa: C901
    issues: list[RuleIssue] = []
    if bar_index < 0 or bar_index >= len(state.piece.bars):
        return [RuleIssue(code="render.out_of_range", message="Bar out of range")]
    bar = state.piece.bars[bar_index]
    positions = chord_slot_positions(bar, state.bar_width, default_duration=4)
    if bar.chords and not positions:
        issues.append(
            RuleIssue(code="render.no_positions", message="No render positions for bar chords"),
        )
        return issues

    if positions:
        style = state.settings.get("style", "french")
        french_c = state.settings.get("frenchc", "normal")
        label_mode = state.settings.get("fretlabelmode", "auto")
        cells = bar_cells_from_chords(
            bar,
            state.piece.strings,
            state.bar_width,
            4,
            style,
            french_c_shape=french_c,
            label_mode=label_mode,
        )
        visible_cols = {
            col
            for col in range(state.bar_width)
            if any(cells[s_idx][col] not in ("-", " ") for s_idx in range(state.piece.strings))
        }
        for col, _denom, _dot in positions:
            if col not in visible_cols:
                issues.append(
                    RuleIssue(
                        code="render.orphan_flag",
                        message=f"Flag without note under it at col {col + 1}",
                    ),
                )
                return issues

    content_width = max(1, bar_content_width_for_cursor(state, bar_index))
    mapping = cursor_display_map_for_bar(state, bar_index, content_width)
    if len(mapping) != state.bar_width:
        issues.append(
            RuleIssue(
                code="render.map_width",
                message="Render cursor map width mismatch",
            ),
        )
        return issues
    if any(left > right for left, right in pairwise(mapping)):
        issues.append(
            RuleIssue(
                code="render.map_non_monotonic",
                message="Render map is non-monotonic",
            ),
        )
        return issues
    if mapping and state.bar_width > 1 and len(set(mapping)) <= 1:
        issues.append(
            RuleIssue(
                code="render.map_collapsed",
                message="Render map collapsed to one column",
                level="warning",
            ),
        )
    return issues


def verify_render_bar(state: EditorState, bar_index: int) -> str:
    issues = verify_render_bar_issues(state, bar_index)
    if not issues:
        return "Render ok"
    return issues[0].message
