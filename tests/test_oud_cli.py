from __future__ import annotations

import sys

from oud import cli
from oud.core.model import Bar, Piece


def test_oud_cli_main_tab(monkeypatch, capsys) -> None:
    piece = Piece(title="Tab", bars=[Bar()], strings=6)
    monkeypatch.setattr(cli, "load_tab", lambda _path: piece)
    monkeypatch.setattr(cli, "load_ft3", lambda _path: piece)
    monkeypatch.setattr(sys, "argv", ["oud/cli.py", "test.tab"])
    assert cli.main() == 0
    output = capsys.readouterr().out
    assert "Title: Tab" in output


def test_oud_cli_main_ascii(monkeypatch, capsys) -> None:
    piece = Piece(title="Ascii", bars=[Bar()], strings=6)
    monkeypatch.setattr(
        cli,
        "load_piece_data",
        lambda _path: (piece, {}, {}, set(), 8),
    )
    monkeypatch.setattr(cli, "load_settings", lambda _path: {"spacing": "10"})
    monkeypatch.setattr(cli, "export_ascii", lambda *_args, **_kwargs: "ASCII\n")
    monkeypatch.setattr(sys, "argv", ["oud/cli.py", "test.ft3", "--ascii"])
    assert cli.main() == 0
    output = capsys.readouterr().out
    assert output == "ASCII\n"
