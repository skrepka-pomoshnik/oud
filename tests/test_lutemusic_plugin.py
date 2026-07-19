from __future__ import annotations

import random
from pathlib import Path

from oud.plugins import lutemusic
from oud.plugins.model import RemoteTab


def test_download_folder_ft3_preserves_subfolders_and_filters_non_ft3(monkeypatch, tmp_path: Path) -> None:
    root = RemoteTab(title="Root", url="https://example.com/tabs/root/", is_dir=True)

    def _fetch(url: str, *, limit: int = 200) -> list[RemoteTab]:
        _ = limit
        if url.endswith("/root/"):
            return [
                RemoteTab(title="sub", url="https://example.com/tabs/root/sub/", is_dir=True),
                RemoteTab(title="x.tab", url="https://example.com/tabs/root/x.tab", is_dir=False),
                RemoteTab(title="a.ft3", url="https://example.com/tabs/root/a.ft3", is_dir=False),
            ]
        if url.endswith("/root/sub/"):
            return [
                RemoteTab(title="b.ft3.gz", url="https://example.com/tabs/root/sub/b.ft3.gz", is_dir=False),
            ]
        return []

    written: list[Path] = []

    def _download(url: str, dest: Path) -> Path:
        written.append(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(url.encode("utf-8"))
        return dest

    monkeypatch.setattr(lutemusic, "fetch_supported_tabs", _fetch)
    monkeypatch.setattr(lutemusic, "_download_url_to", _download)

    out = lutemusic.download_folder_ft3(root, tmp_path)
    rels = sorted(path.relative_to(tmp_path).as_posix() for path in out)
    assert rels == ["a.ft3", "sub/b.ft3.gz"]
    assert all(not rel.endswith(".tab") for rel in rels)
    assert sorted(path.relative_to(tmp_path).as_posix() for path in written) == rels


def test_random_ft3_walks_directories_until_it_finds_ft3(monkeypatch) -> None:
    def _fetch(url: str, *, limit: int = 200) -> list[RemoteTab]:
        _ = limit
        if url.endswith("/tabs/"):
            return [
                RemoteTab(title="A", url="https://example.com/tabs/a/", is_dir=True),
                RemoteTab(title="B", url="https://example.com/tabs/b/", is_dir=True),
                RemoteTab(title="skip.tab", url="https://example.com/tabs/skip.tab", is_dir=False),
            ]
        if url.endswith("/tabs/a/"):
            return [RemoteTab(title="deep", url="https://example.com/tabs/a/deep/", is_dir=True)]
        if url.endswith("/tabs/a/deep/"):
            return [RemoteTab(title="song.ft3", url="https://example.com/tabs/a/deep/song.ft3", is_dir=False)]
        if url.endswith("/tabs/b/"):
            return [RemoteTab(title="other.tab", url="https://example.com/tabs/b/other.tab", is_dir=False)]
        return []

    monkeypatch.setattr(lutemusic, "fetch_supported_tabs", _fetch)
    item = lutemusic.random_ft3(
        start_urls=["https://example.com/tabs/"],
        rng=random.Random(0),  # noqa: S311 - deterministic test seed
        max_visits=10,
    )
    assert item is not None
    assert item.url.endswith("song.ft3")


def test_random_ft3_returns_none_when_no_ft3_found(monkeypatch) -> None:
    def _fetch(url: str, *, limit: int = 200) -> list[RemoteTab]:
        _ = (url, limit)
        return [RemoteTab(title="folder", url="https://example.com/folder/", is_dir=True)]

    monkeypatch.setattr(lutemusic, "fetch_supported_tabs", _fetch)
    item = lutemusic.random_ft3(
        start_urls=["https://example.com/root/"],
        rng=random.Random(0),  # noqa: S311 - deterministic test seed
        max_visits=2,
    )
    assert item is None
