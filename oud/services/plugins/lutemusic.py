# oud-plugin: v1
from __future__ import annotations

import random
from html.parser import HTMLParser
from pathlib import Path
from posixpath import normpath
from typing import NamedTuple
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

from oud.services.plugins.model import RemoteTab

SUPPORTED_EXTS = (".tab", ".ft3", ".ft3.gz")
FT3_EXTS = (".ft3", ".ft3.gz")
PLUGIN_TITLE = "Lutemusic"

LUTEMUSIC_URLS = {
    "composers": "https://browse.lutemusic.org/composers/",
    "sources": "https://browse.lutemusic.org/sources/",
    "tabs": "https://browse.lutemusic.org/tabs/",
}


class _Link(NamedTuple):
    href: str
    text: str


class DownloadError(ValueError):
    def __init__(self) -> None:
        super().__init__("Cannot download a directory")


class _LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._current_href: str | None = None
        self._current_text: list[str] = []
        self.links: list[_Link] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        for key, value in attrs:
            if key == "href" and value:
                self._current_href = value
                self._current_text = []
                return

    def handle_data(self, data: str) -> None:
        if self._current_href is not None:
            self._current_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag != "a" or self._current_href is None:
            return
        text = "".join(self._current_text).strip()
        self.links.append(_Link(self._current_href, text))
        self._current_href = None
        self._current_text = []


def _fetch_html(url: str) -> str:
    req = Request(url, headers={"User-Agent": "oud"})  # noqa: S310
    with urlopen(req, timeout=10) as response:  # noqa: S310
        return response.read().decode("utf-8", errors="replace")


def _is_supported_link(link: str) -> bool:
    lower = link.lower()
    return any(lower.endswith(ext) for ext in SUPPORTED_EXTS)


def _is_ft3_link(link: str) -> bool:
    lower = link.lower()
    return any(lower.endswith(ext) for ext in FT3_EXTS)


def _is_dir_link(link: str) -> bool:
    parsed = urlparse(link)
    path = parsed.path or ""
    if path.endswith("/"):
        return True
    return Path(path).suffix == ""


def _sanitize_title(text: str, fallback: str) -> str:
    cleaned = " ".join(text.split())
    return cleaned if cleaned else fallback


def _is_parent_label(text: str) -> bool:
    return text.strip().lower().startswith("parent directory")


def _is_listing_header(text: str) -> bool:
    lowered = text.strip().lower()
    return lowered in {"name", "last modified", "size", "description"}


def parse_supported_links(html: str, base_url: str) -> list[RemoteTab]:
    base_host = urlparse(base_url).netloc
    parser = _LinkParser()
    parser.feed(html)
    items: list[RemoteTab] = []
    for link in parser.links:
        href = link.href.strip()
        if not href:
            continue
        if href.startswith(("#", "?")):
            continue
        if _is_parent_label(link.text) or _is_listing_header(link.text):
            continue
        absolute = urljoin(base_url, href)
        if urlparse(absolute).netloc and urlparse(absolute).netloc != base_host:
            continue
        is_dir = _is_dir_link(absolute)
        if not _is_supported_link(absolute) and not is_dir:
            continue
        name = Path(urlparse(absolute).path).name or absolute.rstrip("/").split("/")[-1]
        title = _sanitize_title(link.text, name)
        items.append(RemoteTab(title=title, url=absolute, is_dir=is_dir))
    return items


def fetch_supported_tabs(url: str, *, limit: int = 200) -> list[RemoteTab]:
    html = _fetch_html(url)
    items = parse_supported_links(html, url)
    return items[:limit]


def root_items() -> list[RemoteTab]:
    return [
        RemoteTab(title="Random FT3", url="lutemusic:random", is_dir=False),
        RemoteTab(title="Tabs", url="lutemusic:index:tabs", is_dir=True),
        RemoteTab(title="Composers", url="lutemusic:index:composers", is_dir=True),
        RemoteTab(title="Sources", url="lutemusic:index:sources", is_dir=True),
    ]


def _safe_filename(text: str) -> str:
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-")
    return "".join(ch if ch in allowed else "_" for ch in text)


def _safe_rel_path(text: str) -> Path:
    parts = [part for part in text.replace("\\", "/").split("/") if part not in ("", ".", "..")]
    if not parts:
        return Path("download.ft3")
    safe_parts = [_safe_filename(part) or "_" for part in parts]
    return Path(*safe_parts)


def _download_url_to(url: str, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = Request(url, headers={"User-Agent": "oud"})  # noqa: S310
    with urlopen(req, timeout=10) as response:  # noqa: S310
        dest.write_bytes(response.read())
    return dest


def download_tab(item: RemoteTab, dest_dir: Path) -> Path:
    if item.is_dir:
        raise DownloadError
    dest_dir.mkdir(parents=True, exist_ok=True)
    name = Path(urlparse(item.url).path).name
    filename = _safe_filename(name or item.title)
    if not filename:
        filename = "download.tab"
    dest = dest_dir / filename
    return _download_url_to(item.url, dest)


def download_folder_ft3(item: RemoteTab, dest_dir: Path, *, limit: int = 2000) -> list[Path]:  # noqa: C901
    if not item.is_dir:
        raise DownloadError
    root_url = item.url if item.url.endswith("/") else f"{item.url}/"
    root_path = urlparse(root_url).path or "/"
    downloaded: list[Path] = []
    seen_dirs: set[str] = set()
    stack = [root_url]
    while stack:
        url = stack.pop()
        if url in seen_dirs:
            continue
        seen_dirs.add(url)
        for child in fetch_supported_tabs(url, limit=limit):
            if child.is_dir:
                child_url = child.url if child.url.endswith("/") else f"{child.url}/"
                stack.append(child_url)
                continue
            if not _is_ft3_link(child.url):
                continue
            child_path = urlparse(child.url).path or ""
            rel = child_path
            if child_path.startswith(root_path):
                rel = child_path[len(root_path) :]
            rel = normpath(rel).lstrip("/")
            if not rel or rel.startswith(".."):
                rel = Path(child_path).name
            local_path = dest_dir / _safe_rel_path(rel)
            downloaded.append(_download_url_to(child.url, local_path))
    return downloaded


def random_ft3(  # noqa: C901
    *,
    start_urls: list[str] | None = None,
    limit: int = 200,
    max_visits: int = 200,
    rng: random.Random | None = None,
) -> RemoteTab | None:
    walker = rng or random.Random()  # noqa: S311 - UI random pick, not crypto
    pending = list(start_urls or LUTEMUSIC_URLS.values())
    seen_dirs: set[str] = set()
    visited = 0
    while pending and visited < max_visits:
        choice_index = walker.randrange(len(pending))
        url = pending.pop(choice_index)
        if url in seen_dirs:
            continue
        seen_dirs.add(url)
        visited += 1
        items = fetch_supported_tabs(url, limit=limit)
        if not items:
            continue
        walker.shuffle(items)
        dirs: list[RemoteTab] = []
        files: list[RemoteTab] = []
        for item in items:
            if item.is_dir:
                dirs.append(item)
                continue
            if _is_ft3_link(item.url):
                files.append(item)
        if files:
            return walker.choice(files)
        for item in dirs:
            next_url = item.url if item.url.endswith("/") else f"{item.url}/"
            if next_url not in seen_dirs:
                pending.append(next_url)
    return None
