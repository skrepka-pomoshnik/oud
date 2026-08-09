from petrucci.terminal.display import clip_display, display_width, split_display_clusters


def test_display_primitives_keep_combining_and_wide_clusters_atomic() -> None:
    text = "e\u0301界x"

    clusters = split_display_clusters(text)

    assert [cluster.text for cluster in clusters] == ["e\u0301", "界", "x"]
    assert [cluster.width for cluster in clusters] == [1, 2, 1]
    assert display_width(text) == 4
    assert clip_display(text, 2) == "e\u0301"
    assert clip_display(text, 3) == "e\u0301界"
