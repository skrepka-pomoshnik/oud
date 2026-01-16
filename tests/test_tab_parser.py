from tab_parser import load_tab


def test_load_tab_simple(tmp_path) -> None:
    content = "{Title}\n{Author}\n\nb\n0ca\n1 d \nb\n"
    path = tmp_path / "simple.tab"
    path.write_text(content, encoding="utf-8")
    piece = load_tab(str(path))
    assert piece.title == "Title"
    assert piece.author == "Author"
    assert len(piece.bars) == 1
    assert len(piece.bars[0].chords) == 2
