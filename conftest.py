"""Repository-wide pytest resource controls."""

from __future__ import annotations

import resource
import sys

_PYTEST_MEMORY_LIMIT_BYTES = 8 * 1024**3


def pytest_configure() -> None:
    """Keep the serial Linux test process below the repository memory budget."""

    if not sys.platform.startswith("linux"):
        return
    resource.setrlimit(
        resource.RLIMIT_AS,
        (_PYTEST_MEMORY_LIMIT_BYTES, _PYTEST_MEMORY_LIMIT_BYTES),
    )
