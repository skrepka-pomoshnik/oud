#!/usr/bin/env python3
"""List the FT3 files of browse.lutemusic.org and download a deterministic selection of new ones.

Local use only, like ``pdfs.py``: the payloads go to the ignored ``downloads/gerbode`` folder, one request at a
time with a delay, a size cap and a timeout. ``index`` walks the composer folders; ``select`` picks files that no
checked-in manifest lists (seeded, so a batch can be rebuilt) and downloads them with a manifest recording the
SHA-256 of what was received, in the schema ``scripts/corpus/fetch.py`` reads.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, unquote, urlparse
from urllib.request import Request, urlopen

from scripts.corpus.fetch import ALLOWED_HOSTS
from scripts.corpus.pdfs import USER_AGENT, corpus_urls

BASE = "https://browse.lutemusic.org/composers/"
INDEX_FILE = Path("downloads/gerbode/index.json")
FT3_ROOT = Path("downloads/gerbode/ft3")
MAX_BYTES = 5 * 1024 * 1024
MAX_PAGE_BYTES = 2 * 1024 * 1024
MAX_COMPOSERS = 600
TIMEOUT = 30
DEFAULT_DELAY = 0.3
DEFAULT_SEED = 20261011
ERR_HOST = "not an allowed lutemusic URL: {}"
_LINK = re.compile(r'<a href="([^"?/][^"]*)"')


class CrawlError(ValueError):
    pass


def _get(url: str, limit: int) -> bytes:
    if urlparse(url).scheme != "https" or urlparse(url).hostname not in ALLOWED_HOSTS:
        raise CrawlError(ERR_HOST.format(url))
    request = Request(url, headers={"User-Agent": USER_AGENT})  # noqa: S310 - host checked above
    with urlopen(request, timeout=TIMEOUT) as response:  # noqa: S310
        return response.read(limit + 1)[:limit]


def folder_names(listing: str) -> list[str]:
    """Sub-folder names of an Apache directory listing."""

    return sorted({unquote(href[:-1]) for href in _LINK.findall(listing) if href.endswith("/")})


def ft3_names(listing: str) -> list[str]:
    return sorted({unquote(href) for href in _LINK.findall(listing) if href.lower().endswith(".ft3")})


def build_index(*, delay: float, limit: int = MAX_COMPOSERS) -> list[str]:
    """Every ``.ft3`` URL under ``/composers/``, sorted."""

    composers = [name for name in folder_names(_get(BASE, MAX_PAGE_BYTES).decode("utf-8", "replace")) if name]
    urls: list[str] = []
    for composer in composers[:limit]:
        try:
            page = _get(f"{BASE}{quote(composer)}/", MAX_PAGE_BYTES).decode("utf-8", "replace")
        except (URLError, TimeoutError, OSError) as exc:
            print(f"{composer}: {exc}", file=sys.stderr)
            continue
        urls.extend(f"{BASE}{quote(composer)}/{quote(name)}" for name in ft3_names(page))
        time.sleep(delay)
    return sorted(set(urls))


def select_new(index: list[str], known: set[str], count: int, seed: int) -> list[str]:
    """``count`` URLs that no manifest lists, chosen with a seeded shuffle and returned sorted."""

    fresh = sorted(set(index) - known)
    chosen = random.Random(seed).sample(fresh, min(count, len(fresh)))  # noqa: S311 - a reproducible sample
    return sorted(chosen)


def local_path(url: str) -> Path:
    """``downloads/gerbode/ft3/<Composer>/<name>.ft3`` for a lutemusic URL."""

    composer, _, name = unquote(urlparse(url).path).removeprefix("/composers/").partition("/")
    return Path(composer) / name


def download(urls: list[str], *, delay: float) -> list[dict[str, object]]:
    """Fetch the files not yet on disk; returns a manifest entry for every one that is present."""

    files: list[dict[str, object]] = []
    for url in urls:
        relative = local_path(url)
        target = FT3_ROOT / relative
        if not target.is_file():
            try:
                payload = _get(url, MAX_BYTES)
            except (HTTPError, URLError, TimeoutError, OSError) as exc:
                print(f"{relative}: {exc}", file=sys.stderr)
                time.sleep(delay)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payload)
            time.sleep(delay)
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        files.append({"path": relative.as_posix(), "url": url, "sha256": digest, "size": target.stat().st_size})
    return files


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Index browse.lutemusic.org and download a batch of new FT3 files.")
    sub = parser.add_subparsers(dest="command", required=True)
    index = sub.add_parser("index", help="list every FT3 URL into downloads/gerbode/index.json")
    index.add_argument("--delay", type=float, default=DEFAULT_DELAY)
    select = sub.add_parser("select", help="download a seeded batch of files that no manifest lists")
    select.add_argument("manifests", nargs="+", type=Path, help="manifests whose files are already known")
    select.add_argument("--count", type=int, default=500)
    select.add_argument("--seed", type=int, default=DEFAULT_SEED)
    select.add_argument("--delay", type=float, default=DEFAULT_DELAY)
    select.add_argument("--out", type=Path, default=Path("downloads/gerbode/batch2.json"))
    args = parser.parse_args(argv)
    if args.command == "index":
        urls = build_index(delay=args.delay)
        INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)
        INDEX_FILE.write_text(json.dumps(urls, indent=0) + "\n", encoding="utf-8")
        print(f"{len(urls)} FT3 files indexed")
        return 0
    known = set(corpus_urls(args.manifests))
    chosen = select_new(json.loads(INDEX_FILE.read_text(encoding="utf-8")), known, args.count, args.seed)
    files = download(chosen, delay=args.delay)
    manifest = {"schema": 1, "root": FT3_ROOT.as_posix(), "files": files}
    args.out.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"{len(files)} of {len(chosen)} selected files present; manifest {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
