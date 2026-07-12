from __future__ import annotations

from tests.render_snapshot_utils import (
    normalize_snapshot_lines,
    snapshot_cases,
    snapshot_mismatch_report,
)


def test_normalize_snapshot_lines_trims_header_status_and_blank_padding() -> None:
    lines = [
        "HEADER volatile",
        "",
        " 8|--a--|",
        " 7|-----|",
        "",
        "status bar volatile",
    ]
    assert normalize_snapshot_lines(lines) == [" 8|--a--|", " 7|-----|"]


def test_snapshot_fixtures_match_current_render_output() -> None:
    mismatches = [report for case in snapshot_cases() if (report := snapshot_mismatch_report(case)) is not None]
    assert mismatches == []
