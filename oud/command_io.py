"""Atomic, non-interactive file publication for command-line exports."""

from __future__ import annotations

import os
import tempfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import TypeVar

T = TypeVar("T")


class OutputExistsError(FileExistsError):
    def __init__(self, path: Path) -> None:
        super().__init__(f"refusing to overwrite existing output: {path}")


class OutputDirectoryError(FileNotFoundError):
    def __init__(self, path: Path) -> None:
        super().__init__(f"output directory does not exist: {path}")


def ensure_output_available(path: str | Path, *, overwrite: bool) -> Path:
    target = Path(path)
    if target.exists() and not overwrite:
        raise OutputExistsError(target)
    if not target.parent.is_dir():
        raise OutputDirectoryError(target.parent)
    return target


@contextmanager
def atomic_output_path(path: str | Path, *, overwrite: bool) -> Iterator[Path]:
    """Yield a same-directory temporary path and publish it atomically on success."""

    target = ensure_output_available(path, overwrite=overwrite)
    descriptor, raw_temp = tempfile.mkstemp(prefix=f".{target.name}.", suffix=target.suffix, dir=target.parent)
    os.close(descriptor)
    temporary = Path(raw_temp)
    try:
        yield temporary
        _sync(temporary)
        _publish(temporary, target, overwrite=overwrite)
    finally:
        temporary.unlink(missing_ok=True)


def atomic_export(path: str | Path, writer: Callable[[str], T], *, overwrite: bool) -> T:
    with atomic_output_path(path, overwrite=overwrite) as temporary:
        return writer(str(temporary))


def atomic_write_text(path: str | Path, content: str, *, overwrite: bool) -> None:
    with atomic_output_path(path, overwrite=overwrite) as temporary:
        temporary.write_text(content, encoding="utf-8")


def publish_existing(path: str | Path, target: str | Path, *, overwrite: bool) -> None:
    source = Path(path)
    destination = ensure_output_available(target, overwrite=overwrite)
    _sync(source)
    _publish(source, destination, overwrite=overwrite)


def _sync(path: Path) -> None:
    with path.open("rb") as handle:
        os.fsync(handle.fileno())


def _publish(source: Path, target: Path, *, overwrite: bool) -> None:
    if overwrite:
        source.replace(target)
        return
    try:
        os.link(source, target)
    except FileExistsError as exc:
        raise OutputExistsError(target) from exc
    source.unlink()


__all__ = [
    "OutputDirectoryError",
    "OutputExistsError",
    "atomic_export",
    "atomic_output_path",
    "atomic_write_text",
    "ensure_output_available",
    "publish_existing",
]
