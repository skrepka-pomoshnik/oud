from __future__ import annotations

import json
from pathlib import Path

import pytest

from oud.petrucci.model import Bar, Piece
from scripts import corpus_smoke


class BrokenRecordError(ValueError):
    pass


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ("FT3 vocal text imported via raw fallback", "vocal-raw-fallback"),
        ("melody lane is inferred from tablature", "vocal-melody-inferred"),
        ("some vocal details may still be omitted", "vocal-partial"),
        ("FT3 contains additional bar header markers", "bar-header-markers"),
        ("imported as unknown staves", "unknown-staves"),
        ("TAB appears incomplete (missing final 'e')", "tab-incomplete"),
        ("Importer produced an empty piece", "empty-piece"),
        ("TAB import found no recoverable bars", "empty-piece"),
    ],
)
def test_classify_warning(message: str, expected: str) -> None:
    assert corpus_smoke.classify_warning(message) == expected


def test_discover_files_recurses_and_filters(tmp_path: Path) -> None:
    nested = tmp_path / "nested"
    nested.mkdir()
    (tmp_path / "one.ft3").write_bytes(b"")
    (nested / "two.ft3.gz").write_bytes(b"")
    (nested / "three.tab").write_text("", encoding="utf-8")
    (nested / "ignore.txt").write_text("", encoding="utf-8")

    found = corpus_smoke.discover_files([tmp_path])

    assert {path.name for path in found} == {"one.ft3", "three.tab", "two.ft3.gz"}


def test_scan_files_continues_after_importer_error(monkeypatch, tmp_path: Path) -> None:
    good = tmp_path / "good.ft3"
    bad = tmp_path / "bad.ft3"

    def _load(path: Path) -> Piece:
        if path == bad:
            raise BrokenRecordError
        piece = Piece(title="Good", bars=[Bar()])
        piece.import_warnings.append(
            "FT3 contains additional bar header markers; only known markers are decoded.",
        )
        return piece

    monkeypatch.setattr(corpus_smoke, "_load_piece", _load)

    results = corpus_smoke.scan_files([bad, good])

    assert results[0].error == "BrokenRecordError: "
    assert results[1].warning_classes == ("bar-header-markers",)


def test_report_results_json_and_exit_status(capsys) -> None:
    results = [
        corpus_smoke.ScanResult(path="ok.ft3", bars=2),
        corpus_smoke.ScanResult(path="bad.ft3", error="ValueError: bad"),
    ]

    status = corpus_smoke.report_results(
        results,
        json_output=True,
        verbose=False,
        fail_on_warning=False,
    )
    payload = json.loads(capsys.readouterr().out)

    assert status == 1
    assert payload["loaded"] == 1
    assert payload["errors"] == 1
