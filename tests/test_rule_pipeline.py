from __future__ import annotations

from oud.editor.rule_pipeline import RuleContext, RuleIssue, run_rules
from oud.editor.state import EditorState
from oud.editor.verify_ops import verify_bar_issues
from oud.petrucci.model import Bar, Piece


def _state() -> EditorState:
    piece = Piece(title="T", bars=[Bar()], strings=6)
    return EditorState(piece, {"style": "french", "time": "C"})


def test_run_rules_collects_issues_in_order() -> None:
    state = _state()

    def _ok(_state: EditorState, _ctx: RuleContext) -> RuleIssue | None:
        return None

    def _warn(_state: EditorState, _ctx: RuleContext) -> RuleIssue | None:
        return RuleIssue(code="x.warn", message="warn", level="warn")

    def _err(_state: EditorState, _ctx: RuleContext) -> RuleIssue | None:
        return RuleIssue(code="x.err", message="err")

    issues = run_rules(state, (_ok, _warn, _err), bar_index=0)
    assert [issue.code for issue in issues] == ["x.warn", "x.err"]


def test_verify_bar_issues_uses_default_pipeline() -> None:
    state = _state()
    state.settings["time"] = "bad"
    issues = verify_bar_issues(state, 0)
    assert issues
    assert issues[0].code == "time.invalid"
