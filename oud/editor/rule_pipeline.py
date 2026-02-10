from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from oud.editor.state import EditorState


@dataclass(frozen=True)
class RuleContext:
    bar_index: int


@dataclass(frozen=True)
class RuleIssue:
    code: str
    message: str
    level: str = "error"


BarRule = Callable[["EditorState", RuleContext], RuleIssue | None]


def run_rules(
    state: EditorState,
    rules: Iterable[BarRule],
    *,
    bar_index: int,
) -> list[RuleIssue]:
    context = RuleContext(bar_index=bar_index)
    issues: list[RuleIssue] = []
    for rule in rules:
        issue = rule(state, context)
        if issue is not None:
            issues.append(issue)
    return issues
