#!/usr/bin/env python3
"""Fetch the reference PDF of each corpus FT3 into an ignored local folder.

The PDFs are Gerbode's Fronimo typesettings from browse.lutemusic.org (CC BY-NC-SA). They are used only to
compare Oud's engraving with the original look, never committed (``downloads/`` is ignored) and never shipped.
Requests are sequential, spaced, bounded in size and time, and resumable: a file already present is skipped and
every outcome is recorded in ``status.json`` so a 404 is not asked for again.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from scripts.corpus.fetch import ALLOWED_HOSTS, load_manifest

USER_AGENT = "oud-fidelity-check/0.6 (personal use; sequential, rate limited)"
STATUS_FILE = "status.json"
MAX_BYTES = 8 * 1024 * 1024
REQUEST_TIMEOUT = 30
DEFAULT_BATCH = 500
DEFAULT_DELAY = 0.4
HTTP_NOT_FOUND = 404
PDF_MAGIC = b"%PDF"
ERR_HOST = "not an allowed lutemusic URL: {}"
ERR_NOT_FT3 = "not an FT3 URL: {}"


class PdfFetchError(ValueError):
    pass


@dataclass(frozen=True)
class FetchReport:
    fetched: int
    present: int
    missing: int
    failed: int


def pdf_url(ft3_url: str) -> str:
    """``.../Composer/name.ft3`` -> ``.../Composer/pdf/name.pdf`` (the layout of browse.lutemusic.org)."""

    parsed = urlparse(ft3_url)
    if parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS:
        raise PdfFetchError(ERR_HOST.format(ft3_url))
    folder, _, name = ft3_url.rpartition("/")
    stem, dot, extension = name.rpartition(".")
    if not dot or extension.lower() != "ft3" or not stem:
        raise PdfFetchError(ERR_NOT_FT3.format(ft3_url))
    return f"{folder}/pdf/{stem}.pdf"


def corpus_urls(manifests: list[Path]) -> list[str]:
    """Every FT3 URL of the manifests, de-duplicated and sorted so batches are reproducible."""

    urls = {entry.url for manifest in manifests for entry in load_manifest(manifest).files}
    return sorted(urls)


def local_name(ft3_url: str) -> str:
    """A flat, collision-free file name: ``Composer__name.pdf``."""

    folder, _, name = pdf_url(ft3_url).rpartition("/pdf/")
    return f"{folder.rpartition('/')[2]}__{name}"


def _read_status(dest: Path) -> dict[str, dict[str, object]]:
    path = dest / STATUS_FILE
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def _write_status(dest: Path, status: dict[str, dict[str, object]]) -> None:
    (dest / STATUS_FILE).write_text(json.dumps(status, indent=1, sort_keys=True) + "\n", encoding="utf-8")


def _download(url: str) -> tuple[int, bytes]:
    request = Request(url, headers={"User-Agent": USER_AGENT})  # noqa: S310 - host checked by pdf_url
    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT) as response:  # noqa: S310
            return response.status, response.read(MAX_BYTES + 1)
    except HTTPError as exc:
        return exc.code, b""


def fetch_pdfs(urls: list[str], dest: Path, *, limit: int, delay: float) -> FetchReport:
    dest.mkdir(parents=True, exist_ok=True)
    status = _read_status(dest)
    counts = {"fetched": 0, "present": 0, "missing": 0, "failed": 0}
    for ft3_url in urls[:limit]:
        name = local_name(ft3_url)
        target = dest / name
        if target.is_file() or status.get(name, {}).get("status") == HTTP_NOT_FOUND:
            counts["present" if target.is_file() else "missing"] += 1
            continue
        try:
            code, payload = _download(pdf_url(ft3_url))
        except (URLError, TimeoutError, OSError) as exc:
            counts["failed"] += 1
            print(f"{name}: {exc}", file=sys.stderr)
            time.sleep(delay)
            continue
        if code == HTTP_NOT_FOUND:
            status[name] = {"status": code, "url": pdf_url(ft3_url)}
            counts["missing"] += 1
        elif code == 200 and payload.startswith(PDF_MAGIC) and len(payload) <= MAX_BYTES:  # noqa: PLR2004
            target.write_bytes(payload)
            status[name] = {"status": code, "bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}
            counts["fetched"] += 1
        else:
            counts["failed"] += 1
            print(f"{name}: unexpected response {code}, {len(payload)} bytes", file=sys.stderr)
        _write_status(dest, status)
        time.sleep(delay)
    return FetchReport(**counts)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch reference PDFs for the FT3 corpus manifests (local only).")
    parser.add_argument("manifests", nargs="+", type=Path)
    parser.add_argument("--dest", type=Path, default=Path("downloads/gerbode/pdf"))
    parser.add_argument("--batch", type=int, default=DEFAULT_BATCH, help="files per run (default 500)")
    parser.add_argument("--delay", type=float, default=DEFAULT_DELAY, help="seconds between requests")
    args = parser.parse_args(argv)
    report = fetch_pdfs(corpus_urls(args.manifests), args.dest, limit=args.batch, delay=args.delay)
    print(f"fetched {report.fetched}, present {report.present}, missing {report.missing}, failed {report.failed}")
    return 1 if report.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
