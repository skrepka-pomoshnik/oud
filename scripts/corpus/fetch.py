#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

ALLOWED_HOSTS = frozenset({"browse.lutemusic.org"})
ERR_DESTINATION_ESCAPE = "{}: destination escapes {}"
ERR_DOWNLOAD_CHECKSUM = "download checksum mismatch: {}"
ERR_DUPLICATE_PATH = "{}: duplicate destination paths"
ERR_ENTRY_DIGEST = "files[{}].sha256 must be a lowercase SHA-256 digest"
ERR_ENTRY_OBJECT = "files[{}] must be an object"
ERR_ENTRY_URL = "files[{}].url must be an allowed HTTPS URL"
ERR_EXISTING_CHECKSUM = "refusing to replace checksum-mismatched file: {}"
ERR_FILES = "{}: files must be a non-empty list"
ERR_MANIFEST_READ = "cannot read {}: {}"
ERR_MISSING = "missing corpus file: {}"
ERR_PATH_FILE = "{} must name a file"
ERR_PATH_INSIDE = "{} must stay inside the repository"
ERR_PATH_STRING = "{} must be a non-empty string"
ERR_SCHEMA = "{}: unsupported or missing schema"


class ManifestError(ValueError):
    pass


def _manifest_error(template: str, *values: object) -> ManifestError:
    return ManifestError(template.format(*values))


@dataclass(frozen=True)
class CorpusEntry:
    path: Path
    url: str
    sha256: str


@dataclass(frozen=True)
class CorpusManifest:
    path: Path
    root: Path
    files: tuple[CorpusEntry, ...]


@dataclass(frozen=True)
class FetchResult:
    fetched: int
    present: int


def _relative_path(value: object, label: str, *, allow_dot: bool = False) -> Path:
    if not isinstance(value, str) or not value:
        raise _manifest_error(ERR_PATH_STRING, label)
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise _manifest_error(ERR_PATH_INSIDE, label)
    if path == Path() and not allow_dot:
        raise _manifest_error(ERR_PATH_FILE, label)
    return path


def _parse_entry(value: object, index: int) -> CorpusEntry:
    if not isinstance(value, dict):
        raise _manifest_error(ERR_ENTRY_OBJECT, index)
    path = _relative_path(value.get("path"), f"files[{index}].path")
    url = value.get("url")
    digest = value.get("sha256")
    if not isinstance(url, str) or urlparse(url).scheme != "https" or urlparse(url).hostname not in ALLOWED_HOSTS:
        raise _manifest_error(ERR_ENTRY_URL, index)
    sha256_hex_length = 64
    if (
        not isinstance(digest, str)
        or len(digest) != sha256_hex_length
        or any(char not in "0123456789abcdef" for char in digest)
    ):
        raise _manifest_error(ERR_ENTRY_DIGEST, index)
    return CorpusEntry(path=path, url=url, sha256=digest)


def load_manifest(path: Path) -> CorpusManifest:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise _manifest_error(ERR_MANIFEST_READ, path, exc) from exc
    if not isinstance(value, dict) or value.get("schema") != 1:
        raise _manifest_error(ERR_SCHEMA, path)
    root = _relative_path(value.get("root", "."), "root", allow_dot=True)
    raw_files = value.get("files")
    if not isinstance(raw_files, list) or not raw_files:
        raise _manifest_error(ERR_FILES, path)
    files = tuple(_parse_entry(item, index) for index, item in enumerate(raw_files))
    paths = [entry.path for entry in files]
    if len(paths) != len(set(paths)):
        raise _manifest_error(ERR_DUPLICATE_PATH, path)
    return CorpusManifest(path=path, root=root, files=files)


def manifest_paths(manifest: CorpusManifest, repo_root: Path = Path()) -> list[Path]:
    base = (repo_root / manifest.root).resolve()
    paths: list[Path] = []
    for entry in manifest.files:
        target = (base / entry.path).resolve()
        if not target.is_relative_to(base):
            raise _manifest_error(ERR_DESTINATION_ESCAPE, entry.path, base)
        paths.append(target)
    return paths


def _digest_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _download(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": "oud-corpus-fetch"})  # noqa: S310
    with urlopen(request, timeout=30) as response:  # noqa: S310
        return response.read()


def _write_verified(target: Path, payload: bytes) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=target.parent, prefix=f".{target.name}.", delete=False) as handle:
            handle.write(payload)
            temp_path = Path(handle.name)
        temp_path.replace(target)
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def fetch_manifest(
    manifest: CorpusManifest,
    *,
    repo_root: Path = Path(),
    check_only: bool = False,
) -> FetchResult:
    fetched = 0
    present = 0
    for entry, target in zip(manifest.files, manifest_paths(manifest, repo_root), strict=True):
        if target.exists():
            if _digest_file(target) != entry.sha256:
                raise _manifest_error(ERR_EXISTING_CHECKSUM, target)
            present += 1
            continue
        if check_only:
            raise _manifest_error(ERR_MISSING, target)
        payload = _download(entry.url)
        if hashlib.sha256(payload).hexdigest() != entry.sha256:
            raise _manifest_error(ERR_DOWNLOAD_CHECKSUM, entry.url)
        _write_verified(target, payload)
        fetched += 1
    return FetchResult(fetched=fetched, present=present)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fetch a fixed, checksum-verified external FT3 corpus")
    parser.add_argument("manifests", nargs="+", type=Path)
    parser.add_argument("--repo-root", type=Path, default=Path())
    parser.add_argument("--check", action="store_true", help="verify local files without downloading")
    args = parser.parse_args(argv)
    try:
        for path in args.manifests:
            manifest = load_manifest(path)
            result = fetch_manifest(manifest, repo_root=args.repo_root, check_only=args.check)
            print(f"{path}: {result.fetched} fetched, {result.present} already present")
    except (ManifestError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
