"""Reference-PDF fetching: the URL rules and resumability, without any network."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.corpus import pdfs
from scripts.corpus.pdfs import PdfFetchError, fetch_pdfs, local_name, pdf_url

FT3 = "https://browse.lutemusic.org/composers/Milano/milano_028.ft3"


def test_the_pdf_lives_in_a_pdf_folder_beside_the_ft3() -> None:
    assert pdf_url(FT3) == "https://browse.lutemusic.org/composers/Milano/pdf/milano_028.pdf"


def test_the_local_name_keeps_the_composer() -> None:
    assert local_name(FT3) == "Milano__milano_028.pdf"


@pytest.mark.parametrize(
    "url",
    [
        "http://browse.lutemusic.org/composers/A/x.ft3",
        "https://example.com/composers/A/x.ft3",
        "https://browse.lutemusic.org/composers/A/x.mid",
    ],
)
def test_only_lutemusic_ft3_urls_are_accepted(url: str) -> None:
    with pytest.raises(PdfFetchError):
        pdf_url(url)


def test_a_fetched_file_is_not_fetched_again_and_a_missing_one_is_remembered(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []

    def fake(url: str) -> tuple[int, bytes]:
        calls.append(url)
        return (404, b"") if "missing" in url else (200, b"%PDF-1.4 test")

    monkeypatch.setattr(pdfs, "_download", fake)
    monkeypatch.setattr(pdfs.time, "sleep", lambda _seconds: None)
    urls = [FT3, "https://browse.lutemusic.org/composers/Milano/missing_one.ft3"]

    first = fetch_pdfs(urls, tmp_path, limit=10, delay=0)
    second = fetch_pdfs(urls, tmp_path, limit=10, delay=0)

    assert (first.fetched, first.missing, second.fetched, second.present, second.missing) == (1, 1, 0, 1, 1)
    assert len(calls) == 2
    status = json.loads((tmp_path / "status.json").read_text(encoding="utf-8"))
    assert status["Milano__missing_one.pdf"]["status"] == 404


def test_a_reply_that_is_not_a_pdf_is_a_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pdfs, "_download", lambda _url: (200, b"<html>not a pdf"))
    monkeypatch.setattr(pdfs.time, "sleep", lambda _seconds: None)

    report = fetch_pdfs([FT3], tmp_path, limit=1, delay=0)

    assert (report.failed, report.fetched) == (1, 0)
    assert not list(tmp_path.glob("*.pdf"))


def test_the_batch_size_bounds_a_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pdfs, "_download", lambda _url: (200, b"%PDF-1.4 x"))
    monkeypatch.setattr(pdfs.time, "sleep", lambda _seconds: None)
    urls = [f"https://browse.lutemusic.org/composers/C/p{index}.ft3" for index in range(5)]

    assert fetch_pdfs(urls, tmp_path, limit=3, delay=0).fetched == 3
