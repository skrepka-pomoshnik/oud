from __future__ import annotations

import ast
from pathlib import Path

MATRIX_PATH = Path("docs/supported-behavior.md")
CLAIMED_STATUSES = {"Supported", "Partial"}
UNSUPPORTED_BEHAVIORS = {
    "Direct printing",
    "Fronimo templates",
    "Fronimo-compatible page engraving controls",
    "General FT3 or Fronimo parity",
    "Native FT3 save",
}


def _matrix_rows() -> list[list[str]]:
    rows: list[list[str]] = []
    for line in MATRIX_PATH.read_text(encoding="utf-8").splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) == 4 and cells[2] in CLAIMED_STATUSES | {"Unsupported"}:
            rows.append(cells)
    return rows


def _module_test_names(path: Path) -> set[str]:
    module = ast.parse(path.read_text(encoding="utf-8"))
    return {node.name for node in module.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}


def test_every_supported_behavior_names_an_existing_test() -> None:
    rows = _matrix_rows()
    assert rows
    for _area, behavior, status, evidence in rows:
        if status not in CLAIMED_STATUSES:
            continue
        node_id = evidence.strip("`")
        test_path_text, test_name = node_id.split("::", maxsplit=1)
        test_path = Path(test_path_text)
        assert test_path.is_file(), behavior
        assert test_name in _module_test_names(test_path), behavior


def test_unsupported_behavior_is_explicit_and_has_no_fake_evidence() -> None:
    rows = _matrix_rows()
    unsupported = {
        behavior for _area, behavior, status, evidence in rows if status == "Unsupported" and evidence == "-"
    }
    assert unsupported == UNSUPPORTED_BEHAVIORS
