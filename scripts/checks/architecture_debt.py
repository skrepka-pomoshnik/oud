#!/usr/bin/env python3
"""Enforce architecture limits without carrying a debt baseline."""

from __future__ import annotations

import ast
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUFF = Path(sys.executable).with_name("ruff")
MAX_COMPLEXITY = 7
MAX_MODULE_LINES = 1_000
SOURCE_ROOTS = ("oud", "petrucci", "scripts", "tests")
UI_INDEPENDENT_ROOTS = (
    "oud/editor",
    "oud/exports",
    "oud/importers",
    "oud/services/playback",
    "oud/services/plugins",
    "petrucci",
)
UI_ONLY_MODULES = ("curses", "oud.presentation.tui")
COMPLEXITY_RE = re.compile(r"\x60(?P<name>[^\x60]+)\x60 is too complex \((?P<score>\d+) > \d+\)")


def _complexity_findings() -> Counter[tuple[str, str, int]]:
    result = subprocess.run(  # noqa: S603 - the executable is the current environment's Ruff binary
        [
            RUFF,
            "check",
            "--isolated",
            "--select",
            "C901",
            "--config",
            f"lint.mccabe.max-complexity={MAX_COMPLEXITY}",
            "--ignore-noqa",
            "--output-format=json",
            *SOURCE_ROOTS,
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode not in (0, 1):
        print(result.stderr, file=sys.stderr)
        raise SystemExit(result.returncode)
    findings: Counter[tuple[str, str, int]] = Counter()
    for item in json.loads(result.stdout):
        path = Path(item["filename"])
        path = path if path.is_absolute() else ROOT / path
        match = COMPLEXITY_RE.fullmatch(item["message"])
        if match is None:
            print(f"Unexpected Ruff C901 message: {item['message']}", file=sys.stderr)
            raise SystemExit(2)
        findings[(str(path.relative_to(ROOT)), match["name"], int(match["score"]))] += 1
    return findings


def _module_lines() -> dict[str, int]:
    lines: dict[str, int] = {}
    for source_root in SOURCE_ROOTS:
        for path in sorted((ROOT / source_root).rglob("*.py")):
            count = len(path.read_text(encoding="utf-8").splitlines())
            if count > MAX_MODULE_LINES:
                lines[str(path.relative_to(ROOT))] = count
    return lines


def _ui_boundary_violations() -> list[str]:
    paths = (path for source_root in UI_INDEPENDENT_ROOTS for path in (ROOT / source_root).rglob("*.py"))
    return sorted(violation for path in paths for violation in _file_ui_boundary_violations(path))


def _file_ui_boundary_violations(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    relative_path = path.relative_to(ROOT)
    return [
        f"{relative_path}:{lineno}: forbidden dependency on {module}"
        for node in ast.walk(tree)
        for module, lineno in _imported_modules(node)
        if _is_ui_only_module(module)
    ]


def _imported_modules(node: ast.AST) -> tuple[tuple[str, int], ...]:
    if isinstance(node, ast.Import):
        return tuple((alias.name, node.lineno) for alias in node.names)
    if isinstance(node, ast.ImportFrom) and node.module:
        return ((node.module, node.lineno),)
    return ()


def _is_ui_only_module(module: str) -> bool:
    return any(module == blocked or module.startswith(f"{blocked}.") for blocked in UI_ONLY_MODULES)


def _check_ui_boundary() -> bool:
    violations = _ui_boundary_violations()
    if not violations:
        return True
    print("UI-independent modules must not depend on curses or oud.presentation.tui:", file=sys.stderr)
    for violation in violations:
        print(violation, file=sys.stderr)
    return False


def _print_complexity_findings(findings: Counter[tuple[str, str, int]]) -> None:
    for (path, name, score), count in sorted(findings.items()):
        suffix = f" (+{count - 1})" if count > 1 else ""
        print(f"{path}: {name} complexity {score}{suffix}", file=sys.stderr)


def main() -> int:
    if sys.argv[1:]:
        print(f"Usage: {Path(sys.argv[0]).name}", file=sys.stderr)
        return 2
    if not _check_ui_boundary():
        return 1

    complexity = _complexity_findings()
    large_modules = _module_lines()
    if not complexity and not large_modules:
        print("Architecture limits: no violations")
        return 0
    _print_complexity_findings(complexity)
    for path, count in sorted(large_modules.items()):
        print(f"{path}: {count} lines (limit {MAX_MODULE_LINES})", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
