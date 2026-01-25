from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RemoteTab:
    title: str
    url: str
    is_dir: bool = False
