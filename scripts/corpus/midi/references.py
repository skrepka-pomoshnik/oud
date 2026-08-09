from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Literal
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse, urlunparse
from urllib.request import Request, urlopen

from scripts.corpus.fetch import ALLOWED_HOSTS

ERR_SOURCE_URL = "unsupported FT3 source URL: {}"

ReferenceStatus = Literal["cached", "downloaded", "empty", "missing", "error"]


@dataclass(frozen=True, slots=True)
class ReferenceFetch:
    status: ReferenceStatus
    url: str
    path: Path
    detail: str | None = None


def companion_midi_url(ft3_url: str) -> str:
    parsed = urlparse(ft3_url)
    if parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS:
        raise ValueError(ERR_SOURCE_URL.format(ft3_url))
    source = PurePosixPath(parsed.path)
    midi_path = source.parent / "midi" / f"{source.stem}.mid"
    return urlunparse(parsed._replace(path=str(midi_path), query="", fragment=""))


def reference_cache_path(cache_root: Path, ft3_url: str) -> Path:
    parsed = urlparse(companion_midi_url(ft3_url))
    relative = PurePosixPath(parsed.path).relative_to("/")
    return cache_root / parsed.netloc / Path(*relative.parts)


def generated_cache_path(cache_root: Path, ft3_url: str) -> Path:
    parsed = urlparse(ft3_url)
    if parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS:
        raise ValueError(ERR_SOURCE_URL.format(ft3_url))
    relative = PurePosixPath(parsed.path).relative_to("/").with_suffix(".mid")
    return cache_root / parsed.netloc / Path(*relative.parts)


def _write_atomic(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.", delete=False) as handle:
            handle.write(payload)
            temporary = Path(handle.name)
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def fetch_reference(ft3_url: str, cache_root: Path, *, refresh: bool = False) -> ReferenceFetch:
    url = companion_midi_url(ft3_url)
    path = reference_cache_path(cache_root, ft3_url)
    missing_marker = path.with_suffix(f"{path.suffix}.missing")
    if path.exists() and not refresh:
        status: ReferenceStatus = "cached" if path.stat().st_size else "empty"
        return ReferenceFetch(status, url, path)
    if missing_marker.exists() and not refresh:
        return ReferenceFetch("missing", url, path, "cached HTTP 404")
    request = Request(url, headers={"User-Agent": "oud-midi-corpus-audit"})  # noqa: S310
    try:
        with urlopen(request, timeout=30) as response:  # noqa: S310
            payload = response.read()
    except HTTPError as exc:
        if exc.code in {404, 410}:
            _write_atomic(missing_marker, f"{url}\n".encode())
            return ReferenceFetch("missing", url, path, f"HTTP {exc.code}")
        return ReferenceFetch("error", url, path, f"HTTP {exc.code}")
    except (URLError, OSError) as exc:
        return ReferenceFetch("error", url, path, str(exc))
    _write_atomic(path, payload)
    missing_marker.unlink(missing_ok=True)
    status = "downloaded" if payload else "empty"
    return ReferenceFetch(status, url, path)
