from __future__ import annotations

from oud.core.render_utils import note_type_to_denom
from oud.core.tab_assign_policy import AssignmentPolicy, assign_chord_pitches
from oud.core.time_utils import parse_time_signature_value
from oud.core.tuning_utils import parse_tuning_pitches
from oud.editor.rule_pipeline import BarRule, RuleContext, RuleIssue, run_rules
from oud.editor.state import EditorState


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
    if abs(delta) < 0.01:
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
