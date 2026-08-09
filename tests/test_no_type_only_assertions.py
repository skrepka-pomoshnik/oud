from __future__ import annotations

import ast
from pathlib import Path


def _type_only_assertion(node: ast.AST) -> bool:
    test = getattr(node, "test", None)
    function = getattr(test, "func", None)
    if getattr(function, "id", None) == "isinstance":
        return True
    left = getattr(test, "left", None)
    left_function = getattr(left, "func", None)
    return getattr(left_function, "id", None) == "type"


def test_suite_has_no_type_only_assertions() -> None:
    tests_root = Path(__file__).parent
    violations: list[str] = []
    for path in tests_root.glob("test_*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        violations.extend(
            f"{path.name}:{getattr(node, 'lineno', 0)}"
            for node in ast.walk(tree)
            if node.__class__.__name__ == "Assert" and _type_only_assertion(node)
        )
    assert not violations, "type-only assertions test implementation rather than behavior: " + ", ".join(violations)
