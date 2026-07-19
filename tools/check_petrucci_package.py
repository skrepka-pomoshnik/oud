#!/usr/bin/env python3
"""Build the wheel and verify Petrucci as an isolated external consumer sees it."""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]


def _fail(message: str) -> int:
    print(message, file=sys.stderr)
    return 1


def main() -> int:
    uv = shutil.which("uv")
    if uv is None:
        return _fail("uv is required for the Petrucci package check")
    with tempfile.TemporaryDirectory(prefix="petrucci-wheel-") as directory:
        result = subprocess.run(  # noqa: S603 - uv is resolved from PATH and receives fixed build arguments
            [uv, "build", "--wheel", "--out-dir", directory],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode:
            print(result.stdout, file=sys.stderr)
            print(result.stderr, file=sys.stderr)
            return result.returncode
        wheels = tuple(Path(directory).glob("*.whl"))
        if len(wheels) != 1:
            return _fail(f"expected one wheel, found {len(wheels)}")
        wheel = wheels[0]
        with ZipFile(wheel) as archive:
            names = set(archive.namelist())
        required = {"oud/py.typed", "petrucci/__init__.py", "petrucci/py.typed"}
        missing = required - names
        if missing:
            return _fail(f"wheel is missing: {', '.join(sorted(missing))}")
        code = (
            "import sys; "
            f"sys.path.insert(0, {str(wheel)!r}); "
            "import petrucci; "
            "[getattr(petrucci, name) for name in petrucci.__all__]; "
            "assert 'oud' not in sys.modules; "
            "assert 'curses' not in sys.modules"
        )
        imported = subprocess.run(  # noqa: S603 - fixed interpreter and generated local wheel path
            [sys.executable, "-I", "-c", code],
            cwd=directory,
            text=True,
            capture_output=True,
            check=False,
        )
        if imported.returncode:
            print(imported.stderr, file=sys.stderr)
            return imported.returncode
    print("Petrucci wheel: typed top-level import is isolated from Oud and curses")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
