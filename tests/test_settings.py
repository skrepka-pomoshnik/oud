from settings import load_settings, save_settings


def test_save_and_load_settings(tmp_path) -> None:
    path = tmp_path / "config.toml"
    settings = {
        "style": "italian",
        "measures": "five",
        "tuning": "a4b4",
        "strings": "7",
        "flagstyle": "thin",
        "time": "O",
        "key": "G",
        "countdots": "on",
        "keys": "vim",
        "spacing": "10",
        "spacingmode": "spread",
        "linelen": "70",
        "staffthick": "2",
        "fontstyle": "renaissance",
        "charstyle": "board",
        "midipatch": "12",
        "tempo": "120",
        "grid": "on",
        "showdur": "off",
        "showextras": "off",
        "showtactus": "on",
        "italianorient": "reverse",
        "frenchc": "alt",
        "frenche": "tail",
    }
    save_settings(str(path), settings)
    loaded = load_settings(str(path))
    assert loaded["style"] == "italian"
    assert loaded["measures"] == "five"
    assert loaded["tuning"] == "a4b4"
    assert loaded["strings"] == "7"
    assert loaded["flagstyle"] == "thin"
    assert loaded["time"] == "O"
    assert loaded["key"] == "G"
    assert loaded["countdots"] == "on"
    assert loaded["keys"] == "vim"
    assert loaded["spacing"] == "10"
    assert loaded["spacingmode"] == "spread"
    assert loaded["linelen"] == "70"
    assert loaded["staffthick"] == "2"
    assert loaded["fontstyle"] == "renaissance"
    assert loaded["charstyle"] == "board"
    assert loaded["midipatch"] == "12"
    assert loaded["tempo"] == "120"
    assert loaded["grid"] == "on"
    assert loaded["showdur"] == "off"
    assert loaded["showextras"] == "off"
    assert loaded["showtactus"] == "on"
    assert loaded["italianorient"] == "reverse"
    assert loaded["frenchc"] == "alt"
    assert loaded["frenche"] == "tail"
