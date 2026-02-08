from __future__ import annotations

from oud.core.render_utils import note_type_to_denom
from oud.core.time_utils import parse_time_signature_value
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


def _rule_time_signature(state: EditorState, context: RuleContext) -> RuleIssue | None:
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


def default_bar_rules() -> tuple[BarRule, ...]:
    return (_rule_time_signature, _rule_bar_duration)


def verify_bar_issues(state: EditorState, bar_index: int) -> list[RuleIssue]:
    return run_rules(state, default_bar_rules(), bar_index=bar_index)


def verify_bar(state: EditorState, bar_index: int) -> str:
    issues = verify_bar_issues(state, bar_index)
    if not issues:
        return "Measure ok"
    return issues[0].message
