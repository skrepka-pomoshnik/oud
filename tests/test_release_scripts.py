from __future__ import annotations

from pathlib import Path

from scripts.rendering import readme_screenshot as render_readme_screenshot
from scripts.rendering import snapshots as render_snapshots
from tests import render_snapshot_utils


def test_readme_screenshot_main_renders_real_score(tmp_path: Path, capsys) -> None:
    output = tmp_path / "screen.svg"

    status = render_readme_screenshot.main(
        [
            "--source",
            "examples/triste.tab",
            "--output",
            str(output),
            "--width",
            "60",
            "--height",
            "18",
        ],
    )

    content = output.read_text(encoding="utf-8")
    assert status == 0
    assert capsys.readouterr().out == f"Wrote {output}\n"
    assert content.startswith("<svg")
    assert "oud - triste.tab" in content
    assert 'role="img"' in content
    assert 'class="status"' in content


def test_readme_screenshot_svg_escapes_terminal_content() -> None:
    svg = render_readme_screenshot._svg(["<&", ""], title="A < B")

    assert "A &lt; B" in svg
    assert "&lt;&amp;" in svg
    assert "&#160;" in svg


def test_render_snapshots_check_success(monkeypatch, capsys) -> None:
    monkeypatch.setattr(render_snapshot_utils, "snapshot_cases", lambda: ["one"])
    monkeypatch.setattr(render_snapshot_utils, "snapshot_mismatch_report", lambda _case: None)

    assert render_snapshots.main([]) == 0
    assert capsys.readouterr().out == "All render snapshots match.\n"


def test_render_snapshots_reports_mismatch(monkeypatch, capsys) -> None:
    monkeypatch.setattr(render_snapshot_utils, "snapshot_cases", lambda: ["one", "two"])
    monkeypatch.setattr(
        render_snapshot_utils,
        "snapshot_mismatch_report",
        lambda case: f"mismatch: {case}" if case == "two" else None,
    )

    assert render_snapshots.main([]) == 1
    output = capsys.readouterr().out
    assert "mismatch: two" in output
    assert "--update" in output


def test_render_snapshots_update(monkeypatch, capsys) -> None:
    calls: list[str] = []
    monkeypatch.setattr(render_snapshot_utils, "write_snapshot_fixtures", lambda: calls.append("write"))

    assert render_snapshots.main(["--update"]) == 0
    assert calls == ["write"]
    assert capsys.readouterr().out == "Updated render snapshot fixtures.\n"
