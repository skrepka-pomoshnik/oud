from __future__ import annotations

from pathlib import Path

from oud.core.plugin_model import RemoteTab
from oud.plugins import lutemusic


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
