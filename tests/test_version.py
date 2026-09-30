from __future__ import annotations

import tomllib
from pathlib import Path

from oud import __version__


def test_the_package_version_matches_pyproject() -> None:
    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))["project"]

    assert __version__ == project["version"]
