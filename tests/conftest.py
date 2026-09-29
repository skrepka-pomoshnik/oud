from __future__ import annotations

from pathlib import Path

import pytest

# Gerbode FT3 payloads are not redistributable, so a fresh clone has none.
# Fetch them with the command in tests/fixtures/ft3/README.md.
FT3_CORPUS = Path(__file__).parent / "fixtures" / "ft3" / "corpus"
FT3_CORPUS_MARKER = "ft3_corpus"


def ft3_corpus_available() -> bool:
    return FT3_CORPUS.is_dir() and any(FT3_CORPUS.rglob("*.ft3"))


def pytest_runtest_setup(item: pytest.Item) -> None:
    if item.get_closest_marker(FT3_CORPUS_MARKER) is None:
        return
    if not ft3_corpus_available():
        pytest.skip("local FT3 corpus is missing; see tests/fixtures/ft3/README.md")
