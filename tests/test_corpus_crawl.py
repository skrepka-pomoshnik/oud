"""Directory-listing parsing and batch selection for the local lutemusic crawl, without any network."""

from __future__ import annotations

from scripts.corpus.crawl import folder_names, ft3_names, local_path, select_new

LISTING = (
    '<img src="/icons/back.gif"> <a href="/composers/">Parent Directory</a>\n'
    '<a href="?C=N;O=D">Name</a>\n'
    '<img src="/icons/folder.gif"> <a href="midi/">midi/</a>\n'
    '<img src="/icons/folder.gif"> <a href="pdf/">pdf/</a>\n'
    '<a href="sonata_CM_01_moderato.ft3">sonata_CM_01_moderato.ft3</a>\n'
    '<a href="Sonata%20Two.FT3">Sonata Two.FT3</a>\n'
    '<a href="readme.txt">readme.txt</a>\n'
)


def test_folders_exclude_the_parent_and_sort_links() -> None:
    assert folder_names(LISTING) == ["midi", "pdf"]


def test_only_ft3_links_are_listed_and_names_are_decoded() -> None:
    assert ft3_names(LISTING) == ["Sonata Two.FT3", "sonata_CM_01_moderato.ft3"]


def test_the_local_path_keeps_the_composer_folder() -> None:
    url = "https://browse.lutemusic.org/composers/Da%20Milano/piece%201.ft3"

    assert local_path(url).as_posix() == "Da Milano/piece 1.ft3"


def test_selection_is_reproducible_and_skips_known_files() -> None:
    index = [f"https://browse.lutemusic.org/composers/C/p{number}.ft3" for number in range(50)]
    known = set(index[:10])

    first = select_new(index, known, 15, seed=7)

    assert first == select_new(index, known, 15, seed=7)
    assert len(first) == 15 and not set(first) & known
    assert first != select_new(index, known, 15, seed=8)


def test_selection_never_returns_more_than_exists() -> None:
    index = ["https://browse.lutemusic.org/composers/C/a.ft3", "https://browse.lutemusic.org/composers/C/b.ft3"]

    assert select_new(index, set(), 10, seed=1) == index
