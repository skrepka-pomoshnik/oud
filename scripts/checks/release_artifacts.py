#!/usr/bin/env python3
"""Build and inspect release artifacts, including Petrucci's import boundary."""

from __future__ import annotations

import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path, PurePosixPath
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[2]
SDIST_ROOTS = frozenset(
    {
        "LICENSE",
        "MANIFEST.in",
        "PKG-INFO",
        "README.md",
        "oud",
        "oud.egg-info",
        "petrucci",
        "pyproject.toml",
        "setup.cfg",
    },
)
WHEEL_ROOTS = frozenset({"oud", "petrucci"})
DENIED_PARTS = frozenset({".git", ".github", ".pytest_cache", "__pycache__", "corpus", "examples", "tests"})
DENIED_NAMES = frozenset({"AGENTS.md", "DONE.md", "TODO.md"})
DENIED_SUFFIXES = (".ft3", ".ft3.gz", ".ft3.txt", ".mid", ".midi", ".pdf", ".png", ".pyc")
REQUIRED_WHEEL_FILES = frozenset({"oud/py.typed", "petrucci/__init__.py", "petrucci/py.typed"})


class ArtifactError(ValueError):
    @classmethod
    def artifact_count(cls, wheels: int, sdists: int) -> ArtifactError:
        return cls(f"expected one wheel and one sdist, found {wheels} wheel(s) and {sdists} sdist(s)")

    @classmethod
    def sdist_roots(cls, roots: set[str]) -> ArtifactError:
        return cls(f"sdist must have one top-level directory, found {sorted(roots)}")

    @classmethod
    def missing_wheel_files(cls, names: set[str] | frozenset[str]) -> ArtifactError:
        return cls(f"wheel is missing: {', '.join(sorted(names))}")

    @classmethod
    def forbidden_paths(cls, paths: list[str]) -> ArtifactError:
        return cls(f"release artifacts contain forbidden paths: {', '.join(paths)}")


def _fail(message: str) -> int:
    print(message, file=sys.stderr)
    return 1


def _artifact_names(directory: Path) -> tuple[Path, Path, set[str], set[str]]:
    wheels = tuple(directory.glob("*.whl"))
    sdists = tuple(directory.glob("*.tar.gz"))
    if len(wheels) != 1 or len(sdists) != 1:
        raise ArtifactError.artifact_count(len(wheels), len(sdists))
    wheel = wheels[0]
    sdist = sdists[0]
    with ZipFile(wheel) as archive:
        wheel_names = set(archive.namelist())
    with tarfile.open(sdist, mode="r:gz") as archive:
        members = {member.name for member in archive.getmembers() if member.isfile()}
    roots = {name.split("/", maxsplit=1)[0] for name in members}
    if len(roots) != 1:
        raise ArtifactError.sdist_roots(roots)
    root = next(iter(roots))
    sdist_names = {name.removeprefix(f"{root}/") for name in members if name != root}
    return wheel, sdist, wheel_names, sdist_names


def invalid_artifact_names(names: set[str], *, wheel: bool) -> set[str]:
    """Return development or payload paths forbidden in a published artifact."""

    invalid: set[str] = set()
    for name in names:
        path = PurePosixPath(name)
        first = path.parts[0] if path.parts else ""
        allowed_root = first in WHEEL_ROOTS or (wheel and first.endswith(".dist-info"))
        if not wheel:
            allowed_root = first in SDIST_ROOTS
        denied = bool(DENIED_PARTS.intersection(path.parts)) or path.name in DENIED_NAMES
        if not allowed_root or denied or name.lower().endswith(DENIED_SUFFIXES):
            invalid.add(name)
    return invalid


def _build(uv: str, directory: str) -> int:
    result = subprocess.run(  # noqa: S603 - uv is resolved from PATH and receives fixed build arguments
        [uv, "build", "--out-dir", directory],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        print(result.stdout, file=sys.stderr)
        print(result.stderr, file=sys.stderr)
    return result.returncode


def _check_import(wheel: Path, directory: str) -> int:
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


def _verify_artifacts(directory: Path) -> Path:
    wheel, _sdist, wheel_names, sdist_names = _artifact_names(directory)
    missing = REQUIRED_WHEEL_FILES - wheel_names
    if missing:
        raise ArtifactError.missing_wheel_files(missing)
    invalid_wheel = invalid_artifact_names(wheel_names, wheel=True)
    invalid_sdist = invalid_artifact_names(sdist_names, wheel=False)
    if invalid_wheel or invalid_sdist:
        paths = sorted({f"wheel:{name}" for name in invalid_wheel} | {f"sdist:{name}" for name in invalid_sdist})
        raise ArtifactError.forbidden_paths(paths)
    return wheel


def main() -> int:
    uv = shutil.which("uv")
    if uv is None:
        return _fail("uv is required for the release artifact check")
    with tempfile.TemporaryDirectory(prefix="oud-release-") as directory:
        if status := _build(uv, directory):
            return status
        try:
            wheel = _verify_artifacts(Path(directory))
        except ArtifactError as exc:
            return _fail(str(exc))
        if status := _check_import(wheel, directory):
            return status
    print("Release artifacts: clean wheel/sdist; Petrucci import is isolated from Oud and curses")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
