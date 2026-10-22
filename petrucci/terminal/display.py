"""Deterministic display-cell primitives shared by terminal backends."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from functools import lru_cache

_MAX_CACHED_TEXT_LENGTH = 512


@dataclass(frozen=True, slots=True)
class DisplayCluster:
    text: str
    width: int


def split_display_clusters(text: str) -> tuple[DisplayCluster, ...]:
    """Split text into simple terminal clusters with explicit cell widths."""

    # Glyphs and staff strokes repeat each frame; never retain arbitrarily large input text.
    return _cached_display_clusters(text) if len(text) <= _MAX_CACHED_TEXT_LENGTH else _split_display_clusters(text)


@lru_cache(maxsize=128)
def _cached_display_clusters(text: str) -> tuple[DisplayCluster, ...]:
    return _split_display_clusters(text)


def _split_display_clusters(text: str) -> tuple[DisplayCluster, ...]:
    clusters: list[DisplayCluster] = []
    join_next = False
    for char in text:
        width = _char_width(char)
        combining = width == 0
        if clusters and (combining or join_next):
            previous = clusters[-1]
            joined_width = max(previous.width, width) if join_next else previous.width
            clusters[-1] = DisplayCluster(previous.text + char, joined_width)
        elif combining:
            continue
        else:
            clusters.append(DisplayCluster(char, width))
        join_next = char == "\u200d"
    return tuple(clusters)


def display_width(text: str) -> int:
    return sum(cluster.width for cluster in split_display_clusters(text))


def clip_display(text: str, width: int) -> str:
    """Clip without splitting a cluster or writing a partial wide glyph."""

    if width <= 0:
        return ""
    used = 0
    out: list[str] = []
    for cluster in split_display_clusters(text):
        if used + cluster.width > width:
            break
        out.append(cluster.text)
        used += cluster.width
    return "".join(out)


def _char_width(char: str) -> int:
    if char == "\u200d" or unicodedata.combining(char):
        return 0
    category = unicodedata.category(char)
    if category in {"Cc", "Cf", "Mn", "Me"}:
        return 0
    return 2 if unicodedata.east_asian_width(char) in {"F", "W"} else 1
