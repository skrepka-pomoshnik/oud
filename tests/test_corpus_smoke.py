from __future__ import annotations

import json
from pathlib import Path

import pytest

from oud.services.plugins.model import RemoteTab
from petrucci.core.model import Bar, Piece
from scripts.corpus import smoke as corpus_smoke


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


def test_collect_remote_items_recurses_filters_and_reports_listing_errors(monkeypatch) -> None:
    root = "https://example.test/root/"
    child = "https://example.test/child/"
    broken = "https://example.test/broken/"

    def fake_fetch(url: str, *, limit: int) -> list[RemoteTab]:
        assert limit == 2000
        if url == broken:
            message = "listing failed"
            raise OSError(message)
        if url == child:
            return [
                RemoteTab("Root", root, is_dir=True),
                RemoteTab("Second", "https://example.test/second.ft3.gz"),
            ]
        return [
            RemoteTab("Child", child, is_dir=True),
            RemoteTab("Broken", broken, is_dir=True),
            RemoteTab("First", "https://example.test/first.ft3"),
            RemoteTab("Ignored", "https://example.test/readme.pdf"),
        ]

    monkeypatch.setattr(corpus_smoke, "fetch_supported_tabs", fake_fetch)

    items, errors = corpus_smoke._collect_remote_items(root, 10)

    assert [item.title for item in items] == ["First", "Second"]
    assert len(errors) == 1
    assert errors[0].path == broken
    assert errors[0].error == "listing OSError: listing failed"


def test_download_remote_corpus_keeps_partial_downloads(monkeypatch, tmp_path: Path) -> None:
    good = RemoteTab("Good", "https://example.test/good.ft3")
    bad = RemoteTab("Bad", "https://example.test/bad.ft3")
    listing_error = corpus_smoke.ScanResult(path="listing", error="listing failed")
    monkeypatch.setattr(
        corpus_smoke,
        "_collect_remote_items",
        lambda _url, _limit: ([good, bad], [listing_error]),
    )

    def fake_download(item: RemoteTab, destination: Path) -> Path:
        if item == bad:
            message = "download failed"
            raise OSError(message)
        return destination / item.title.lower()

    monkeypatch.setattr(corpus_smoke, "download_tab", fake_download)

    paths, errors = corpus_smoke.download_remote_corpus("root", 2, tmp_path, jobs=0)

    assert paths == [tmp_path / "0000" / "good"]
    assert errors[0] == listing_error
    assert errors[1].path == bad.url
    assert errors[1].error == "download OSError: download failed"


def test_report_results_text_covers_warning_error_verbose_and_empty(capsys) -> None:
    warned = corpus_smoke.ScanResult(
        path="warn.ft3",
        bars=3,
        warnings=("partial",),
        warning_classes=("vocal-partial",),
    )
    failed = corpus_smoke.ScanResult(path="bad.ft3", error="ValueError: bad")

    assert (
        corpus_smoke.report_results(
            [warned, failed],
            json_output=False,
            verbose=True,
            fail_on_warning=False,
        )
        == 1
    )
    output = capsys.readouterr().out
    assert "Warning classes:" in output
    assert "vocal-partial" in output
    assert "Errors:" in output
    assert "warn.ft3: 3 bars [vocal-partial]" in output

    assert corpus_smoke.report_results([], json_output=False, verbose=False, fail_on_warning=False) == 2
    capsys.readouterr()
    assert corpus_smoke.report_results([warned], json_output=False, verbose=False, fail_on_warning=True) == 1
    capsys.readouterr()
    clean = corpus_smoke.ScanResult(path="clean.ft3", bars=1)
    assert corpus_smoke.report_results([clean], json_output=False, verbose=False, fail_on_warning=True) == 0


def test_corpus_main_defaults_to_local_directory(monkeypatch, capsys) -> None:
    seen_roots: list[Path] = []

    def fake_discover(roots) -> list[Path]:
        seen_roots.extend(roots)
        return []

    monkeypatch.setattr(corpus_smoke, "discover_files", fake_discover)

    assert corpus_smoke.main([]) == 2
    assert seen_roots == [Path("lutemusic")]
    assert "Scanned 0 file(s)" in capsys.readouterr().out


def test_corpus_main_combines_remote_results(monkeypatch, tmp_path: Path, capsys) -> None:
    remote = tmp_path / "remote.ft3"
    fetch_error = corpus_smoke.ScanResult(path="listing", error="listing failed")
    monkeypatch.setattr(corpus_smoke, "discover_files", lambda _roots: [])

    def fake_download_remote(_url: str, _limit: int, _destination: Path, *, jobs: int):
        assert jobs == 2
        return [remote], [fetch_error]

    monkeypatch.setattr(
        corpus_smoke,
        "download_remote_corpus",
        fake_download_remote,
    )
    monkeypatch.setattr(
        corpus_smoke,
        "scan_files",
        lambda paths: [corpus_smoke.ScanResult(path=str(path), bars=1) for path in paths],
    )

    assert corpus_smoke.main(["--fetch-lutemusic", "1", "--jobs", "2", "--json"]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["attempted"] == 2
    assert payload["loaded"] == 1


def test_corpus_main_rejects_nonpositive_remote_limit() -> None:
    with pytest.raises(SystemExit) as exc_info:
        corpus_smoke.main(["--fetch-lutemusic", "0"])
    assert exc_info.value.code == 2
