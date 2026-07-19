#!/usr/bin/env python3
"""Prevent known complexity and oversized-module debt from growing."""

from __future__ import annotations

import ast
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "architecture-debt.json"
RUFF = Path(sys.executable).with_name("ruff")
MAX_COMPLEXITY = 7
MAX_MODULE_LINES = 1_000
SOURCE_ROOTS = ("oud", "petrucci", "scripts", "tests", "tools")
UI_INDEPENDENT_ROOTS = ("oud/editor", "oud/exports", "oud/importers", "oud/playback", "oud/plugins", "petrucci")
UI_ONLY_MODULES = ("curses", "oud.tui")
COMPLEXITY_RE = re.compile(r"`(?P<name>[^`]+)` is too complex \((?P<score>\d+) > \d+\)")


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
        for path in (ROOT / source_root).rglob("*.py"):
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
    print("UI-independent modules must not depend on curses or oud.tui:", file=sys.stderr)
    for violation in violations:
        print(violation, file=sys.stderr)
    return False


def _load_baseline() -> tuple[Counter[tuple[str, str, int]], dict[str, int]]:
    data = json.loads(BASELINE.read_text(encoding="utf-8"))
    complexity = Counter(
        {
            (path, finding["name"], finding["complexity"]): finding.get("count", 1)
            for path, findings in data["complexity"].items()
            for finding in findings
        }
    )
    return complexity, data["large_modules"]


def _write_baseline(
    complexity: Counter[tuple[str, str, int]],
    large_modules: dict[str, int],
) -> None:
    grouped: dict[str, list[dict[str, int | str]]] = {}
    for (path, name, score), count in sorted(complexity.items()):
        finding: dict[str, int | str] = {"name": name, "complexity": score}
        if count != 1:
            finding["count"] = count
        grouped.setdefault(path, []).append(finding)
    payload = {
        "version": 1,
        "limits": {"complexity": MAX_COMPLEXITY, "module_lines": MAX_MODULE_LINES},
        "complexity": grouped,
        "large_modules": dict(sorted(large_modules.items())),
    }
    BASELINE.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _large_module_regressions(current: dict[str, int], baseline: dict[str, int]) -> list[str]:
    regressions: list[str] = []
    for path, count in sorted(current.items()):
        allowed = baseline.get(path, MAX_MODULE_LINES)
        if count > allowed:
            regressions.append(f"{path}: {count} lines (baseline {allowed})")
    return regressions


def main() -> int:
    complexity = _complexity_findings()
    large_modules = _module_lines()
    if sys.argv[1:] == ["--write"]:
        _write_baseline(complexity, large_modules)
        print(
            f"Wrote {sum(complexity.values())} complexity findings and "
            f"{len(large_modules)} oversized modules to {BASELINE.name}"
        )
        return 0
    if sys.argv[1:]:
        print(f"Usage: {Path(sys.argv[0]).name} [--write]", file=sys.stderr)
        return 2

    if not _check_ui_boundary():
        return 1

    baseline_complexity, baseline_modules = _load_baseline()
    complexity_regressions = complexity - baseline_complexity
    module_regressions = _large_module_regressions(large_modules, baseline_modules)
    if complexity_regressions or module_regressions:
        for (path, name, score), count in sorted(complexity_regressions.items()):
            print(f"{path}: {name} complexity {score} (+{count})", file=sys.stderr)
        for message in module_regressions:
            print(message, file=sys.stderr)
        return 1

    retired_complexity = baseline_complexity - complexity
    retired_modules = set(baseline_modules) - set(large_modules)
    retired = sum(retired_complexity.values()) + len(retired_modules)
    suffix = f"; {retired} entries ready to retire" if retired else ""
    print(
        f"Architecture debt: {sum(complexity.values())}/{sum(baseline_complexity.values())} complex functions, "
        f"{len(large_modules)}/{len(baseline_modules)} oversized modules{suffix}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
