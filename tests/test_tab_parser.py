from core.tab_parser import load_tab, load_tab_data


def test_load_tab_simple(tmp_path) -> None:
    content = "{Title}\n{Author}\n\nb\n0ca\n1 d \nb\n"
    path = tmp_path / "simple.tab"
    path.write_text(content, encoding="utf-8")
    piece = load_tab(str(path))
    assert piece.title == "Title"
    assert piece.author == "Author"
    assert len(piece.bars) == 1
    assert len(piece.bars[0].chords) == 2


def test_load_tab_data_export_format(tmp_path) -> None:
    content = "\n".join(
        [
            "# TITLE: T",
            "Flag: I",
            "Dur: 4",
            "6|a---",
            "5|----",
            "4|----",
            "3|----",
            "2|----",
            "1|----",
            "",
        ]
    )
    path = tmp_path / "export.tab"
    path.write_text(content, encoding="utf-8")
    parsed = load_tab_data(str(path))
    assert parsed is not None
    assert parsed.piece.title == "T"
    assert parsed.overrides[(0, 0, 0)] == "a"
    assert parsed.durations[(0, 0, 0)] == 4
