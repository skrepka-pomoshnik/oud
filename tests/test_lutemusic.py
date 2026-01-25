from plugins.lutemusic import parse_supported_links


def test_parse_supported_links_filters_and_titles() -> None:
    html = (
        '<a href="file.tab"> My Tab </a>'
        '<a href="/path/foo.ft3.gz"></a>'
        '<a href="/path/dir/">Dir</a>'
        '<a href="/path/parent/">Parent Directory</a>'
        '<a href="?C=N;O=D">Name</a>'
        '<a href="skip.pdf">Skip</a>'
    )
    items = parse_supported_links(html, "https://example.com/base/")
    assert len(items) == 3
    assert items[0].title == "My Tab"
    assert items[0].url == "https://example.com/base/file.tab"
    assert items[1].title == "foo.ft3.gz"
    assert items[1].url == "https://example.com/path/foo.ft3.gz"
    assert items[2].title == "Dir"
    assert items[2].url == "https://example.com/path/dir/"
    assert items[2].is_dir is True
